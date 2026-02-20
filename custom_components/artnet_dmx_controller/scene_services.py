"""
Scene recording and playback helpers for ArtNet DMX Controller.

This module provides small functions to record the current DMX buffer into
the shared `SceneStore` and to play back a stored scene by writing DMX
channel values to the configured Art-Net helper.
"""
from __future__ import annotations

from typing import Any

from .const import DOMAIN, LOGGER


async def async_record_scene(hass: Any, entry_id: str, name: str) -> None:
    """Record a scene for the given config entry by capturing the Art-Net buffer."""
    scene_store = hass.data.get(f"{DOMAIN}_scene_store")
    if scene_store is None:
        LOGGER.error("SceneStore not initialized; cannot record scene")
        return

    artnet_helper = hass.data.get(DOMAIN, {}).get(entry_id)
    if artnet_helper is None:
        LOGGER.error("ArtNet helper for entry %s not found", entry_id)
        return

    # artnet_helper maintains an internal _dmx_data bytearray buffer
    dmx = getattr(artnet_helper, "_dmx_data", None)
    if dmx is None:
        LOGGER.error("ArtNet helper has no DMX buffer; cannot record scene")
        return

    # capture non-zero channels to keep the scene compact
    entities: dict[int, int] = {}
    for idx, val in enumerate(dmx, start=1):
        if val:
            entities[idx] = int(val)

    await scene_store.async_capture(name, entities)


async def async_play_scene(hass: Any, entry_id: str, name: str) -> None:
    """Play a stored scene by applying saved channel values to the Art-Net helper."""
    scene_store = hass.data.get(f"{DOMAIN}_scene_store")
    if scene_store is None:
        LOGGER.error("SceneStore not initialized; cannot play scene")
        return

    artnet_helper = hass.data.get(DOMAIN, {}).get(entry_id)
    if artnet_helper is None:
        LOGGER.error("ArtNet helper for entry %s not found", entry_id)
        return

    scenes = scene_store.async_list()
    scene = scenes.get(name)
    if not scene:
        LOGGER.error("Scene '%s' not found", name)
        return

    entities = scene.get("entities", {})

    # If artnet_helper supports bulk set_channels, use it; otherwise call set_channel
    if hasattr(artnet_helper, "set_channels"):
        await artnet_helper.set_channels(entities)
    else:
        for ch, val in entities.items():
            await artnet_helper.set_channel(int(ch), int(val))
