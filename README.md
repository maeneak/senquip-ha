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
  - Multi-packet DM1 (2+ faults, sent as a BAM transfer) is detected and reported as "N Active Faults (details not decoded)". A Senquip payload holds one frame per CAN ID, so the individual DTCs cannot be reassembled; that ECU's lamps show `Unknown`, Active SPN/FMI show `Unknown`, and Occurrence Count keeps its last value. In the fault history, that ECU's previously known faults stay active until it sends a single-frame DM1 again
  - An ECU missing from a payload keeps its last DM1 state for up to 5 payloads, so the port values do not flicker when a frame is not captured. After that it is dropped; if no ECU is left the Active Fault shows `No DM1 Received` with lamps `Unknown`. This memory is cleared when the device goes offline or the port becomes unavailable
  - `DM1 Fault History` sensor per J1939 port with DM1 signals selected: persistent log of past faults (SPN, FMI, description, lamps, first seen, last activated, cleared, activation count). Saved to `.storage` about a second after each change, so it survives restarts and power loss. Keeps up to 25 entries: the least recently active cleared faults are dropped first and active faults are never dropped
  - A `senquip_dm1_fault` event is fired whenever a logged fault becomes active or clears (see [Fault events](#fault-events))
- J1939 engine diagnostics from EEC1 (PGN 61444):
  - `Engine Starter Mode` (SPN 1675): start not requested, starter active, start finished, or why a start is inhibited (engine running, not ready, driveline engaged, immobilizer, starter over-temperature, unknown)
  - `Source Address of Controlling Device` (SPN 1483): which controller is commanding the engine (e.g. `39` = 0x27, the MAN control system)
  - Existing entries pick these up via the options flow (`Configure` -> rediscover -> select the new signals)
  - SPN 1483 was previously named `Source Address of Engine Controller` and recorded as a measurement. If you had it selected, Home Assistant reports that its state class was removed: fix it once from the repair prompt or `Developer Tools -> Statistics`
- MAN D2862 gearbox status (PGN 65308) shows `Not Reported` when the engine sets none of the neutral / forward / reverse flags
- Profile overlays for CAN protocols via `custom_components/senquip/can_profiles/`
- Options flow to rediscover and reconfigure protocols/signals without removing the integration
- Diagnostics output includes `selected_signals`, `port_configs`, and protocol-specific CAN summaries

## Fault events

The `DM1 Fault History` sensor fires `senquip_dm1_fault` on the event bus each time a fault becomes active or clears. A fault that stays active fires no further events, and a change of lamps or description on an active fault is not an event. Events need the `DM1 Fault History` entity: it exists when any DM1 signal is selected on the port, and disabling it stops the events.

| Field | Description |
| --- | --- |
| `status` | `active` or `cleared` |
| `spn`, `fmi` | Fault SPN and FMI (`null` for a multi-packet DM1 whose faults cannot be decoded) |
| `description` | Fault text, e.g. `SPN 520202: Engine Start Prevented (FMI 14: Special Instructions)` |
| `lamps` | Lamps reported Active with the fault, e.g. `["Red Stop"]` |
| `source_address` | J1939 source address of the ECU reporting the fault |
| `occurrence_count`, `count` | ECU occurrence count; number of times the log has seen the fault activate |
| `first_seen`, `last_activated`, `cleared` | ISO timestamps (UTC) |
| `device_id`, `device_name` | Home Assistant device of the CAN port (`device_name` uses your rename if you set one) |
| `senquip_id`, `port`, `entity_id` | Senquip device ID, CAN port and the fault history sensor |

Example automation sending a phone notification:

```yaml
triggers:
  - trigger: event
    event_type: senquip_dm1_fault
    event_data:
      status: active
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: "{{ trigger.event.data.device_name }} fault"
      message: "{{ trigger.event.data.description }} {{ trigger.event.data.lamps | join(', ') }}"
```

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
  "spn_encoding": "little_endian",
  "ports": ["can2"],
  "source_addresses": [0, 39],
  "custom_fault_spns": { "520198": "Emergency Stop" }
}
```

- `spn_encoding`: `little_endian` (J1939-73 standard, default) or `big_endian` (SPN packed most significant byte first). The MAN D2862 PDF's worked example implies `big_endian`, but the engines in service send the standard layout, so the bundled MAN profile uses `little_endian`. Fault history entries logged before 0.8.0 from the MAN profile's sources are corrected to the little-endian SPN (and description) once, when the history is loaded after upgrading. 0.8.0 keeps the history in a new storage file; faults logged after a downgrade to 0.7.0 are not carried back on a later upgrade
- `ports`: limit the DM1 options to these ports. Leave it out (or `null`) for all ports using the profile
- `source_addresses`: limit the DM1 options to DM1 from these J1939 source addresses, so other ECUs on the same bus keep standard decoding. Leave it out (or `null`) for all sources. The bundled MAN profile uses `[0, 1, 39]` (engine #1, engine #2, MAN MCS); add any other MAN ECU address on a shared bus. An empty list, or a value that is not a list of valid entries (port names; integers 0-255), matches nothing rather than everything, so a typo cannot widen the options
- `custom_fault_spns`: names for proprietary fault SPNs. Only applied to DM1 from the ports and sources above, since proprietary SPNs overlap between manufacturers

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
