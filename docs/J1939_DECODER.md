# J1939 Decoder Specification

## Overview

The J1939 decoder converts raw CAN bus frames from Senquip devices into meaningful physical values. CAN frames arrive as JSON objects with a decimal CAN ID and hex data string:

```json
{"id": 217056256, "data": "3FFFCD883927F4FF"}
```

The decoder:
1. Extracts the PGN (Parameter Group Number) from the 29-bit CAN ID
2. Looks up known SPNs (Suspect Parameter Numbers) for that PGN
3. Extracts raw bit values from the data payload
4. Applies resolution and offset to produce physical values

---

## CAN ID Structure

J1939 uses 29-bit extended CAN identifiers. The Senquip JSON provides these as **decimal integers**.

```
Bit 28-26:  Priority (3 bits)
Bit 25:     Reserved
Bit 24:     Data Page (DP)
Bit 23-16:  PDU Format (PF)
Bit 15-8:   PDU Specific (PS)
              - If PF >= 240: PS = Group Extension (part of PGN)
              - If PF < 240:  PS = Destination Address (not part of PGN)
Bit 7-0:    Source Address (SA)
```

### PGN Extraction

```python
def extract_pgn(can_id: int) -> tuple[int, int, int]:
    """Extract (priority, pgn, source_address) from 29-bit J1939 CAN ID."""
    source = can_id & 0xFF
    pf = (can_id >> 16) & 0xFF
    ps = (can_id >> 8) & 0xFF
    dp = (can_id >> 24) & 0x01
    priority = (can_id >> 26) & 0x7

    if pf >= 240:
        # PDU2 (broadcast): PGN includes Group Extension
        pgn = (dp << 16) | (pf << 8) | ps
    else:
        # PDU1 (peer-to-peer): PS is destination, not part of PGN
        pgn = (dp << 16) | (pf << 8)

    return priority, pgn, source
```

### Verification

| CAN ID (decimal) | CAN ID (hex) | PF | PS | PGN | PGN Name |
|---|---|---|---|---|---|
| 217056256 | 0x0CF00400 | 0xF0 (240) | 0x04 | 61444 | EEC1 |
| 217056000 | 0x0CF00300 | 0xF0 (240) | 0x03 | 61443 | EEC2 |
| 419360256 | 0x18FEEE00 | 0xFE (254) | 0xEE | 65262 | ET1 |
| 419360512 | 0x18FEEF00 | 0xFE (254) | 0xEF | 65263 | EFL/P1 |
| 419361280 | 0x18FEF200 | 0xFE (254) | 0xF2 | 65266 | LFE1 |
| 419357952 | 0x18FEE500 | 0xFE (254) | 0xE5 | 65253 | HOURS |
| 419358976 | 0x18FEE900 | 0xFE (254) | 0xE9 | 65257 | LFC |
| 419362304 | 0x18FEF600 | 0xFE (254) | 0xF6 | 65270 | IC1 |
| 419358208 | 0x18FEE600 | 0xFE (254) | 0xE6 | 65254 | TD |
| 419362560 | 0x18FEF700 | 0xFE (254) | 0xF7 | 65271 | VEP1 |
| 419362816 | 0x18FEF800 | 0xFE (254) | 0xF8 | 65272 | — |
| 419338240 | 0x18FE9800 | 0xFE (254) | 0x98 | 65176 | — |
| 419351040 | 0x18FECA00 | 0xFE (254) | 0xCA | 65226 | — |
| 419337984 | 0x18FE9700 | 0xFE (254) | 0x97 | 65175 | — |
| 419321344 | 0x18FE5600 | 0xFE (254) | 0x56 | 65110 | — |
| 419372032 | 0x18FF1C00 | 0xFF (255) | 0x1C | 65308 | Proprietary |

---

## SPN Decoding

### Data Model

```python
@dataclass(frozen=True, slots=True)
class SPNDefinition:
    spn: int               # SPN number (e.g., 190)
    name: str              # Human-readable name (e.g., "Engine Speed")
    pgn: int               # Parent PGN number
    start_byte: int        # 1-indexed byte position in 8-byte payload
    start_bit: int         # 1-indexed bit within start byte (1=LSB, 8=MSB)
    bit_length: int        # Total number of bits
    resolution: float      # Physical = raw * resolution + offset
    offset: float          # Offset value
    unit: str              # Unit string (e.g., "rpm", "deg C", "km/h")
    min_value: float | None = None
    max_value: float | None = None

@dataclass(frozen=True, slots=True)
class PGNDefinition:
    pgn: int               # PGN number
    name: str              # Full name
    acronym: str           # Short name (e.g., "EEC1")
    length: int            # Data length in bytes (typically 8)
    spns: tuple[int, ...]  # SPN numbers in this PGN
```

