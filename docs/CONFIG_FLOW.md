# Config Flow Specification

## Overview

The integration uses a multi-step UI config flow with MQTT-based discovery. The user provides a topic, the integration listens for a message, analyzes it, and presents discovered sensors for selection.

---

## Step 1: `async_step_user` — Device Configuration

**Purpose:** Collect device name and MQTT topic.

**Form schema:**
```python
vol.Schema({
    vol.Required("device_name"): str,
    vol.Required("mqtt_topic"): str,
})
```

**Fields:**
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `device_name` | string | Human-readable name for the device | "Excavator CAT 320" |
| `mqtt_topic` | string | MQTT topic this device publishes to | "senquip/HE8EV12LF/data" |

**Validation:**
- Topic must not be empty
- No uniqueness check yet (device ID is unknown until discovery)

**On submit:** Store values in `self._device_name` and `self._mqtt_topic`, transition to `async_step_discover`.

---

## Step 2: `async_step_discover` — MQTT Discovery

**Purpose:** Subscribe to the MQTT topic, wait for the first message, parse it, and discover available sensors.

**UI:** Progress spinner with message "Waiting for data from the device..."

**Pattern:** Uses `async_show_progress` / `async_show_progress_done`:

```python
async def async_step_discover(self, user_input=None):
    if self._discovery_task is None:
        self._discovery_task = self.hass.async_create_task(
            self._async_discover_sensors()
        )

    if not self._discovery_task.done():
        return self.async_show_progress(
            step_id="discover",
            progress_action="discovering",
            progress_task=self._discovery_task,
        )

    try:
        await self._discovery_task
    except (TimeoutError, Exception):
        return self.async_show_progress_done(next_step_id="discovery_failed")

    return self.async_show_progress_done(next_step_id="select_sensors")
```

### Discovery Task (`_async_discover_sensors`)

1. `await mqtt.async_wait_for_mqtt_client(self.hass)` — ensure MQTT broker is connected
2. Create `asyncio.Event` for message receipt
3. `mqtt.async_subscribe(self.hass, topic, callback)` — subscribe with callback that:
   - Parses JSON payload
   - Stores parsed data
   - Sets the event
4. `await asyncio.wait_for(event.wait(), timeout=60)` — wait up to 60 seconds
5. Unsubscribe from topic
6. Extract `deviceid` from payload
7. `await self.async_set_unique_id(device_id)` + `self._abort_if_unique_id_configured()`
8. Call `_classify_payload(payload)` to categorize all fields into sensor groups

### Discovery Failure (`async_step_discovery_failed`)

Shows an error form with a "Retry" button. Clears the failed task and returns to `async_step_discover`.

---

## Step 3: `async_step_select_sensors` — Sensor Selection

**Purpose:** Present all discovered sensors for user selection.

**Form schema:** Dynamic `SelectSelector` with `multiple=True`:

```python
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
)

options = []
for category, sensors in self._discovered_sensors.items():
    for sensor in sensors:
        options.append(
            SelectOptionDict(
                value=sensor.key,
                label=f"{category}: {sensor.name} ({sensor.sample_value} {sensor.unit or ''})"
            )
        )

schema = vol.Schema({
    vol.Required(
        "selected_sensors",
        default=[s.key for cat in self._discovered_sensors.values() for s in cat if s.default_selected]
    ): SelectSelector(
        SelectSelectorConfig(
            options=options,
            multiple=True,
            mode=SelectSelectorMode.LIST,
        )
    )
})
```

**Example presentation:**
```
[x] Internal: System Voltage (4.17 V)
[x] Internal: Input Voltage (28.27 V)
[x] Internal: Ambient Temperature (38.45 °C)
[x] Internal: Light Level (0 lx)
[x] Internal: Acceleration X (1.06 g)
[x] Internal: Acceleration Y (-0.01 g)
[x] Internal: Acceleration Z (-0.07 g)
[x] Internal: Roll (-0.5 °)
[x] Internal: Pitch (-86.1 °)
[x] Internal: Tilt Angle (86.1 °)
[x] Internal: Motion Count (392)
[x] Internal: Movement Hours (0 h)
[x] Internal: WiFi Signal Strength (-23 dBm)
[x] Internal: WiFi IP Address (192.168.100.179)
[x] Internal: Device State (0)
[x] CAN2: Engine Speed — EEC1 (1841.0 rpm)
[x] CAN2: Actual Engine Torque — EEC1 (80 %)
[x] CAN2: Engine Coolant Temp — ET1 (120 °C)
[x] CAN2: Vehicle Speed — CCVS1 (50.1 km/h)
[x] CAN2: Engine Total Hours — HOURS (504.0 h)
[x] CAN2: Total Fuel Used — LFC (371.0 L)
[x] CAN2: Barometric Pressure — AMB (0 kPa)
[x] Custom: Parameter 18 (504)
[x] Custom: Parameter 19 (86)
    ...
[x] Events: Last Event
[ ] CAN2: Unknown PGN 65308 (raw)
```

