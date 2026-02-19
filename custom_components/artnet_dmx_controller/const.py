"""Constants for ArtNet DMX Controller."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "artnet_dmx_controller"
DEFAULT_PORT = 6454

# Config flow constants
CONF_TARGET_IP = "target_ip"
CONF_UNIVERSE = "universe"

# Default values
DEFAULT_UNIVERSE = 0
DEFAULT_CHANNEL_COUNT = 10

# DMX constants
DMX_CHANNELS = 512
DMX_MAX_VALUE = 255
DMX_MIN_CHANNEL = 1
MAX_UNIVERSE = 32767
