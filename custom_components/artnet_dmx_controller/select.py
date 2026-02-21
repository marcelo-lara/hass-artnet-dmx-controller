"""Select platform for ArtNet DMX Controller."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .channel_math import clamp_dmx_value, value_from_label
from .const import DOMAIN, LOGGER
from .dmx_writer import DMXWriter
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

    fixture_type = entry.data.get("fixture_type")
    start_channel = entry.data.get("start_channel")
    channel_count = entry.data.get("channel_count")

    if fixture_type and start_channel and channel_count:
        try:
            mapping = load_fixture_mapping()
            fixture_def = mapping.get("fixtures", {}).get(fixture_type)
            if fixture_def:
                fixture_label = (
                    fixture_def.get("label")
                    or entry.data.get("name")
                    or getattr(entry, "title", None)
                    or fixture_type
                    or entry.entry_id
                )
                channels = fixture_def.get("channels", [])
                for ch in channels:
                    if "value_map" in ch:
                        offset = ch.get("offset")
                        abs_channel = int(start_channel) + int(offset) - 1
                        entities.append(
                            ArtNetDMXSelect(
                                artnet_helper=artnet_helper,
                                dmx_writer=dmx_writer,
                                channel=abs_channel,
                                entry_id=entry.entry_id,
                                channel_name=ch.get("name"),
                                value_map=ch.get("value_map", {}),
                                hidden_by_default=bool(ch.get("hidden_by_default", False)),
                                fixture_label=fixture_label,
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
        self._attr_unique_id = f"{entry_id}_channel_{channel}"
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
        self._current = None
        self._is_on = False
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": fixture_label or f"{entry_id} Fixture",
        }
        self._attr_icon = "mdi:format-list-bulleted"

    @property
    def options(self) -> list[str]:
        return list(self._value_map.values())

    @property
    def current_option(self) -> str | None:
        return self._current

    async def async_select_option(self, option: str) -> None:
        try:
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
