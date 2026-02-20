"""SceneStore for the ArtNet DMX Controller integration.

Persistent store key and implementation live under the integration
`custom_components/artnet_dmx_controller/scene`.
"""
from __future__ import annotations

from typing import Any, Dict
import logging
from datetime import datetime, timezone

try:
    from homeassistant.helpers.storage import Store
    from homeassistant.core import HomeAssistant
except Exception:  # pragma: no cover - allow running tests outside HA
    Store = None
    HomeAssistant = object

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "artnet_dmx_controller_scene_store"


class SceneStore:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._store = None if Store is None else Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: Dict[str, Any] = {}

    async def async_load(self) -> None:
        if self._store is None:
            _LOGGER.debug("SceneStore: Store helper not available; using in-memory only")
            self._data = {}
            return
        data = await self._store.async_load()
        if not data:
            self._data = {}
            return
        self._data = data.get("scenes", {})

    async def async_save(self) -> None:
        if self._store is None:
            _LOGGER.debug("SceneStore: skipping persist (no Store helper)")
            return
        payload = {"scenes": self._data}
        await self._store.async_save(payload)

    async def async_capture(self, name: str, entities: Dict[str, Any]) -> None:
        # Use timezone-aware UTC timestamp
        self._data[name] = {"name": name, "created_at": datetime.now(timezone.utc).isoformat(), "entities": entities}
        await self.async_save()

    async def async_apply(self, name: str, transition: int | None = None) -> None:
        scene = self._data.get(name)
        if not scene:
            _LOGGER.error("Scene not found: %s", name)
            return
        # Minimal: apply by calling services on entities would be implemented here
        _LOGGER.debug("Would apply scene '%s' with %s entities", name, len(scene.get("entities", {})))

    def async_list(self) -> Dict[str, Any]:
        return self._data

    async def async_delete(self, name: str) -> None:
        if name in self._data:
            del self._data[name]
            await self.async_save()
