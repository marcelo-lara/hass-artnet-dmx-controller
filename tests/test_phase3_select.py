import asyncio
import importlib
from types import SimpleNamespace

from custom_components.artnet_dmx_controller import select as select_mod


def test_select_entity_value_map_and_send():
    hass = SimpleNamespace()
    hass.data = {}

    # artnet helper that records sent channel/value pairs
    sent = []

    async def set_channel(ch, val):
        sent.append((ch, val))

    helper = SimpleNamespace()
    helper.set_channel = set_channel

    entry_id = "select-test-entry"
    domain = "artnet_dmx_controller"
    hass.data.setdefault(domain, {})
    hass.data[domain][entry_id] = helper

    # mapping with one channel having a value_map
    mapping = {
        "fixtures": {
            "vm": {
                "channel_count": 1,
                "channels": [
                    {
                        "name": "color",
                        "offset": 1,
                        "description": "color wheel",
                        "value_map": {"0": "White", "10": "Red", "20": "Blue"},
                    }
                ],
            }
        }
    }

    # Monkeypatch loader on select module
    sel_mod = importlib.import_module("custom_components.artnet_dmx_controller.select")
    orig_loader = sel_mod.load_fixture_mapping
    sel_mod.load_fixture_mapping = lambda: mapping

    try:
        entry = SimpleNamespace(entry_id=entry_id, data={"fixture_type": "vm", "start_channel": 20, "channel_count": 1})

        added = []

        def async_add_entities(entities):
            added.extend(entities)

        asyncio.run(select_mod.async_setup_entry(hass, entry, async_add_entities))

    finally:
        # restore loader
        sel_mod.load_fixture_mapping = orig_loader

    # find the select entity (has options)
    select_entities = [e for e in added if hasattr(e, "options")]
    assert len(select_entities) == 1
    sel = select_entities[0]

    # options should match mapping labels
    assert set(sel.options) == {"White", "Red", "Blue"}

    # select an option and verify helper recorded the numeric value
    asyncio.run(sel.async_select_option("Red"))
    assert sent == [(20, 10)]
