"""
Custom integration for ArtNet DMX Controller with Home Assistant.

For more details about this integration, please refer to
https://github.com/marcelo-lara/hass-artnet-dmx-controller
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .artnet import ArtNetDMXHelper
from .const import CONF_TARGET_IP, CONF_UNIVERSE, DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up ArtNet DMX Controller from a config entry."""
    target_ip = entry.data[CONF_TARGET_IP]
    universe = entry.data[CONF_UNIVERSE]

    # Create Art-Net helper
    artnet_helper = ArtNetDMXHelper(
        hass=hass,
        target_ip=target_ip,
        universe=universe,
    )

    # Setup the socket
    artnet_helper.setup_socket()

    # Store the helper in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = artnet_helper

    LOGGER.info(
        "ArtNet DMX Controller configured for %s (Universe %s)",
        target_ip,
        universe,
    )

    # Forward the setup to the light platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Close the socket
    if entry.entry_id in hass.data[DOMAIN]:
        artnet_helper = hass.data[DOMAIN][entry.entry_id]
        artnet_helper.close_socket()
        hass.data[DOMAIN].pop(entry.entry_id)

    # Unload the platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
