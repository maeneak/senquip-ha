"""Sensor platform for the Senquip Telemetry integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
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
    CONF_SELECTED_SENSORS,
    DOMAIN,
    KNOWN_INTERNAL_SENSORS,
    SPN_UNIT_TO_HA,
    SensorMeta,
)
from .j1939_database import PGN_DATABASE, SPN_DATABASE, PGNDefinition, SPNDefinition

_LOGGER = logging.getLogger(__name__)


def _resolve_sensor_meta(
    sensor_key: str,
    pgn_database: dict[int, PGNDefinition] | None = None,
    spn_database: dict[int, SPNDefinition] | None = None,
) -> SensorMeta:
    """Determine HA sensor attributes from a sensor key string."""
    pgn_db = pgn_database if pgn_database is not None else PGN_DATABASE
    spn_db = spn_database if spn_database is not None else SPN_DATABASE

    # Internal sensors
    if sensor_key.startswith("internal."):
        json_key = sensor_key.removeprefix("internal.")
        if json_key in KNOWN_INTERNAL_SENSORS:
            return KNOWN_INTERNAL_SENSORS[json_key]
        return SensorMeta(name=json_key.replace("_", " ").title())

    # CAN-decoded SPNs
    if ".spn" in sensor_key:
        parts = sensor_key.split(".")
        spn_str = parts[1]  # "spn190"
        spn_num = int(spn_str.removeprefix("spn"))

        spn_def = spn_db.get(spn_num)
        if spn_def:
            pgn_def = pgn_db.get(spn_def.pgn)
            acronym = pgn_def.acronym if pgn_def else ""
            ha_mapping = SPN_UNIT_TO_HA.get(spn_def.unit)
            if ha_mapping:
                device_class, unit, state_class = ha_mapping
            else:
                device_class, unit, state_class = (
                    None,
                    spn_def.unit if spn_def.unit else None,
                    SensorStateClass.MEASUREMENT,
                )

            name = spn_def.name
            if acronym:
                name = f"{spn_def.name} ({acronym})"

            return SensorMeta(
                name=name,
                device_class=device_class,
                state_class=state_class,
                unit=unit,
            )

        return SensorMeta(name=f"SPN {spn_num}")

    # Raw unknown PGN
    if ".raw." in sensor_key:
        parts = sensor_key.split(".")
        pgn = parts[2]
        return SensorMeta(
            name=f"PGN {pgn} (Raw)",
            state_class=None,
            icon="mdi:numeric",
        )

    # DM1 (Diagnostic Trouble Code) sensors
    if ".dm1." in sensor_key:
        dm1_field = sensor_key.split(".dm1.")[1]
        dm1_meta: dict[str, SensorMeta] = {
            "active_fault": SensorMeta(
                name="DM1 Active Fault",
                state_class=None,
                icon="mdi:engine",
            ),
            "protect_lamp": SensorMeta(
                name="DM1 Protect Lamp",
                state_class=None,
                icon="mdi:alert-circle",
            ),
            "amber_warning": SensorMeta(
                name="DM1 Amber Warning",
                state_class=None,
                icon="mdi:alert",
            ),
            "red_stop": SensorMeta(
                name="DM1 Red Stop",
                state_class=None,
                icon="mdi:alert-octagon",
            ),
            "mil": SensorMeta(
                name="DM1 MIL Lamp",
                state_class=None,
                icon="mdi:engine-outline",
            ),
            "active_spn": SensorMeta(
                name="DM1 Active SPN",
                state_class=None,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:identifier",
            ),
            "active_fmi": SensorMeta(
                name="DM1 Active FMI",
                state_class=None,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:identifier",
            ),
            "occurrence_count": SensorMeta(
                name="DM1 Occurrence Count",
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon="mdi:counter",
            ),
        }
        return dm1_meta.get(
            dm1_field,
            SensorMeta(name=f"DM1 {dm1_field}", state_class=None),
        )

    # Events
    if sensor_key == "events.last":
        return SensorMeta(
            name="Last Event",
            state_class=None,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:alert-circle-outline",
        )

    return SensorMeta(name=sensor_key)


# Port prefixes that get their own sub-device
_PORT_PREFIXES = ("can1.", "can2.")


def _build_device_info(
    sensor_key: str, device_id: str, device_name: str
) -> DeviceInfo:
    """Return DeviceInfo for the base device or a port sub-device."""
    for prefix in _PORT_PREFIXES:
        if sensor_key.startswith(prefix):
            port = prefix.rstrip(".")  # "can1" or "can2"
            port_label = port.upper().replace("CAN", "CAN ")  # "CAN 1"
            return DeviceInfo(
                identifiers={(DOMAIN, f"{device_id}_{port}")},
                name=f"{device_name} {port_label}",
                manufacturer="Senquip",
                via_device=(DOMAIN, device_id),
            )

    # Base device for internal sensors, events, etc.
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
    selected: list[str] = entry.data[CONF_SELECTED_SENSORS]

    entities: list[SenquipSensorEntity] = []
    for sensor_key in selected:
        # Determine which port's decoder to use for metadata resolution
        pgn_db = None
        spn_db = None
        if sensor_key.startswith("can1."):
            decoder = coordinator._decoders.get("can1")
            if decoder:
                pgn_db = decoder._pgn_db
                spn_db = decoder._spn_db
        elif sensor_key.startswith("can2."):
            decoder = coordinator._decoders.get("can2")
            if decoder:
                pgn_db = decoder._pgn_db
                spn_db = decoder._spn_db

        meta = _resolve_sensor_meta(
            sensor_key,
            pgn_database=pgn_db,
            spn_database=spn_db,
        )
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
        coordinator: Any,
        sensor_key: str,
        sensor_meta: SensorMeta,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key

        # Entity attributes
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

        # Device grouping — assign to base device or port sub-device
        self._attr_device_info = _build_device_info(
            sensor_key, device_id, device_name
        )

    @property
    def native_value(self) -> StateType:
        """Return the current sensor value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._sensor_key)
