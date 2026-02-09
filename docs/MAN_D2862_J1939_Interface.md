# MAN D2862-LE466 J1939-71 Interface — Extracted Reference

> Extracted from `MAN D2862-LE466 J1939-71 Interface.pdf` (20 pages) using pdfplumber.
> Source address for all MAN PGNs: **0x27** (MCS / Marine Control System).
> CAN bus: CAN-2 (bridge display interface).

---

## General Instructions (§18.1)

1. Precise scope of transmitted sensor values depends on engine project — clarify with MAN.
2. Non-present values are set to `0xFF` (1-byte) or `0xFF00` (2-byte).
3. Error-flagged values are set to `0xFE` (1-byte) or `0xFE00` (2-byte).

---

## PGN Summary Table

| § | PGN | Acronym | Name | CAN ID | Rate | Bytes |
|---|-----|---------|------|--------|------|-------|
| 18.2.1 | 61444 | EEC1 | Electronic Engine Controller 1 | `0x0CF00427` | 50 ms | 8 |
| 18.2.2 | 61443 | EEC2 | Electronic Engine Controller 2 | `0x0CF00327` | 50 ms | 8 |
| 18.2.3 | 65176 | TC4 | Turbocharger Info 4 | `0x18FE9827` | 500 ms | 8 |
| 18.2.4 | 65175 | TC5 | Turbocharger Info 5 | `0x18FE9727` | 500 ms | 8 |
| 18.2.5 | 65262 | ET1 | Engine Temperature | `0x18FEEE27` | 1000 ms | 8 |
| 18.2.6 | 65263 | EFL/P | Fluid Level Pressure | `0x18FEEF27` | 50 ms | 8 |
| 18.2.7 | 65269 | IC1 | Intake/Exhaust Conditions | `0x18FEF627` | 500 ms | 8 |
| 18.2.8 | 65271 | VEP1 | Engine Electrical Power | `0x18FEF727` | 1000 ms | 8 |
| 18.2.9 | 65110 | AT1T1 | Exhaust Fluid Tank | `0x18FE5627` | 1000 ms | 8 |
| 18.2.10 | 65272 | TF | Transmission Fluids | `0x18FEF827` | 1000 ms | 8 |
| 18.2.11 | 65254 | TD | Time/Date | `0x18FEE627` | 1000 ms | 8 |
| 18.2.12 | 65253 | EH | Engine Hours | `0x18FEE527` | 1000 ms | 8 |
| 18.2.13 | 65266 | FE | Fuel Economy | `0x18FEF227` | 100 ms | 8 |
| 18.2.14 | 65257 | LFC | Fuel Consumption | `0x18FEE927` | 1000 ms | 8 |
| 18.2.15 | 64701 | AT1SI2 | Aftertreatment 1 SCR Service Info 2 | `0x18FCBD27` | 1000 ms | 8 |
| 18.2.16 | 65308 | — | Aux MAN Engine | `0x18FF1C27` | 50 ms | 8 |
| 18.2.17 | 65226 | DM1 | Diagnostic Message 1 | `0x1CFECA27` | 1000 ms | var |

---

## PGN Byte Layouts

### 18.2.1 — EEC1 (PGN 61444) `0x0CF00427`

| Byte | SPN | Name | Resolution | Offset | Unit | Range | Notes |
|------|-----|------|------------|--------|------|-------|-------|
| 4–5 | 190 | Actual Engine Speed | 0.125 rpm/bit | 0 | rpm | 0–8031.875 | |
| 6 | — | Source Address of Controlling Device | — | — | — | — | 0x00=EDC17, 0x27=MCS |
| 1–3, 7–8 | — | — | — | — | — | — | Not supported (0xFF) |

### 18.2.2 — EEC2 (PGN 61443) `0x0CF00327`

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 2 | 91 | Throttle Position | 0.4%/bit | 0 | % | 0–100 |
| 3 | 92 | Load at Current Speed | 1%/bit | 0 | % | 0–125 |
| 1, 4–8 | — | — | — | — | — | Not supported (0xFF) |