### Decoding Algorithm

```python
def decode_spn(spn_def: SPNDefinition, data_bytes: bytes) -> float | None:
    """Decode a single SPN value from CAN data bytes.

    Returns None if the value indicates 'not available' (all bits = 1)
    or 'error' (all bits = 1 except LSB = 0).
    """
    start_idx = spn_def.start_byte - 1  # Convert to 0-indexed
    byte_count = (spn_def.bit_length + 7) // 8

    # Bounds check
    if start_idx + byte_count > len(data_bytes):
        return None

    # Read bytes (J1939 uses little-endian for multi-byte values)
    raw_bytes = data_bytes[start_idx : start_idx + byte_count]
    raw_value = int.from_bytes(raw_bytes, byteorder="little")

    # Sub-byte extraction: shift and mask for bit position
    if spn_def.bit_length < 8 or spn_def.start_bit > 1:
        shift = spn_def.start_bit - 1
        mask = (1 << spn_def.bit_length) - 1
        raw_value = (raw_value >> shift) & mask

    # Not-available: all bits set to 1
    not_available = (1 << spn_def.bit_length) - 1
    if raw_value == not_available:
        return None

    # Error indicator: all bits = 1 except LSB = 0 (e.g., 0xFE for 8-bit)
    error_indicator = not_available - 1
    if raw_value == error_indicator:
        return None

    # Apply resolution and offset
    physical_value = (raw_value * spn_def.resolution) + spn_def.offset

    return round(physical_value, 4)
```

### Frame Decoding

```python
def decode_frame(self, can_id: int, hex_data: str) -> dict[int, float | None]:
    """Decode all known SPNs from a CAN frame.

    Args:
        can_id: 29-bit CAN ID as decimal integer
        hex_data: Data payload as hex string (e.g., "3FFFCD883927F4FF")

    Returns:
        Dict mapping SPN number to decoded physical value (or None if not available)
    """
    _, pgn, _ = self.extract_pgn(can_id)
    data_bytes = bytes.fromhex(hex_data)

    pgn_def = PGN_DATABASE.get(pgn)
    if pgn_def is None:
        return {}  # Unknown PGN

    results = {}
    for spn_num in pgn_def.spns:
        spn_def = SPN_DATABASE.get(spn_num)
        if spn_def is None:
            continue
        value = self.decode_spn(spn_def, data_bytes)
        results[spn_num] = value

    return results
```

---

## PGN/SPN Database

### Initial Coverage (9 PGNs from example data)

#### PGN 61444 — EEC1 (Electronic Engine Controller 1)

| SPN | Name | Byte | Bit | Length | Resolution | Offset | Unit | Range |
|-----|------|------|-----|--------|------------|--------|------|-------|
| 899 | Engine Torque Mode | 1 | 1 | 4 bits | 1 | 0 | — | 0-15 |
| 512 | Driver's Demand Torque | 2 | 1 | 8 bits | 1 | -125 | % | -125 to 125 |
| 513 | Actual Engine Torque | 3 | 1 | 8 bits | 1 | -125 | % | -125 to 125 |
| 190 | Engine Speed | 4 | 1 | 16 bits | 0.125 | 0 | rpm | 0-8031.875 |
| 1483 | Source Address | 6 | 1 | 8 bits | 1 | 0 | — | 0-255 |
| 2432 | Engine Demand Torque | 8 | 1 | 8 bits | 1 | -125 | % | -125 to 125 |

#### PGN 61443 — EEC2 (Electronic Engine Controller 2)

| SPN | Name | Byte | Bit | Length | Resolution | Offset | Unit | Range |
|-----|------|------|-----|--------|------------|--------|------|-------|
| 29 | Accel Pedal Low Idle Switch | 1 | 1 | 2 bits | 1 | 0 | — | 0-3 |
| 91 | Accelerator Pedal Position 1 | 2 | 1 | 8 bits | 0.4 | 0 | % | 0-100 |
| 92 | Engine Percent Load | 3 | 1 | 8 bits | 1 | 0 | % | 0-250 |
| 974 | Remote Accel Pedal Position | 4 | 1 | 8 bits | 0.4 | 0 | % | 0-100 |
| 2970 | Accelerator Pedal Position 2 | 6 | 1 | 8 bits | 0.4 | 0 | % | 0-100 |

#### PGN 65262 — ET1 (Engine Temperature 1)

