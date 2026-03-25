import asyncio
from types import SimpleNamespace

from custom_components.artnet_dmx_controller.number import async_setup_entry


def test_hidden_by_default_sets_entity_registry_enabled_default():
    hass = SimpleNamespace()
    hass.data = {}

    helper = SimpleNamespace()
    helper.sent = []
    helper._dmx_data = bytearray(512)

    async def set_channel(channel, value):
        helper.sent.append((channel, value))

    helper.set_channel = set_channel
    helper.get_channel_value = lambda channel: helper._dmx_data[channel - 1]

    entry_id = "ent-reg-test"
    hass.data.setdefault("artnet_dmx_controller", {})
    hass.data["artnet_dmx_controller"][entry_id] = helper

    mapping = {
        "fixtures": {
            "mix": {
                "fixture_specie": "moving_head",
                "channel_count": 3,
                "channels": [
                    {"name": "dim", "offset": 1, "description": "d", "hidden_by_default": False},
                    {"name": "prog", "offset": 2, "description": "p", "hidden_by_default": True},
                    {"name": "strobe", "offset": 3, "description": "s"},
                ],
            }
        }
    }

    import importlib

    number_mod = importlib.import_module("custom_components.artnet_dmx_controller.number")
    orig_loader = number_mod.load_fixture_mapping
    number_mod.load_fixture_mapping = lambda: mapping

    try:
        entry = SimpleNamespace(
            entry_id=entry_id,
            data={
                "id": "fixture-mix",
                "target_ip": "192.168.1.100",
                "universe": 0,
                "fixture_type": "mix",
                "start_channel": 5,
                "channel_count": 3,
            },
        )

        added = []

        def async_add_entities(entities):
            added.extend(entities)

        asyncio.run(async_setup_entry(hass, entry, async_add_entities))
    finally:
        number_mod.load_fixture_mapping = orig_loader

    assert len(added) == 2
    name_to_enabled = {entity._attr_name: getattr(entity, "_attr_entity_registry_enabled_default", True) for entity in added}
    assert any("prog" in name.lower() and not enabled for name, enabled in name_to_enabled.items())
    assert any("strobe" in name.lower() and enabled for name, enabled in name_to_enabled.items())
