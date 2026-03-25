"""Number platform for ArtNet DMX Controller."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .channel_math import absolute_channel
from .const import CONF_FIXTURE_ID, CONF_FIXTURE_TYPE, CONF_NAME, CONF_START_CHANNEL, DOMAIN, LOGGER
from .dmx_writer import DMXWriter
from .entry_fixtures import get_fixture_entry
from .fixture_mapping import HomeAssistantError, load_fixture_mapping

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .artnet import ArtNetDMXHelper


def _humanize(text: str | None) -> str | None:
    if not text:
        return None
    return str(text).replace("_", " ").strip().title()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up configuration number entities for one fixture entry."""
    artnet_helper: ArtNetDMXHelper = hass.data[DOMAIN][entry.entry_id]
    dmx_writer = DMXWriter(artnet_helper)
    entities: list[NumberEntity] = []

    try:
        fixture = get_fixture_entry(entry)
        mapping = load_fixture_mapping()
        fixture_type = fixture[CONF_FIXTURE_TYPE]
        start_channel = int(fixture[CONF_START_CHANNEL])
        fixture_id = fixture[CONF_FIXTURE_ID]
        fixture_def = mapping.get("fixtures", {}).get(fixture_type)
        if not fixture_def:
            LOGGER.warning("Fixture type %s not found for entry %s", fixture_type, entry.entry_id)
            return

        fixture_label = (
            fixture.get(CONF_NAME)
            or fixture_def.get("label")
            or getattr(entry, "title", None)
            or fixture_type
            or entry.entry_id
        )
        channels = fixture_def.get("channels", [])
        fixture_specie = fixture_def.get("fixture_specie")
        name_map = {channel.get("name"): channel for channel in channels}
        handled_offsets: set[int] = set()

        rgb_offsets: set[int] = set()
        if fixture_specie == "parcan" and all(name in name_map for name in ("red", "green", "blue")):
            rgb_offsets = {
                int(name_map["red"]["offset"]),
                int(name_map["green"]["offset"]),
                int(name_map["blue"]["offset"]),
            }
            if "dim" in name_map:
                rgb_offsets.add(int(name_map["dim"]["offset"]))

        moving_head_primary_offset = None
        if fixture_specie == "moving_head" and "dim" in name_map:
            moving_head_primary_offset = int(name_map["dim"]["offset"])

        for name, channel_def in name_map.items():
            if not name or not name.endswith("_msb"):
                continue
            base_name = name[:-4]
            lsb_name = f"{base_name}_lsb"
            if lsb_name not in name_map:
                continue
            handled_offsets.update({int(channel_def["offset"]), int(name_map[lsb_name]["offset"])})

            entities.append(
                ArtNetDMX16BitNumber(
                    artnet_helper=artnet_helper,
                    dmx_writer=dmx_writer,
                    msb_channel=absolute_channel(start_channel, int(channel_def["offset"])),
                    lsb_channel=absolute_channel(start_channel, int(name_map[lsb_name]["offset"])),
                    entry_id=entry.entry_id,
                    fixture_id=fixture_id,
                    channel_name=base_name,
                    hidden_by_default=bool(
                        channel_def.get("hidden_by_default", False)
                        or name_map[lsb_name].get("hidden_by_default", False)
                    ),
                    fixture_label=fixture_label,
                )
            )

        for channel in channels:
            offset = int(channel["offset"])
            if offset in handled_offsets:
                continue
            if "value_map" in channel:
                continue
            if offset in rgb_offsets:
                continue
            if moving_head_primary_offset is not None and offset == moving_head_primary_offset:
                continue

            entities.append(
                ArtNetDMXNumber(
                    artnet_helper=artnet_helper,
                    dmx_writer=dmx_writer,
                    channel=absolute_channel(start_channel, offset),
                    entry_id=entry.entry_id,
                    fixture_id=fixture_id,
                    channel_name=channel.get("name"),
                    hidden_by_default=bool(channel.get("hidden_by_default", False)),
                    fixture_label=fixture_label,
                )
            )
    except HomeAssistantError:
        LOGGER.exception("Failed to load fixture mapping for number platform")

    if entities:
        async_add_entities(entities)


