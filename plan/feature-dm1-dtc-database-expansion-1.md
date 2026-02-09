---
goal: Add J1939 DM1 diagnostic trouble code support, MAN-proprietary PGN 65308, 8 missing standard PGNs, MAN profile corrections, and supporting unit mappings
version: 1.1
date_created: 2026-02-09
last_updated: 2026-02-10
owner: maeneak
status: 'Planned'
tags: [feature, j1939, dm1, dtc, can-bus, man-d2862, database-expansion]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan adds DM1 (PGN 65226) diagnostic trouble code support as standard sensors, the MAN-proprietary PGN 65308 (Aux MAN Engine), 8 missing standard J1939 PGNs observed in live CAN data, MAN D2862 profile corrections (LFC byte swap, VEP1 SPN 168 fix), TD timezone SPNs, and new HA unit mappings. DM1 lamp statuses are modelled as normal 2-bit SPNs. The first active DTC is exposed as a composite sensor with fault count as state and SPN/FMI/OC detail in `extra_state_attributes`. Multi-packet DM1 (transport protocol) is explicitly out of scope.

## 1. Requirements & Constraints

- **REQ-001**: DM1 lamp statuses (SPNs 987, 624, 623, 1213) must be exposed as standard numeric sensors with values 0–3. Because `decode_spn()` treats all-bits-set as "not available" and all-bits-set-minus-LSB as "error indicator" (returning `None` for both), a `raw_value: bool` flag must be added to `SPNDefinition` so that 2-bit lamp SPNs bypass those checks and return the raw integer directly
- **REQ-002**: First active DTC from DM1 must be exposed as a composite sensor: state = active fault count, attributes = SPN number, SPN name (if known), FMI code, FMI description, occurrence count
- **REQ-003**: PGN 65308 (Aux MAN Engine) must be added to the MAN D2862 profile only (proprietary PGN, not standard J1939)
- **REQ-004**: 8 missing standard PGNs (65247, 65276, 65248, 65272, 65176, 65175, 65110, 64701) must be added to the built-in `j1939_database.py`
- **REQ-005**: MAN LFC byte order must be corrected in the MAN profile: SPN 182 at bytes 1–4, SPN 250 at bytes 5–8
- **REQ-006**: MAN VEP1 SPN 168 byte position must be corrected from `start_byte: 7` to `start_byte: 5`
- **REQ-007**: TD timezone SPNs 1601 and 1602 must be added to the built-in database and PGN 65254 spns tuple
- **REQ-008**: DM1 DTC sensors must appear in config flow discovery and be selectable
- **CON-001**: Multi-packet DM1 via J1939 transport protocol (BAM/TP.DT) is out of scope — the Senquip captures individual CAN frames, not reassembled sessions
- **CON-002**: Breaking changes are acceptable — backward compatibility with existing config entries is not required
- **CON-003**: No new HA platforms — all sensors use the existing `sensor` platform
- **CON-004**: PGN 65308 goes in the MAN profile JSON only; standard PGNs go in the built-in Python database
- **GUD-001**: DM1 lamp SPNs use the standard SPN extraction path through `decode_frame()` — they are real J1939 SPNs with defined bit positions. However, because the standard `decode_spn()` returns `None` for 2-bit values 2 (error indicator) and 3 (not available), these SPNs must set `raw_value=True` to bypass the not-available/error-indicator filtering
- **GUD-002**: DTC extraction is handled in `_parse_payload()` in `__init__.py` since the SPN/FMI fields are non-contiguously bit-packed and don't map to the `SPNDefinition` model
- **GUD-003**: The DTC composite sensor uses a `SenquipDTCSensorEntity` subclass that overrides `native_value` and `extra_state_attributes`
- **PAT-001**: Follow existing `SPNDefinition` / `PGNDefinition` dataclass patterns for all new database entries
- **PAT-002**: Follow existing `SensorMeta` pattern for new sensor metadata
- **PAT-003**: Follow existing test class grouping pattern (one class per feature area)

