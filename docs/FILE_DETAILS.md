# File Details

Detailed specification for each file in `custom_components/senquip/`.

---

## `manifest.json`

```json
{
    "domain": "senquip",
    "name": "Senquip Telemetry",
    "codeowners": [],
    "config_flow": true,
    "dependencies": ["mqtt"],
    "documentation": "https://docs.senquip.com/quad-c2-user-guide/",
    "iot_class": "local_push",
    "version": "1.0.0"
}
```

- `"dependencies": ["mqtt"]` — ensures HA's MQTT integration loads first
- `"config_flow": true` — enables UI-based setup
- `"iot_class": "local_push"` — device pushes data via MQTT (no polling)

---

## `const.py`

Central constants and sensor metadata definitions.

```python
from dataclasses import dataclass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfPressure,
    UnitOfVolume,
)

DOMAIN = "senquip"
PLATFORMS = ["sensor"]

# Config entry data keys
CONF_MQTT_TOPIC = "mqtt_topic"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_SELECTED_SENSORS = "selected_sensors"


@dataclass(frozen=True)
class SensorMeta:
    """Metadata for a known sensor type."""
    name: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT
    unit: str | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None


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
        state_class=None,  # Not a measurement
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:ip-network",
    ),
    "state": SensorMeta(
        name="Device State",
        state_class=None,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
    ),
    # Analog inputs (for General IO port — future use)
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


# Map J1939 SPN units to HA device class and unit
SPN_UNIT_TO_HA: dict[str, tuple[SensorDeviceClass | None, str | None, SensorStateClass]] = {
    "rpm": (None, "rpm", SensorStateClass.MEASUREMENT),
    "deg C": (SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS, SensorStateClass.MEASUREMENT),
    "km/h": (SensorDeviceClass.SPEED, UnitOfSpeed.KILOMETERS_PER_HOUR, SensorStateClass.MEASUREMENT),
    "h": (SensorDeviceClass.DURATION, UnitOfTime.HOURS, SensorStateClass.TOTAL_INCREASING),
    "L": (SensorDeviceClass.VOLUME, UnitOfVolume.LITERS, SensorStateClass.TOTAL_INCREASING),
    "V": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT, SensorStateClass.MEASUREMENT),
    "kPa": (SensorDeviceClass.PRESSURE, UnitOfPressure.KPA, SensorStateClass.MEASUREMENT),
    "%": (None, PERCENTAGE, SensorStateClass.MEASUREMENT),
    "s": (None, UnitOfTime.SECONDS, SensorStateClass.MEASUREMENT),
    "min": (None, UnitOfTime.MINUTES, SensorStateClass.MEASUREMENT),
    "rev": (None, "rev", SensorStateClass.TOTAL_INCREASING),
    "day": (None, "day", SensorStateClass.MEASUREMENT),
    "month": (None, None, SensorStateClass.MEASUREMENT),
    "year": (None, None, SensorStateClass.MEASUREMENT),
}
```

---

## `__init__.py`

Integration entry point with data coordinator.

### Responsibilities:
1. `async_setup_entry`: Create coordinator, subscribe to MQTT, forward to sensor platform
2. `async_unload_entry`: Unsubscribe from MQTT, clean up
3. `SenquipDataCoordinator`: Central class that receives MQTT messages, parses JSON, decodes CAN, distributes data

### SenquipDataCoordinator

```python
class SenquipDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate MQTT data for a single Senquip device."""

    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=f"Senquip {entry.data[CONF_DEVICE_ID]}")
        self._entry = entry
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._selected = set(entry.data[CONF_SELECTED_SENSORS])
        self._decoder = J1939Decoder()
        self._unsubscribe = None

    async def async_subscribe(self):
        await mqtt.async_wait_for_mqtt_client(self.hass)
        self._unsubscribe = await mqtt.async_subscribe(
            self.hass, self._entry.data[CONF_MQTT_TOPIC],
            self._handle_message, qos=0,
        )

    async def async_unsubscribe(self):
        if self._unsubscribe:
            self._unsubscribe()

    @callback
    def _handle_message(self, msg):
        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, ValueError):
            return
        data = self._parse_payload(payload)
        self.async_set_updated_data(data)

    def _parse_payload(self, payload: dict) -> dict[str, Any]:
        data = {}
        for key, value in payload.items():
            if key in ("deviceid", "ts", "time"):
                continue

            if key in ("can1", "can2") and isinstance(value, list):
                for frame in value:
                    can_id = frame.get("id")
                    hex_data = frame.get("data")
                    if can_id is None or hex_data is None:
                        continue
                    decoded = self._decoder.decode_frame(can_id, hex_data)
                    for spn_num, spn_value in decoded.items():
                        sensor_key = f"{key}.spn{spn_num}"
                        if sensor_key in self._selected:
                            data[sensor_key] = spn_value
                    # Handle raw unknown PGNs
                    if not decoded:
                        _, pgn, _ = self._decoder.extract_pgn(can_id)
                        raw_key = f"{key}.raw.{pgn}"
                        if raw_key in self._selected:
                            data[raw_key] = hex_data

            elif key == "events" and isinstance(value, list):
                if "events.last" in self._selected and value:
                    data["events.last"] = value[-1].get("msg", "")

            elif key.startswith("cp") and key[2:].isdigit():
                sensor_key = f"custom.{key}"
                if sensor_key in self._selected:
                    data[sensor_key] = value

            else:
                sensor_key = f"internal.{key}"
                if sensor_key in self._selected:
                    data[sensor_key] = value

        return data
```