### 18.2.3 — TC4 (PGN 65176) `0x18FE9827`

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 1–2 | 1180 | Exhaust Temp Before Turbo 1 | 0.03125°C/bit | -273°C | °C | -273–1735 |
| 3–4 | 1181 | Exhaust Temp Before Turbo 2 | 0.03125°C/bit | -273°C | °C | -273–1735 |
| 5–8 | — | — | — | — | — | Not supported (0xFFFFFFFF) |

### 18.2.4 — TC5 (PGN 65175) `0x18FE9727`

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 1–2 | 1184 | Exhaust Temp After Turbo 1 | 0.03125°C/bit | -273°C | °C | -273–1735 |
| 3–4 | 1185 | Exhaust Temp After Turbo 2 | 0.03125°C/bit | -273°C | °C | -273–1735 |
| 5–8 | — | — | — | — | — | Not supported (0xFFFFFFFF) |

### 18.2.5 — ET1 (PGN 65262) `0x18FEEE27`

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 1 | 110 | Engine Coolant Temp | 1°C/bit | -40°C | °C | -40–210 |
| 2 | 174 | Fuel Temperature | 1°C/bit | -40°C | °C | -40–210 |
| 3–4 | 175 | Engine Oil Temperature | 0.03125°C/bit | -273°C | °C | -273–1735 |
| 5–8 | — | — | — | — | — | Not supported (0xFFFFFFFF) |

### 18.2.6 — EFL/P (PGN 65263) `0x18FEEF27`

| Byte | SPN | Name | Resolution | Offset | Unit | Range | Notes |
|------|-----|------|------------|--------|------|-------|-------|
| 1 | 94 | Fuel Delivery Pressure | 40 mbar/bit | 0 | mbar | 0–10000 | |
| 2 | — | Extended Crankcase Blow-by Pressure | — | — | — | — | Not supported (0xFF) |
| 3 | 98 | Engine Oil Level | 0.4%/bit | 0 | % | 0–100 | MAN PDF mis-labels as "SPN 94" — should be SPN 98 |
| 4 | 100 | Engine Oil Pressure | 40 mbar/bit | 0 | mbar | 0–10000 | |
| 5–6 | — | Engine Crankcase Pressure | — | — | — | — | Not supported (0xFFFF) |
| 7 | 109 | Engine Coolant Pressure | 10 mbar/bit | 0 | mbar | 0–5000 | |
| 8 | 111 | Engine Coolant Level | 0.4%/bit | 0 | % | 0–100 | Binary: 0%=low, 100%=OK |

### 18.2.7 — IC1 (PGN 65269) `0x18FEF627`

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 1 | 81 | Exhaust Back Pressure | 5 mbar/bit | 0 | mbar | 0–1250 |
| 2 | 102 | Boost Pressure | 20 mbar/bit | 0 | mbar | 0–5000 |
| 3 | 105 | Intake Manifold Temp | 1°C/bit | -40°C | °C | -40–210 |
| 4–8 | — | — | — | — | — | Not supported (0xFFFFFFFFFF) |

### 18.2.8 — VEP1 (PGN 65271) `0x18FEF727` ⚠️ MAN-specific byte layout

| Byte | SPN | Name | Resolution | Offset | Unit | Range | Notes |
|------|-----|------|------------|--------|------|-------|-------|
| 1 | — | Net Battery Current | — | — | — | — | Not supported (0xFF) |
| 2 | — | Alternator Current | — | — | — | — | Not supported (0xFF) |
| 3–4 | 167 | Alternator Potential (Voltage) | 0.05 V/bit | 0 | V | 0–3212.75 | **Standard J1939 puts SPN 167 at bytes 5–6** |
| 5–6 | 168 | Battery Potential (Voltage) | 0.05 V/bit | 0 | V | 0–3212.75 | **Standard J1939 puts SPN 168 at bytes 7–8** |
| 7–8 | — | Battery Potential (Switched) | — | — | — | — | Not supported (0xFFFF) |

> **Override required**: MAN moves SPN 167 to bytes 3–4 (standard: 5–6) and SPN 168 to bytes 5–6 (standard: 7–8). The `man_d2862.json` profile must override both byte positions.