| SPN | Name | Byte | Bit | Length | Resolution | Offset | Unit | Range |
|-----|------|------|-----|--------|------------|--------|------|-------|
| 110 | Engine Coolant Temperature | 1 | 1 | 8 bits | 1 | -40 | deg C | -40 to 210 |
| 174 | Fuel Temperature 1 | 2 | 1 | 8 bits | 1 | -40 | deg C | -40 to 210 |
| 175 | Engine Oil Temperature 1 | 3 | 1 | 16 bits | 0.03125 | -273 | deg C | -273 to 1735 |
| 176 | Turbo Oil Temperature | 5 | 1 | 16 bits | 0.03125 | -273 | deg C | -273 to 1735 |
| 52 | Engine Intercooler Temp | 7 | 1 | 8 bits | 1 | -40 | deg C | -40 to 210 |
| 1134 | Intercooler Thermostat Opening | 8 | 1 | 8 bits | 0.4 | 0 | % | 0-100 |

#### PGN 65265 — CCVS1 (Cruise Control / Vehicle Speed)

| SPN | Name | Byte | Bit | Length | Resolution | Offset | Unit | Range |
|-----|------|------|-----|--------|------------|--------|------|-------|
| 70 | Parking Brake Switch | 1 | 1 | 2 bits | 1 | 0 | — | 0-3 |
| 84 | Wheel-Based Vehicle Speed | 2 | 1 | 16 bits | 1/256 | 0 | km/h | 0-250.996 |
| 595 | Cruise Control Active | 4 | 1 | 2 bits | 1 | 0 | — | 0-3 |
| 596 | Cruise Control Enable Switch | 4 | 3 | 2 bits | 1 | 0 | — | 0-3 |
| 597 | Brake Switch | 4 | 5 | 2 bits | 1 | 0 | — | 0-3 |
| 598 | Clutch Switch | 4 | 7 | 2 bits | 1 | 0 | — | 0-3 |
| 86 | Cruise Control Set Speed | 6 | 1 | 8 bits | 1 | 0 | km/h | 0-250 |

#### PGN 65253 — HOURS (Engine Hours, Revolutions)

| SPN | Name | Byte | Bit | Length | Resolution | Offset | Unit | Range |
|-----|------|------|-----|--------|------------|--------|------|-------|
| 247 | Engine Total Hours of Operation | 1 | 1 | 32 bits | 0.05 | 0 | h | 0-210554060.75 |
| 249 | Engine Total Revolutions | 5 | 1 | 32 bits | 1000 | 0 | rev | 0-4211081215000 |

#### PGN 65257 — LFC (Fuel Consumption, Liquid)

| SPN | Name | Byte | Bit | Length | Resolution | Offset | Unit | Range |
|-----|------|------|-----|--------|------------|--------|------|-------|
| 250 | Engine Total Fuel Used | 1 | 1 | 32 bits | 0.5 | 0 | L | 0-2105540607.5 |
| 252 | Engine Trip Fuel | 5 | 1 | 32 bits | 0.5 | 0 | L | 0-2105540607.5 |

#### PGN 65269 — AMB (Ambient Conditions)

| SPN | Name | Byte | Bit | Length | Resolution | Offset | Unit | Range |
|-----|------|------|-----|--------|------------|--------|------|-------|
| 108 | Barometric Pressure | 1 | 1 | 8 bits | 0.5 | 0 | kPa | 0-125 |
| 170 | Cab Interior Temperature | 2 | 1 | 16 bits | 0.03125 | -273 | deg C | -273 to 1735 |
| 171 | Ambient Air Temperature | 4 | 1 | 16 bits | 0.03125 | -273 | deg C | -273 to 1735 |
| 172 | Air Inlet Temperature | 6 | 1 | 8 bits | 1 | -40 | deg C | -40 to 210 |
| 79 | Road Surface Temperature | 7 | 1 | 16 bits | 0.03125 | -273 | deg C | -273 to 1735 |

#### PGN 65254 — TD (Time/Date)

| SPN | Name | Byte | Bit | Length | Resolution | Offset | Unit | Range |
|-----|------|------|-----|--------|------------|--------|------|-------|
| 959 | Seconds | 1 | 1 | 8 bits | 0.25 | 0 | s | 0-59.75 |
| 960 | Minutes | 2 | 1 | 8 bits | 1 | 0 | min | 0-59 |
| 961 | Hours | 3 | 1 | 8 bits | 1 | 0 | h | 0-23 |
| 962 | Month | 4 | 1 | 8 bits | 1 | 0 | month | 1-12 |
| 963 | Day | 5 | 1 | 8 bits | 0.25 | 0 | day | 0.25-31.0 |
| 964 | Year | 6 | 1 | 8 bits | 1 | 1985 | year | 1985-2235 |

#### PGN 65263 — EFL/P1 (Engine Fluid Level/Pressure 1)

