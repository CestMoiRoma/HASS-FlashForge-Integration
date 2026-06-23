"""Constants for the Flashforge integration."""

DOMAIN = "flashforge"
DEFAULT_NAME = "FlashForge"

CONF_SERIAL_NUMBER = "serial_number"
CONF_CHECK_CODE = "check_code"
CONF_API_TYPE = "api_type"

# Connection back-ends.
API_TYPE_LEGACY = "legacy"  # M-code TCP protocol on port 8899 (ffpp)
API_TYPE_NEW = "new"  # HTTP JSON API on port 8898 (5M / AD5X / Creator series)

LEGACY_PORT = 8899
NEW_API_PORT = 8898

SCAN_INTERVAL = 30
MAX_FAILED_UPDATES = 3
