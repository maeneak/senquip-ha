"""Constants for the Senquip Telemetry integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
PLATFORMS = ["sensor", "binary_sensor"]

CONF_MQTT_TOPIC = "mqtt_topic"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_SELECTED_SIGNALS = "selected_signals"
CONF_PORT_CONFIGS = "port_configs"

DEVICE_TIMEOUT = 30

DISCOVERY_TIMEOUT = 60

# Fraction threshold below which a TOTAL_INCREASING sensor drop is treated as
# a legitimate meter reset rather than a noisy regression (mirrors HA behaviour).
TOTAL_INCREASING_REGRESSION_TOLERANCE = 0.9

# Maximum number of CAN frames included per port in diagnostics output.
DIAGNOSTICS_MAX_FRAMES = 50

CAN_PROFILE_DIR = "can_profiles"
CAN_PROTOCOL_J1939 = "j1939"

KNOWN_PORT_FAMILIES: dict[str, str] = {
    "internal": "internal",
    "can1": "can",
    "can2": "can",
    "serial1": "serial",
    "input1": "io_input",
    "input2": "io_input",
    "output1": "io_output",
    "current1": "io_current",
    "current2": "io_current",
    "ble": "ble",
    "gps": "gps",
}

CAN_PORTS: tuple[str, ...] = ("can1", "can2")

PORT_DISPLAY_NAMES: dict[str, str] = {
    "can1": "CAN 1",
    "can2": "CAN 2",
    "serial1": "Serial 1",
    "input1": "Input 1",
    "input2": "Input 2",
    "output1": "Output 1",
    "current1": "Current 1",
    "current2": "Current 2",
    "ble": "BLE",
    "gps": "GPS",
    "internal": "Internal",
}


@dataclass(frozen=True)
class PortConfig:
    """Saved config for a logical Senquip port."""

    family: str
    active: bool
    protocol: str | None = None
    profiles: tuple[str, ...] = ()


def build_default_port_configs(
    active_overrides: dict[str, bool] | None = None,
) -> dict[str, PortConfig]:
    """Build default port config for all known port families."""
    active_overrides = active_overrides or {}
    configs: dict[str, PortConfig] = {}
    for port_id, family in KNOWN_PORT_FAMILIES.items():
        is_active = bool(active_overrides.get(port_id, False))
        protocol: str | None = CAN_PROTOCOL_J1939 if family == "can" else None
        configs[port_id] = PortConfig(
            family=family,
            active=is_active,
            protocol=protocol,
            profiles=(),
        )
    return configs


def serialize_port_configs(configs: dict[str, PortConfig]) -> dict[str, dict[str, Any]]:
    """Convert PortConfig objects to config-entry serializable dictionaries."""
    serialized: dict[str, dict[str, Any]] = {}
    for port_id, cfg in configs.items():
        serialized[port_id] = {
            "family": cfg.family,
            "active": cfg.active,
            "protocol": cfg.protocol,
            "profiles": list(cfg.profiles),
        }
    return serialized


def deserialize_port_configs(raw: Any) -> dict[str, PortConfig]:
    """Parse stored port configuration dictionaries."""
    configs = build_default_port_configs()
    if not isinstance(raw, dict):
        return configs

    for port_id, payload in raw.items():
        if port_id not in KNOWN_PORT_FAMILIES or not isinstance(payload, dict):
            continue
        family = payload.get("family", KNOWN_PORT_FAMILIES[port_id])
        active = bool(payload.get("active", False))
        protocol_raw = payload.get("protocol")
        protocol = str(protocol_raw) if protocol_raw is not None else None
        profiles_raw = payload.get("profiles", [])
        if isinstance(profiles_raw, list):
            profiles = tuple(str(item) for item in profiles_raw)
        else:
            profiles = ()
        configs[port_id] = PortConfig(
            family=str(family),
            active=active,
            protocol=protocol,
            profiles=profiles,
        )
    return configs


@dataclass(frozen=True)
class SensorMeta:
    """Metadata for a known sensor type."""

    name: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    unit: str | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None
    options: list[str] | None = None


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
    "angle": SensorMeta(name="Tilt Angle", unit=DEGREE, icon="mdi:angle-acute"),
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


SPN_STATE_CLASS_OVERRIDES: dict[int, SensorStateClass] = {
    182: SensorStateClass.TOTAL,  # Engine Trip Fuel — resets each power cycle
    961: SensorStateClass.MEASUREMENT,  # Hours (Time/Date) — hour-of-day, not cumulative
}


SPN_UNIT_TO_HA: dict[str, tuple[SensorDeviceClass | None, str | None, SensorStateClass]] = {
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

