import asyncio
import importlib
from types import SimpleNamespace

from homeassistant.helpers.entity import EntityCategory

from custom_components.artnet_dmx_controller import select as select_mod


def test_select_entity_value_map_and_send():
    hass = SimpleNamespace()
    hass.data = {}

    sent = []

    async def set_channel(channel, value):
        sent.append((channel, value))

    helper = SimpleNamespace()
    helper.set_channel = set_channel
    helper._dmx_data = bytearray(512)
    helper.get_channel_value = lambda channel: helper._dmx_data[channel - 1]

    entry_id = "select-test-entry"
    hass.data.setdefault("artnet_dmx_controller", {})
    hass.data["artnet_dmx_controller"][entry_id] = helper

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

    sel_mod = importlib.import_module("custom_components.artnet_dmx_controller.select")
    orig_loader = sel_mod.load_fixture_mapping
    sel_mod.load_fixture_mapping = lambda: mapping

    try:
        entry = SimpleNamespace(
            entry_id=entry_id,
            data={
                "id": "fixture-vm",
                "target_ip": "192.168.1.100",
                "universe": 0,
                "fixture_type": "vm",
                "start_channel": 20,
                "channel_count": 1,
            },
        )

        added = []

        def async_add_entities(entities):
            added.extend(entities)

        asyncio.run(select_mod.async_setup_entry(hass, entry, async_add_entities))
    finally:
        sel_mod.load_fixture_mapping = orig_loader

    select_entities = [entity for entity in added if hasattr(entity, "options")]
    assert len(select_entities) == 1
    entity = select_entities[0]
    assert set(entity.options) == {"White", "Red", "Blue"}
    assert entity.current_option == "White"
    assert entity.entity_category == EntityCategory.CONFIG

    asyncio.run(entity.async_select_option("Red"))
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
