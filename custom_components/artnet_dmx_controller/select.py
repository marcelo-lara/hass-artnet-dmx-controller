"""Select platform for ArtNet DMX Controller."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .channel_math import clamp_dmx_value, label_from_value, value_from_label
from .const import DOMAIN, LOGGER
from .dmx_writer import DMXWriter
from .entry_fixtures import fixture_label as get_fixture_label
from .entry_fixtures import get_entry_fixtures
from .fixture_mapping import HomeAssistantError, load_fixture_mapping


def _humanize(text: str | None) -> str | None:
    if not text:
        return None
    return str(text).replace("_", " ").strip().title()

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .artnet import ArtNetDMXHelper


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry", async_add_entities: "AddEntitiesCallback") -> None:
    """Set up select entities for ArtNet DMX from a config entry."""
    artnet_helper: "ArtNetDMXHelper" = hass.data[DOMAIN][entry.entry_id]
    dmx_writer = DMXWriter(artnet_helper)
    entities = []

    try:
        mapping = load_fixture_mapping()
        fixtures = get_entry_fixtures(entry)
        for fixture in fixtures:
            fixture_type = fixture["fixture_type"]
            start_channel = fixture["start_channel"]
            fixture_id = fixture["id"]
            fixture_def = mapping.get("fixtures", {}).get(fixture_type)
            if not fixture_def:
                LOGGER.warning("Fixture type %s not found for entry %s", fixture_type, entry.entry_id)
                continue
            entity_fixture_label = (
                get_fixture_label(fixture, fixture_def.get("label"))
                or entry.data.get("name")
                or getattr(entry, "title", None)
                or fixture_type
                or entry.entry_id
            )
            channels = fixture_def.get("channels", [])
            for channel in channels:
                if "value_map" not in channel:
                    continue
                offset = channel.get("offset")
                abs_channel = int(start_channel) + int(offset) - 1
                entities.append(
                    ArtNetDMXSelect(
                        artnet_helper=artnet_helper,
                        dmx_writer=dmx_writer,
                        channel=abs_channel,
                        entry_id=entry.entry_id,
                        fixture_id=fixture_id,
                        channel_name=channel.get("name"),
                        value_map=channel.get("value_map", {}),
                        hidden_by_default=bool(channel.get("hidden_by_default", False)),
                        fixture_label=entity_fixture_label,
                    )
                )
    except HomeAssistantError:
        LOGGER.exception("Failed to load fixture mapping for select platform")

    if entities:
        async_add_entities(entities)


class ArtNetDMXSelect(SelectEntity):
    """Select entity for DMX channels with discrete value maps."""

    _attr_has_entity_name = True

    def __init__(
        self,
        artnet_helper,
        channel: int,
        entry_id: str,
        fixture_id: str,
        channel_name: str | None = None,
        value_map: dict | None = None,
        hidden_by_default: bool = False,
        dmx_writer: DMXWriter | None = None,
        fixture_label: str | None = None,
    ) -> None:
        self._artnet_helper = artnet_helper
        self._dmx_writer = dmx_writer
        self._channel = channel
        self._value_map = value_map or {}
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
        current_value = _channel_value(artnet_helper, channel)
        current_label = label_from_value(self._value_map, current_value)
        self._synthetic_options: dict[str, int] = {}
        if current_label is None:
            current_label = f"Value {current_value}"
            self._synthetic_options[current_label] = current_value
        self._current = current_label
        self._is_on = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=fixture_label or f"{entry_id} Fixture",
        )
        self._attr_icon = "mdi:format-list-bulleted"

    @property
    def options(self) -> list[str]:
        options = list(self._value_map.values())
        for label in self._synthetic_options:
            if label not in options:
                options.append(label)
        return options

    @property
    def current_option(self) -> str | None:
        return self._current

    async def async_select_option(self, option: str) -> None:
        try:
            if option in self._synthetic_options:
                value = self._synthetic_options[option]
            else:
                value = value_from_label(self._value_map, option)
            value = clamp_dmx_value(value)
        except Exception:
            return
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channel(self._channel, int(value))
        else:
            await self._artnet_helper.set_channel(self._channel, int(value))
        self._current = option
        try:
            self.async_write_ha_state()
        except RuntimeError:
            # In tests the entity may not be registered with hass; ignore
            pass

    @property
    def is_on(self) -> bool:
        """Return whether the select is considered "on" for light service compatibility."""
        return bool(self._is_on)

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Handle light.turn_on calls against this entity by marking it on."""
        self._is_on = True
        try:
            self.async_write_ha_state()
        except RuntimeError:
            pass

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Handle light.turn_off calls against this entity by marking it off."""
        self._is_on = False
        try:
            self.async_write_ha_state()
        except RuntimeError:
            pass


def _channel_value(artnet_helper, channel: int) -> int:
    """Read a buffered DMX value when available, defaulting to 0."""
    if hasattr(artnet_helper, "get_channel_value"):
        try:
            return int(artnet_helper.get_channel_value(channel))
        except Exception:
            return 0
    return 0