### 18.2.9 — AT1T1 (PGN 65110) `0x18FE5627`

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 1 | 1761 | Exhaust Fluid (DEF) Tank Level | 0.4%/bit | 0 | % | 0–100 |
| 2 | 3031 | Exhaust Fluid (DEF) Tank Temp | 1°C/bit | -40°C | °C | -40–210 |
| 3–8 | — | — | — | — | — | Not supported (0xFFFFFFFFFFFF) |

### 18.2.10 — TF (PGN 65272) `0x18FEF827`

| Byte | SPN | Name | Resolution | Offset | Unit | Range | Notes |
|------|-----|------|------------|--------|------|-------|-------|
| 1 | — | — | — | — | — | — | Not supported (0xFF) |
| 2 | 124 | Transmission Oil Level | 0.4%/bit | 0 | % | 0–100 | Binary: 0%=low, 100%=OK |
| 3 | 126 | Trans Filter Diff Pressure | 20 mbar/bit | 0 | mbar | 0–5000 | **MAN uses 20 mbar/bit; standard J1939 uses 2 kPa/bit (=20 mbar/bit, same)** |
| 4 | 127 | Transmission Oil Pressure | 160 mbar/bit | 0 | mbar | 0–40000 | **MAN uses 160 mbar/bit; standard J1939 uses 4 kPa/bit (=40 mbar/bit, different!)** |
| 5–6 | 177 | Transmission Oil Temp | 0.03125°C/bit | -273°C | °C | -273–1735 | MAN shows byte 4 but specifies 0.03125°C (16-bit) — PDF may have typo; treat as bytes 5–6 |
| 7–8 | — | — | — | — | — | — | Not supported (0xFFFF) |

> **Note on TF SPN 127**: MAN specifies 160 mbar/bit (=16 kPa/bit), but standard J1939 says 4 kPa/bit. These differ by 4×. The `man_d2862.json` profile may need to override SPN 127 resolution. Verify with live data.

### 18.2.11 — TD (PGN 65254) `0x18FEE627`

| Byte | SPN | Name | Resolution | Offset | Unit | Range | Notes |
|------|-----|------|------------|--------|------|-------|-------|
| 1 | 959 | Seconds | 0.25 s/bit | 0 | s | 0–59.75 | MAN internal UTC |
| 2 | 960 | Minutes | 1 min/bit | 0 | min | 0–59 | |
| 3 | 961 | Hours | 1 h/bit | 0 | h | 0–23 | |
| 4 | 963 | Month | 1 month/bit | 0 | month | 0–12 | **Standard J1939: byte 4 = SPN 962 (Day), byte 5 = SPN 963 (Month)** |
| 5 | 962 | Day | 0.25 day/bit | 0 | day | 0–31.75 | **MAN swaps Day/Month vs standard** |
| 6 | 964 | Year | 1 year/bit | 1985 | year | 1985–2235 | |
| 7 | 1601 | Local Minute Offset | 1 min/bit | -125 | min | -125–125 | |
| 8 | 1602 | Local Hour Offset | 1 h/bit | -125 | h | -125–125 | |

> **Warning**: MAN swaps bytes 4 and 5 relative to standard J1939 — Month at byte 4, Day at byte 5. Standard J1939 has Day at byte 4 (SPN 962) and Month at byte 5 (SPN 963). Our standard database follows J1939 ordering. If MAN CAN2 dates appear wrong, a profile override for byte positions is needed.

### 18.2.12 — EH (PGN 65253) `0x18FEE527`

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 1–4 | 247 | Total Engine Hours | 0.05 h/bit | 0 | h | 0–210554060.75 |
| 5–8 | — | Total Engine Revolutions | — | — | — | Not supported (0xFFFFFFFF) |

### 18.2.13 — FE (PGN 65266) `0x18FEF227`

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 1–2 | 183 | Fuel Rate | 0.05 L/h per bit | 0 | L/h | 0–3212.75 |
| 3–8 | — | — | — | — | — | Not supported (0xFFFFFFFFFFFF) |

