import asyncio
from types import SimpleNamespace

from custom_components.artnet_dmx_controller.number import async_setup_entry


class DummyArtNetHelper:
    def __init__(self):
        self.sent = []
        self._dmx_data = bytearray(512)

    async def set_channels(self, channel_values):
        self.sent.append(dict(channel_values))
        for channel, value in channel_values.items():
            self._dmx_data[channel - 1] = value

    async def set_channel(self, channel: int, value: int):
        self.sent.append({channel: value})
        self._dmx_data[channel - 1] = value

    def get_channel_value(self, channel: int):
        return self._dmx_data[channel - 1]


def test_async_setup_entry_creates_pan_tilt_number_entities():
    hass = SimpleNamespace()
    hass.data = {}

    helper = DummyArtNetHelper()
    entry_id = "test-number-entry"
    hass.data.setdefault("artnet_dmx_controller", {})
    hass.data["artnet_dmx_controller"][entry_id] = helper

    entry = SimpleNamespace(
        entry_id=entry_id,
        data={
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

    assert len(added) == 2
    assert {entity._attr_name for entity in added} == {"Mini Beam Prism Pan", "Mini Beam Prism Tilt"}


def test_pan_tilt_number_sends_split_16bit_value():
    async def _run():
        hass = SimpleNamespace()
        hass.data = {}

        helper = DummyArtNetHelper()
        entry_id = "test-number-write"
        hass.data.setdefault("artnet_dmx_controller", {})
        hass.data["artnet_dmx_controller"][entry_id] = helper

        entry = SimpleNamespace(
            entry_id=entry_id,
            data={
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

        await async_setup_entry(hass, entry, async_add_entities)

        pan_entity = next(entity for entity in added if entity._attr_name.endswith("Pan"))
        await pan_entity.async_set_native_value(4660)
        await asyncio.sleep(0.01)

        assert helper.sent[-1] == {1: 18, 2: 52}
        assert pan_entity.native_value == 4660

    asyncio.run(_run())