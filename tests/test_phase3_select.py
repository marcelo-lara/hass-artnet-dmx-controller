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
    helper._dmx_data = bytearray(512)

    def get_channel_value(channel):
        return helper._dmx_data[channel - 1]

    helper.get_channel_value = get_channel_value

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
        entry = SimpleNamespace(
            entry_id=entry_id,
            data={
                "fixtures": [
                    {"id": "fixture-vm", "fixture_type": "vm", "start_channel": 20, "channel_count": 1}
                ]
            },
        )

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
    assert sel.current_option == "White"

    # select an option and verify helper recorded the numeric value
    asyncio.run(sel.async_select_option("Red"))
    assert sent == [(20, 10)]


def test_select_entity_uses_explicit_fallback_for_zero_when_unmapped():
    helper = SimpleNamespace()
    helper._dmx_data = bytearray(512)
    helper.get_channel_value = lambda channel: helper._dmx_data[channel - 1]

    entity = select_mod.ArtNetDMXSelect(
        artnet_helper=helper,
        dmx_writer=None,
        channel=5,
        entry_id="entry-id",
        fixture_id="fixture-id",
        channel_name="gobo",
        value_map={"10": "Open", "20": "Pattern 1"},
    )

    assert entity.current_option == "Value 0"
    assert "Value 0" in entity.options
