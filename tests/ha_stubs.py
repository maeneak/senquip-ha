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
    ENUM = "enum"
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
# homeassistant.components.binary_sensor
# ---------------------------------------------------------------------------

class BinarySensorDeviceClass(str, enum.Enum):
    CONNECTIVITY = "connectivity"
    RUNNING = "running"
    BATTERY = "battery"
    MOTION = "motion"


class BinarySensorEntity:
    _attr_has_entity_name: bool = False
    _attr_unique_id: str | None = None
    _attr_name: str | None = None
    _attr_device_class: BinarySensorDeviceClass | None = None
    _attr_entity_category: Any = None
    _attr_device_info: Any = None

    @property
    def is_on(self) -> bool | None:
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


class DeviceRegistry:
    """Stub device registry; ``devices`` maps device id to a device object."""

    def __init__(self):
        self.devices = {}

    def async_get(self, device_id):
        return self.devices.get(device_id)


DEVICE_REGISTRY = DeviceRegistry()


def device_registry_async_get(hass):
    return DEVICE_REGISTRY


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
        self.state_writes = 0

    def _handle_coordinator_update(self):
        self.async_write_ha_state()

    def async_write_ha_state(self):
        self.state_writes += 1


# ---------------------------------------------------------------------------
# homeassistant.helpers.restore_state
# ---------------------------------------------------------------------------

class ExtraStoredData:
    def as_dict(self):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# homeassistant.helpers.storage
# ---------------------------------------------------------------------------

class Store:
    """In-memory stand-in for HA's Store. ``Store.saved`` is shared across instances."""

    saved: dict[str, Any] = {}

    def __init__(self, hass, version, key, **kwargs):
        self.key = key
        self.version = version
        self.kwargs = kwargs
        self.save_calls = 0
        self._pending = None

    async def async_load(self):
        return Store.saved.get(self.key)

    def async_delay_save(self, data_func, delay=0):
        """Like HA, ``data_func`` is only called when the write happens (``flush``)."""
        self.save_calls += 1
        self._pending = data_func

    def flush(self):
        """Run a pending delayed save, as HA's timer would."""
        if self._pending is not None:
            Store.saved[self.key] = self._pending()
            self._pending = None

    async def async_save(self, data):
        self._pending = None
        Store.saved[self.key] = data

    async def async_remove(self):
        Store.saved.pop(self.key, None)


class RestoreEntity:
    """Stub — set ``_stub_last_extra_data`` on an instance to simulate a restore."""

    _stub_last_extra_data = None

    async def async_added_to_hass(self):
        pass

    async def async_will_remove_from_hass(self):
        pass

    async def async_get_last_extra_data(self):
        return self._stub_last_extra_data


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


# ---------------------------------------------------------------------------
# homeassistant.helpers.event
# ---------------------------------------------------------------------------

def async_call_later(hass, delay, callback):
    """Stub — returns a cancel callback. Does not actually schedule."""
    def cancel():
        pass
    return cancel
