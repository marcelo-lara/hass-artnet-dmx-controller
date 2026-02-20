"""DMX Scene integration (minimal scaffold).

Registers scene services: capture, apply, list, delete, and provides a
lightweight storage-backed SceneStore.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import ATTR_NAME
import logging

from .scene_store import SceneStore

DOMAIN = "dmx_scene"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the DMX Scene integration (register services)."""
    store = SceneStore(hass)
    await store.async_load()
    hass.data.setdefault(DOMAIN, {})["store"] = store

    async def handle_capture(call: ServiceCall) -> None:
        name = call.data.get(ATTR_NAME)
        if not name:
            _LOGGER.error("capture: missing name")
            return
        entities = call.data.get("entities")
        if entities is None:
            # In a real implementation we would capture current entity states.
            entities = {}
        await store.async_capture(name, entities)
        _LOGGER.info("Captured scene '%s'", name)

    async def handle_apply(call: ServiceCall) -> None:
        name = call.data.get(ATTR_NAME)
        if not name:
            _LOGGER.error("apply: missing name")
            return
        await store.async_apply(name, transition=call.data.get("transition"))
        _LOGGER.info("Applied scene '%s'", name)

    async def handle_list(call: ServiceCall) -> None:
        scenes = store.async_list()
        # Expose count via log for now; integrations/UI can use services to read
        _LOGGER.info("Scenes (%d): %s", len(scenes), list(scenes.keys()))

    async def handle_delete(call: ServiceCall) -> None:
        name = call.data.get(ATTR_NAME)
        if not name:
            _LOGGER.error("delete: missing name")
            return
        await store.async_delete(name)
        _LOGGER.info("Deleted scene '%s'", name)

    hass.services.async_register(DOMAIN, "capture", handle_capture)
    hass.services.async_register(DOMAIN, "apply", handle_apply)
    hass.services.async_register(DOMAIN, "list", handle_list)
    hass.services.async_register(DOMAIN, "delete", handle_delete)

    return True