### 18.2.14 — LFC (PGN 65257) `0x18FEE927` ⚠️ MAN-specific byte order

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 1–4 | 182 | Engine Trip Fuel | 0.5 L/bit | 0 | L | 0–2105540607.5 |
| 5–8 | 250 | Engine Total Fuel Used | 0.5 L/bit | 0 | L | 0–2105540607.5 |

> **Override required**: Standard J1939 has SPN 250 (Total) at bytes 1–4 and SPN 182 (Trip) at bytes 5–8. MAN swaps them — SPN 182 (Trip) at bytes 1–4, SPN 250 (Total) at bytes 5–8. The `man_d2862.json` profile must override both byte positions.

### 18.2.15 — AT1SI2 (PGN 64701) `0x18FCBD27`

| Byte | SPN | Name | Resolution | Offset | Unit | Range |
|------|-----|------|------------|--------|------|-------|
| 1–4 | 5963 | SCR System Total DEF Used | 0.5 L/bit | 0 | L | 0–2105540607.5 |
| 5–8 | 6563 | SCR System Trip DEF Used | 0.5 L/bit | 0 | L | 0–2105540607.5 |

### 18.2.16 — Aux MAN Engine (PGN 65308) `0x18FF1C27` ⚠️ MAN-proprietary

This is a **MAN-proprietary PGN** not in the J1939 standard. All SPNs are MAN-specific.

| Byte | SPN | Name | Resolution | Offset | Unit | Range | Notes |
|------|-----|------|------------|--------|------|-------|-------|
| 1 | — | Control bits (gearbox/engine status) | — | — | — | — | See bit-level detail below |
| 2 | — | Control bits (start/stop requests) | — | — | — | — | See bit-level detail below |
| 3 | — | Current Max Permissible Load | 1%/bit | -125% | % | -125–125 | MAN-specific |
| 4 | — | Exhaust Back Pressure 2 | 5 mbar/bit | 0 | mbar | 0–1250 | Similar to SPN 81 |
| 5–6 | — | SCR Sys 1 Catalyst Outlet Gas Temp | 0.03125°C/bit | -273°C | °C | -273–1735 | Similar to SPN 4363 |
| 7–8 | — | SCR Sys 2 Catalyst Outlet Gas Temp | 0.03125°C/bit | -273°C | °C | -273–1735 | Similar to SPN 4363 |

#### Byte 1 — Gearbox Status (bit-level)

| Bits | Name | Values |
|------|------|--------|
| 1–2 | Gearbox Neutral Position | 00=not neutral, 01=neutral, 1x=invalid |
| 3–4 | Gearbox Forward Position | 00=not forward, 01=forward, 1x=invalid |
| 5–6 | Gearbox Reverse Position | 00=not reverse, 01=reverse, 1x=invalid |
| 7–8 | — | Default `11` (not used) |

#### Byte 2 — Engine Start/Stop (bit-level)

| Bits | Name | Values |
|------|------|--------|
| 1–2 | Engine Start Request | 00=not active, 01=active, 1x=invalid |
| 3–4 | Engine Stop Request | 00=not active, 01=active, 1x=invalid |
| 5–6 | — | Not documented |
| 7–8 | — | Default `0xF` (not used) |

---

## 18.2.17 — DM1 (PGN 65226) `0x1CFECA27`

Transmission per SAE J1939-73. Rate: 1000 ms. Variable length.

### Single-Frame Format (0 or 1 active fault)

CAN ID: `0x1CFECA27`, 8 bytes.

| Byte | Field | Detail |
|------|-------|--------|
| 1 | Lamp Status | Bits 1–2: Protect Lamp (SPN 987). Bits 3–4: Amber Warning (SPN 624). Bits 5–6: Red Stop (SPN 623). Bits 7–8: MIL (SPN 1213, default `11` = not used) |
| 2 | Reserved | `0xFF` |
| 3 | SPN low byte | SPN bits — see encoding note below |
| 4 | SPN mid byte | SPN bits |
| 5 | FMI + SPN high | Bits 1–5: FMI. Bits 6–8: SPN most significant bits |
| 6 | OC + CM | Bits 1–7: Occurrence Counter. Bit 8: Conversion Method (=0) |
| 7–8 | Reserved | `0xFFFF` |

