"""Constants for ArtNet DMX Controller."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "artnet_dmx_controller"
DEFAULT_PORT = 6454

# Config flow constants
CONF_TARGET_IP = "target_ip"
CONF_UNIVERSE = "universe"
CONF_FIXTURES = "fixtures"
CONF_FIXTURE_ID = "id"
CONF_FIXTURE_TYPE = "fixture_type"
CONF_START_CHANNEL = "start_channel"
CONF_CHANNEL_COUNT = "channel_count"
CONF_NAME = "name"

# Default values
DEFAULT_UNIVERSE = 0
DEFAULT_CHANNEL_COUNT = 10

# DMX constants
DMX_CHANNELS = 512
DMX_MAX_VALUE = 255
DMX_MIN_CHANNEL = 1
MAX_UNIVERSE = 32767