## 2. Implementation Steps

### Phase 1: Database Expansion — Standard PGNs and SPNs

- GOAL-001: Add all missing standard J1939 PGN/SPN definitions to `j1939_database.py` so that live CAN frames decode correctly without any profile

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add PGN 65226 (DM1) to `PGN_DATABASE` in `j1939_database.py` with `spns=(987, 624, 623, 1213)` | | |
| TASK-002 | Add SPN 987 (Protect Lamp, byte 1 bits 1-2), SPN 624 (Amber Warning Lamp, byte 1 bits 3-4), SPN 623 (Red Stop Lamp, byte 1 bits 5-6), SPN 1213 (MIL, byte 1 bits 7-8) to `SPN_DATABASE` — all 2-bit, resolution 1, offset 0, unit `""`, **`raw_value=True`** so `decode_spn()` returns the raw integer (0–3) without filtering values 2/3 as not-available/error-indicator | | |
| TASK-002b | Add `raw_value: bool = False` field to the `SPNDefinition` dataclass in `j1939_database.py`. In `decode_spn()` in `j1939_decoder.py`, skip the not-available and error-indicator checks when `spn_def.raw_value is True` — return `float(raw_value) * resolution + offset` directly. This ensures 2-bit DM1 lamp status values 2 ("Error") and 3 ("Not Available") are preserved as numeric sensor states rather than being swallowed to `None`. | | |
| TASK-003 | Add PGN 65247 (EEC3) to `PGN_DATABASE` with `spns=(514, 515, 2978)`. Add SPN 514 (Nominal Friction Torque, byte 1, 8-bit, 1%/bit, -125% offset, unit `%`), SPN 515 (Engine Desired Operating Speed, bytes 2-3, 16-bit, 0.125 rpm/bit, unit `rpm`), SPN 2978 (Engine Desired Operating Speed Asymmetry Adjustment, byte 4, 8-bit, 1%/bit, -125% offset, unit `%`) | | |
| TASK-004 | Add PGN 65276 (DD) to `PGN_DATABASE` with `spns=(80, 96, 95, 99)`. Add SPN 80 (Washer Fluid Level, byte 1, 8-bit, 0.4%/bit, unit `%`), SPN 96 (Fuel Level 1, byte 2, 8-bit, 0.4%/bit, unit `%`), SPN 95 (Fuel Filter Diff Pressure, byte 3, 8-bit, 2 kPa/bit, unit `kPa`), SPN 99 (Oil Filter Diff Pressure, byte 4, 8-bit, 0.5 kPa/bit, unit `kPa`) — J1939-71 standard byte layout for PGN 65276 Dash Display | | |
| TASK-005 | Add PGN 65248 (VD) to `PGN_DATABASE` with `spns=(245, 246)`. Add SPN 245 (Total Vehicle Distance, bytes 1-4, 32-bit, 0.125 km/bit, unit `km`), SPN 246 (Trip Distance, bytes 5-8, 32-bit, 0.125 km/bit, unit `km`) | | |
| TASK-006 | Add PGN 65272 (TF) to `PGN_DATABASE` with `spns=(124, 126, 127, 177)`. Add SPN 124 (Trans Oil Level, byte 2, 8-bit, 0.4%/bit, unit `%`), SPN 126 (Trans Filter ΔP, byte 1, 8-bit, 2 kPa/bit, unit `kPa`), SPN 127 (Trans Oil Pressure, byte 3, 8-bit, 4 kPa/bit, unit `kPa`), SPN 177 (Trans Oil Temp, bytes 4-5, 16-bit, 0.03125°C/bit, -273°C offset, unit `deg C`) | | |
| TASK-007 | Add PGN 65176 (TC4) to `PGN_DATABASE` with `spns=(1180, 1181)`. Add SPN 1180 (Exhaust Temp Before Turbo 1, bytes 1-2, 16-bit, 0.03125°C/bit, -273°C offset, unit `deg C`), SPN 1181 (Exhaust Temp Before Turbo 2, bytes 3-4, 16-bit, same) | | |
| TASK-008 | Add PGN 65175 (TC5) to `PGN_DATABASE` with `spns=(1184, 1185)`. Add SPN 1184 (Exhaust Temp After Turbo 1, bytes 1-2, 16-bit, 0.03125°C/bit, -273°C offset, unit `deg C`), SPN 1185 (Exhaust Temp After Turbo 2, bytes 3-4, same) | | |
| TASK-009 | Add PGN 65110 (AT1T1) to `PGN_DATABASE` with `spns=(1761, 3031)`. Add SPN 1761 (DEF Tank Level, byte 1, 8-bit, 0.4%/bit, unit `%`), SPN 3031 (DEF Tank Temp, byte 2, 8-bit, 1°C/bit, -40°C offset, unit `deg C`) | | |
| TASK-010 | Add PGN 64701 (AT1SI2) to `PGN_DATABASE` with `spns=(5963, 6563)`. Add SPN 5963 (Total DEF Used, bytes 1-4, 32-bit, 0.5 L/bit, unit `L`), SPN 6563 (Trip DEF Used, bytes 5-8, 32-bit, 0.5 L/bit, unit `L`) | | |
| TASK-011 | Add SPN 1601 (Local Minute Offset, byte 7, 8-bit, 1 min/bit, -125 min offset, unit `min`) and SPN 1602 (Local Hour Offset, byte 8, 8-bit, 1 h/bit, -125 h offset, unit `h`) to `SPN_DATABASE`. Update PGN 65254 `spns` tuple from `(959, 960, 961, 962, 963, 964)` to `(959, 960, 961, 962, 963, 964, 1601, 1602)` | | |

