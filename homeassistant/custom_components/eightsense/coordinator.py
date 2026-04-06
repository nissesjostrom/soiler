"""Coordinator for the 8sense Home Assistant integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_PATH, DEFAULT_SCAN_INTERVAL, DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EightSenseApiClientError(Exception):
    """Raised when the 8sense API request fails."""


class EightSenseApiClient:
    """Simple client for the 8sense Flask API."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        self._session = async_get_clientsession(hass)
        self.base_url = f"http://{host}:{port}"
        self.api_url = f"{self.base_url}{API_PATH}"

    async def async_get_payload(self) -> dict:
        """Fetch the Home Assistant payload from the API."""
        try:
            async with self._session.get(self.api_url, timeout=DEFAULT_TIMEOUT) as response:
                response.raise_for_status()
                payload = await response.json()
        except (ClientError, TimeoutError, ValueError) as err:
            raise EightSenseApiClientError(f"Unable to fetch 8sense data: {err}") from err

        if "sensor_catalog" not in payload or "device" not in payload:
            raise EightSenseApiClientError("8sense API response is missing required fields")

        return payload


class EightSenseDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Fetch 8sense sensor data and fan it out to entities."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: EightSenseApiClient,
    ) -> None:
        self.client = client
        self.config_entry = entry
        interval_seconds = entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval_seconds),
        )

    async def _async_update_data(self) -> dict:
        """Fetch the latest payload."""
        try:
            return await self.client.async_get_payload()
        except EightSenseApiClientError as err:
            raise UpdateFailed(str(err)) from err

    @property
    def catalog_by_key(self) -> dict[str, dict]:
        """Return the sensor catalog keyed by stable sensor key."""
        return {
            item["key"]: item
            for item in self.data.get("sensor_catalog", [])
            if item.get("key")
        }

    @property
    def entities_by_key(self) -> dict[str, dict]:
        """Return the active entity payload keyed by stable sensor key."""
        return {
            item["key"]: item
            for item in self.data.get("entities", [])
            if item.get("key")
        }
