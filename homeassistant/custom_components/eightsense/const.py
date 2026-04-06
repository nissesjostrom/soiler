"""Constants for the 8sense Home Assistant integration."""

from homeassistant.const import Platform

DOMAIN = "eightsense"
PLATFORMS: list[Platform] = [Platform.SENSOR]

DEFAULT_NAME = "8sense Soil Sensor"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5001
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
API_PATH = "/api/homeassistant"
