"""Light platform for ArtNet DMX Controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Optional

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .channel_math import (
    absolute_channel,
    clamp_dmx_value,
)

from .const import DOMAIN, LOGGER
from .dmx_writer import DMXWriter
from .entry_fixtures import fixture_label as get_fixture_label
from .entry_fixtures import get_entry_fixtures
from .fixture_mapping import HomeAssistantError, load_fixture_mapping


def _humanize(text: Optional[str]) -> Optional[str]:
    """Convert underscore_separated text to Title Case with spaces.

    Returns None if input is falsy.
    """
    if not text:
        return None
    return str(text).replace("_", " ").strip().title()

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
            name_map = {ch.get("name"): ch for ch in channels}

            rgb_group = None
            if all(name in name_map for name in ("red", "green", "blue")):
                rgb_group = {
                    "red": name_map["red"]["offset"],
                    "green": name_map["green"]["offset"],
                    "blue": name_map["blue"]["offset"],
                    "dim": name_map.get("dim", {}).get("offset"),
                }

            bit16_pairs: dict[str, tuple[int, int]] = {}
            for name, channel_def in name_map.items():
                if name.endswith("_msb"):
                    base = name[:-4]
                    lsb_name = f"{base}_lsb"
                    if lsb_name in name_map:
                        bit16_pairs[base] = (channel_def.get("offset"), name_map[lsb_name].get("offset"))

            handled_offsets: set[int] = set()
            for msb_offset, lsb_offset in bit16_pairs.values():
                handled_offsets.update({msb_offset, lsb_offset})

            for base, (msb_offset, lsb_offset) in bit16_pairs.items():
                abs_msb = absolute_channel(int(start_channel), int(msb_offset))
                abs_lsb = absolute_channel(int(start_channel), int(lsb_offset))
                msb_def = name_map.get(f"{base}_msb", {})
                lsb_def = name_map.get(f"{base}_lsb", {})
                hidden = bool(msb_def.get("hidden_by_default", False) or lsb_def.get("hidden_by_default", False))
                entities.append(
                    ArtNetDMX16BitLight(
                        artnet_helper=artnet_helper,
                        msb_channel=abs_msb,
                        lsb_channel=abs_lsb,
                        entry_id=entry.entry_id,
                        fixture_id=fixture_id,
                        channel_name=base,
                        hidden_by_default=hidden,
                        fixture_label=entity_fixture_label,
                        dmx_writer=dmx_writer,
                    )
                )

            for channel in channels:
                offset = channel.get("offset")
                if offset in handled_offsets:
                    continue
                if rgb_group and offset in (rgb_group["red"], rgb_group["green"], rgb_group["blue"]):
                    red_offset = rgb_group["red"]
                    green_offset = rgb_group["green"]
                    blue_offset = rgb_group["blue"]
                    dim_offset = rgb_group.get("dim")
                    handled_offsets.update({red_offset, green_offset, blue_offset})
                    if dim_offset:
                        handled_offsets.add(dim_offset)
                    abs_red = absolute_channel(int(start_channel), int(red_offset))
                    abs_green = absolute_channel(int(start_channel), int(green_offset))
                    abs_blue = absolute_channel(int(start_channel), int(blue_offset))
                    abs_dim = absolute_channel(int(start_channel), int(dim_offset)) if dim_offset else None
                    entities.append(
                        ArtNetDMXRGBLight(
                            artnet_helper=artnet_helper,
                            dmx_writer=dmx_writer,
                            red_channel=abs_red,
                            green_channel=abs_green,
                            blue_channel=abs_blue,
                            dim_channel=abs_dim,
                            entry_id=entry.entry_id,
                            fixture_id=fixture_id,
                            channel_name=fixture_type,
                            fixture_label=entity_fixture_label,
                        )
                    )

            for channel in channels:
                offset = channel.get("offset")
                if offset in handled_offsets:
                    continue
                if "value_map" in channel:
                    continue
                abs_channel = absolute_channel(int(start_channel), int(offset))
                entities.append(
                    ArtNetDMXLight(
                        artnet_helper=artnet_helper,
                        dmx_writer=dmx_writer,
                        channel=abs_channel,
                        entry_id=entry.entry_id,
                        fixture_id=fixture_id,
                        channel_name=channel.get("name"),
                        hidden_by_default=bool(channel.get("hidden_by_default", False)),
                        fixture_label=entity_fixture_label,
                    )
                )
    except HomeAssistantError:
        LOGGER.exception("Failed to load fixture mapping for light platform")

    if entities:
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
        fixture_id: str,
        channel_name: str | None = None,
        hidden_by_default: bool = False,
        dmx_writer: DMXWriter | None = None,
        fixture_label: str | None = None,
    ) -> None:
        """
        Initialize the ArtNet DMX Light.

        Args:
            artnet_helper: The Art-Net helper instance
            channel: DMX channel number (1-512)
            entry_id: Config entry ID

        """
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
        # Allow mapping to request the channel be disabled by default in the entity registry
        self._attr_entity_registry_enabled_default = not bool(hidden_by_default)
        # Device grouping information: associate entities for the same config entry (fixture)
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
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channel(self._channel, int(self._brightness))
        else:
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
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channel(self._channel, 0)
        else:
            await self._artnet_helper.set_channel(self._channel, 0)

        LOGGER.debug("Turned off DMX channel %s", self._channel)

        # Update the state
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
            self._attr_name = f"{human_channel}"
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
        self._rgb = (red_value, green_value, blue_value)
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
        # default full
        elif self._brightness == 0:
            self._brightness = 255

        if rgb is not None:
            self._rgb = tuple(int(c) for c in rgb)

        # compute scale factor
        scale = self._brightness / 255.0 if self._brightness is not None else 1.0

        # send dim if available

        if self._dim is not None:
            if self._dmx_writer is not None:
                await self._dmx_writer.set_channel(self._dim, int(clamp_dmx_value(self._brightness)))
            else:
                await self._artnet_helper.set_channel(self._dim, int(clamp_dmx_value(self._brightness)))

        # send rgb channels scaled by brightness
        r = clamp_dmx_value(int(self._rgb[0] * scale))
        g = clamp_dmx_value(int(self._rgb[1] * scale))
        b = clamp_dmx_value(int(self._rgb[2] * scale))
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channels({self._red: r, self._green: g, self._blue: b})
        else:
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
            if self._dmx_writer is not None:
                await self._dmx_writer.set_channel(self._dim, 0)
            else:
                await self._artnet_helper.set_channel(self._dim, 0)
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channels({self._red: 0, self._green: 0, self._blue: 0})
        else:
            await self._artnet_helper.set_channel(self._red, 0)
            await self._artnet_helper.set_channel(self._green, 0)
            await self._artnet_helper.set_channel(self._blue, 0)
        self._is_on = False
        try:
            self.async_write_ha_state()
        except RuntimeError:
            pass


class ArtNetDMX16BitLight(LightEntity):
    """Composite 16-bit channel represented as a single Light entity.

    This entity maps an 8-bit brightness (0-255) to a 16-bit DMX value
    (0-65535) and writes the MSB and LSB channels accordingly.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        artnet_helper: ArtNetDMXHelper,
        msb_channel: int,
        lsb_channel: int,
        entry_id: str,
        fixture_id: str,
        channel_name: str | None = None,
        hidden_by_default: bool = False,
        dmx_writer: DMXWriter | None = None,
        fixture_label: str | None = None,
    ) -> None:
        self._artnet_helper = artnet_helper
        self._dmx_writer = dmx_writer
        self._msb = msb_channel
        self._lsb = lsb_channel
        self._attr_unique_id = f"{entry_id}_{fixture_id}_channel_{self._msb}_{self._lsb}"
        human_label = _humanize(fixture_label) or fixture_label
        human_channel = _humanize(channel_name) or channel_name
        if human_label and human_channel:
            self._attr_name = f"{human_label} {human_channel}"
        elif human_label:
            self._attr_name = f"{human_label} 16-bit {self._msb}"
        elif human_channel:
            self._attr_name = f"{human_channel}"
        else:
            self._attr_name = f"DMX 16-bit {self._msb}"
        self._attr_entity_registry_enabled_default = not bool(hidden_by_default)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=fixture_label or f"{entry_id} Fixture",
        )
        self._attr_icon = "mdi:lightbulb"
        msb_value = _channel_value(artnet_helper, self._msb)
        lsb_value = _channel_value(artnet_helper, self._lsb)
        initial_16bit = (msb_value << 8) | lsb_value
        self._brightness = initial_16bit // 257
        self._is_on = initial_16bit > 0


def _channel_value(artnet_helper: ArtNetDMXHelper, channel: int) -> int:
    """Read a buffered DMX value when the helper exposes one."""
    if hasattr(artnet_helper, "get_channel_value"):
        try:
            return int(artnet_helper.get_channel_value(channel))
        except Exception:
            return 0
    return 0

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
        # Map 0..255 to 0..65535 by multiplying by 257
        val16 = int(self._brightness) * 257
        msb = (val16 >> 8) & 0xFF
        lsb = val16 & 0xFF
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channel(self._msb, msb)
            await self._dmx_writer.set_channel(self._lsb, lsb)
        else:
            await self._artnet_helper.set_channel(self._msb, msb)
            await self._artnet_helper.set_channel(self._lsb, lsb)
        self.async_write_ha_state()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        self._brightness = 0
        self._is_on = False
        if self._dmx_writer is not None:
            await self._dmx_writer.set_channel(self._msb, 0)
            await self._dmx_writer.set_channel(self._lsb, 0)
        else:
            await self._artnet_helper.set_channel(self._msb, 0)
            await self._artnet_helper.set_channel(self._lsb, 0)
        try:
            self.async_write_ha_state()
        except RuntimeError:
            pass
