"""Sensor platform for the 8sense Home Assistant integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EightSenseDataUpdateCoordinator

DEVICE_CLASS_MAP = {
    "moisture": SensorDeviceClass.MOISTURE,
    "temperature": SensorDeviceClass.TEMPERATURE,
}

STATE_CLASS_MAP = {
    "measurement": SensorStateClass.MEASUREMENT,
}

UNIT_MAP = {
    "%": PERCENTAGE,
    "°C": UnitOfTemperature.CELSIUS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 8sense sensors from a config entry."""
    coordinator: EightSenseDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        EightSenseMeasurementSensor(coordinator, entry, sensor_key)
        for sensor_key in coordinator.catalog_by_key
    ]
    entities.extend(
        [
            EightSenseStatusSensor(coordinator, entry),
            EightSenseActiveSetSensor(coordinator, entry),
            EightSenseLastUpdateSensor(coordinator, entry),
            EightSenseTopCropSensor(coordinator, entry),
            EightSenseTopCropScoreSensor(coordinator, entry),
        ]
    )

    async_add_entities(entities)


class EightSenseEntity(CoordinatorEntity[EightSenseDataUpdateCoordinator], SensorEntity):
    """Shared entity behavior for 8sense entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EightSenseDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for all 8sense entities."""
        payload = self.coordinator.data.get("device", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer=payload.get("manufacturer"),
            model=payload.get("model"),
            sw_version=payload.get("sw_version"),
            configuration_url=self.coordinator.client.base_url,
        )


class EightSenseMeasurementSensor(EightSenseEntity):
    """Represent one raw soil measurement."""

    def __init__(
        self,
        coordinator: EightSenseDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_key: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{entry.entry_id}_{sensor_key}"

    @property
    def _catalog(self) -> dict[str, Any]:
        return self.coordinator.catalog_by_key.get(self._sensor_key, {})

    @property
    def _entity_data(self) -> dict[str, Any] | None:
        return self.coordinator.entities_by_key.get(self._sensor_key)

    @property
    def name(self) -> str:
        """Return the entity name."""
        return self._catalog.get("name", self._sensor_key.replace("_", " ").title())

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        if not super().available:
            return False
        if not self._catalog.get("enabled", True):
            return False
        return self._entity_data is not None and self.coordinator.data.get("available", False)

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        entity_data = self._entity_data
        if entity_data is None:
            return None
        return entity_data.get("value")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit for the entity."""
        return UNIT_MAP.get(self._catalog.get("unit"), self._catalog.get("unit"))

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return self._catalog.get("icon")

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the Home Assistant device class."""
        return DEVICE_CLASS_MAP.get(self._catalog.get("device_class"))

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class."""
        return STATE_CLASS_MAP.get(self._catalog.get("state_class"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes for the reading."""
        return {
            "status": (self._entity_data or {}).get("status"),
            "default_name": self._catalog.get("default_name"),
            "min": self._catalog.get("min"),
            "max": self._catalog.get("max"),
            "source_index": self._catalog.get("source_index"),
            "active_set": (self.coordinator.data.get("active_set") or {}).get("name"),
        }


class EightSenseStatusSensor(EightSenseEntity):
    """Represent the API status string."""

    _attr_unique_id: str
    _attr_name = "Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator: EightSenseDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("status")


class EightSenseActiveSetSensor(EightSenseEntity):
    """Represent the active sensor set name."""

    _attr_unique_id: str
    _attr_name = "Active set"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:tune-variant"

    def __init__(self, coordinator: EightSenseDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_active_set"

    @property
    def native_value(self) -> str | None:
        active_set = self.coordinator.data.get("active_set") or {}
        return active_set.get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        active_set = self.coordinator.data.get("active_set") or {}
        return {"set_id": active_set.get("id")}


class EightSenseLastUpdateSensor(EightSenseEntity):
    """Represent the time of the last sensor update."""

    _attr_unique_id: str
    _attr_name = "Last update"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: EightSenseDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_update"

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self.coordinator.data.get("last_update") is not None

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.data.get("last_update")
        if not value:
            return None
        parsed = dt_util.parse_datetime(value)
        if parsed is not None:
            return parsed
        return dt_util.as_utc(datetime.fromisoformat(value))


class EightSenseTopCropSensor(EightSenseEntity):
    """Represent the best crop recommendation."""

    _attr_unique_id: str
    _attr_name = "Top crop"
    _attr_icon = "mdi:sprout"

    def __init__(self, coordinator: EightSenseDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_top_crop"

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self.coordinator.data.get("top_crop") is not None

    @property
    def native_value(self) -> str | None:
        top_crop = self.coordinator.data.get("top_crop") or {}
        return top_crop.get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        top_crop = self.coordinator.data.get("top_crop") or {}
        return {
            "rank": top_crop.get("rank"),
            "score": top_crop.get("score"),
            "yield": top_crop.get("yield"),
            "value": top_crop.get("value"),
            "icon": top_crop.get("icon"),
        }


class EightSenseTopCropScoreSensor(EightSenseEntity):
    """Represent the score for the top crop recommendation."""

    _attr_unique_id: str
    _attr_name = "Top crop score"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:chart-line"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EightSenseDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_top_crop_score"

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self.coordinator.data.get("top_crop") is not None

    @property
    def native_value(self) -> Any:
        top_crop = self.coordinator.data.get("top_crop") or {}
        return top_crop.get("score")
