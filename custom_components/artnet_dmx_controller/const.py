"""Constants for ArtNet DMX Controller."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "artnet_dmx_controller"
DEFAULT_PORT = 6454

# Config flow constants
CONF_TARGET_IP = "target_ip"
CONF_UNIVERSE = "universe"
CONF_FIXTURE_ID = "id"
CONF_FIXTURE_TYPE = "fixture_type"
CONF_START_CHANNEL = "start_channel"
CONF_CHANNEL_COUNT = "channel_count"
CONF_NAME = "name"
CONF_LOCATION = "location"

# Runtime storage keys
DATA_ENTRY_DATA = "entry_data"
DATA_ENTRY_HELPER_KEYS = "entry_helper_keys"
DATA_HELPER_LOCK = "helper_lock"
DATA_HELPER_REFCOUNTS = "helper_refcounts"
DATA_SHARED_HELPERS = "shared_helpers"

# Default values
DEFAULT_UNIVERSE = 0

# DMX constants
DMX_CHANNELS = 512
DMX_MAX_VALUE = 255
DMX_MIN_CHANNEL = 1
MAX_UNIVERSE = 32767
