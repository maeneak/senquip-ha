"""Constants for the Senquip Telemetry integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)

DOMAIN = "senquip"
PLATFORMS = ["sensor"]

# Config entry data keys
CONF_MQTT_TOPIC = "mqtt_topic"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_SELECTED_SENSORS = "selected_sensors"

# Discovery timeout in seconds
DISCOVERY_TIMEOUT = 60


@dataclass(frozen=True)
class SensorMeta:
    """Metadata for a known sensor type."""

    name: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    unit: str | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None


# Metadata for known internal/flat JSON keys
KNOWN_INTERNAL_SENSORS: dict[str, SensorMeta] = {
    "vsys": SensorMeta(
        name="System Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "vin": SensorMeta(
        name="Input Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
    ),
    "ambient": SensorMeta(
        name="Ambient Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        unit=UnitOfTemperature.CELSIUS,
    ),
    "light": SensorMeta(
        name="Light Level",
        device_class=SensorDeviceClass.ILLUMINANCE,
        unit=LIGHT_LUX,
    ),
    "accel_x": SensorMeta(name="Acceleration X", unit="g", icon="mdi:axis-x-arrow"),
    "accel_y": SensorMeta(name="Acceleration Y", unit="g", icon="mdi:axis-y-arrow"),
    "accel_z": SensorMeta(name="Acceleration Z", unit="g", icon="mdi:axis-z-arrow"),
    "roll": SensorMeta(name="Roll", unit=DEGREE, icon="mdi:rotate-3d-variant"),
    "pitch": SensorMeta(name="Pitch", unit=DEGREE, icon="mdi:rotate-3d-variant"),
    "angle": SensorMeta(
        name="Tilt Angle", unit=DEGREE, icon="mdi:angle-acute"
    ),
    "movement_hrs": SensorMeta(
        name="Movement Hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit=UnitOfTime.HOURS,
    ),
    "motion": SensorMeta(
        name="Motion Count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:motion-sensor",
    ),
    "wifi_rssi": SensorMeta(
        name="WiFi Signal Strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "wifi_ip": SensorMeta(
        name="WiFi IP Address",
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:ip-network",
    ),
    "state": SensorMeta(
        name="Device State",
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
    ),
    "analog1": SensorMeta(
        name="Analog Input 1",
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
    ),
    "analog2": SensorMeta(
        name="Analog Input 2",
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
    ),
    "current1": SensorMeta(
        name="Current Input 1",
        device_class=SensorDeviceClass.CURRENT,
        unit="mA",
    ),
    "current2": SensorMeta(
        name="Current Input 2",
        device_class=SensorDeviceClass.CURRENT,
        unit="mA",
    ),
    "pulse1": SensorMeta(
        name="Pulse Count 1",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:pulse",
    ),
    "pulse2": SensorMeta(
        name="Pulse Count 2",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:pulse",
    ),
    "din": SensorMeta(
        name="Digital Input",
        state_class=None,
        icon="mdi:electric-switch",
    ),
}


# Map J1939 SPN unit strings to HA (device_class, unit, state_class)
SPN_UNIT_TO_HA: dict[
    str, tuple[SensorDeviceClass | None, str | None, SensorStateClass]
] = {
    "rpm": (None, "rpm", SensorStateClass.MEASUREMENT),
    "deg C": (
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    "km/h": (
        SensorDeviceClass.SPEED,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        SensorStateClass.MEASUREMENT,
    ),
    "h": (
        SensorDeviceClass.DURATION,
        UnitOfTime.HOURS,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "L": (
        SensorDeviceClass.VOLUME,
        UnitOfVolume.LITERS,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "V": (
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
        SensorStateClass.MEASUREMENT,
    ),
    "kPa": (
        SensorDeviceClass.PRESSURE,
        UnitOfPressure.KPA,
        SensorStateClass.MEASUREMENT,
    ),
    "%": (None, PERCENTAGE, SensorStateClass.MEASUREMENT),
    "s": (None, UnitOfTime.SECONDS, SensorStateClass.MEASUREMENT),
    "min": (None, UnitOfTime.MINUTES, SensorStateClass.MEASUREMENT),
    "rev": (None, "rev", SensorStateClass.TOTAL_INCREASING),
    "day": (None, "day", SensorStateClass.MEASUREMENT),
    "month": (None, None, SensorStateClass.MEASUREMENT),
    "year": (None, None, SensorStateClass.MEASUREMENT),
    "L/h": (None, "L/h", SensorStateClass.MEASUREMENT),
    "km/L": (None, "km/L", SensorStateClass.MEASUREMENT),
    "A": (
        SensorDeviceClass.CURRENT,
        "A",
        SensorStateClass.MEASUREMENT,
    ),
}
