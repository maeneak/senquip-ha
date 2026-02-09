# Senquip Telemetry — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

A custom [Home Assistant](https://www.home-assistant.io/) integration for [Senquip](https://senquip.com/) QUAD-C2 telemetry devices. Subscribes to MQTT, decodes raw J1939 CAN bus frames, and exposes sensor entities — all configured through a UI-based config flow.

## Features

- **MQTT-based** — subscribes to per-device MQTT topics; push-based, no polling
- **J1939 CAN bus decoding** — extracts PGNs and SPNs from raw CAN frames with resolution/offset math
- **Auto-discovery** — listens for the first MQTT message, classifies all available sensors, and lets you pick which to create
- **Sensor categories:**
  - **Internal** — system voltage, temperature, accelerometer, WiFi, motion, etc.
  - **CAN** — decoded J1939 SPNs (engine speed, coolant temp, vehicle speed, fuel, hours, …)
  - **Custom parameters** — user-defined `cp1`–`cp34` values from the device
  - **Events** — last event message
- **Profile-based J1939 overrides** — drop JSON profiles into `j1939_custom/` and select them per device
- **Extensible PGN/SPN database** — still possible by editing `j1939_database.py`
- **Device grouping** — all sensors for a device appear under one HA device entry
- **Options flow** — re-trigger discovery and change selected sensors without removing the integration

## Supported PGNs

| PGN | Acronym | Description |
|-----|---------|-------------|
| 61444 | EEC1 | Engine Speed, Torque |
| 61443 | EEC2 | Accelerator Pedal, Load |
| 65262 | ET1 | Engine Temperatures |
| 65263 | EFL/P1 | Engine Fluid Levels & Pressures |
| 65265 | CCVS1 | Vehicle Speed, Cruise Control |
| 65253 | HOURS | Engine Hours & Revolutions |
| 65257 | LFC | Fuel Consumption |
| 65266 | LFE1 | Fuel Economy |
| 65269 | AMB | Ambient Conditions |
| 65270 | IC1 | Inlet/Exhaust Conditions |
| 65271 | VEP1 | Vehicle Electrical Power |
| 65254 | TD | Time/Date |

Unknown PGNs are shown as raw hex and can be optionally selected.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click **⋮** → **Custom repositories**
3. Add the repository URL and select **Integration** as the category
4. Search for "Senquip Telemetry" and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/senquip/` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Senquip Telemetry**
3. Enter a device name and the MQTT topic the device publishes to (e.g. `senquip/HE8EV12LF/data`)
4. Wait for the integration to receive the first MQTT message and discover sensors
5. (Optional) Select any J1939 profile overrides for your engine/manufacturer
6. Select which sensors to create as HA entities
7. Done — entities will update automatically on each MQTT message

### Changing Selected Sensors

Go to the integration's **Configure** button to re-discover sensors and update your selection without removing the device.

## Requirements

- Home Assistant with the **MQTT integration** configured and connected to your broker
- A Senquip QUAD-C2 device publishing JSON telemetry to MQTT

## Adding New J1939 PGNs/SPNs

Edit `custom_components/senquip/j1939_database.py`:

```python
# Add to PGN_DATABASE
65180: PGNDefinition(
    pgn=65180, name="My Custom PGN", acronym="MCP",
    length=8, spns=(9999,),
),

# Add to SPN_DATABASE
9999: SPNDefinition(
    spn=9999, name="My Custom Value", pgn=65180,
    start_byte=1, start_bit=1, bit_length=16,
    resolution=0.1, offset=0, unit="bar",
),
```

Restart Home Assistant and re-add (or reconfigure) the device to discover the new sensors.

## Using J1939 Profile Overrides (JSON)

For manufacturer-specific byte layouts (e.g., MAN VEP1), place a JSON profile in
`custom_components/senquip/j1939_custom/` and select it during setup or in the
Options flow.

### Profile Behavior

- Profiles **override** built-in PGNs/SPNs with the same IDs.
- If a profile defines PGN `65271`, the built-in PGN `65271` (and its SPN list)
  is completely replaced by the profile definition.
- Multiple profiles can be selected; later profiles override earlier ones.

### Profile Schema

Keys for `pgns` and `spns` are **strings** (JSON limitation). All SPN fields map
to the built-in `SPNDefinition` fields.

```json
{
  "name": "MAN D2862-LE466",
  "description": "MAN V12 marine diesel",
  "pgns": {
    "65271": {
      "name": "Vehicle Electrical Power 1",
      "acronym": "VEP1",
      "length": 8,
      "spns": [167, 168]
    }
  },
  "spns": {
    "167": {
      "name": "Alternator Voltage",
      "pgn": 65271,
      "start_byte": 3,
      "start_bit": 1,
      "bit_length": 16,
      "resolution": 0.05,
      "offset": 0,
      "unit": "V",
      "min_value": 0,
      "max_value": 3212.75
    }
  }
}
```

### Recommended Workflow

1. Create a new profile JSON in `custom_components/senquip/j1939_custom/`.
2. Restart Home Assistant.
3. Reconfigure the integration and select the profile in the **J1939 Profiles**
   step (Options flow also supported).

### Profile Order

If you select multiple profiles, they are merged in the order shown in the list,
and later profiles override earlier ones when they define the same PGN/SPN.

## Diagnostics

The integration exposes a diagnostics payload (in Home Assistant: the device
page → **Diagnostics**). It includes:

- The config values (MQTT topic, selected sensors, and selected J1939 profiles)
- Current sensor values from the coordinator
- A CAN bus summary with known/unknown frames and per-frame decoded SPNs

## License

MIT
