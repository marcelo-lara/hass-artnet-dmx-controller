import asyncio

import pytest


def test_batching_with_set_channels():
    async def _run():
        sent = []

        class Helper:
            async def set_channels(self, channel_values):
                # record a copy of the dict for assertions
                sent.append(("bulk", dict(channel_values)))

            async def set_channel(self, ch, val):
                sent.append(("single", (ch, val)))

        helper = Helper()

        from custom_components.artnet_dmx_controller.dmx_writer import DMXWriter

        writer = DMXWriter(helper)

        # schedule two writes in the same event loop tick
        await writer.set_channel(1, 10)
        await writer.set_channel(2, 20)

        # yield to event loop so flush task runs
        await asyncio.sleep(0.01)

        assert sent == [("bulk", {1: 10, 2: 20})]

    asyncio.run(_run())


def test_fallback_to_single_channel():
    async def _run():
        sent = []

        class Helper:
            async def set_channel(self, ch, val):
                sent.append((ch, val))

        helper = Helper()
        from custom_components.artnet_dmx_controller.dmx_writer import DMXWriter

        writer = DMXWriter(helper)

        # single-channel helper should receive immediate forwarded writes
        await writer.set_channel(5, 55)
        assert sent == [(5, 55)]

    asyncio.run(_run())


def test_set_channels_forward_when_no_bulk():
    async def _run():
        sent = []

        class Helper:
            async def set_channel(self, ch, val):
                sent.append((ch, val))

        helper = Helper()
        from custom_components.artnet_dmx_controller.dmx_writer import DMXWriter

        writer = DMXWriter(helper)

        await writer.set_channels({3: 30, 4: 40})
        assert set(sent) == {(3, 30), (4, 40)}

    asyncio.run(_run())
