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
| `custom_components/senquip/fault_history.py` | Pure-Python persistent DM1 fault log used by the fault history sensor. |
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
- MAN big-endian DM1 supported via profile `dm1.spn_encoding`, optionally limited by `dm1.ports` and `dm1.source_addresses`. The MAN engines on the vessel transmit from SA 0x00, not the 0x27 in the MAN doc, so the MAN profile lists 0x00, 0x01 and 0x27 (engine #1, engine #2, MCS). `ports` / `source_addresses` omitted or null = all; a given list = only those (empty or invalid = none). `custom_fault_spns` use the same port/source filter
- Lamp byte is four 2-bit fields, LSB first: Protect, Amber, Red Stop, MIL. `00`=Off, `01`=Active, `10`/`11`=Not Available
- A Senquip payload holds one frame per CAN ID, so multi-packet (BAM/TP) DM1 cannot be reassembled. A TP.CM BAM announcing PGN 65226 is detected and reported as a DTC count (`J1939Decoder.decode_dm1_bam`); that source's lamps are `Unknown`
- `decode_runtime` takes one DM1 report per source per payload (multi-packet beats a single frame, since payload order is CAN-ID slot order, not time), merges it into the per-port `decoder.dm1_tracker` (`DM1SourceTracker`, which keeps absent sources for up to 5 port payloads and is reset via `CANProtocol.reset_runtime_state` when the device goes offline or the port becomes unavailable), then `_combine_dm1_reports` produces the port-level `dm1.*` values (worst lamp state, all faults listed, `active_fault_count`; `No DM1 Received` when every source has aged out)
- `fault_history.py` (`DM1FaultLog`) keeps a per-port fault log keyed by (source address, SPN, FMI); a multi-packet DM1 is one entry per source with `spn`/`fmi` None. The coordinator exposes each payload's DM1 reports via `get_dm1_reports(port)`, and `SenquipDM1FaultHistorySensor` feeds them into the log and saves it with HA `Store` (`fault_history_store_key`). It is created automatically for J1939 ports with any `dm1.` signal selected. `async_remove_entry` deletes the stores

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
- `tests/test_fault_history.py`
- `tests/test_dm1_followups.py`

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