| SPN | Name | Byte | Bit | Length | Resolution | Offset | Unit | Range |
|-----|------|------|-----|--------|------------|--------|------|-------|
| 94 | Fuel Delivery Pressure | 1 | 1 | 8 bits | 4 | 0 | kPa | 0-1000 |
| 22 | Extended Crankcase Blow-by Pressure | 2 | 1 | 8 bits | 0.05 | 0 | kPa | 0-12.5 |
| 98 | Engine Oil Level | 3 | 1 | 8 bits | 0.4 | 0 | % | 0-100 |
| 100 | Engine Oil Pressure | 4 | 1 | 8 bits | 4 | 0 | kPa | 0-1000 |
| 101 | Crankcase Pressure | 5 | 1 | 16 bits | 1/128 | -250 | kPa | -250 to 252 |
| 109 | Coolant Pressure | 7 | 1 | 8 bits | 2 | 0 | kPa | 0-500 |
| 111 | Coolant Level | 8 | 1 | 8 bits | 0.4 | 0 | % | 0-100 |

---

## Verification Against Example Data

### Device HE8EV12LF, CAN2

**Frame:** `{"id": 217056256, "data": "3FFFCD883927F4FF"}`
- PGN: 61444 (EEC1)
- Bytes: `[0x3F, 0xFF, 0xCD, 0x88, 0x39, 0x27, 0xF4, 0xFF]`
- SPN 190 (Engine Speed): bytes 4-5 = `[0x88, 0x39]`, LE uint16 = 0x3988 = 14728, x 0.125 = **1841.0 rpm**
- SPN 513 (Actual Torque): byte 3 = 0xCD = 205, + (-125) = **80%**
- Cross-check: cp28 = 1841 (matches engine speed!)

**Frame:** `{"id": 419360512, "data": "A0FFFFB3FFFF9CFA"}`
- PGN: 65263 (EFL/P1)
- Bytes: `[0xA0, 0xFF, 0xFF, 0xB3, 0xFF, 0xFF, 0x9C, 0xFA]`
- SPN 94 (Fuel Delivery Pressure): byte 1 = 0xA0 = 160, x 4 = **640 kPa**
- SPN 100 (Engine Oil Pressure): byte 4 = 0xB3 = 179, x 4 = **716 kPa**

**Frame:** `{"id": 419361280, "data": "FF0F32000000FFFF"}`
- PGN: 65266 (LFE1)
- Bytes: `[0xFF, 0x0F, 0x32, 0x00, 0x00, 0x00, 0xFF, 0xFF]`
- SPN 183 (Fuel Rate): bytes 1-2 = `[0xFF, 0x0F]`, LE uint16 = 0x0FFF = 4095, x 0.05 = **204.75 L/h**

**Frame:** `{"id": 419357952, "data": "5F27000000000000"}`
- PGN: 65253 (HOURS)
- SPN 247 (Total Hours): bytes 1-4 = `[0x5F, 0x27, 0x00, 0x00]`, LE uint32 = 0x0000275F = 10079, x 0.05 = **503.95 h**
- Cross-check: cp18 = 504 (matches!)

**Frame:** `{"id": 419358976, "data": "E2020000BC1E0200"}`
- PGN: 65257 (LFC)
- SPN 250 (Total Fuel): bytes 1-4 = `[0xE2, 0x02, 0x00, 0x00]`, LE uint32 = 0x000002E2 = 738, x 0.5 = **369.0 L**
- SPN 252 (Trip Fuel): bytes 5-8 = `[0xBC, 0x1E, 0x02, 0x00]`, LE uint32 = 0x00021EBC = 138940, x 0.5 = **69470.0 L**

---

## Handling Unknown PGNs

When a CAN frame's PGN is not in `PGN_DATABASE`:
1. The frame is still reported during discovery as "Unknown PGN XXXXX (raw)"
2. The sample value shown is the hex data string
3. It defaults to NOT selected in the sensor selection step
4. If selected, it creates a text sensor showing the raw hex data
5. Users can extend `j1939_database.py` with new PGN/SPN definitions

### Extensibility

To add a new PGN, users add entries to `j1939_database.py`:
```python
# Add to PGN_DATABASE
65180: PGNDefinition(pgn=65180, name="My Custom PGN", acronym="MCP", length=8, spns=(9999,)),

# Add to SPN_DATABASE
9999: SPNDefinition(spn=9999, name="My Custom Value", pgn=65180,
                     start_byte=1, start_bit=1, bit_length=16,
                     resolution=0.1, offset=0, unit="bar"),
```

---

## Same SPN on Multiple Ports

A device may report the same PGN on both CAN1 and CAN2 (seen in example data where both ports carry EEC1). The sensor key includes the port name for uniqueness:
- `can1.spn190` = "CAN1 Engine Speed"
- `can2.spn190` = "CAN2 Engine Speed"

### Same PGN, Different Source Addresses

In v1, if the same PGN appears multiple times on one port from different source addresses, the last frame wins. A future enhancement could incorporate source address into the key: `can2.sa0.spn190`.