**Default selection logic:**
- Known internal sensors: selected
- Known CAN SPNs with non-null values: selected
- Custom parameters: selected
- Events: selected
- Unknown/raw PGNs: NOT selected
- CAN SPNs returning null (not-available): NOT selected

**On submit:** Create config entry:
```python
return self.async_create_entry(
    title=self._device_name,
    data={
        "mqtt_topic": self._mqtt_topic,
        "device_id": self._device_id,
        "device_name": self._device_name,
        "selected_sensors": user_input["selected_sensors"],
    },
)
```

---

## Sensor Classification Algorithm

The `_classify_payload` method processes the raw JSON payload:

```python
@dataclass
class DiscoveredSensor:
    key: str              # e.g., "can2.spn190"
    name: str             # e.g., "Engine Speed — EEC1"
    sample_value: Any     # e.g., 1841.0
    unit: str | None      # e.g., "rpm"
    default_selected: bool

def _classify_payload(self, payload: dict) -> dict[str, list[DiscoveredSensor]]:
    result = {}
    decoder = J1939Decoder()

    for key, value in payload.items():
        # Skip metadata
        if key in ("deviceid", "ts", "time"):
            continue

        # CAN ports
        if key in ("can1", "can2") and isinstance(value, list):
            category = key.upper()
            sensors = []
            for frame in value:
                can_id, hex_data = frame.get("id"), frame.get("data")
                if can_id is None or hex_data is None:
                    continue
                decoded = decoder.decode_frame(can_id, hex_data)
                pgn_info = decoder.get_pgn_info(can_id)

                if decoded:
                    for spn_num, spn_value in decoded.items():
                        spn_def = decoder.get_spn_def(spn_num)
                        acronym = pgn_info.acronym if pgn_info else "?"
                        sensors.append(DiscoveredSensor(
                            key=f"{key}.spn{spn_num}",
                            name=f"{spn_def.name} — {acronym}",
                            sample_value=spn_value,
                            unit=spn_def.unit,
                            default_selected=spn_value is not None,
                        ))
                else:
                    # Unknown PGN
                    _, pgn, _ = decoder.extract_pgn(can_id)
                    sensors.append(DiscoveredSensor(
                        key=f"{key}.raw.{pgn}",
                        name=f"Unknown PGN {pgn} (0x{pgn:04X})",
                        sample_value=hex_data,
                        unit=None,
                        default_selected=False,
                    ))
            if sensors:
                result[category] = sensors

        # Events
        elif key == "events" and isinstance(value, list):
            result["Events"] = [DiscoveredSensor(
                key="events.last",
                name="Last Event",
                sample_value=value[0].get("msg", "") if value else "",
                unit=None,
                default_selected=True,
            )]

        # Custom parameters
        elif key.startswith("cp") and key[2:].isdigit():
            result.setdefault("Custom", []).append(DiscoveredSensor(
                key=f"custom.{key}",
                name=f"Parameter {key[2:]}",
                sample_value=value,
                unit=None,
                default_selected=True,
            ))

        # Internal sensors
        elif isinstance(value, (int, float, str)):
            meta = KNOWN_INTERNAL_SENSORS.get(key)
            name = meta.name if meta else key.replace("_", " ").title()
            unit = meta.unit if meta else None
            result.setdefault("Internal", []).append(DiscoveredSensor(
                key=f"internal.{key}",
                name=name,
                sample_value=value,
                unit=unit,
                default_selected=True,
            ))

    return result
```

---

## strings.json Structure

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
          "device_name": "A friendly name for this device (e.g., 'Excavator CAT 320')",
          "mqtt_topic": "The MQTT topic this device publishes telemetry to"
        }
      },
      "discover": {
        "title": "Discovering Sensors"
      },
      "select_sensors": {
        "title": "Select Sensors",
        "description": "Found {sensor_count} sensors on device {device_id}. Select which sensors to create.",
        "data": {
          "selected_sensors": "Sensors"
        }
      },
      "discovery_failed": {
        "title": "Discovery Failed",
        "description": "No data was received from the device within 60 seconds. Ensure the device is powered on and publishing to the specified MQTT topic."
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
