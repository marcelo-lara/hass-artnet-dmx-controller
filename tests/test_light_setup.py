import asyncio

from types import SimpleNamespace

from custom_components.artnet_dmx_controller.light import async_setup_entry, ArtNetDMXLight


class DummyArtNetHelper:
    def __init__(self):
        self.sent = []

    async def set_channel(self, channel: int, value: int):
        self.sent.append((channel, value))


class DummyEntry:
    def __init__(self, entry_id: str, data: dict):
        self.entry_id = entry_id
        self.data = data


def test_async_setup_entry_creates_fixture_entities():
    # Prepare fake hass with minimal data storage
    hass = SimpleNamespace()
    hass.data = {}

    # Create a dummy artnet helper and register under domain
    helper = DummyArtNetHelper()
    domain = "artnet_dmx_controller"
    entry_id = "test-entry"
    hass.data.setdefault(domain, {})
    hass.data[domain][entry_id] = helper

    # Use a known fixture type from the bundled mapping: 'parcan' (5 channels)
    entry = DummyEntry(entry_id, {"fixture_type": "parcan", "start_channel": 10, "channel_count": 5})

    added = []

    def async_add_entities(entities):
        # mimic Home Assistant's async_add_entities which may be sync in tests
        added.extend(entities)

    # Run the async setup
    asyncio.run(async_setup_entry(hass, entry, async_add_entities))

    # Expect 5 entities created for parcan
    assert len(added) == 5

    # Verify channels are absolute: start_channel + offset - 1
    channels = [e._channel for e in added]
    assert channels == [10 + i for i in range(5)]

    # Ensure unique ids present and stable
    unique_ids = {e._attr_unique_id for e in added}
    assert len(unique_ids) == 5
