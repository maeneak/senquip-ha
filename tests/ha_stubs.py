"""Minimal Home Assistant stubs for running unit tests without a full HA install.

Only stubs the modules/classes/constants actually imported by the integration code.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from types import ModuleType
from typing import Any


# ---------------------------------------------------------------------------
# homeassistant.components.sensor
# ---------------------------------------------------------------------------

class SensorDeviceClass(str, enum.Enum):
    VOLTAGE = "voltage"
    TEMPERATURE = "temperature"
    ILLUMINANCE = "illuminance"
    SIGNAL_STRENGTH = "signal_strength"
    DURATION = "duration"
    SPEED = "speed"
    VOLUME = "volume"
    PRESSURE = "pressure"
    CURRENT = "current"


class SensorStateClass(str, enum.Enum):
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"
    TOTAL = "total"


class SensorEntity:
    _attr_has_entity_name: bool = False
    _attr_should_poll: bool = True
    _attr_unique_id: str | None = None
    _attr_name: str | None = None
    _attr_device_class: SensorDeviceClass | None = None
    _attr_state_class: SensorStateClass | None = None
    _attr_native_unit_of_measurement: str | None = None
    _attr_entity_category: Any = None
    _attr_icon: str | None = None
    _attr_device_info: Any = None

    @property
    def native_value(self):
        return None


# ---------------------------------------------------------------------------
# homeassistant.const
# ---------------------------------------------------------------------------

DEGREE = "°"
LIGHT_LUX = "lx"
PERCENTAGE = "%"
SIGNAL_STRENGTH_DECIBELS_MILLIWATT = "dBm"


class EntityCategory(str, enum.Enum):
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


class UnitOfElectricPotential(str, enum.Enum):
    VOLT = "V"
    MILLIVOLT = "mV"


class UnitOfSpeed(str, enum.Enum):
    KILOMETERS_PER_HOUR = "km/h"
    MILES_PER_HOUR = "mph"
    METERS_PER_SECOND = "m/s"


class UnitOfTemperature(str, enum.Enum):
    CELSIUS = "°C"
    FAHRENHEIT = "°F"
    KELVIN = "K"


class UnitOfTime(str, enum.Enum):
    HOURS = "h"
    MINUTES = "min"
    SECONDS = "s"
    MILLISECONDS = "ms"


class UnitOfPressure(str, enum.Enum):
    KPA = "kPa"
    BAR = "bar"
    PSI = "psi"


class UnitOfVolume(str, enum.Enum):
    LITERS = "L"
    GALLONS = "gal"


# ---------------------------------------------------------------------------
# homeassistant.helpers
# ---------------------------------------------------------------------------

class DeviceInfo(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class AddEntitiesCallback:
    pass


class StateType:
    pass


# ---------------------------------------------------------------------------
# homeassistant.helpers.update_coordinator
# ---------------------------------------------------------------------------

class DataUpdateCoordinator:
    def __init__(self, hass=None, logger=None, *, name=""):
        self.hass = hass
        self.data = None
        self.name = name

    def async_set_updated_data(self, data):
        self.data = data

    def __class_getitem__(cls, item):
        return cls


class CoordinatorEntity:
    def __init__(self, coordinator, *args, **kwargs):
        self.coordinator = coordinator


# ---------------------------------------------------------------------------
# homeassistant.config_entries
# ---------------------------------------------------------------------------

class ConfigEntry:
    def __init__(self, data=None, entry_id="test_entry"):
        self.data = data or {}
        self.entry_id = entry_id


class ConfigFlow:
    domain: str = ""
    VERSION: int = 1

    def __init_subclass__(cls, *, domain: str = "", **kwargs):
        super().__init_subclass__(**kwargs)
        cls.domain = domain

    def __init__(self):
        self.hass = None

    def async_show_form(self, **kwargs):
        return kwargs

    def async_show_progress(self, **kwargs):
        return kwargs

    def async_show_progress_done(self, **kwargs):
        return kwargs

    def async_create_entry(self, **kwargs):
        return kwargs

    async def async_set_unique_id(self, unique_id):
        pass

    def _abort_if_unique_id_configured(self):
        pass


class OptionsFlow:
    def __init__(self, *args, **kwargs):
        self.hass = None

    def async_show_form(self, **kwargs):
        return kwargs

    def async_show_progress(self, **kwargs):
        return kwargs

    def async_show_progress_done(self, **kwargs):
        return kwargs

    def async_create_entry(self, **kwargs):
        return kwargs


# ---------------------------------------------------------------------------
# homeassistant.core
# ---------------------------------------------------------------------------

def callback(func):
    """Decorator stub — just returns the function."""
    return func


class HomeAssistant:
    pass


# ---------------------------------------------------------------------------
# homeassistant.data_entry_flow
# ---------------------------------------------------------------------------

FlowResult = dict


# ---------------------------------------------------------------------------
# homeassistant.helpers.selector
# ---------------------------------------------------------------------------

class SelectOptionDict(dict):
    def __init__(self, *, value, label):
        super().__init__(value=value, label=label)


class SelectSelectorMode(str, enum.Enum):
    LIST = "list"
    DROPDOWN = "dropdown"


@dataclass
class SelectSelectorConfig:
    options: list = None
    multiple: bool = False
    mode: SelectSelectorMode = SelectSelectorMode.LIST


class SelectSelector:
    def __init__(self, config: SelectSelectorConfig):
        self.config = config


# ---------------------------------------------------------------------------
# homeassistant.components.mqtt
# ---------------------------------------------------------------------------

class _MQTTModels:
    class ReceiveMessage:
        def __init__(self, topic="", payload="", qos=0, retain=False):
            self.topic = topic
            self.payload = payload
            self.qos = qos
            self.retain = retain


mqtt_models = _MQTTModels()
