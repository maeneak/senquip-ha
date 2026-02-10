# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Home Assistant custom integration for Senquip QUAD-C2 telemetry devices. Subscribes to MQTT, decodes raw J1939 CAN bus frames, and exposes sensor entities. Two CAN buses are monitored: CAN1 (Cummins QSB4.5 generator, standard J1939) and CAN2 (MAN D2862-LE466 main engine, requires profile overrides).

## Running Tests

```bash
pytest tests/
pytest tests/test_j1939_decoder.py          # single file
pytest tests/test_j1939_decoder.py -k "test_extract_pgn"  # single test
```

Tests use standalone HA stubs (no Home Assistant installation required). The `tests/conftest.py` injects minimal stubs for all `homeassistant.*` modules into `sys.modules`, and `tests/ha_stubs.py` provides the mock implementations. No pyproject.toml, tox, or CI pipeline exists.

## Architecture

**Data flow:** MQTT message → `SenquipDataCoordinator._parse_payload()` → `J1939Decoder` → flat `{sensor_key: value}` dict → `CoordinatorEntity` sensors

### Key modules

- **`__init__.py`** — `SenquipDataCoordinator` subscribes to MQTT, parses JSON payloads, decodes CAN frames, and publishes a flat `dict[str, Any]` via `async_set_updated_data()`. DM1 frames get special handling with per-port big-endian/little-endian selection.
- **`j1939_decoder.py`** — `J1939Decoder` class. Extracts PGN from 29-bit CAN IDs, decodes SPNs with bit-level extraction and resolution/offset math. Handles DM1 (PGN 65226) diagnostic trouble codes with both standard LE and MAN BE SPN encoding. Accepts optional `DM1Config` for per-port encoding control.
- **`j1939_database.py`** — Built-in PGN/SPN definitions (~16 PGNs, ~80+ SPNs). `PGNDefinition` and `SPNDefinition` frozen dataclasses.
- **`j1939_profile_loader.py`** — Loads JSON profiles from `j1939_custom/` that override/extend the built-in database. `merge_databases()` returns `(pgn_db, spn_db, dm1_config)`. `DM1Config` controls per-port DM1 SPN encoding.
- **`config_flow.py`** — Multi-step UI flow: topic input → MQTT discovery (60s timeout) → profile selection → sensor selection. `_classify_payload()` categorizes sensors. `_build_profile_decoder()` creates a decoder with selected profiles.
- **`sensor.py`** — `_resolve_sensor_meta()` maps sensor keys to HA metadata (device class, unit, icon). `_build_device_info()` groups sensors under CAN1/CAN2 sub-devices.
- **`const.py`** — `SensorMeta` dataclass, `SPN_UNIT_TO_HA` mapping, `KNOWN_INTERNAL_SENSORS`.

### Sensor key conventions

Keys follow the pattern `{namespace}.{identifier}`:
- `internal.{json_key}` — flat JSON values (vsys, vin, ambient, etc.)
- `{port}.spn{num}` — decoded J1939 SPNs (e.g. `can1.spn190`)
- `{port}.dm1.{field}` — DM1 diagnostic sensors (e.g. `can2.dm1.active_fault`)
- `{port}.raw.{pgn}` — unknown PGN hex data
- `events.last` — last event message

### Profile system

JSON profiles in `j1939_custom/` override built-in PGN/SPN definitions. Each profile must have internally consistent cross-references (every SPN in a PGN's `spns` list must be defined, and vice versa). Cross-references are validated within each profile, not across the merged database. The `dm1` section configures DM1 encoding per port.

### DM1/DTC decoding

DM1 (PGN 65226) uses a different byte format than normal SPNs and is handled separately from `decode_frame()`. The `dm1.ports` field in profiles controls which CAN ports use big-endian SPN encoding; unlisted ports default to standard J1939 little-endian. This allows one device to decode both CAN1 (Cummins LE) and CAN2 (MAN BE) simultaneously.

## Important return signatures

- `merge_databases()` → `tuple[dict[int, PGNDefinition], dict[int, SPNDefinition], DM1Config | None]`
- `decode_can_port()` → `tuple[dict[int, float | None], DM1Result | None]`
- `load_profile()` → `tuple[dict[int, PGNDefinition], dict[int, SPNDefinition], DM1Config | None]`

## Known gotchas

- Don't use `field` as a loop variable name when `dataclasses.field` is imported — it shadows the import.
- SPN 962 = **Day**, SPN 963 = **Month** in standard J1939 (counterintuitive).
- MAN D2862 VEP1: SPN 168 stays at byte 7 despite MAN documentation suggesting byte 5. Live data confirms bytes 5-6 are 0xFFFF.
- J1939 `start_byte` is 1-indexed in definitions but converted to 0-indexed in `decode_spn()`.
