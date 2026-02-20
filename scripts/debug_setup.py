import asyncio
from types import SimpleNamespace

from custom_components.artnet_dmx_controller.light import async_setup_entry, load_fixture_mapping


def main():
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

        print(f"Created {len(added)} entities")
        for i, e in enumerate(added, 1):
            print(i, type(e).__name__, getattr(e, '_attr_name', None), getattr(e, '_attr_unique_id', None), getattr(e, '_attr_entity_registry_enabled_default', None))
    finally:
        light_mod.load_fixture_mapping = orig_loader


if __name__ == '__main__':
    main()
