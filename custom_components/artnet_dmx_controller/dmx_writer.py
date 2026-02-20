"""Centralized DMX write helper (Phase 4).

Batches channel updates occurring in the same event-loop turn and forwards
them to the underlying ArtNet helper via `set_channels` when available.
"""
from __future__ import annotations

import asyncio
from typing import Any

from .channel_math import clamp_dmx_value


class DMXWriter:
    """Batching writer that serializes and batches DMX writes.

    This class accepts single-channel writes via `set_channel` and will batch
    multiple writes that happen in the same event-loop tick into a single
    `set_channels` call when the underlying helper supports it.
    """

    def __init__(self, artnet_helper: Any) -> None:
        self._helper = artnet_helper
        self._pending: dict[int, int] = {}
        self._lock = asyncio.Lock()
        self._flush_scheduled = False

    async def set_channel(self, channel: int, value: int) -> None:
        """Enqueue a single channel update and schedule a flush."""
        v = clamp_dmx_value(int(value))
        # If helper does not support bulk `set_channels`, forward immediately
        if not hasattr(self._helper, "set_channels"):
            await self._helper.set_channel(channel, v)
            return

        self._pending[channel] = v

        if not self._flush_scheduled:
            self._flush_scheduled = True
            # schedule a short debounce to allow batching in the same loop turn
            asyncio.create_task(self._flush_debounced())

    async def set_channels(self, channel_values: dict[int, int]) -> None:
        """Enqueue multiple channel updates and schedule a flush."""
        # If helper supports bulk, enqueue for batch; otherwise forward immediately
        if not hasattr(self._helper, "set_channels"):
            for ch, val in channel_values.items():
                await self._helper.set_channel(ch, clamp_dmx_value(int(val)))
            return

        for ch, val in channel_values.items():
            self._pending[ch] = clamp_dmx_value(int(val))

        if not self._flush_scheduled:
            self._flush_scheduled = True
            asyncio.create_task(self._flush_debounced())

    async def _flush_debounced(self) -> None:
        """Flush pending updates after yielding to the event loop."""
        # yield control so callers in the same loop tick can accumulate updates
        await asyncio.sleep(0)

        async with self._lock:
            pending = dict(self._pending)
            self._pending.clear()
            self._flush_scheduled = False

        if not pending:
            return

        # Prefer a bulk `set_channels` if available on the helper
        if hasattr(self._helper, "set_channels"):
            await self._helper.set_channels(pending)
        else:
            # Fallback to single-channel writes
            for ch, val in pending.items():
                await self._helper.set_channel(ch, val)