**When no fault is active**: SPN = 0, FMI = 0, OC = 0.

### Lamp Status Values (MAN-specific meanings)

| Value | Protect (SPN 987) | Amber (SPN 624) | Red Stop (SPN 623) |
|-------|-------------------|-----------------|---------------------|
| 00 | No sensor failure | No warning | No alarm |
| 01 | Sensor failure active | Warning active | Alarm active |
| 10/11 | — | — | — |

### DM1 SPN Encoding — CRITICAL NOTE

The MAN PDF describes the DTC SPN byte layout and provides worked examples. Verification of the examples reveals that the **SPN is packed MSByte-first (big-endian)**, not LSByte-first as in the standard J1939-73 little-endian formula:

```
Standard J1939-73 (little-endian):
  SPN = byte3 | (byte4 << 8) | ((byte5 >> 5) << 16)

MAN D2862 examples decode correctly only with big-endian:
  SPN = (byte3 << 11) | (byte4 << 3) | (byte5 >> 5)
```

**Verification** (from PDF page 19–20 examples):

| Bytes (3–6) | Standard LE SPN | Big-Endian SPN | MAN Expected | Match |
|-------------|-----------------|----------------|-------------|-------|
| `FE 00 C2 01` | 393470 | **520198** | 520198 (Emergency Stop) | BE ✓ |
| `00 0C 81 01` | 265216 | **100** | 100 (Oil Pressure) | BE ✓ |

> **Impact on implementation**: The DM1 DTC extraction in `_parse_payload()` may need to detect the source (CAN1=Cummins vs CAN2=MAN) and use the appropriate formula, OR verify with live CAN2 DM1 data which encoding the Senquip captures. The Cummins QSB4.5 on CAN1 should use the standard J1939-73 little-endian formula.

### Multi-Packet DM1 (>1 active fault)

Uses J1939 Transport Protocol (BAM/TP.DT):
- BAM: `0x1CECFF27` — Broadcast Announce Message
- TP.DT: `0x1CEBFF27` — Transport Protocol Data Transfer

Structure: 2 bytes lamp + unused, then 4 bytes per DTC. Max ~10 faults per MAN documentation.

> Multi-packet DM1 is out of scope for the current integration — the Senquip captures individual CAN frames, not reassembled TP sessions.

---

## DM1 Known Fault SPNs (MAN D2862)

All faults transmit with `FMI=2` for sensor failure OR the FMI listed under Warning/Alarm.

