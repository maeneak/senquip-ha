"""Conftest providing sys.path setup and HA stubs for standalone test execution."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

# Ensure the repo root is on sys.path so `custom_components.senquip` resolves
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Install minimal HA stubs so our integration modules can be imported
# without a full Home Assistant installation.
# ---------------------------------------------------------------------------

from tests import ha_stubs  # noqa: E402

# Build the module tree that the integration imports from
_ha = ModuleType("homeassistant")
_ha.__path__ = []

# homeassistant.const
_ha_const = ModuleType("homeassistant.const")
for name in (
    "DEGREE", "LIGHT_LUX", "PERCENTAGE", "SIGNAL_STRENGTH_DECIBELS_MILLIWATT",
    "EntityCategory", "UnitOfElectricPotential", "UnitOfSpeed",
    "UnitOfTemperature", "UnitOfTime", "UnitOfPressure", "UnitOfVolume",
):
    setattr(_ha_const, name, getattr(ha_stubs, name))

# homeassistant.core
_ha_core = ModuleType("homeassistant.core")
_ha_core.HomeAssistant = ha_stubs.HomeAssistant
_ha_core.callback = ha_stubs.callback

# homeassistant.components
_ha_components = ModuleType("homeassistant.components")
_ha_components.__path__ = []

# homeassistant.components.mqtt
_ha_mqtt = ModuleType("homeassistant.components.mqtt")
_ha_mqtt.async_subscribe = MagicMock()
_ha_mqtt.async_wait_for_mqtt_client = MagicMock()
_ha_mqtt.models = ha_stubs.mqtt_models
_ha_mqtt_models = ModuleType("homeassistant.components.mqtt.models")
_ha_mqtt_models.ReceiveMessage = ha_stubs._MQTTModels.ReceiveMessage

# homeassistant.components.sensor
_ha_sensor = ModuleType("homeassistant.components.sensor")
_ha_sensor.SensorDeviceClass = ha_stubs.SensorDeviceClass
_ha_sensor.SensorStateClass = ha_stubs.SensorStateClass
_ha_sensor.SensorEntity = ha_stubs.SensorEntity

# homeassistant.config_entries
_ha_config_entries = ModuleType("homeassistant.config_entries")
_ha_config_entries.ConfigEntry = ha_stubs.ConfigEntry
_ha_config_entries.ConfigFlow = ha_stubs.ConfigFlow
_ha_config_entries.OptionsFlow = ha_stubs.OptionsFlow

# homeassistant.data_entry_flow
_ha_flow = ModuleType("homeassistant.data_entry_flow")
_ha_flow.FlowResult = ha_stubs.FlowResult

# homeassistant.helpers
_ha_helpers = ModuleType("homeassistant.helpers")
_ha_helpers.__path__ = []

_ha_helpers_selector = ModuleType("homeassistant.helpers.selector")
_ha_helpers_selector.SelectOptionDict = ha_stubs.SelectOptionDict
_ha_helpers_selector.SelectSelector = ha_stubs.SelectSelector
_ha_helpers_selector.SelectSelectorConfig = ha_stubs.SelectSelectorConfig
_ha_helpers_selector.SelectSelectorMode = ha_stubs.SelectSelectorMode

_ha_helpers_coordinator = ModuleType("homeassistant.helpers.update_coordinator")
_ha_helpers_coordinator.DataUpdateCoordinator = ha_stubs.DataUpdateCoordinator
_ha_helpers_coordinator.CoordinatorEntity = ha_stubs.CoordinatorEntity

_ha_helpers_device = ModuleType("homeassistant.helpers.device_registry")
_ha_helpers_device.DeviceInfo = ha_stubs.DeviceInfo

_ha_helpers_platform = ModuleType("homeassistant.helpers.entity_platform")
_ha_helpers_platform.AddEntitiesCallback = ha_stubs.AddEntitiesCallback

_ha_helpers_typing = ModuleType("homeassistant.helpers.typing")
_ha_helpers_typing.StateType = ha_stubs.StateType

# voluptuous stub
_vol = MagicMock()
_vol.Schema = lambda x: x
_vol.Required = lambda key, **kw: key

# Register all modules
sys.modules.update({
    "homeassistant": _ha,
    "homeassistant.const": _ha_const,
    "homeassistant.core": _ha_core,
    "homeassistant.components": _ha_components,
    "homeassistant.components.mqtt": _ha_mqtt,
    "homeassistant.components.mqtt.models": _ha_mqtt_models,
    "homeassistant.components.sensor": _ha_sensor,
    "homeassistant.config_entries": _ha_config_entries,
    "homeassistant.data_entry_flow": _ha_flow,
    "homeassistant.helpers": _ha_helpers,
    "homeassistant.helpers.selector": _ha_helpers_selector,
    "homeassistant.helpers.update_coordinator": _ha_helpers_coordinator,
    "homeassistant.helpers.device_registry": _ha_helpers_device,
    "homeassistant.helpers.entity_platform": _ha_helpers_platform,
    "homeassistant.helpers.typing": _ha_helpers_typing,
    "voluptuous": _vol,
})
