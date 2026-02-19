"""Art-Net DMX packet helper for ArtNet DMX Controller."""

from __future__ import annotations

import asyncio
import socket
import struct
from typing import TYPE_CHECKING

from .const import DEFAULT_PORT, DMX_CHANNELS, DMX_MAX_VALUE, DMX_MIN_CHANNEL, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Art-Net constants
ARTNET_HEADER = b"Art-Net\x00"
ARTNET_OPCODE_OUTPUT = 0x5000  # OpOutput/OpDmx


class ArtNetDMXHelper:
    """Helper class for constructing and sending Art-Net DMX packets."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_ip: str,
        universe: int = 0,
        port: int = DEFAULT_PORT,
    ) -> None:
        """
        Initialize the Art-Net DMX helper.

        Args:
            hass: Home Assistant instance
            target_ip: Target IP address for Art-Net packets
            universe: DMX universe number (0-32767)
            port: Art-Net port (default 6454)

        """
        self.hass = hass
        self.target_ip = target_ip
        self.universe = universe
        self.port = port
        self._socket: socket.socket | None = None
        self._dmx_data = bytearray(DMX_CHANNELS)  # DMX data buffer

    def setup_socket(self) -> None:
        """Set up the UDP socket for Art-Net communication."""
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setblocking(False)  # noqa: FBT003
            LOGGER.debug(
                "Art-Net socket created for %s:%s (Universe %s)",
                self.target_ip,
                self.port,
                self.universe,
            )

    def close_socket(self) -> None:
        """Close the UDP socket."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
            LOGGER.debug("Art-Net socket closed")

    def construct_artnet_packet(self, dmx_data: bytes | bytearray) -> bytes:
        """
        Construct an Art-Net DMX packet (OpOutput).

        Args:
            dmx_data: DMX channel data (up to 512 bytes)

        Returns:
            Complete Art-Net packet as bytes

        """
        # Ensure DMX data is exactly DMX_CHANNELS bytes
        data = bytearray(dmx_data[:DMX_CHANNELS])
        if len(data) < DMX_CHANNELS:
            data.extend(b"\x00" * (DMX_CHANNELS - len(data)))

        # Calculate subnet and universe from the universe number
        subnet = (self.universe >> 4) & 0x0F
        universe_addr = self.universe & 0x0F

        # Art-Net packet structure:
        # - Header: "Art-Net\x00" (8 bytes)
        # - OpCode: 0x5000 (2 bytes, little-endian)
        # - ProtVer: 14 (2 bytes, big-endian)
        # - Sequence: 0 (1 byte)
        # - Physical: 0 (1 byte)
        # - SubUni: subnet (4 bits) + universe (4 bits) (1 byte)
        # - Net: 0 (1 byte)
        # - Length: 512 (2 bytes, big-endian)
        # - Data: DMX data (512 bytes)

        packet = bytearray()
        packet.extend(ARTNET_HEADER)  # Header
        packet.extend(struct.pack("<H", ARTNET_OPCODE_OUTPUT))  # OpCode (little-endian)
        packet.extend(struct.pack(">H", 14))  # ProtVer 14 (big-endian)
        packet.append(0)  # Sequence
        packet.append(0)  # Physical
        packet.append((subnet << 4) | universe_addr)  # SubUni
        packet.append(0)  # Net
        packet.extend(struct.pack(">H", DMX_CHANNELS))  # Length (big-endian)
        packet.extend(data)  # DMX data

        return bytes(packet)

    async def send_dmx_data(self, dmx_data: bytes | bytearray) -> None:
        """
        Send DMX data via Art-Net packet asynchronously.

        Args:
            dmx_data: DMX channel data to send

        """
        if self._socket is None:
            self.setup_socket()

        packet = self.construct_artnet_packet(dmx_data)

        # Send using asyncio's loop to avoid blocking
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                None,
                self._socket.sendto,
                packet,
                (self.target_ip, self.port),
            )
            LOGGER.debug(
                "Sent Art-Net packet to %s:%s (Universe %s)",
                self.target_ip,
                self.port,
                self.universe,
            )
        except OSError as err:
            LOGGER.error("Failed to send Art-Net packet: %s", err)

    async def set_channel(self, channel: int, value: int) -> None:
        """
        Set a single DMX channel value and send the data.

        Args:
            channel: DMX channel number (1-512)
            value: DMX value (0-255)

        """
        if not DMX_MIN_CHANNEL <= channel <= DMX_CHANNELS:
            msg = (
                f"Channel must be between {DMX_MIN_CHANNEL} and "
                f"{DMX_CHANNELS}, got {channel}"
            )
            raise ValueError(msg)
        if not 0 <= value <= DMX_MAX_VALUE:
            msg = f"Value must be between 0 and {DMX_MAX_VALUE}, got {value}"
            raise ValueError(msg)

        # DMX channels are 1-indexed, but our array is 0-indexed
        self._dmx_data[channel - 1] = value
        await self.send_dmx_data(self._dmx_data)

    async def set_channels(self, channel_values: dict[int, int]) -> None:
        """
        Set multiple DMX channel values and send the data.

        Args:
            channel_values: Dictionary mapping channel numbers to values

        """
        for channel, value in channel_values.items():
            if not DMX_MIN_CHANNEL <= channel <= DMX_CHANNELS:
                msg = (
                    f"Channel must be between {DMX_MIN_CHANNEL} and "
                    f"{DMX_CHANNELS}, got {channel}"
                )
                raise ValueError(msg)
            if not 0 <= value <= DMX_MAX_VALUE:
                msg = f"Value must be between 0 and {DMX_MAX_VALUE}, got {value}"
                raise ValueError(msg)
            self._dmx_data[channel - 1] = value

        await self.send_dmx_data(self._dmx_data)
