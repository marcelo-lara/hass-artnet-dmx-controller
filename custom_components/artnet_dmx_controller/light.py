"""Light platform for ArtNet DMX Controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR, LightEntity
from homeassistant.components.light.const import ColorMode
from homeassistant.helpers.device_registry import DeviceInfo

from .channel_math import absolute_channel, clamp_dmx_value
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
    """Convert underscore-separated text to title case."""
    if not text:
        return None
    return str(text).replace("_", " ").strip().title()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ArtNet DMX light entities from one fixture entry."""
    artnet_helper: ArtNetDMXHelper = hass.data[DOMAIN][entry.entry_id]
    dmx_writer = DMXWriter(artnet_helper)
    entities: list[LightEntity] = []

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
        name_map = {channel.get("name"): channel for channel in channels}

        rgb_group = None
        if all(name in name_map for name in ("red", "green", "blue")):
            rgb_group = {
                "red": int(name_map["red"]["offset"]),
                "green": int(name_map["green"]["offset"]),
                "blue": int(name_map["blue"]["offset"]),
                "dim": int(name_map["dim"]["offset"]) if "dim" in name_map else None,
            }

        bit16_pairs: dict[str, tuple[int, int]] = {}
        for name, channel_def in name_map.items():
            if not name or not name.endswith("_msb"):
                continue
            base_name = name[:-4]
            lsb_name = f"{base_name}_lsb"
            if lsb_name in name_map:
                bit16_pairs[base_name] = (int(channel_def["offset"]), int(name_map[lsb_name]["offset"]))

        handled_offsets: set[int] = set()

        for msb_offset, lsb_offset in bit16_pairs.values():
            handled_offsets.update({msb_offset, lsb_offset})

        if rgb_group is not None:
            handled_offsets.update({rgb_group["red"], rgb_group["green"], rgb_group["blue"]})
            if rgb_group["dim"] is not None:
                handled_offsets.add(rgb_group["dim"])
            entities.append(
                ArtNetDMXRGBLight(
                    artnet_helper=artnet_helper,
                    red_channel=absolute_channel(start_channel, rgb_group["red"]),
                    green_channel=absolute_channel(start_channel, rgb_group["green"]),
                    blue_channel=absolute_channel(start_channel, rgb_group["blue"]),
                    dim_channel=(
                        absolute_channel(start_channel, rgb_group["dim"])
                        if rgb_group["dim"] is not None
                        else None
                    ),
                    entry_id=entry.entry_id,
                    fixture_id=fixture_id,
                    channel_name=fixture_type,
                    dmx_writer=dmx_writer,
                    fixture_label=fixture_label,
                )
            )

        for channel in channels:
            offset = int(channel["offset"])
            if offset in handled_offsets or "value_map" in channel:
                continue
            entities.append(
                ArtNetDMXLight(
                    artnet_helper=artnet_helper,
                    channel=absolute_channel(start_channel, offset),
                    entry_id=entry.entry_id,
                    fixture_id=fixture_id,
                    channel_name=channel.get("name"),
                    hidden_by_default=bool(channel.get("hidden_by_default", False)),
                    dmx_writer=dmx_writer,
                    fixture_label=fixture_label,
                )
            )
    except HomeAssistantError:
        LOGGER.exception("Failed to load fixture mapping for light platform")

    if entities:
        async_add_entities(entities)


