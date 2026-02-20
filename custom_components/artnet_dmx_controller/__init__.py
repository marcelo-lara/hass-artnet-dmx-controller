"""
Custom integration for ArtNet DMX Controller with Home Assistant.

For more details about this integration, please refer to
https://github.com/marcelo-lara/hass-artnet-dmx-controller
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

from .artnet import ArtNetDMXHelper
from .const import CONF_TARGET_IP, CONF_UNIVERSE, DOMAIN, LOGGER
from .scene.scene_store import SceneStore
from .scene_services import async_play_scene, async_record_scene

# Service schemas
RECORD_SCHEMA = vol.Schema({vol.Required("entry_id"): cv.string, vol.Required("name"): cv.string})
PLAY_SCHEMA = vol.Schema({vol.Required("entry_id"): cv.string, vol.Required("name"): cv.string, vol.Optional("transition"): vol.Any(None, vol.Coerce(int))})
DELETE_SCHEMA = vol.Schema({vol.Required("name"): cv.string})
LIST_SCHEMA = vol.Schema({})

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

    # Initialize shared SceneStore and register services once
    scene_key = f"{DOMAIN}_scene_store"
    if scene_key not in hass.data:
        store = SceneStore(hass)
        await store.async_load()
        hass.data[scene_key] = store

        # Register services for scene recording and playback under the integration domain
        async def _svc_record(call):
            entry_id = call.data.get("entry_id")
            name = call.data.get("name")
            await async_record_scene(hass, entry_id, name)

        async def _svc_play(call):
            entry_id = call.data.get("entry_id")
            name = call.data.get("name")
            await async_play_scene(hass, entry_id, name)

        async def _svc_list(call):
            scenes = hass.data.get(f"{DOMAIN}_scene_store").async_list()
            LOGGER.info("Available scenes: %s", list(scenes.keys()))

        async def _svc_delete(call):
            name = call.data.get("name")
            await hass.data.get(f"{DOMAIN}_scene_store").async_delete(name)

        hass.services.async_register(DOMAIN, "record_scene", _svc_record, schema=RECORD_SCHEMA)
        hass.services.async_register(DOMAIN, "play_scene", _svc_play, schema=PLAY_SCHEMA)
        hass.services.async_register(DOMAIN, "list_scenes", _svc_list, schema=LIST_SCHEMA)
        hass.services.async_register(DOMAIN, "delete_scene", _svc_delete, schema=DELETE_SCHEMA)

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