class ArtNetDMX16BitNumber(NumberEntity):
    """Number entity for a 16-bit DMX value backed by MSB/LSB channels."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_native_min_value = 0
    _attr_native_max_value = 65535
    _attr_native_step = 1

    def __init__(
        self,
        artnet_helper: ArtNetDMXHelper,
        dmx_writer: DMXWriter | None,
        msb_channel: int,
        lsb_channel: int,
        entry_id: str,
        fixture_id: str,
        channel_name: str | None = None,
        hidden_by_default: bool = False,
        fixture_label: str | None = None,
    ) -> None:
        self._artnet_helper = artnet_helper
        self._dmx_writer = dmx_writer
        self._msb = msb_channel
        self._lsb = lsb_channel
        self._attr_unique_id = f"{entry_id}_{fixture_id}_number_{self._msb}_{self._lsb}"
        human_label = _humanize(fixture_label) or fixture_label
        human_channel = _humanize(channel_name) or channel_name
        if human_label and human_channel:
            self._attr_name = f"{human_label} {human_channel}"
        elif human_label:
            self._attr_name = f"{human_label} 16-bit {self._msb}"
        elif human_channel:
            self._attr_name = human_channel
        else:
            self._attr_name = f"DMX 16-bit {self._msb}"
        self._attr_entity_registry_enabled_default = not bool(hidden_by_default)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=fixture_label or f"{entry_id} Fixture",
        )
        self._attr_icon = "mdi:tune-vertical"
        self._native_value = float(self._read_value())

    @property
    def native_value(self) -> float:
        return self._native_value

    async def async_set_native_value(self, value: float) -> None:
        numeric_value = max(0, min(65535, int(round(value))))
        msb = (numeric_value >> 8) & 0xFF
        lsb = numeric_value & 0xFF
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channels({self._msb: msb, self._lsb: lsb})
        else:
            await self._artnet_helper.set_channel(self._msb, msb)
            await self._artnet_helper.set_channel(self._lsb, lsb)
        self._native_value = float(numeric_value)
        try:
            self.async_write_ha_state()
        except RuntimeError:
            pass

    def _read_value(self) -> int:
        msb = _channel_value(self._artnet_helper, self._msb)
        lsb = _channel_value(self._artnet_helper, self._lsb)
        return (msb << 8) | lsb


class ArtNetDMXNumber(NumberEntity):
    """Number entity for a single 8-bit DMX configuration channel."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_native_min_value = 0
    _attr_native_max_value = 255
    _attr_native_step = 1

    def __init__(
        self,
        artnet_helper: ArtNetDMXHelper,
        dmx_writer: DMXWriter | None,
        channel: int,
        entry_id: str,
        fixture_id: str,
        channel_name: str | None = None,
        hidden_by_default: bool = False,
        fixture_label: str | None = None,
    ) -> None:
        self._artnet_helper = artnet_helper
        self._dmx_writer = dmx_writer
        self._channel = channel
        self._attr_unique_id = f"{entry_id}_{fixture_id}_number_{channel}"
        human_label = _humanize(fixture_label) or fixture_label
        human_channel = _humanize(channel_name) or channel_name
        if human_label and human_channel:
            self._attr_name = f"{human_label} {human_channel}"
        elif human_label:
            self._attr_name = f"{human_label} Channel {channel}"
        elif human_channel:
            self._attr_name = human_channel
        else:
            self._attr_name = f"DMX Channel {channel}"
        self._attr_entity_registry_enabled_default = not bool(hidden_by_default)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=fixture_label or f"{entry_id} Fixture",
        )
        self._attr_icon = "mdi:tune"
        self._native_value = float(_channel_value(self._artnet_helper, self._channel))

    @property
    def native_value(self) -> float:
        return self._native_value

    async def async_set_native_value(self, value: float) -> None:
        numeric_value = max(0, min(255, int(round(value))))
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channel(self._channel, numeric_value)
        else:
            await self._artnet_helper.set_channel(self._channel, numeric_value)
        self._native_value = float(numeric_value)
        try:
            self.async_write_ha_state()
        except RuntimeError:
            pass


def _channel_value(artnet_helper: ArtNetDMXHelper, channel: int) -> int:
    """Read a buffered DMX value when the helper exposes one."""
    if hasattr(artnet_helper, "get_channel_value"):
        try:
            return int(artnet_helper.get_channel_value(channel))
        except Exception:
            return 0
    return 0