# Senquip Telemetry - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)

A custom [Home Assistant](https://www.home-assistant.io/) integration for [Senquip](https://senquip.com/) QUAD-C2 telemetry devices.

The integration subscribes to MQTT telemetry, supports protocol-based CAN decoding, and exposes selected signals as Home Assistant sensor entities.

## Features

- MQTT push model (no polling)
- Protocol-first CAN architecture (per-port protocol selection)
- Active-port config flow:
  - `user -> discover -> configure_ports -> select_signals`
- Canonical signal keys:
  - `internal.main.<json_key>`
  - `can.<port>.<protocol>.spn<num>`
  - `can.<port>.<protocol>.dm1.<field>`
  - `can.<port>.<protocol>.raw.<pgn>`
  - `event.main.last`
- J1939 DM1 fault reporting:
  - Active fault, active fault count, lamp status (Protect / Amber Warning / Red Stop / MIL) and SPN/FMI sensors
  - DM1 from several ECUs on one port is combined: each lamp shows the most severe state (Active > Unknown > Off > Not Available) and the fault text lists every decoded fault
  - Multi-packet DM1 (2+ faults, sent as a BAM transfer) is detected and reported as "N Active Faults (details not decoded)". A Senquip payload holds one frame per CAN ID, so the individual DTCs cannot be reassembled; that ECU's lamps show `Unknown`
  - `DM1 Fault History` sensor per J1939 port with DM1 signals selected: persistent log of past faults (SPN, FMI, description, lamps, first seen, last activated, cleared, activation count). Saved to `.storage` about a second after each change, so it survives restarts and power loss. Keeps up to 25 entries: the least recently active cleared faults are dropped first and active faults are never dropped
- Profile overlays for CAN protocols via `custom_components/senquip/can_profiles/`
- Options flow to rediscover and reconfigure protocols/signals without removing the integration
- Diagnostics output includes `selected_signals`, `port_configs`, and protocol-specific CAN summaries

## Supported CAN Protocols

| Protocol | Mode | Notes |
| --- | --- | --- |
| `j1939` | Decoded | Full SPN/PGN decode with DM1 support |
| `nmea2000` | Raw | Raw PGN capture (no semantic decode yet) |
| `iso11783` | Raw | Raw PGN capture (no semantic decode yet) |
| `canopen` | Raw | Raw frame/PGN capture (no semantic decode yet) |

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant.
2. Go to `Custom repositories`.
3. Add this repository as an `Integration`.
4. Install `Senquip Telemetry`.
5. Restart Home Assistant.

### Manual

1. Copy `custom_components/senquip/` into your HA config directory at `config/custom_components/senquip/`.
2. Restart Home Assistant.

## Configuration

**Prerequisite**: Ensure the [Home Assistant MQTT integration](https://www.home-assistant.io/integrations/mqtt/) is installed and configured.

1. Go to `Settings -> Devices & Services -> Add Integration`.
2. Add `Senquip Telemetry`.
3. Enter:
   - Device name
   - MQTT topic (example: `senquip/HE8EV12LF/data`)
4. Wait for discovery message.
5. In `Configure Ports`:
   - Select protocol per active CAN port.
   - Optionally select matching profile overlays for the selected protocol.
6. In `Select Signals`, choose which signals/entities to create.

## Important Breaking Change

This refactor intentionally changed config schema and signal keys:

- `selected_sensors` -> `selected_signals`
- `j1939_profiles` -> `port_configs`
- Legacy signal keys (for example `can1.spn190`) -> canonical keys (for example `can.can1.j1939.spn190`)

No migration/backward compatibility is provided for old entries.

## CAN Profiles

Profiles live in:

- `custom_components/senquip/can_profiles/`

Each profile uses the generic schema:

```json
{
  "name": "MAN D2862-LE466",
  "base_protocol": "j1939",
  "description": "Profile description",
  "protocol_data": {
    "j1939": {
      "pgns": {},
      "spns": {},
      "dm1": {}
    }
  }
}
```

### DM1 options

The optional `dm1` section configures manufacturer-specific DM1 decoding:

```json
"dm1": {
  "spn_encoding": "big_endian",
  "ports": ["can2"],
  "source_addresses": [0, 39],
  "custom_fault_spns": { "520198": "Emergency Stop" }
}
```

- `spn_encoding`: `little_endian` (J1939-73 standard, default) or `big_endian` (MAN)
- `ports`: limit `spn_encoding` to these ports (empty = all ports using the profile)
- `source_addresses`: limit `spn_encoding` to DM1 from these J1939 source addresses (empty = all), so other ECUs on the same bus keep standard decoding
- `custom_fault_spns`: names for proprietary fault SPNs

### Current bundled profile

- `custom_components/senquip/can_profiles/man_d2862.json`

## Extending J1939 Built-ins

To add built-in J1939 PGN/SPN definitions, edit:

- `custom_components/senquip/can_protocols/j1939/database.py`

After updates, restart Home Assistant and rerun the integration options flow to rediscover signals.

## Diagnostics

Diagnostics payload includes:

- Config values: MQTT topic, selected signals, port configs
- Current values
- Per-port CAN frame summaries including protocol and known/unknown frame counts

## Debugging

To enable debug logging, add the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.senquip: debug
```

## Development and Tests

Run tests:

```bash
pytest tests/
```

Dev tools are documented in:

- `dev-tools/README.md`

## License

MIT
