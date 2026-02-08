# Senquip Quad C2 — Home Assistant Integration Plan

## Overview

A custom Home Assistant integration that subscribes to MQTT topics from Senquip Quad C2 telemetry devices, decodes raw J1939 CAN bus data into meaningful sensor values, and exposes selected readings as HA entities.

**Key characteristics:**
- Each Senquip device publishes a single JSON object to its own MQTT topic
- J1939 CAN bus decoding performed in HA (not on-device)
- RX only — no commands sent to devices
- UI-based config flow with MQTT discovery and user sensor selection
- v1 scope: CAN + Internal sensors + Custom Parameters + Events (Serial/Modbus/General IO deferred)

---

## Architecture

```
MQTT Broker
  │
  │  Per-device topic (e.g. senquip/HE8EV12LF/data)
  │  Single JSON object payload
  │
  ▼
SenquipDataCoordinator (one per config entry / device)
  │
  │  1. Parse JSON
  │  2. Extract flat fields → internal.{key}: value
  │  3. Decode CAN frames via J1939Decoder → {port}.spn{N}: value
  │  4. Extract custom params → custom.cp{N}: value
  │  5. Extract last event → events.last: message string
  │  6. Filter to selected_sensors only
  │  7. async_set_updated_data(flat_dict)
  │
  ▼
SenquipSensorEntity instances (CoordinatorEntity + SensorEntity)
  │
  │  Each reads coordinator.data[self._sensor_key]
  │  _attr_should_poll = False (push-based)
  │
  ▼
Home Assistant State Machine
```

### Why this architecture?

- **DataUpdateCoordinator** (not per-entity MQTT subscriptions): Each device publishes ALL sensor data in a single JSON message. One subscription, parsed once, distributed to 30+ entities. Far more efficient than each entity subscribing independently.
- **Custom integration** (not built-in MQTT sensors): The built-in MQTT sensor platform requires one topic per entity and Jinja2 templates. Our nested CAN data requires algorithmic decoding (bit extraction, resolution/offset math) that templates cannot handle.
- **J1939 in HA** (not on-device): Provides visibility into all CAN data, standard PGN/SPN naming, and ability to add PGN support without touching the Senquip device.

---

## File Structure

```
custom_components/senquip/
├── __init__.py          # Entry setup/teardown, SenquipDataCoordinator
├── manifest.json        # Integration metadata
├── config_flow.py       # Multi-step config flow with MQTT discovery
├── const.py             # Constants, sensor metadata definitions
├── sensor.py            # SenquipSensorEntity class
├── j1939_decoder.py     # J1939Decoder class (CAN ID parsing, SPN extraction)
├── j1939_database.py    # PGN/SPN definitions (pure data, extensible)
├── strings.json         # Config flow UI text
└── translations/
    └── en.json          # English translations
```

See [FILE_DETAILS.md](FILE_DETAILS.md) for detailed specifications of each file.

---

## Config Flow

See [CONFIG_FLOW.md](CONFIG_FLOW.md) for the complete config flow specification.

**Summary — 3 steps + progress spinner:**

1. **Device Configuration** — User enters device name and MQTT topic
2. **Discovery** (with progress spinner) — Integration subscribes to MQTT, waits for first message, parses JSON, decodes CAN frames, classifies all available sensors
3. **Sensor Selection** — User sees all discovered sensors with sample values, selects which to create as HA entities

---

## J1939 Decoder

See [J1939_DECODER.md](J1939_DECODER.md) for complete decoder specification and PGN/SPN database.

**Summary:**
- Extracts PGN from 29-bit CAN ID (decimal integer)
- Decodes SPNs using byte position, bit position, resolution, offset
- Ships with 9 PGNs covering the CAN frames in example data
- Extensible database — add new PGNs/SPNs by editing `j1939_database.py`
- Verified against example data: SPN 190 = 1841 RPM (matches cp28), SPN 247 = 503.95h (matches cp18)

---

## Implementation Order

### Phase 1: J1939 Core (testable independently)
1. `const.py` — DOMAIN, config keys, SensorMeta dataclass, KNOWN_INTERNAL_SENSORS
2. `j1939_database.py` — SPNDefinition/PGNDefinition dataclasses, PGN/SPN data
3. `j1939_decoder.py` — J1939Decoder class

### Phase 2: Integration Skeleton
4. `manifest.json` — Integration metadata
5. `strings.json` + `translations/en.json` — UI text
6. `__init__.py` — SenquipDataCoordinator + entry setup/teardown

### Phase 3: Config Flow
7. `config_flow.py` — All 3 steps + discovery + sensor classification

### Phase 4: Entities
8. `sensor.py` — SenquipSensorEntity + entity creation from config

### Phase 5: Verification
- Publish example device payloads to test MQTT broker
- Verify discovery finds all sensors with correct sample values
- Verify CAN decoding matches expected values
- Verify entities update on subsequent MQTT messages
- Verify device grouping in HA UI