### Phase 2: MAN D2862 Profile Update

- GOAL-002: Correct existing MAN overrides and add PGN 65308 (Aux MAN Engine) as a fully defined MAN-proprietary PGN in `man_d2862.json`

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-012 | In `j1939_custom/man_d2862.json`, change SPN 168 `start_byte` from `7` to `5` to match the MAN PDF (VEP1 bytes 5-6) | | |
| TASK-013 | In `j1939_custom/man_d2862.json`, add PGN 65257 (LFC) override with `spns: [182, 250]`. Add SPN 182 override with `start_byte: 1` and SPN 250 override with `start_byte: 5` — swapping byte positions so SPN 182 moves from byte 5 (standard) to byte 1, and SPN 250 moves from byte 1 (standard) to byte 5, matching MAN D2862 layout | | |
| TASK-014 | In `j1939_custom/man_d2862.json`, add PGN 65308 definition with `name: "Auxiliary MAN Engine"`, `acronym: "AUX_MAN"`, `length: 8`. Define SPNs: (a) SPN 70000 "Gearbox Position" — byte 1, 8-bit, resolution 1, offset 0, unit `""` (use synthetic SPN number since this is MAN-proprietary with no J1939 SPN assignment); (b) SPN 70001 "Maximum Permissible Engine Load" — byte 3, 8-bit, 1%/bit, -125% offset, unit `%`; (c) SPN 70002 "Exhaust Back Pressure 2" — byte 4, 8-bit, 5 mbar/bit, 0 offset, unit `mbar`; (d) SPN 70003 "SCR System 1 Catalyst Outlet Temp" — bytes 5-6, 16-bit, 0.03125°C/bit, -273°C offset, unit `deg C`; (e) SPN 70004 "SCR System 2 Catalyst Outlet Temp" — bytes 7-8, 16-bit, 0.03125°C/bit, -273°C offset, unit `deg C` | | |
| TASK-015 | Update the profile `description` field to reflect expanded scope: `"MAN V12 marine diesel — overrides VEP1, LFC byte order; adds proprietary PGN 65308 (Aux MAN Engine)"` | | |

### Phase 3: DM1 DTC Composite Sensor

