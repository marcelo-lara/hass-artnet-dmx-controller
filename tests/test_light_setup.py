import asyncio
from types import SimpleNamespace

from custom_components.artnet_dmx_controller.light import async_setup_entry


class DummyArtNetHelper:
    def __init__(self):
        self.sent = []
        self._dmx_data = bytearray(512)

    async def set_channel(self, channel: int, value: int):
        self.sent.append((channel, value))

    def get_channel_value(self, channel: int):
        return self._dmx_data[channel - 1]


class DummyEntry:
    def __init__(self, entry_id: str, data: dict):
        self.entry_id = entry_id
        self.data = data


def test_async_setup_entry_creates_fixture_entities():
    hass = SimpleNamespace()
    hass.data = {}

    helper = DummyArtNetHelper()
    entry_id = "test-entry"
    hass.data.setdefault("artnet_dmx_controller", {})
    hass.data["artnet_dmx_controller"][entry_id] = helper

    entry = DummyEntry(
        entry_id,
        {
            "id": "fixture-1",
            "target_ip": "192.168.1.100",
            "universe": 0,
            "fixture_type": "parcan_rgb_gen",
            "start_channel": 10,
            "channel_count": 5,
        },
    )

    added = []

    def async_add_entities(entities):
        added.extend(entities)

    asyncio.run(async_setup_entry(hass, entry, async_add_entities))

    assert len(added) == 1
    rgb_entities = [entity for entity in added if hasattr(entity, "_red") and hasattr(entity, "_green")]
    assert len(rgb_entities) == 1
    assert len({entity._attr_unique_id for entity in added}) == 1


def test_async_setup_entry_skips_value_map_channels_in_light_platform():
    hass = SimpleNamespace()
    hass.data = {}

    helper = DummyArtNetHelper()
    entry_id = "test-entry-value-map"
    hass.data.setdefault("artnet_dmx_controller", {})
    hass.data["artnet_dmx_controller"][entry_id] = helper

    entry = DummyEntry(
        entry_id,
        {
            "id": "fixture-1",
            "target_ip": "192.168.1.100",
            "universe": 0,
            "fixture_type": "mini_beam_prism",
            "start_channel": 1,
            "channel_count": 12,
        },
    )

    added = []

    def async_add_entities(entities):
        added.extend(entities)

    asyncio.run(async_setup_entry(hass, entry, async_add_entities))

    assert len(added) == 1
    assert all(entity.__class__.__name__ != "ArtNetDMXSelect" for entity in added)
    assert added[0]._attr_name.endswith("Dim")