class ArtNetDMXLight(LightEntity):
    """Representation of a single DMX light channel."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        artnet_helper: ArtNetDMXHelper,
        channel: int,
        entry_id: str,
        fixture_id: str,
        channel_name: str | None = None,
        hidden_by_default: bool = False,
        dmx_writer: DMXWriter | None = None,
        fixture_label: str | None = None,
    ) -> None:
        self._artnet_helper = artnet_helper
        self._dmx_writer = dmx_writer
        self._channel = channel
        self._attr_unique_id = f"{entry_id}_{fixture_id}_channel_{channel}"
        human_label = _humanize(fixture_label) or fixture_label
        human_channel = _humanize(channel_name) or channel_name
        if human_label and human_channel:
            self._attr_name = f"{human_label} {human_channel}"
        elif human_label:
            self._attr_name = f"{human_label} Channel {channel}"
        elif human_channel:
            self._attr_name = f"DMX Channel {channel} {human_channel}"
        else:
            self._attr_name = f"DMX Channel {channel}"
        self._attr_entity_registry_enabled_default = not bool(hidden_by_default)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=fixture_label or f"{entry_id} Fixture",
        )
        self._attr_icon = "mdi:lightbulb"
        initial_value = _channel_value(artnet_helper, channel)
        self._is_on = initial_value > 0
        self._brightness = initial_value

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def brightness(self) -> int:
        return self._brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._brightness = clamp_dmx_value(brightness)
        self._is_on = True
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channel(self._channel, int(self._brightness))
        else:
            await self._artnet_helper.set_channel(self._channel, int(self._brightness))
        self.async_write_ha_state()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        self._brightness = 0
        self._is_on = False
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channel(self._channel, 0)
        else:
            await self._artnet_helper.set_channel(self._channel, 0)
        self.async_write_ha_state()


class ArtNetDMXRGBLight(LightEntity):
    """Composite RGB light backed by three DMX channels and optional dim channel."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.RGB}

    def __init__(
        self,
        artnet_helper: ArtNetDMXHelper,
        red_channel: int,
        green_channel: int,
        blue_channel: int,
        dim_channel: int | None,
        entry_id: str,
        fixture_id: str,
        channel_name: str | None = None,
        dmx_writer: DMXWriter | None = None,
        fixture_label: str | None = None,
    ) -> None:
        self._artnet_helper = artnet_helper
        self._dmx_writer = dmx_writer
        self._red = red_channel
        self._green = green_channel
        self._blue = blue_channel
        self._dim = dim_channel
        self._attr_unique_id = f"{entry_id}_{fixture_id}_rgb_{self._red}_{self._green}_{self._blue}"
        human_label = _humanize(fixture_label) or fixture_label
        human_channel = _humanize(channel_name) or channel_name
        if human_label and human_channel:
            self._attr_name = f"{human_label} {human_channel}"
        elif human_label:
            self._attr_name = f"{human_label} RGB {self._red}"
        elif human_channel:
            self._attr_name = human_channel
        else:
            self._attr_name = f"DMX RGB {self._red}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=fixture_label or f"{entry_id} Fixture",
        )
        self._attr_icon = "mdi:led-strip-variant"
        red_value = _channel_value(artnet_helper, self._red)
        green_value = _channel_value(artnet_helper, self._green)
        blue_value = _channel_value(artnet_helper, self._blue)
        if self._dim is not None:
            self._brightness = _channel_value(artnet_helper, self._dim)
        else:
            self._brightness = max(red_value, green_value, blue_value)
        self._rgb: tuple[int, int, int] = (red_value, green_value, blue_value)
        self._is_on = any(self._rgb) or self._brightness > 0

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self._rgb

    async def async_turn_on(self, **kwargs: Any) -> None:
        rgb = kwargs.get(ATTR_RGB_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is not None:
            self._brightness = clamp_dmx_value(int(brightness))
        elif self._brightness == 0:
            self._brightness = 255

        if rgb is not None:
            self._rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))

        scale = self._brightness / 255.0 if self._brightness is not None else 1.0
        red = clamp_dmx_value(int(self._rgb[0] * scale))
        green = clamp_dmx_value(int(self._rgb[1] * scale))
        blue = clamp_dmx_value(int(self._rgb[2] * scale))

        payload = {self._red: red, self._green: green, self._blue: blue}
        if self._dim is not None:
            payload[self._dim] = int(clamp_dmx_value(self._brightness))

        if self._dmx_writer is not None:
            await self._dmx_writer.set_channels(payload)
        else:
            for channel, value in payload.items():
                await self._artnet_helper.set_channel(channel, value)

        self._is_on = True
        try:
            self.async_write_ha_state()
        except RuntimeError:
            pass

    async def async_turn_off(self, **_kwargs: Any) -> None:
        payload = {self._red: 0, self._green: 0, self._blue: 0}
        if self._dim is not None:
            payload[self._dim] = 0
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channels(payload)
        else:
            for channel, value in payload.items():
                await self._artnet_helper.set_channel(channel, value)
        self._is_on = False
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
