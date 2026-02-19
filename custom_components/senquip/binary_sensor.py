"""Binary sensor platform for the Senquip Telemetry integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import SenquipDataCoordinator

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PORT_CONFIGS,
    DOMAIN,
    PORT_DISPLAY_NAMES,
    deserialize_port_configs,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Senquip connectivity binary sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_id: str = entry.data[CONF_DEVICE_ID]
    device_name: str = entry.data[CONF_DEVICE_NAME]
    port_configs = deserialize_port_configs(entry.data.get(CONF_PORT_CONFIGS))

    entities: list[BinarySensorEntity] = [
        SenquipDeviceConnectivitySensor(coordinator, device_id, device_name),
    ]

    for port_id, config in port_configs.items():
        if config.family == "can" and config.active:
            entities.append(
                SenquipCANPortConnectivitySensor(
                    coordinator, device_id, device_name, port_id
                )
            )
            entities.append(
                SenquipCANDeviceActiveSensor(
                    coordinator, device_id, device_name, port_id
                )
            )

    async_add_entities(entities)


class SenquipDeviceConnectivitySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor showing whether the Senquip device is online."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SenquipDataCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{device_id}_connectivity"
        self._attr_name = "Connectivity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Senquip",
            model="QUAD-C2",
        )

    @property
    def is_on(self) -> bool:
        """Return True if the device is online."""
        return self.coordinator.is_device_online()


class SenquipCANPortConnectivitySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor showing whether a CAN bus port is online."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SenquipDataCoordinator,
        device_id: str,
        device_name: str,
        port_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._port_id = port_id
        self._attr_unique_id = f"{device_id}_{port_id}_connectivity"
        self._attr_name = "Connectivity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device_id}_{port_id}")},
            name=device_name,
            model=PORT_DISPLAY_NAMES.get(port_id, port_id),
            manufacturer="Senquip",
            via_device=(DOMAIN, device_id),
        )

    @property
    def is_on(self) -> bool:
        """Return True if the device is online and the CAN port has data."""
        return (
            self.coordinator.is_device_online()
            and self.coordinator.is_can_port_available(self._port_id)
        )


class SenquipCANDeviceActiveSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor showing whether a CAN-connected device is active.

    Unlike the connectivity sensor (diagnostic), this has no entity_category
    so it appears in dashboards by default — useful for overlaying operating
    windows on history graphs.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: Any,
        device_id: str,
        device_name: str,
        port_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._port_id = port_id
        self._attr_unique_id = f"{device_id}_{port_id}_device_active"
        self._attr_name = "Device Active"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device_id}_{port_id}")},
            name=device_name,
            model=PORT_DISPLAY_NAMES.get(port_id, port_id),
            manufacturer="Senquip",
            via_device=(DOMAIN, device_id),
        )

    @property
    def is_on(self) -> bool:
        """Return True if the CAN-connected device is actively transmitting."""
        return (
            self.coordinator.is_device_online()
            and self.coordinator.is_can_port_available(self._port_id)
        )
