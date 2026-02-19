"""Sensor platform for the Senquip Telemetry integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import SenquipDataCoordinator

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_SELECTED_SIGNALS,
    DOMAIN,
    KNOWN_INTERNAL_SENSORS,
    PORT_DISPLAY_NAMES,
    SensorMeta,
)

_LOGGER = logging.getLogger(__name__)

def _resolve_sensor_meta(sensor_key: str, coordinator: SenquipDataCoordinator) -> SensorMeta:
    """Determine HA sensor attributes from a canonical signal key."""
    if sensor_key.startswith("internal.main."):
        json_key = sensor_key.removeprefix("internal.main.")
        if json_key in KNOWN_INTERNAL_SENSORS:
            return KNOWN_INTERNAL_SENSORS[json_key]
        return SensorMeta(name=json_key.replace("_", " ").title())

    if sensor_key == "event.main.last":
        return SensorMeta(
            name="Last Event",
            state_class=None,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:alert-circle-outline",
        )

    if sensor_key.startswith("can."):
        parts = sensor_key.split(".")
        if len(parts) < 4:
            return SensorMeta(name=sensor_key, state_class=None)
        port_id = parts[1]
        runtime = coordinator.get_can_runtime(port_id)
        if runtime is None:
            return SensorMeta(name=sensor_key, state_class=None)
        protocol, decoder = runtime
        return protocol.resolve_signal_meta(sensor_key, decoder)

    return SensorMeta(name=sensor_key)


def _build_device_info(
    sensor_key: str,
    device_id: str,
    device_name: str,
) -> DeviceInfo:
    """Return DeviceInfo for the base device or a port sub-device."""
    parts = sensor_key.split(".")

    if len(parts) >= 2:
        category = parts[0]
        port_id = parts[1]

        if category == "can" and port_id in PORT_DISPLAY_NAMES:
            return DeviceInfo(
                identifiers={(DOMAIN, f"{device_id}_{port_id}")},
                name=device_name,
                model=PORT_DISPLAY_NAMES[port_id],
                manufacturer="Senquip",
                via_device=(DOMAIN, device_id),
            )

        if category == "internal" and port_id == "main":
            return DeviceInfo(
                identifiers={(DOMAIN, device_id)},
                name=device_name,
                manufacturer="Senquip",
                model="QUAD-C2",
            )

        if port_id in PORT_DISPLAY_NAMES and port_id != "internal":
            return DeviceInfo(
                identifiers={(DOMAIN, f"{device_id}_{port_id}")},
                name=device_name,
                model=PORT_DISPLAY_NAMES[port_id],
                manufacturer="Senquip",
                via_device=(DOMAIN, device_id),
            )

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer="Senquip",
        model="QUAD-C2",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Senquip sensor entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_id: str = entry.data[CONF_DEVICE_ID]
    device_name: str = entry.data[CONF_DEVICE_NAME]
    selected: list[str] = entry.data[CONF_SELECTED_SIGNALS]

    entities: list[SenquipSensorEntity] = []
    for sensor_key in selected:
        meta = _resolve_sensor_meta(sensor_key, coordinator)
        entities.append(
            SenquipSensorEntity(
                coordinator=coordinator,
                sensor_key=sensor_key,
                sensor_meta=meta,
                device_id=device_id,
                device_name=device_name,
            )
        )

    if entities:
        async_add_entities(entities)


class SenquipSensorEntity(CoordinatorEntity, SensorEntity):
    """A single sensor value from a Senquip telemetry device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SenquipDataCoordinator,
        sensor_key: str,
        sensor_meta: SensorMeta,
        device_id: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_name = sensor_meta.name

        if sensor_meta.device_class is not None:
            self._attr_device_class = sensor_meta.device_class
        if sensor_meta.state_class is not None:
            self._attr_state_class = sensor_meta.state_class
        if sensor_meta.unit is not None:
            self._attr_native_unit_of_measurement = sensor_meta.unit
        if sensor_meta.entity_category is not None:
            self._attr_entity_category = sensor_meta.entity_category
        if sensor_meta.icon is not None:
            self._attr_icon = sensor_meta.icon
        if sensor_meta.options is not None:
            self._attr_options = sensor_meta.options

        self._attr_device_info = _build_device_info(sensor_key, device_id, device_name)

    @property
    def available(self) -> bool:
        """Return whether the sensor is available."""
        if not self.coordinator.is_device_online():
            return False
        if self._sensor_key.startswith("can."):
            parts = self._sensor_key.split(".")
            if len(parts) >= 2:
                port_id = parts[1]
                if not self.coordinator.is_can_port_available(port_id):
                    return False
        return True

    @property
    def native_value(self) -> StateType:
        """Return current sensor value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._sensor_key)

