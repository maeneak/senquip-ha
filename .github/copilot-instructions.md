# Copilot Instructions — Senquip HA Integration

## What This Is

A Home Assistant custom integration for Senquip QUAD-C2 telemetry devices. Subscribes to MQTT, decodes J1939 CAN bus frames from two marine engines (CAN1: Cummins QSB4.5, CAN2: MAN D2862-LE466), and exposes sensor entities. Still in active development — no backward compatibility or migration code required.

## Architecture

**Data flow:** MQTT → `SenquipDataCoordinator._parse_payload()` → `J1939Decoder` → flat `{sensor_key: value}` dict → `CoordinatorEntity` sensors

| Module | Role |
|--------|------|
| `__init__.py` | `SenquipDataCoordinator` — MQTT subscription, `_parse_payload()` extracts sensors from JSON. Per-port decoders (`self._decoders`). DM1 faults handled separately with 8 keys per port. |
| `j1939_decoder.py` | `J1939Decoder` — `extract_pgn()`, `decode_spn()`, `decode_dm1()`, `decode_can_port()`. DM1 supports both standard LE and MAN big-endian SPN encoding via `DM1Config`. |
| `j1939_database.py` | Built-in PGN/SPN definitions. `PGNDefinition` and `SPNDefinition` frozen dataclasses. `start_byte` is **1-indexed** in definitions, converted to 0-indexed in `decode_spn()`. |
| `j1939_profile_loader.py` | Loads JSON profiles from `j1939_custom/`. `merge_databases()` → `(pgn_db, spn_db, dm1_config)`. Cross-references validated per-profile, not across merged output. |
| `config_flow.py` | Multi-step UI: topic → MQTT discovery (60s) → profile selection → sensor selection. `_classify_payload()` always adds DM1 sensors for active CAN ports. |
| `sensor.py` | `_resolve_sensor_meta()` routes by key pattern. `_build_device_info()` creates CAN sub-devices via `via_device`. |
| `const.py` | `SensorMeta` dataclass (defaults `state_class=MEASUREMENT` — set `None` explicitly for non-measurements), `SPN_UNIT_TO_HA`, `KNOWN_INTERNAL_SENSORS`. |

### Sensor Key Patterns

- `internal.{json_key}` — flat JSON values (vsys, vin, ambient, etc.)
- `{port}.spn{num}` — decoded J1939 SPNs (e.g. `can1.spn190`)
- `{port}.dm1.{field}` — 8 DM1 fields: `protect_lamp`, `amber_warning`, `red_stop`, `mil`, `active_spn`, `active_fmi`, `active_fault`, `occurrence_count`
- `{port}.raw.{pgn}` — unknown PGN hex data
- `events.last` — last event message

### Profile System

JSON profiles in `j1939_custom/` override built-in PGN/SPN definitions. Each profile must have internally consistent cross-references (every SPN in a PGN's `spns` list must be defined, and vice versa). Cross-references are validated within each profile, not across the merged database. The `dm1` section configures DM1 encoding per port.

### DM1/DTC Decoding

DM1 (PGN 65226) uses a different byte format than normal SPNs and is handled separately from `decode_frame()`. The `dm1.ports` field in profiles controls which CAN ports use big-endian SPN encoding; unlisted ports default to standard J1939 little-endian. This allows one device to decode both CAN1 (Cummins LE) and CAN2 (MAN BE) simultaneously.

## Running Tests

```bash
pytest tests/                              # all tests
pytest tests/test_j1939_decoder.py -k "test_extract_pgn"  # single test
```

Tests run **without Home Assistant installed** — `tests/conftest.py` injects HA stubs from `tests/ha_stubs.py` into `sys.modules`.

### Test Conventions

- **Class-based grouping**: `class TestFeatureName:` with `test_descriptive_snake_case` methods
- **Parametrize**: `@pytest.mark.parametrize("input, expected, description", [...])` with assertion messages
- **Fixtures**: function-scoped `@pytest.fixture`, e.g. `decoder()` returning `J1939Decoder()`
- **Helpers**: module-level `_helper_name()` prefixed with underscore
- **No mocking of integration code** — tests import functions directly or reimplement them standalone
- **`test_parse_payload.py` reimplements `_parse_payload`** as a standalone function mirroring `__init__.py`. Changes to source must be mirrored here.

## Dev Environment

```bash
cd dev-tools && docker compose up        # HA + Mosquitto + MQTT publisher
docker compose restart homeassistant     # pick up code changes
```

7 test scenarios in `dev-tools/mqtt-publisher/scenarios/`. See `dev-tools/README.md` for full setup, multi-device simulation, and standalone usage.

## Critical Rules

1. **HA stub updates required**: Any new `homeassistant.*` import in integration code needs updates in BOTH `tests/ha_stubs.py` (class/constant) AND `tests/conftest.py` (module registration)
2. **All dataclasses are `frozen=True`**: `SPNDefinition`, `PGNDefinition`, `DM1Config`, `DM1Result`, `SensorMeta` are immutable
3. **Profile cross-references are per-profile**: A profile's SPN→PGN and PGN→SPN references must be internally consistent; validation doesn't check the merged database
4. **DM1 empty ports = ALL ports**: An empty `ports` tuple in `DM1Config` means "apply to all ports", not "no ports"
5. **Don't shadow `field`**: Never use `field` as a loop variable when `dataclasses.field` is imported
6. **MAN VEP1 quirk**: SPN 168 is at byte 7, not byte 5, despite MAN PDF suggesting otherwise — confirmed by live data (bytes 5-6 = 0xFFFF)
7. **SPN 962 = Day, SPN 963 = Month**: Standard J1939 ordering is counterintuitive

## Key Return Signatures

```python
merge_databases(base_pgn, base_spn, profiles) → tuple[dict[int, PGNDefinition], dict[int, SPNDefinition], DM1Config | None]
decode_can_port(frames, port)                 → tuple[dict[int, float | None], DM1Result | None]
load_profile(filepath)                        → tuple[dict[int, PGNDefinition], dict[int, SPNDefinition], DM1Config | None]
```

## Adding New PGNs/SPNs

- **Standard PGNs** go in `j1939_database.py` — follow existing `PGNDefinition`/`SPNDefinition` patterns
- **Manufacturer-proprietary PGNs** go in profile JSON only (e.g. PGN 65308 in `man_d2862.json`)
- Use synthetic SPN numbers 800000+ for manufacturer-specific SPNs with no J1939 assignment
- New units need a `SPN_UNIT_TO_HA` mapping in `const.py`

## Reference Files

- `docs/MAN_D2862_J1939_Interface.md` — complete MAN PDF extraction with all PGN byte layouts, DM1 encoding details, and deviation table
- `dev-tools/mqtt-publisher/scenarios/` — test payloads matching real device output
- `diag/` — real diagnostic JSON dumps from HA