- GOAL-003: Implement DTC extraction in the coordinator and a dedicated sensor entity subclass to expose active fault count with SPN/FMI detail as state attributes

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016 | Add `FMI_DESCRIPTIONS: dict[int, str]` to `const.py` containing all 32 standard J1939 Failure Mode Identifiers: `{0: "Data valid but above normal operational range", 1: "Data valid but below normal operational range", 2: "Data erratic, intermittent, or incorrect", 3: "Voltage above normal or shorted high", 4: "Voltage below normal or shorted low", 5: "Current below normal or open circuit", 6: "Current above normal or grounded circuit", 7: "Mechanical system not responding properly", 8: "Abnormal frequency, pulse width, or period", 9: "Abnormal update rate", 10: "Abnormal rate of change", 11: "Root cause not known", 12: "Bad intelligent device or component", 13: "Out of calibration", 14: "Special instructions", 15: "Data valid but above normal operating range - least severe", 16: "Data valid but above normal operating range - moderately severe", 17: "Data valid but below normal operating range - least severe", 18: "Data valid but below normal operating range - moderately severe", 19: "Received network data in error", 20: "Data drifted high", 21: "Data drifted low", 31: "Condition exists"}` | | |
| TASK-017 | Add `DM1_PGN = 65226` constant to `const.py` | | |
| TASK-018 | In `__init__.py` `_parse_payload()`, after the existing SPN extraction loop for each CAN frame, add DM1 detection: if `pgn == 65226`, extract the first DTC from bytes 3-6 of `data_bytes` using the bit-packing layout: `spn_lo = b[2]`, `spn_mid = b[3]`, `fmi_and_spn_hi = b[4]`, `fmi = fmi_and_spn_hi & 0x1F`, `spn_hi = (fmi_and_spn_hi >> 5) & 0x07`, `spn = spn_lo | (spn_mid << 8) | (spn_hi << 16)`, `oc = b[5] & 0x7F`. Determine fault count: if `spn == 0 and fmi == 0 and oc == 0` then 0 faults, elif `spn == 0x7FFFF and fmi == 0x1F` then 0 faults (not available), else 1 fault. Store result as `{port}.dm1_dtc` in data dict as a dict: `{"count": fault_count, "spn": spn_or_none, "fmi": fmi_or_none, "fmi_description": desc_or_none, "occurrence_count": oc_or_none}`. The sensor key `{port}.dm1_dtc` must be in `self._selected` for the value to be stored. | | |
| TASK-019 | Add `_resolve_sensor_meta()` case in `sensor.py`: if `sensor_key` ends with `.dm1_dtc`, return `SensorMeta(name="Active Fault Count (DM1)", state_class=None, icon="mdi:alert-circle", entity_category=EntityCategory.DIAGNOSTIC)` | | |
| TASK-020 | Add `SenquipDTCSensorEntity` subclass in `sensor.py`. Override `native_value` property: if coordinator data contains a dict for this key, return `data["count"]`; else return `None`. Add `extra_state_attributes` property: if coordinator data contains a dict for this key and `data["count"] > 0`, return `{"spn": data["spn"], "fmi": data["fmi"], "fmi_description": data["fmi_description"], "occurrence_count": data["occurrence_count"]}`; else return `{}`. | | |
| TASK-021 | In `sensor.py` `async_setup_entry()`, when creating entities from selected sensors: if `sensor_key` ends with `.dm1_dtc`, instantiate `SenquipDTCSensorEntity` instead of `SenquipSensorEntity` | | |

### Phase 4: Config Flow Discovery Update

- GOAL-004: Make DM1 DTC sensors discoverable and selectable during config flow setup

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-022 | In `config_flow.py` `_classify_payload()`, after the existing SPN loop for each CAN frame, add detection: if `pgn == 65226`, append a `DiscoveredSensor(key=f"{key}.dm1_dtc", name="Diagnostic Trouble Codes — DM1", sample_value="No active faults", unit=None, default_selected=True)` to the sensors list (only if not already added for this port — track with a `seen_dm1` set). Import `DM1_PGN` from `const.py` and use it for the check. | | |

