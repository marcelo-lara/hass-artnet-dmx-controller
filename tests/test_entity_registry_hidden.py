import asyncio
from types import SimpleNamespace

from custom_components.artnet_dmx_controller.light import async_setup_entry


def test_hidden_by_default_sets_entity_registry_enabled_default():
    """
    Entities for channels with hidden_by_default=True should be disabled by default.

    This test monkeypatches the mapping used by the light setup by providing an
    inline mapping via the `fixture_type` referenced by the test entry.
    """
    hass = SimpleNamespace()
    hass.data = {}

    helper = SimpleNamespace()
    helper.sent = []
    async def set_channel(ch, val):
        helper.sent.append((ch, val))
    helper.set_channel = set_channel

    domain = "artnet_dmx_controller"
    entry_id = "ent-reg-test"
    hass.data.setdefault(domain, {})
    hass.data[domain][entry_id] = helper

    # Create a small mapping with mixed hidden_by_default flags
    mapping = {
        "fixtures": {
            "mix": {
                "channel_count": 3,
                "channels": [
                    {"name": "dim", "offset": 1, "description": "d", "hidden_by_default": False},
                    {"name": "prog", "offset": 2, "description": "p", "hidden_by_default": True},
                    {"name": "strobe", "offset": 3, "description": "s"},
                ],
            }
        }
    }

    # Monkeypatch the loader in the light module so async_setup_entry uses our mapping
    import importlib
    light_mod = importlib.import_module("custom_components.artnet_dmx_controller.light")
    orig_loader = light_mod.load_fixture_mapping
    light_mod.load_fixture_mapping = lambda: mapping

    try:
        entry = SimpleNamespace(entry_id=entry_id, data={"fixture_type": "mix", "start_channel": 5, "channel_count": 3})

        added = []

        def async_add_entities(entities):
            added.extend(entities)

        asyncio.run(async_setup_entry(hass, entry, async_add_entities))
    finally:
        light_mod.load_fixture_mapping = orig_loader

    # Expect 3 entities created
    assert len(added) == 3

    # Map names to enabled_default flag
    name_to_enabled = {e._attr_name: getattr(e, "_attr_entity_registry_enabled_default", True) for e in added}

    # Channel 1 (dim) should be enabled by default
    assert any("dim" in n and v for n, v in name_to_enabled.items())
    # Channel 2 (prog) should be disabled by default (hidden_by_default=True -> enabled_default False)
    assert any("prog" in n and not v for n, v in name_to_enabled.items())
