import asyncio
from types import SimpleNamespace

from custom_components.artnet_dmx_controller.light import (
    async_setup_entry,
)


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

    # Expect composite RGB + strobe for parcan -> 2 entities
    assert len(added) == 2

    # Find rgb composite entity (we detect by presence of internal _red attribute)
    rgb_entities = [e for e in added if hasattr(e, "_red") and hasattr(e, "_green") and hasattr(e, "_blue")]
    assert len(rgb_entities) == 1
    strobe_entities = [e for e in added if e not in rgb_entities]
    assert len(strobe_entities) == 1

    # Ensure unique ids present and stable
    unique_ids = {e._attr_unique_id for e in added}
    assert len(unique_ids) == 2


def test_async_setup_entry_skips_value_map_channels_in_light_platform():
    # Prepare fake hass with minimal data storage
    hass = SimpleNamespace()
    hass.data = {}

    helper = DummyArtNetHelper()
    domain = "artnet_dmx_controller"
    entry_id = "test-entry-value-map"
    hass.data.setdefault(domain, {})
    hass.data[domain][entry_id] = helper

    # mini_beam_prism includes value_map channels (color/gobo) that should be
    # created only by the select platform, not light platform.
    entry = DummyEntry(
        entry_id,
        {"fixture_type": "mini_beam_prism", "start_channel": 1, "channel_count": 12},
    )

    added = []

    def async_add_entities(entities):
        added.extend(entities)

    asyncio.run(async_setup_entry(hass, entry, async_add_entities))

    # Expected light platform entities:
    # - pan + tilt as 16-bit composites: 2
    # - speed, dim, strobe, prism, autoplay, reset as lights: 6
    # Total: 8
    assert len(added) == 8
    # Select entities should not be created by light.py
    assert all(e.__class__.__name__ != "ArtNetDMXSelect" for e in added)
