import asyncio
import importlib
from types import SimpleNamespace

integration_init = importlib.import_module("custom_components.artnet_dmx_controller")
from custom_components.artnet_dmx_controller.const import DOMAIN


def make_fake_hass(registrations):
    hass = SimpleNamespace()
    hass.data = {}

    class Services:
        def async_register(self, domain, service, handler, schema=None):
            registrations.append((domain, service, handler, schema))

    hass.services = Services()

    class ConfigEntries:
        async def async_forward_entry_setups(self, entry, platforms):
            return None

    hass.config_entries = ConfigEntries()
    return hass


def test_services_registered_with_schemas():
    regs = []
    hass = make_fake_hass(regs)

    # Force in-memory SceneStore to avoid Home Assistant storage requirement
    ss_mod = importlib.import_module("custom_components.artnet_dmx_controller.scene.scene_store")
    ss_mod.Store = None

    entry = SimpleNamespace()
    entry.entry_id = "e1"
    entry.data = {"target_ip": "127.0.0.1", "universe": 0}

    asyncio.run(integration_init.async_setup_entry(hass, entry))

    services = {r[1]: r for r in regs}
    assert "record_scene" in services
    assert "play_scene" in services
    assert "list_scenes" in services
    assert "delete_scene" in services

    # Ensure schemas were attached (not None)
    assert services["record_scene"][3] is not None
    assert services["play_scene"][3] is not None
    assert services["delete_scene"][3] is not None


def test_delete_scene_service_removes_scene():
    # Prepare hass and store
    regs = []
    hass = make_fake_hass(regs)
    ss_mod = importlib.import_module("custom_components.artnet_dmx_controller.scene.scene_store")
    ss_mod.Store = None
    entry = SimpleNamespace()
    entry.entry_id = "e1"
    entry.data = {"target_ip": "127.0.0.1", "universe": 0}

    asyncio.run(integration_init.async_setup_entry(hass, entry))

    store = hass.data.get(f"{DOMAIN}_scene_store")
    # capture a scene directly
    asyncio.run(store.async_capture("tosave", {1: 10}))
    assert "tosave" in store.async_list()

    # call the registered delete handler
    delete_reg = next(r for r in regs if r[1] == "delete_scene")
    # handler is at index 2
    handler = delete_reg[2]
    # Call handler with a fake service call
    call = SimpleNamespace()
    call.data = {"name": "tosave"}
    asyncio.run(handler(call))

    assert "tosave" not in store.async_list()  # noqa: S101
