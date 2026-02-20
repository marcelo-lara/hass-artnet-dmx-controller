import asyncio
from types import SimpleNamespace

from custom_components.artnet_dmx_controller.const import DOMAIN
from custom_components.artnet_dmx_controller.scene.scene_store import SceneStore
from custom_components.artnet_dmx_controller.scene_services import (
    async_play_scene,
    async_record_scene,
)


def test_record_and_play_scene():
    hass = SimpleNamespace()
    hass.data = {}

    # create a helper with an internal DMX buffer and a recorder for set_channels
    sent = []

    class Helper:
        def __init__(self):
            self._dmx_data = bytearray(512)

        async def set_channels(self, channel_values):
            sent.append(dict(channel_values))

    helper = Helper()
    # set some channel values
    helper._dmx_data[9] = 100  # channel 10
    helper._dmx_data[19] = 200  # channel 20

    entry_id = "entry-1"
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry_id] = helper

    # attach an in-memory SceneStore: force the module to use in-memory fallback
    import importlib
    ss_mod = importlib.import_module("custom_components.artnet_dmx_controller.scene.scene_store")
    ss_mod.Store = None
    hass.config = SimpleNamespace(config_dir="/tmp")
    store = SceneStore(hass)
    # in-memory store doesn't require async load but call to be symmetric
    asyncio.run(store.async_load())
    hass.data[f"{DOMAIN}_scene_store"] = store

    # record scene
    asyncio.run(async_record_scene(hass, entry_id, "testscene"))

    scenes = store.async_list()
    assert "testscene" in scenes
    # recorded entities should include 10 and 20
    entities = scenes["testscene"]["entities"]
    assert 10 in entities and 20 in entities

    # play the scene and assert helper got the bulk write
    asyncio.run(async_play_scene(hass, entry_id, "testscene"))
    assert len(sent) == 1
    applied = sent[0]
    assert applied.get(10) == 100 and applied.get(20) == 200