### Phase 5: Unit Mappings

- GOAL-005: Add missing HA unit mappings so new SPNs display with correct device classes

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-023 | Add `"mbar": (SensorDeviceClass.PRESSURE, "mbar", SensorStateClass.MEASUREMENT)` to `SPN_UNIT_TO_HA` in `const.py` | | |
| TASK-024 | Add `"km": (SensorDeviceClass.DISTANCE, UnitOfLength.KILOMETERS, SensorStateClass.TOTAL_INCREASING)` to `SPN_UNIT_TO_HA` in `const.py`. Add `UnitOfLength` to the imports from `homeassistant.const`. | | |

### Phase 6: Tests

- GOAL-006: Add comprehensive tests for all new functionality and database entries

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-025 | In `tests/test_j1939_decoder.py`, add class `TestDM1Decoding` with: (a) `test_dm1_lamp_spns_decode_all_off` — decode frame CAN ID `0x18FECA00` data `00FF00000000FFFF`, verify SPN 987=0, SPN 624=0, SPN 623=0, SPN 1213=0; (b) `test_dm1_lamp_spns_decode_active_fault` — decode frame with data `C1FFFE00C201FFFF`, verify SPN 987=1 (protect on), SPN 623=0 (red off); (c) `test_dm1_lamp_not_available` — data `C0FF00000000FFFF`, verify SPN 1213=3 (MIL not available is preserved as raw value 3 thanks to `raw_value=True`); (d) `test_dm1_lamp_error_indicator` — data `80FF00000000FFFF`, verify SPN 1213=2 (error indicator is preserved as raw value 2 thanks to `raw_value=True`) | | |
| TASK-026 | In `tests/test_j1939_decoder.py`, add to existing database integrity section: (a) `test_new_pgns_all_have_spn_definitions` — for each of the new PGNs (65226, 65247, 65276, 65248, 65272, 65176, 65175, 65110, 64701), verify every SPN in the PGN's `spns` tuple exists in `SPN_DATABASE`; (b) `test_new_spns_reference_valid_pgns` — verify each new SPN's `pgn` field matches an entry in `PGN_DATABASE`; (c) `test_td_pgn_includes_timezone_spns` — verify PGN 65254 `spns` includes 1601 and 1602 | | |
| TASK-027 | In `tests/test_j1939_decoder.py`, add class `TestNewPGNDecoding` — (a) `test_eec3_decode` — decode a synthetic EEC3 frame, verify SPN 514 value; (b) `test_vehicle_distance_decode` — decode VD frame, verify SPN 245; (c) `test_tc4_exhaust_temps` — decode TC4 frame, verify SPN 1180 | | |
| TASK-028 | In `tests/test_parse_payload.py`, add `test_dm1_dtc_extraction_no_faults` — build a payload with a CAN frame containing DM1 PGN 65226 data `C0FF00000000FFFF`, selected sensors including `can1.dm1_dtc`, verify `data["can1.dm1_dtc"]` is `{"count": 0, "spn": None, "fmi": None, "fmi_description": None, "occurrence_count": None}` | | |
| TASK-029 | In `tests/test_parse_payload.py`, add `test_dm1_dtc_extraction_with_fault` — build a payload with DM1 data where SPN=100, FMI=1, OC=1 (hex `C1FF640001010100`), verify `data["can1.dm1_dtc"]["count"]` is 1, `spn` is 100, `fmi` is 1, `fmi_description` is `"Data valid but below normal operational range"` | | |
| TASK-030 | In `tests/test_classify_payload.py`, add `test_dm1_discovery` — build a payload with a CAN1 DM1 frame, run `_classify_payload()`, verify a sensor with key `can1.dm1_dtc` appears in the result | | |
| TASK-031 | In `tests/test_resolve_sensor_meta.py`, add class `TestResolveDM1` with `test_dm1_dtc_meta` — call `_resolve_sensor_meta("can1.dm1_dtc")`, verify `name` contains "DM1", `icon` is `"mdi:alert-circle"`, `entity_category` is `EntityCategory.DIAGNOSTIC` | | |
| TASK-032 | In `tests/test_j1939_decoder.py`, add `test_pgn_65308_not_in_builtin` — verify PGN 65308 is NOT in `PGN_DATABASE` (it's profile-only) | | |
| TASK-033 | In `tests/test_j1939_decoder.py` or `test_j1939_profile_loader.py`, add `test_man_profile_lfc_override` — load the MAN profile, merge with base, decode LFC frame `0100000002000000` with merged databases, verify SPN 182 decodes from bytes 1-4 (= 0.5 L) and SPN 250 from bytes 5-8 (= 1.0 L) | | |
| TASK-034 | In `tests/test_j1939_decoder.py` or `test_j1939_profile_loader.py`, add `test_man_profile_vep1_spn168_byte5` — load MAN profile, merge, decode VEP1 frame, verify SPN 168 is read from byte 5 not byte 7 | | |

### Phase 7: Cleanup

- GOAL-007: Remove temporary analysis scripts from workspace root

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-035 | Delete `check_dm1.py`, `check_dm1_data.py`, `check_dm1_v2.py`, `check_dm1_v3.py`, `check_dm1_v4.py`, `decode_dm1.py` from workspace root | | |

### Phase 8: Verification

- GOAL-008: Run full test suite and validate all changes

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-036 | Run `pytest tests/ -v` — all tests pass (existing + new) | | |
| TASK-037 | Verify MAN profile loads without error: run `python -c "from custom_components.senquip.j1939_profile_loader import load_profile; from pathlib import Path; load_profile(Path('custom_components/senquip/j1939_custom/man_d2862.json'))"` — exits 0 | | |
| TASK-038 | Verify no circular import issues: run `python -c "from custom_components.senquip.j1939_database import PGN_DATABASE, SPN_DATABASE; print(f'{len(PGN_DATABASE)} PGNs, {len(SPN_DATABASE)} SPNs')"` — prints updated counts | | |

## 3. Alternatives

- **ALT-001**: Use `binary_sensor` platform for DM1 lamp statuses — rejected because lamp values 0–3 carry semantic meaning (off/on/error/N/A) that a binary sensor would lose. Keeping as numeric sensors preserves all 4 states and avoids adding a new platform.
- **ALT-002**: Use HA `event` entity for DTCs — rejected because DTCs are persistent states (fault active until cleared), not transient events.
- **ALT-003**: Decode DM1 DTC bytes inside `decode_frame()` using synthetic SPNs — rejected because the DTC SPN/FMI bit-packing is non-contiguous across 4 bytes and doesn't fit the `SPNDefinition` model. Handling in `_parse_payload()` keeps the decoder pure and the composite logic where it can access the full data dict and FMI descriptions.
- **ALT-004**: Support multi-packet DM1 via transport protocol reassembly — rejected for now. The Senquip captures individual CAN frames per MQTT payload; multi-packet reassembly across potential payload boundaries is significantly more complex and would require stateful TP session tracking. Deferred to a future plan.
- **ALT-005**: Put standard PGNs (EEC3, DD, VD, etc.) in the MAN profile — rejected because these are standard J1939 PGNs that apply to all manufacturers, not just MAN.

## 4. Dependencies

- **DEP-001**: Existing `j1939_database.py` dataclass model (`PGNDefinition`, `SPNDefinition`) — `SPNDefinition` gains a `raw_value: bool = False` field (TASK-002b) to support DM1 lamp SPNs; all other entries use existing fields unchanged
- **DEP-002**: Existing `j1939_profile_loader.py` — no changes needed, MAN profile updates are JSON-only
- **DEP-003**: Existing `SenquipSensorEntity` class in `sensor.py` — the new `SenquipDTCSensorEntity` subclasses it
- **DEP-004**: `homeassistant.const.UnitOfLength` — new import needed in `const.py` for the `km` unit mapping
- **DEP-005**: J1939-71 standard and MAN D2862-LE466 J1939-71 Interface PDF — used as source of truth for byte positions, resolutions, and offsets of all new SPNs

## 5. Files

- **FILE-001**: `custom_components/senquip/j1939_database.py` — Add `raw_value: bool = False` field to `SPNDefinition`, add 9 new PGNs (65226, 65247, 65276, 65248, 65272, 65176, 65175, 65110, 64701), ~35 new SPNs, update PGN 65254 spns tuple
- **FILE-002**: `custom_components/senquip/j1939_custom/man_d2862.json` — Fix VEP1 SPN 168 byte position, add LFC byte-swap override, add PGN 65308 with 5 SPNs, update description
- **FILE-003**: `custom_components/senquip/const.py` — Add `FMI_DESCRIPTIONS` dict, `DM1_PGN` constant, `mbar` and `km` unit mappings, `UnitOfLength` import
- **FILE-004**: `custom_components/senquip/__init__.py` — Add DM1 DTC extraction in `_parse_payload()`, import `DM1_PGN` and `FMI_DESCRIPTIONS` from const
- **FILE-005**: `custom_components/senquip/sensor.py` — Add `SenquipDTCSensorEntity` subclass, add `.dm1_dtc` case in `_resolve_sensor_meta()`, update `async_setup_entry()` to use DTC entity subclass
- **FILE-006**: `custom_components/senquip/config_flow.py` — Add DM1 DTC discovery sensor in `_classify_payload()`, import `DM1_PGN`
- **FILE-001b**: `custom_components/senquip/j1939_decoder.py` — In `decode_spn()`, skip not-available/error-indicator checks when `spn_def.raw_value is True`
- **FILE-007**: `tests/test_j1939_decoder.py` — Add `TestDM1Decoding` (including `raw_value` lamp tests), `TestNewPGNDecoding` classes, database integrity tests, profile override tests
- **FILE-008**: `tests/test_parse_payload.py` — Add DM1 DTC extraction tests (no-fault, with-fault)
- **FILE-009**: `tests/test_classify_payload.py` — Add DM1 discovery test
- **FILE-010**: `tests/test_resolve_sensor_meta.py` — Add `TestResolveDM1` class

## 6. Testing

- **TEST-001**: `test_dm1_lamp_spns_decode_all_off` — Verify lamp SPN extraction from DM1 frame `00FF00000000FFFF`, expect SPN 987=0, 624=0, 623=0, 1213=0
- **TEST-001b**: `test_dm1_lamp_not_available` — Verify SPN 1213=3 (MIL not available) is preserved from frame `C0FF00000000FFFF` thanks to `raw_value=True`
- **TEST-001c**: `test_dm1_lamp_error_indicator` — Verify SPN 1213=2 (error indicator) is preserved from frame `80FF00000000FFFF` thanks to `raw_value=True`
- **TEST-002**: `test_dm1_lamp_spns_decode_active_fault` — Verify lamp SPN extraction from frame `C1FFFE00C201FFFF`, expect SPN 987=1
- **TEST-003**: `test_dm1_all_lamps_off` — Verify all lamp SPNs = 0 from frame `00FF00000000FFFF`
- **TEST-004**: `test_new_pgns_all_have_spn_definitions` — Cross-reference validation for all 9 new PGNs
- **TEST-005**: `test_new_spns_reference_valid_pgns` — Reverse cross-reference validation for all new SPNs
- **TEST-006**: `test_td_pgn_includes_timezone_spns` — Verify PGN 65254 spns tuple includes 1601 and 1602
- **TEST-007**: `test_eec3_decode` — Decode synthetic EEC3 frame, verify SPN 514 physical value
- **TEST-008**: `test_vehicle_distance_decode` — Decode synthetic VD frame, verify SPN 245 physical value
- **TEST-009**: `test_tc4_exhaust_temps` — Decode synthetic TC4 frame, verify SPN 1180 physical value
- **TEST-010**: `test_dm1_dtc_extraction_no_faults` — End-to-end: payload with DM1 no-fault frame → coordinator → `can1.dm1_dtc["count"]` = 0
- **TEST-011**: `test_dm1_dtc_extraction_with_fault` — End-to-end: payload with DM1 SPN=100/FMI=1/OC=1 (hex `C1FF640001010100`) → `count` = 1, `spn` = 100, `fmi` = 1, `fmi_description` correct
- **TEST-012**: `test_dm1_discovery` — `_classify_payload()` produces `can1.dm1_dtc` sensor from DM1 frame
- **TEST-013**: `test_dm1_dtc_meta` — `_resolve_sensor_meta("can1.dm1_dtc")` returns correct name, icon, entity_category
- **TEST-014**: `test_pgn_65308_not_in_builtin` — PGN 65308 absent from `PGN_DATABASE`
- **TEST-015**: `test_man_profile_lfc_override` — Merged MAN profile swaps LFC SPN 182/250 byte positions correctly
- **TEST-016**: `test_man_profile_vep1_spn168_byte5` — Merged MAN profile places SPN 168 at byte 5

## 7. Risks & Assumptions

- **RISK-001**: PGN 65276 (DD) byte layout varies between J1939 revisions. The SPNs listed are from the most common Version 8 layout. If the Cummins ECU uses a different revision, byte positions may be wrong. Mitigation: verify with live hex data during testing.
- **RISK-002**: Synthetic SPN numbers 70000–70004 for MAN PGN 65308 could theoretically collide with future J1939 standard assignments. Risk is negligible — the highest standardized SAE J1939 SPN numbers are well below 70000.
- **RISK-003**: Single-frame DM1 only reports the first active DTC. If an engine has multiple simultaneous faults, only the first is shown. Users see fault count = 1 even with multiple faults (multi-packet DM1 would be needed for the rest). Mitigation: document this limitation.
- **ASSUMPTION-001**: The Senquip QUAD-C2 passes DM1 frames as regular 8-byte CAN frames in the JSON payload (not pre-decoded). Confirmed by live data showing CAN ID `0x18FECA00` with 8-byte hex data.
- **ASSUMPTION-002**: All SPNs in the CAN1 Cummins QSB4.5 data follow standard J1939 byte positions without manufacturer-specific overrides. This is standard for Cummins marine engines.
- **ASSUMPTION-003**: MAN PGN 65308 SPN byte positions match the PDF `MAN D2862-LE466 J1939-71 Interface.pdf` — the PDF is the authoritative source for MAN-proprietary definitions.
- **ASSUMPTION-004**: DM1 single-frame format (≤1 active fault) is sufficient for initial release. In the observed live data, all DM1 frames contained 0 active faults in single-frame format.
- **ASSUMPTION-005**: MAN VEP1 SPN 168 is at bytes 5-6 (per PDF), not byte 7 (current profile). If live data contradicts the PDF, the byte position should be adjusted.

## 8. Related Specifications / Further Reading

- [J1939-71 Vehicle Application Layer (SAE International)](https://www.sae.org/standards/content/j1939/71/)
- [J1939 DM1 Diagnostic Message Specification](https://www.sae.org/standards/content/j1939/73/)
- [MAN D2862-LE466 J1939-71 Interface PDF](./MAN%20D2862-LE466%20J1939-71%20Interface.pdf) — Source for PGN 65308, VEP1/LFC byte layouts
- [Previous implementation plan: modularjson.md](./plan/modularjson.md) — JSON profile system that this plan extends
- [Home Assistant Sensor Entity Documentation](https://developers.home-assistant.io/docs/core/entity/sensor/)
- [Home Assistant extra_state_attributes](https://developers.home-assistant.io/docs/core/entity/#extra-state-attributes)
