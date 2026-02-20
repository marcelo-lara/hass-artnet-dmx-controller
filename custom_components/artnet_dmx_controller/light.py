"""Light platform for ArtNet DMX Controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)

from .const import DEFAULT_CHANNEL_COUNT, DOMAIN, LOGGER
from .fixture_mapping import load_fixture_mapping, HomeAssistantError
from .channel_math import absolute_channel

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .artnet import ArtNetDMXHelper


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ArtNet DMX light entities from a config entry."""
    artnet_helper: ArtNetDMXHelper = hass.data[DOMAIN][entry.entry_id]
    entities = []

    # If fixture metadata is present on the entry, create per-fixture channels
    fixture_type = entry.data.get("fixture_type")
    start_channel = entry.data.get("start_channel")
    channel_count = entry.data.get("channel_count")

    if fixture_type and start_channel and channel_count:
        try:
            mapping = load_fixture_mapping()
            fixture_def = mapping.get("fixtures", {}).get(fixture_type)
            if fixture_def:
                for ch in fixture_def.get("channels", []):
                    offset = ch.get("offset")
                    name = ch.get("name")
                    hidden = bool(ch.get("hidden_by_default", False))
                    abs_channel = absolute_channel(int(start_channel), int(offset))
                    entities.append(
                        ArtNetDMXLight(
                            artnet_helper=artnet_helper,
                            channel=abs_channel,
                            entry_id=entry.entry_id,
                            channel_name=name,
                            hidden_by_default=hidden,
                        )
                    )
        except HomeAssistantError:
            # Fallback to default behavior below
            LOGGER.exception("Failed to load fixture mapping; falling back to default channels")

    if not entities:
        # Fallback: create default channel entities
        entities = [
            ArtNetDMXLight(
                artnet_helper=artnet_helper,
                channel=channel,
                entry_id=entry.entry_id,
            )
            for channel in range(1, DEFAULT_CHANNEL_COUNT + 1)
        ]

    async_add_entities(entities)


class ArtNetDMXLight(LightEntity):
    """Representation of an ArtNet DMX Light channel."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        artnet_helper: ArtNetDMXHelper,
        channel: int,
        entry_id: str,
        channel_name: str | None = None,
        hidden_by_default: bool = False,
    ) -> None:
        """
        Initialize the ArtNet DMX Light.

        Args:
            artnet_helper: The Art-Net helper instance
            channel: DMX channel number (1-512)
            entry_id: Config entry ID

        """
        self._artnet_helper = artnet_helper
        self._channel = channel
        # Unique id includes the absolute channel number to keep stability
        self._attr_unique_id = f"{entry_id}_channel_{channel}"
        if channel_name:
            self._attr_name = f"DMX Channel {channel} {channel_name}"
        else:
            self._attr_name = f"DMX Channel {channel}"
        # Allow mapping to request the channel be disabled by default in the entity registry
        self._attr_entity_registry_enabled_default = not bool(hidden_by_default)
        self._is_on = False
        self._brightness = 0

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._is_on

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

        self._brightness = brightness
        self._is_on = True

        # Send the DMX value
        await self._artnet_helper.set_channel(self._channel, brightness)

        LOGGER.debug(
            "Turned on DMX channel %s with brightness %s",
            self._channel,
            brightness,
        )

        # Update the state
        self.async_write_ha_state()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the light off."""
        self._brightness = 0
        self._is_on = False

        # Send DMX value 0
        await self._artnet_helper.set_channel(self._channel, 0)

        LOGGER.debug("Turned off DMX channel %s", self._channel)

        # Update the state
        self.async_write_ha_state()
