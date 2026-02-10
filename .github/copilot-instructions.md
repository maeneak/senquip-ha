# Copilot Instructions - Senquip HA Integration

## What This Is

A Home Assistant custom integration for Senquip QUAD-C2 telemetry devices. It subscribes to MQTT JSON payloads, decodes internal signals and CAN data, and exposes selected signals as HA sensors.

The CAN stack is now protocol-first:

- J1939 decoded mode
- NMEA2000 raw mode
- ISO11783 raw mode
- CANopen raw mode

No backward compatibility is required for pre-refactor config/signal formats.

## Architecture

Data flow:

- MQTT -> `SenquipDataCoordinator._parse_payload()` -> protocol adapter decode -> flat `{signal_key: value}` -> `CoordinatorEntity` sensors

### Core modules

| Module | Role |
| --- | --- |
| `custom_components/senquip/__init__.py` | Coordinator runtime. Builds per-port protocol decoders from `port_configs`; parses payload to canonical signal keys. |
| `custom_components/senquip/config_flow.py` | Config flow and options flow: `user -> discover -> configure_ports -> select_signals`. |
| `custom_components/senquip/const.py` | Config keys, known port families, `PortConfig`, `SensorMeta`, internal sensor metadata, SPN-to-HA unit mapping. |
| `custom_components/senquip/sensor.py` | Metadata resolution from canonical keys and device grouping (base + CAN sub-devices). |
| `custom_components/senquip/diagnostics.py` | Diagnostics payload using `selected_signals`, `port_configs`, and protocol-aware CAN summaries. |
| `custom_components/senquip/can_protocols/base.py` | CAN protocol interface and discovered-signal type. |
| `custom_components/senquip/can_protocols/registry.py` | Protocol registry/options. |
| `custom_components/senquip/can_protocols/j1939/*` | J1939 database, decoder, overlay parsing, protocol adapter. |
| `custom_components/senquip/can_protocols/raw.py` | Raw protocol adapter used by NMEA2000/ISO11783/CANopen. |
| `custom_components/senquip/can_profiles/loader.py` | Generic CAN profile loading and schema validation. |
| `custom_components/senquip/can_profiles/*.json` | Profile files (for example `man_d2862.json`). |

## Config Entry Schema

- `selected_signals`: list of canonical signal keys
- `port_configs`: per-port config object

`port_configs` includes known families:

- `internal`, `can1`, `can2`, `serial1`, `input1`, `input2`, `output1`, `current1`, `current2`, `ble`, `gps`

CAN entries include:

- `family: "can"`
- `active: bool`
- `protocol: str`
- `profiles: list[str]`

## Canonical Signal Key Patterns

- `internal.main.<json_key>`
- `can.<port>.<protocol>.spn<num>` (J1939 decoded)
- `can.<port>.<protocol>.dm1.<field>` (J1939 DM1)
- `can.<port>.<protocol>.raw.<pgn>` (raw/unknown frames)
- `event.main.last`

## Profile System

Profiles live under:

- `custom_components/senquip/can_profiles/`

Schema:

```json
{
  "name": "Profile Name",
  "base_protocol": "j1939",
  "description": "Optional description",
  "protocol_data": {
    "j1939": {
      "pgns": {},
      "spns": {},
      "dm1": {}
    }
  }
}
```

J1939 overlay validation rules:

- PGN references must point to defined SPNs in that profile section.
- SPN `pgn` references must point to defined PGNs in that profile section.
- Validation is per profile section, not across merged output.

## DM1/DTC

DM1 (PGN 65226) is decoded separately from normal SPNs.

- Standard little-endian DM1 supported
- MAN big-endian DM1 supported via profile `dm1.spn_encoding` and optional `dm1.ports`

## Tests

Run all:

```bash
pytest tests/
```

Current notable tests:

- `tests/test_j1939_decoder.py`
- `tests/test_j1939_profile_loader.py`
- `tests/test_parse_payload.py`
- `tests/test_classify_payload.py`
- `tests/test_resolve_sensor_meta.py`
- `tests/test_can_protocol_registry.py`
- `tests/test_config_flow_ports.py`
- `tests/test_config_flow_steps.py`
- `tests/test_raw_protocol.py`

Tests run without Home Assistant installed by using stubs in:

- `tests/ha_stubs.py`
- `tests/conftest.py`

If new HA imports are added, update both stubs and module registration.

## Critical Rules

1. Dataclasses used for config/definitions are immutable unless there is a strong reason to change that.
2. `start_byte` in SPN definitions is 1-indexed; decoder logic converts to 0-indexed.
3. Do not reintroduce legacy config keys (`selected_sensors`, `j1939_profiles`) or legacy signal key patterns.
4. For raw protocols, signals stay raw (`can.<port>.<protocol>.raw.<pgn>`) until a real decoder is implemented.
5. Keep profile filtering by `base_protocol` in config flow.

## Reference Files

- `README.md`
- `dev-tools/README.md`
- `docs/MAN_D2862_J1939_Interface.md`
- `dev-tools/mqtt-publisher/scenarios/`
- `diag/`