### Entry Setup/Teardown

```python
async def async_setup_entry(hass, entry):
    coordinator = SenquipDataCoordinator(hass, entry)
    await coordinator.async_subscribe()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass, entry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_unsubscribe()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
```

---

## `sensor.py`

Entity creation and state management.

### `async_setup_entry`

Creates one `SenquipSensorEntity` per selected sensor key:

```python
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]
    device_name = entry.data[CONF_DEVICE_NAME]
    selected = entry.data[CONF_SELECTED_SENSORS]

    entities = []
    for sensor_key in selected:
        meta = _resolve_sensor_meta(sensor_key)
        entities.append(SenquipSensorEntity(
            coordinator, sensor_key, meta, device_id, device_name,
        ))

    async_add_entities(entities)
```

### `_resolve_sensor_meta`

Determines HA sensor attributes from the sensor key:

```python
def _resolve_sensor_meta(sensor_key: str) -> SensorMeta:
    if sensor_key.startswith("internal."):
        json_key = sensor_key.removeprefix("internal.")
        if json_key in KNOWN_INTERNAL_SENSORS:
            return KNOWN_INTERNAL_SENSORS[json_key]
        return SensorMeta(name=json_key.replace("_", " ").title())

    if sensor_key.startswith(("can1.spn", "can2.spn")):
        port = sensor_key.split(".")[0]
        spn_num = int(sensor_key.split("spn")[1])
        spn_def = SPN_DATABASE.get(spn_num)
        if spn_def:
            pgn_def = PGN_DATABASE.get(spn_def.pgn)
            acronym = pgn_def.acronym if pgn_def else ""
            ha_class, ha_unit, state_class = SPN_UNIT_TO_HA.get(
                spn_def.unit, (None, spn_def.unit, SensorStateClass.MEASUREMENT)
            )
            return SensorMeta(
                name=f"{port.upper()} {spn_def.name}",
                device_class=ha_class,
                state_class=state_class,
                unit=ha_unit,
            )
        return SensorMeta(name=f"{port.upper()} SPN {spn_num}")

    if sensor_key.startswith(("can1.raw.", "can2.raw.")):
        port = sensor_key.split(".")[0]
        pgn = sensor_key.split("raw.")[1]
        return SensorMeta(
            name=f"{port.upper()} PGN {pgn} (Raw)",
            state_class=None,
            icon="mdi:numeric",
        )

    if sensor_key.startswith("custom.cp"):
        num = sensor_key.removeprefix("custom.cp")
        return SensorMeta(
            name=f"Custom Parameter {num}",
            icon="mdi:numeric",
        )

    if sensor_key == "events.last":
        return SensorMeta(
            name="Last Event",
            state_class=None,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:alert-circle-outline",
        )

    return SensorMeta(name=sensor_key)
```

### `SenquipSensorEntity`

```python
class SenquipSensorEntity(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, sensor_key, meta, device_id, device_name):
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_name = meta.name
        self._attr_device_class = meta.device_class
        self._attr_state_class = meta.state_class
        self._attr_native_unit_of_measurement = meta.unit
        self._attr_entity_category = meta.entity_category
        self._attr_icon = meta.icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Senquip",
            model="QUAD-C2",
        )

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._sensor_key)
```

---

## `config_flow.py`

See [CONFIG_FLOW.md](CONFIG_FLOW.md) for the full specification.

---

## `j1939_decoder.py` and `j1939_database.py`

See [J1939_DECODER.md](J1939_DECODER.md) for the full specification.

---

## `strings.json`

```json
{
    "config": {
        "flow_title": "Senquip {device_name}",
        "step": {
            "user": {
                "title": "Configure Senquip Device",
                "description": "Enter the device name and the MQTT topic it publishes to.",
                "data": {
                    "device_name": "Device Name",
                    "mqtt_topic": "MQTT Topic"
                },
                "data_description": {
                    "device_name": "A friendly name for this device",
                    "mqtt_topic": "The MQTT topic this device publishes telemetry to"
                }
            },
            "discover": {
                "title": "Discovering Sensors"
            },
            "select_sensors": {
                "title": "Select Sensors",
                "description": "Found {sensor_count} sensors on device {device_id}. Select which sensors to create as Home Assistant entities.",
                "data": {
                    "selected_sensors": "Sensors"
                }
            },
            "discovery_failed": {
                "title": "Discovery Failed",
                "description": "No data received within 60 seconds. Ensure the device is powered on and publishing to the specified MQTT topic.",
                "data": {}
            }
        },
        "progress": {
            "discovering": "Waiting for data from the device..."
        },
        "abort": {
            "already_configured": "This device is already configured."
        }
    }
}
```

## `translations/en.json`

Mirrors `strings.json` exactly (HA uses this for runtime translations).