| SPN | Name | FMI (Warning/Alarm) |
|-----|------|---------------------|
| 190 | Engine Speed | 0 |
| 91 | Throttle | 14 |
| 525 | Transmission Requested Gear | 14 |
| 100 | Oil Pressure | 1 |
| 99 | Oil Filter Diff Pressure | 0 |
| 175 | Oil Temperature | 0 |
| 98 | Engine Oil Level | 14 |
| 1381 | Fuel Pressure Hand Pump | 1 |
| 94 | Fuel Supply Pressure | 1 |
| 174 | Fuel Temperature | 0 |
| 1239 | Injection Pipe Leakage | 14 |
| 97 | Water In Fuel Indicator | 14 |
| 108 | Atmospheric Pressure | 14 |
| 102 | Charge Air Pressure | 14 |
| 105 | Charge Air Temperature | 0 |
| 109 | Coolant Pressure | 1 |
| 110 | Coolant Temperature | 0 |
| 111 | Coolant Level | 1 |
| 1209 | Engine Exhaust Pressure | 0 |
| 5749 | Engine Exhaust Pressure 2 | 0 |
| 4358 | Aftertreatment 1 SCR Diff Pressure | 0 |
| 4411 | Aftertreatment 2 SCR Diff Pressure | 0 |
| 1180 | Exhaust Temp Before Turbo 1 | 0 |
| 1181 | Exhaust Temp Before Turbo 2 | 0 |
| 1184 | Exhaust Temp After Turbo 1 | 0 |
| 1185 | Exhaust Temp After Turbo 2 | 0 |
| 4363 | Aftertreatment 1 SCR Outlet Temp | 0 |
| 4415 | Aftertreatment 2 SCR Outlet Temp | 0 |
| 1761 | DEF Tank Level | 1 |
| 3031 | DEF Tank Temperature | 0 |
| 127 | Gear Oil Pressure | 1 |
| 126 | Gear Oil Filter Diff Pressure | 0 |
| 177 | Gear Oil Temperature | 0 |
| 124 | Gear Oil Level | 1 |
| 2435 | Sea Water Pressure | 1 |
| 1136 | Temperature MCS | 0 |
| 158 | Battery Voltage | 14 |
| 167 | Alternator Voltage | 14 |
| 606 | Override | 14 |
| 520192 | Engine Fuel Return Flow Pressure | 0 |
| 520194 | Sea Water Temperature | 0 |
| 520196 | Temperature Plug X1 | 1 |
| 520197 | Reduction by Partner Engine | 14 |
| 520198 | Emergency Stop | 14 |
| 520199 | Alarm Safety System | 14 |
| 520200 | General Electronic Error | 14 |
| 520201 | Engine Stop by Safety System | 14 |
| 520202 | Engine Start Prevented | 14 |
| 520203 | MAN Emergency Operation Units | 14 |
| 520204 | MAN Start/Stop Unit | 14 |
| 520205 | MAN Local Operation Unit | 14 |
| 520206 | Engine is Operating in Overload | 0 |
| 520207 | Inducement Failure DEF Tank Level | 14 |
| 520208 | Inducement Failure DEF Quality | 14 |
| 520209 | Inducement Failure Dosing System Error | 14 |
| 520210 | Inducement Failure Interrupt of Dosing | 14 |
| 520211 | Oil Temperature Axial Bearing | 0 |
| 520212 | Gear Lube Oil Pressure | 1 |

---

## MAN-Specific Deviations from Standard J1939

| PGN | Field | Standard J1939 | MAN D2862 | Override Needed |
|-----|-------|----------------|-----------|-----------------|
| 65271 (VEP1) | SPN 167 byte position | Bytes 5–6 | **Bytes 3–4** | Yes |
| 65271 (VEP1) | SPN 168 byte position | Bytes 7–8 | **Bytes 5–6** | Yes |
| 65257 (LFC) | SPN 182 byte position | Bytes 5–8 | **Bytes 1–4** | Yes |
| 65257 (LFC) | SPN 250 byte position | Bytes 1–4 | **Bytes 5–8** | Yes |
| 65254 (TD) | SPN 962 (Day) byte | Byte 4 | **Byte 5** | Maybe — verify |
| 65254 (TD) | SPN 963 (Month) byte | Byte 5 | **Byte 4** | Maybe — verify |
| 65272 (TF) | SPN 127 resolution | 4 kPa/bit | **160 mbar/bit (16 kPa/bit)** | Maybe — verify |
| 65226 (DM1) | SPN byte order in DTC | Little-endian | **Big-endian** | Needs investigation |
| 65308 | Entire PGN | Not in standard | **MAN-proprietary** | Profile-only |

---

## CAN Trace Example (from PDF page 19)

```
Timestamp  ID          Name                    DLC Data
1.200000   1CFECA27    DM_1_MAN-Engine         8   C1 FF FE 00 C2 01 FF FF
2.200000   1CFECA27    DM_1_MAN-Engine         8   C1 FF FE 00 C2 01 FF FF
3.200000   1CECFF27    BAM_MAN-Engine          8   20 0A 00 02 FF CA FE 00
3.250000   1CEBFF27    P_MAN-Engine            8   01 D1 FF FE 00 C2 01 00
3.300000   1CEBFF27    P_MAN-Engine            8   02 0C 81 01 FF FF FF FF
```

Decoded:
- **Single-frame DM1** (`C1 FF FE 00 C2 01 FF FF`): Protect Lamp ON (sensor failure active), SPN 520198 (Emergency Stop), FMI 2 (sensor failure), OC 1.
- **Multi-packet DM1** (2 faults): Fault 1 = SPN 520198/FMI 2, Fault 2 = SPN 100 (Oil Pressure)/FMI 1.
