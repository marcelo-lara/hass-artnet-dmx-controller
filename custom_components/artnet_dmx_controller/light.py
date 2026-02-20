"""Light platform for ArtNet DMX Controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.components.select import SelectEntity

from .const import DEFAULT_CHANNEL_COUNT, DOMAIN, LOGGER
from .fixture_mapping import load_fixture_mapping, HomeAssistantError
from .channel_math import absolute_channel
from .channel_math import value_from_label, label_from_value, clamp_dmx_value

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
                    # Build a name->channel mapping for group detection
                    channels = fixture_def.get("channels", [])
                    name_map = {ch.get("name"): ch for ch in channels}

                    # Detect RGB fixture (has red, green, blue channels)
                    rgb_group = None
                    if all(n in name_map for n in ("red", "green", "blue")):
                        # gather offsets
                        rgb_group = {
                            "red": name_map["red"]["offset"],
                            "green": name_map["green"]["offset"],
                            "blue": name_map["blue"]["offset"],
                            "dim": name_map.get("dim", {}).get("offset"),
                        }

                    handled_offsets: set[int] = set()

                    for ch in channels:
                        offset = ch.get("offset")
                        # skip offsets handled by composite groups
                        if offset in handled_offsets:
                            continue

                        # If this offset is part of RGB group, create composite entity
                        if rgb_group and offset in (rgb_group["red"], rgb_group["green"], rgb_group["blue"]):
                            # create RGB composite
                            red_off = rgb_group["red"]
                            green_off = rgb_group["green"]
                            blue_off = rgb_group["blue"]
                            dim_off = rgb_group.get("dim")
                            # mark offsets as handled
                            handled_offsets.update({red_off, green_off, blue_off})
                            if dim_off:
                                handled_offsets.add(dim_off)

                            abs_red = absolute_channel(int(start_channel), int(red_off))
                            abs_green = absolute_channel(int(start_channel), int(green_off))
                            abs_blue = absolute_channel(int(start_channel), int(blue_off))
                            abs_dim = None
                            if dim_off:
                                abs_dim = absolute_channel(int(start_channel), int(dim_off))

                            entities.append(
                                ArtNetDMXRGBLight(
                                    artnet_helper=artnet_helper,
                                    red_channel=abs_red,
                                    green_channel=abs_green,
                                    blue_channel=abs_blue,
                                    dim_channel=abs_dim,
                                    entry_id=entry.entry_id,
                                    channel_name=f"{fixture_type}",
                                )
                            )
                            # continue to next channel
                            continue

                    # after composite handling, create remaining entities
                    for ch in channels:
                        offset = ch.get("offset")
                        if offset in handled_offsets:
                            continue
                        name = ch.get("name")
                        hidden = bool(ch.get("hidden_by_default", False))
                        abs_channel = absolute_channel(int(start_channel), int(offset))
                        # If channel has a value_map, create a Select entity
                        if "value_map" in ch:
                            entities.append(
                                ArtNetDMXSelect(
                                    artnet_helper=artnet_helper,
                                    channel=abs_channel,
                                    entry_id=entry.entry_id,
                                    channel_name=name,
                                    value_map=ch.get("value_map", {}),
                                    hidden_by_default=hidden,
                                )
                            )
                        else:
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
        # Device grouping information: associate entities for the same config entry (fixture)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"{entry_id} Fixture",
        }
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

        # Normalize/clamp brightness to DMX range
        self._brightness = clamp_dmx_value(brightness)
        self._is_on = True

        # Send the DMX value
        await self._artnet_helper.set_channel(self._channel, int(self._brightness))

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



class ArtNetDMXSelect(SelectEntity):
    """Select entity for DMX channels with discrete value maps."""

    _attr_has_entity_name = True

    def __init__(
        self,
        artnet_helper: ArtNetDMXHelper,
        channel: int,
        entry_id: str,
        channel_name: str | None = None,
        value_map: dict | None = None,
        hidden_by_default: bool = False,
    ) -> None:
        self._artnet_helper = artnet_helper
        self._channel = channel
        self._value_map = value_map or {}
        self._attr_unique_id = f"{entry_id}_channel_{channel}"
        if channel_name:
            self._attr_name = f"DMX Channel {channel} {channel_name}"
        else:
            self._attr_name = f"DMX Channel {channel}"
        self._attr_entity_registry_enabled_default = not bool(hidden_by_default)
        self._current = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"{entry_id} Fixture",
        }

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
        await self._artnet_helper.set_channel(self._channel, int(value))
        self._current = option
        try:
            self.async_write_ha_state()
        except RuntimeError:
            # In tests the entity may not be registered with hass; ignore
            pass



class ArtNetDMXRGBLight(LightEntity):
    """Composite RGB light backed by three DMX channels and optional dim channel."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.RGB}

    def __init__(
        self,
        artnet_helper: "ArtNetDMXHelper",
        red_channel: int,
        green_channel: int,
        blue_channel: int,
        dim_channel: int | None,
        entry_id: str,
        channel_name: str | None = None,
    ) -> None:
        self._artnet_helper = artnet_helper
        self._red = red_channel
        self._green = green_channel
        self._blue = blue_channel
        self._dim = dim_channel
        self._attr_unique_id = f"{entry_id}_rgb_{self._red}_{self._green}_{self._blue}"
        if channel_name:
            self._attr_name = f"{channel_name}"
        else:
            self._attr_name = f"DMX RGB {self._red}"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry_id)}, "name": f"{entry_id} Fixture"}
        self._is_on = False
        self._brightness = 0
        self._rgb = (0, 0, 0)

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
        else:
            # default full
            if self._brightness == 0:
                self._brightness = 255

        if rgb is not None:
            self._rgb = tuple(int(c) for c in rgb)

        # compute scale factor
        scale = self._brightness / 255.0 if self._brightness is not None else 1.0

        # send dim if available

        if self._dim is not None:
            await self._artnet_helper.set_channel(self._dim, int(clamp_dmx_value(self._brightness)))

        # send rgb channels scaled by brightness
        r = clamp_dmx_value(int(self._rgb[0] * scale))
        g = clamp_dmx_value(int(self._rgb[1] * scale))
        b = clamp_dmx_value(int(self._rgb[2] * scale))
        await self._artnet_helper.set_channel(self._red, r)
        await self._artnet_helper.set_channel(self._green, g)
        await self._artnet_helper.set_channel(self._blue, b)

        self._is_on = True
        try:
            self.async_write_ha_state()
        except RuntimeError:
            pass

    async def async_turn_off(self, **_kwargs: Any) -> None:
        # set rgb channels to 0 and dim to 0 if present
        if self._dim is not None:
            await self._artnet_helper.set_channel(self._dim, 0)
        await self._artnet_helper.set_channel(self._red, 0)
        await self._artnet_helper.set_channel(self._green, 0)
        await self._artnet_helper.set_channel(self._blue, 0)
        self._is_on = False
        try:
            self.async_write_ha_state()
        except RuntimeError:
            pass
