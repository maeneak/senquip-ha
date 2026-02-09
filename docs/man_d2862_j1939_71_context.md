# MAN D2862-LE466 J1939-71 Interface - Context

Source: MAN D2862-LE466 J1939-71 Interface.pdf (Interface CAN-2 touch display, section 18.2.*)

This file summarizes the CAN-2 "Display - Send Messages" layouts, identifiers, PGNs, SPNs, scaling, offsets, and special rules, exactly as documented in the PDF.

## General Rules
- Non-present values: 0xFF (1 byte) or 0xFF00 (2 bytes).
- Error values: 0xFE (1 byte) or 0xFE00 (2 bytes).
- "Not supported" bytes are sent as 0xFF or 0xFFFF.

## Message Index
| Section | Name | Identifier | PGN (hex) | PGN (dec) | Rate | Length | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 18.2.1 | EEC1 | 0x0C F0 04 27 | 0x0F004 | 61444 | 10 ms | 8 | Engine speed/torque |
| 18.2.2 | EEC2 | 0x0C F0 03 27 | 0x0F003 | 61443 | 50 ms | 8 | Throttle/load |
| 18.2.3 | Turbocharger Info 4 | 0x18 FE 98 27 | 0x0FE98 | 65176 | 500 ms | 8 | Exhaust temps before turbo |
| 18.2.4 | Turbocharger Info 5 | 0x18 FE 97 27 | 0x0FE97 | 65175 | 500 ms | 8 | Exhaust temps after turbo |
| 18.2.5 | Engine Temperature | 0x18 FE EE 27 | 0x0FEEE | 65262 | 1000 ms | 8 | Coolant/fuel/oil temps |
| 18.2.6 | Fluid Level Pressure | 0x18 FE EF 27 | 0x0FEEF | 65263 | 50 ms | 8 | Fuel/oil/coolant pressures and levels |
| 18.2.7 | Intake/Exhaust Conditions | 0x18 FE F6 27 | 0x0FEF6 | 65270 | 500 ms | 8 | Exhaust back pressure, boost, intake temp |
| 18.2.8 | Engine Electrical Power | 0x18 FE F7 27 | 0x0FEF7 | 65271 | 1000 ms | 8 | Alternator/electrical potential |
| 18.2.9 | Exhaust Fluid Tank | 0x18 FE 56 27 | 0x0FE56 | 65110 | 1000 ms | 8 | DEF level/temp |
| 18.2.10 | Transmission Fluids | 0x18 FE F8 27 | 0x0FEF8 | 65272 | 1000 ms | 8 | Transmission oil level/pressure/temp |
| 18.2.11 | Time/Date | 0x18 FE E6 27 | 0x0FEE6 | 65254 | 1000 ms | 8 | MAN internal UTC and offsets |
| 18.2.12 | Engine Hours | 0x18 FE E5 27 | 0x0FEE5 | 65253 | 1000 ms | 8 | Total engine hours |
| 18.2.13 | Fuel Economy | 0x18 FE F2 27 | 0x0FEF2 | 65266 | 100 ms | 8 | Fuel rate |
| 18.2.14 | Fuel Consumption | 0x18 FE E9 27 | 0x0FEE9 | 65257 | 1000 ms | 8 | Trip/total fuel used |
| 18.2.15 | Aftertreatment 1 SCR Service Info 2 | 0x18 FC BD 27 | 0x0FCBD | 64701 | 1000 ms | 8 | SCR DEF used |
| 18.2.16 | Aux MAN Engine | 0x18 FF 1C 27 | 0x0FF1C | 65308 | 50 ms | 8 | MAN-specific gearbox/start/stop + SCR temps |
| 18.2.17 | DM_1_MAN-Engine | 0x1C FE CA 27 | 0x0FECA | 65226 | 1000 ms | variable | DM1 single and multi-packet |
| 18.2.17 | BAM_MAN-Engine_to_global | 0x1C EC FF 27 | 0x0EC00 | 60416 | N/A | 8 | J1939-73 BAM for DM1 |
| 18.2.17 | P_MAN-Engine_to_global | 0x1C EB FF 27 | 0x0EB00 | 60160 | N/A | 8 | J1939-73 TP.DT for DM1 |

## 18.2.1 EEC1 (PGN 61444)
Identifier: 0x0C F0 04 27
Rate: 10 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-4 | N/A | Control bits | N/A | N/A | N/A | N/A | Default value 0xF, not supported |
| 1 | 5-8 | 4154 | Actual engine - percent torque high resolution | 0.125 % step | 0 | 0.000 to 0.875 | % | 4-bit field; values 8-15 not available |
| 2 | 1-8 | N/A | Drivers demand engine torque | N/A | N/A | N/A | N/A | Not supported (0xFF) |
| 3 | 1-8 | 513 | Actual engine torque | 1 %/bit | -125 | -125 to 125 | % | N/A |
| 4-5 | 1-16 | 190 | Actual engine speed | 0.125 rpm/bit | 0 | 0 to 8031.875 | rpm | N/A |
| 6 | 1-8 | 1483 | Source address of controlling device for engine control | N/A | N/A | N/A | N/A | 0x00 EDC17, 0x27 MCS, 0xD0..0xD5 emergency stand 1..6, 0xF2 local drive from engine display |
| 7 | 1-4 | 1675 | Engine starter mode | N/A | N/A | N/A | N/A | 000 start not requested, 001 before start, 010 start, 100 after start |
| 7 | 5-8 | N/A | Control bits | N/A | N/A | N/A | N/A | Default value 0xF, not supported |
| 8 | 1-8 | N/A | Engine demand, percent torque | N/A | N/A | N/A | N/A | Not supported (0xFF) |

## 18.2.2 EEC2 (PGN 61443)
Identifier: 0x0C F0 03 27
Rate: 50 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-8 | N/A | Default value | N/A | N/A | N/A | N/A | Not supported (0xFF) |
| 2 | 1-8 | 91 | Throttle position | 0.4 %/bit | 0 | 0 to 100 | % | N/A |
| 3 | 1-8 | 92 | Load at current speed | 1 %/bit | 0 | 0 to 125 | % | N/A |
| 4-8 | 1-40 | N/A | Default value | N/A | N/A | N/A | N/A | Not supported (0xFF FF FF FF FF) |

## 18.2.3 Turbocharger Info 4 (PGN 65176)
Identifier: 0x18 FE 98 27
Rate: 500 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1-2 | 1-16 | 1180 | Exhaust temperature before turbo 1 | 0.03125 deg C/bit | -273 | -273 to 1735 | deg C | N/A |
| 3-4 | 1-16 | 1181 | Exhaust temperature before turbo 2 | 0.03125 deg C/bit | -273 | -273 to 1735 | deg C | N/A |
| 5-8 | 1-32 | N/A | Default value | N/A | N/A | N/A | N/A | Not supported (0xFF FF FF FF) |

## 18.2.4 Turbocharger Info 5 (PGN 65175)
Identifier: 0x18 FE 97 27
Rate: 500 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1-2 | 1-16 | 1184 | Exhaust temperature after turbo 1 | 0.03125 deg C/bit | -273 | -273 to 1735 | deg C | N/A |
| 3-4 | 1-16 | 1185 | Exhaust temperature after turbo 2 | 0.03125 deg C/bit | -273 | -273 to 1735 | deg C | N/A |
| 5-8 | 1-32 | N/A | Default value | N/A | N/A | N/A | N/A | Not supported (0xFF FF FF FF) |

## 18.2.5 Engine Temperature (PGN 65262)
Identifier: 0x18 FE EE 27
Rate: 1000 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-8 | 110 | Engine coolant temperature | 1 deg C/bit | -40 | -40 to 210 | deg C | N/A |
| 2 | 1-8 | 174 | Fuel temperature | 1 deg C/bit | -40 | -40 to 210 | deg C | N/A |
| 3-4 | 1-16 | 175 | Engine oil temperature | 0.03125 deg C/bit | -273 | -273 to 1735 | deg C | N/A |
| 5-8 | 1-32 | N/A | Default value | N/A | N/A | N/A | N/A | Not supported (0xFF FF FF FF) |

## 18.2.6 Fluid Level Pressure (PGN 65263)
Identifier: 0x18 FE EF 27
Rate: 50 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-8 | 94 | Engine fuel delivery pressure | 40 mbar/bit | 0 | 0 to 10 | bar | N/A |
| 2 | 1-8 | N/A | Extended crankcase blow-by pressure | N/A | N/A | N/A | N/A | Not supported (0xFF) |
| 3 | 1-8 | 94 | Engine oil level | 0.4 %/bit | 0 | 0 to 100 | % | PDF lists SPN 94 here |
| 4 | 1-8 | 100 | Engine oil pressure | 40 mbar/bit | 0 | 0 to 10 | bar | N/A |
| 5-6 | 1-16 | N/A | Engine crankcase pressure | N/A | N/A | N/A | N/A | Not supported (0xFF FF) |
| 7 | 1-8 | 109 | Engine coolant pressure | 10 mbar/bit | 0 | 0 to 5 | bar | N/A |
| 8 | 1-8 | 111 | Engine coolant level | 0.4 %/bit | 0 | 0 to 100 | % | Only two states: 0% low level detected, 100% no low level detected |

## 18.2.7 Intake/Exhaust Conditions (PGN 65270)
Identifier: 0x18 FE F6 27
Rate: 500 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-8 | 81 | Exhaust back pressure | 5 mbar/bit | 0 | 0 to 1.25 | bar | N/A |
| 2 | 1-8 | 102 | Boost pressure | 20 mbar/bit | 0 | 0 to 5 | bar | N/A |
| 3 | 1-8 | 105 | Intake manifold temperature | 1 deg C/bit | -40 | -40 to 210 | deg C | N/A |
| 4-8 | 1-40 | N/A | Default value | N/A | N/A | N/A | N/A | Not supported (0xFF FF FF FF FF) |

## 18.2.8 Engine Electrical Power (PGN 65271)
Identifier: 0x18 FE F7 27
Rate: 1000 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-8 | N/A | Net battery current | N/A | N/A | N/A | N/A | Not supported (0xFF) |
| 2 | 1-8 | N/A | Alternator current | N/A | N/A | N/A | N/A | Not supported (0xFF) |
| 3-4 | 1-16 | 167 | Alternator potential (voltage) | 0.05 V/bit | 0 | 0 to 3212.75 | V | N/A |
| 5-6 | 1-16 | 168 | Electrical potential (voltage) | 0.05 V/bit | 0 | 0 to 3212.75 | V | N/A |
| 7-8 | 1-16 | N/A | Battery potential (voltage), switched | N/A | N/A | N/A | N/A | Not supported (0xFF FF) |

## 18.2.9 Exhaust Fluid Tank (PGN 65110)
Identifier: 0x18 FE 56 27
Rate: 1000 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-8 | 1761 | Exhaust fluid tank level | 0.4 %/bit | 0 | 0 to 100 | % | N/A |
| 2 | 1-8 | 3031 | Exhaust fluid tank temperature | 1 deg C/bit | -40 | -40 to 210 | deg C | N/A |
| 3-8 | 1-48 | N/A | Default value | N/A | N/A | N/A | N/A | Not supported (0xFF FF FF FF FF FF) |

## 18.2.10 Transmission Fluids (PGN 65272)
Identifier: 0x18 FE F8 27
Rate: 1000 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-8 | N/A | Default value | N/A | N/A | N/A | N/A | Not supported (0xFF) |
| 2 | 1-8 | 124 | Transmission oil level | 0.4 %/bit | 0 | 0 to 100 | % | Only two states: 0% low level detected, 100% no low level detected |
| 2 | 1-8 | 126 | Transmission filter differential pressure | 20 mbar/bit | 0 | 0 to 5 | bar | PDF labels this as Byte 2 |
| 3 | 1-8 | 127 | Transmission oil pressure | 160 mbar/bit | 0 | 0 to 40 | bar | N/A |
| 4 | 1-8 | 177 | Transmission oil temperature | 0.03125 deg C/bit | -273 | -273 to 1735 | deg C | N/A |
| 3-8 | 1-48 | N/A | Default value | N/A | N/A | N/A | N/A | PDF states "Byte 3-8: Default Value = 0xFF FF, Not supported" |

## 18.2.11 Time/Date (PGN 65254)
Identifier: 0x18 FE E6 27
Rate: 1000 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-8 | 959 | Seconds (MAN internal UTC) | 0.25 s/bit | 0 | 0 to 59.75 | s | N/A |
| 2 | 1-8 | 960 | Minutes (MAN internal UTC) | 1 min/bit | 0 | 0 to 59 | min | N/A |
| 3 | 1-8 | 961 | Hours (MAN internal UTC) | 1 h/bit | 0 | 0 to 23 | h | N/A |
| 4 | 1-8 | 963 | Month (MAN internal UTC) | 1 month/bit | 0 | 0 to 12 | month | N/A |
| 5 | 1-8 | 962 | Day (MAN internal UTC) | 0.25 day/bit | 0 | 0 to 31.75 | day | N/A |
| 6 | 1-8 | 964 | Year (MAN internal UTC) | 1 year/bit | +1985 | 1985 to 2235 | year | N/A |
| 7 | 1-8 | 1601 | Local minute offset | 1 min/bit | -125 | -125 to 125 | min | N/A |
| 8 | 1-8 | 1602 | Local hour offset | 1 h/bit | -125 | -125 to 125 | h | N/A |

## 18.2.12 Engine Hours (PGN 65253)
Identifier: 0x18 FE E5 27
Rate: 1000 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1-4 | 1-32 | 247 | Total engine hours of operation | 0.05 h/bit | 0 | 0 to 210554060.75 | h | N/A |
| 5-8 | 1-32 | N/A | Total engine revolutions | N/A | N/A | N/A | N/A | Not supported (0xFF FF FF FF) |

## 18.2.13 Fuel Economy (PGN 65266)
Identifier: 0x18 FE F2 27
Rate: 100 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1-2 | 1-16 | 183 | Fuel rate | 0.05 L/h per bit | 0 | 0 to 3212.75 | L/h | N/A |
| 3-8 | 1-48 | N/A | Default value | N/A | N/A | N/A | N/A | Not supported (0xFF FF FF FF FF FF) |

## 18.2.14 Fuel Consumption (PGN 65257)
Identifier: 0x18 FE E9 27
Rate: 1000 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1-4 | 1-32 | 182 | Engine trip fuel | 0.5 L/bit | 0 | 0 to 2105540607.5 | L | N/A |
| 5-8 | 1-32 | 250 | Engine total fuel used | 0.5 L/bit | 0 | 0 to 2105540607.5 | L | N/A |

## 18.2.15 Aftertreatment 1 SCR Service Info 2 (PGN 64701)
Identifier: 0x18 FC BD 27
Rate: 1000 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1-4 | 1-32 | 5963 | SCR system total DEF used | 0.5 L/bit | 0 | 0 to 2105540607.5 | L | N/A |
| 5-8 | 1-32 | 6563 | SCR system trip DEF used | 0.5 L/bit | 0 | 0 to 2105540607.5 | L | N/A |

## 18.2.16 Aux MAN Engine (PGN 65308, MAN-specific)
Identifier: 0x18 FF 1C 27
Rate: 50 ms
Length: 8 bytes

| Byte(s) | Bits | SPN | Name | Scale | Offset | Range | Units | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1-2 | N/A | Status gearbox neutral position | N/A | N/A | N/A | N/A | 00 not neutral, 01 neutral, 1x invalid -> treat as 00 |
| 1 | 3-4 | N/A | Status gearbox forward position | N/A | N/A | N/A | N/A | 00 not forward, 01 forward, 1x invalid -> treat as 00 |
| 1 | 5-6 | N/A | Status gearbox reverse position | N/A | N/A | N/A | N/A | 00 not reverse, 01 reverse, 1x invalid -> treat as 00 |
| 1 | 7-8 | N/A | Default value | N/A | N/A | N/A | N/A | 11 bin (not used) |
| 2 | 1-2 | N/A | Engine start request | N/A | N/A | N/A | N/A | 00 not active, 01 active, 1x invalid -> treat as 00 |
| 2 | 3-4 | N/A | Engine stop request | N/A | N/A | N/A | N/A | 00 not active, 01 active, 1x invalid -> treat as 00 |
| 2 | 7-8 | N/A | Default value | N/A | N/A | N/A | N/A | 0xF (not used) |
| 3 | 1-8 | N/A | Current maximum permissible load | 1 %/bit | -125 | -125 to 125 | % | MAN-specific |
| 4 | 1-8 | N/A | Exhaust back pressure 2 | 5 mbar/bit | 0 | 0 to 1.25 | bar | MAN-specific, similar to SPN 81 |
| 5-6 | 1-16 | N/A | SCR system 1 catalyst outlet gas temperature | 0.03125 deg C/bit | -273 | -273 to 1735 | deg C | MAN-specific, similar to SPN 4363 |
| 7-8 | 1-16 | N/A | SCR system 2 catalyst outlet gas temperature | 0.03125 deg C/bit | -273 | -273 to 1735 | deg C | MAN-specific, similar to SPN 4363 |

## 18.2.17 DM_1_MAN-Engine (PGN 65226)
Identifier (single message): 0x1C FE CA 27
Rate: 1000 ms
Length: variable (multi-packet when more than 1 error)

### Single Message Layout (0x1CFECA27)
| Byte(s) | Bits | Field | Notes |
| --- | --- | --- | --- |
| 1 | 1-2 | Protect lamp status (Sensor Failure) | 00 no sensor failure, 01 sensor failure active (MAN-specific) |
| 1 | 3-4 | Amber warning lamp status (Warning) | 00 no warning, 01 warning active (MAN-specific) |
| 1 | 5-6 | Red stop lamp status (ALARM) | 00 no alarm, 01 alarm active (MAN-specific) |
| 1 | 7-8 | Not used | Default 11 |
| 2 | 1-8 | Not used | 0xFF |
| 3 | 1-8 | SPN LSB | SPN bits 1-8 (bit 8 is MSB of this byte) |
| 4 | 1-8 | SPN second byte | SPN bits 9-16 |
| 5 | 1-5 | FMI | 00000 above normal, 00001 below normal, 00010 erratic, 01110 special instructions |
| 5 | 6-8 | SPN MSB | SPN bits 17-19 (bit 7 is MSB of SPN) |
| 6 | 1-7 | Occurrence counter | 0 if no failure active, 1 if failure active |
| 6 | 8 | CM | SPN conversion method = 0 |
| 7-8 | 1-16 | Not used | 0xFFFF |

Note: SPN is set to 0 when no fault is active.

### Multi-Packet (J1939-73 BAM + TP.DT)
Header (BAM_MAN-Engine_to_global, 0x1CECFF27)
| Byte(s) | Field | Notes |
| --- | --- | --- |
| 1 | Control | 0x20 broadcast announce message (BAM) |
| 2-3 | Total length | Total length of DM1 multi-packet data (use bytes) |
| 4 | Packet count | Number of following packets |
| 5 | Reserved | 0xFF |
| 6-7 | PGN | 0xFECA |
| 8 | Reserved | 0x00 |

Packet (P_MAN-Engine_to_global, 0x1CEBFF27)
| Byte(s) | Field | Notes |
| --- | --- | --- |
| 1 | Packet number | 0x01, 0x02, ... |
| 2 | Lamp status | Same lamp status definition as single message |
| 3 | Not used | 0xFF |
| 4 | SPN LSB | 1st active fault |
| 5 | SPN second byte | 1st active fault |
| 6 | FMI + SPN MSB | 1st active fault |
| 7 | Occurrence counter + CM | 1st active fault |
| 8 | SPN LSB | 2nd active fault |

Second packet (0x02) continues:
| Byte(s) | Field | Notes |
| --- | --- | --- |
| 2 | SPN second byte | 2nd active fault |
| 3 | FMI + SPN MSB | 2nd active fault |
| 4 | Occurrence counter + CM | 2nd active fault |
| 5 | SPN LSB | 3rd active fault |
| 6 | SPN second byte | 3rd active fault |
| 7 | FMI + SPN MSB | 3rd active fault |
| 8 | Occurrence counter + CM | PDF shows this occurrence counter as "Byte 4" for the 3rd fault; treat as byte 8 in practice |

Unused bytes in the last packet are filled with 0xFF.

### DM1 SPN List (PDF)
All entries use Sensor failure FMI = 2. Warning/Alarm FMI varies as listed below.

| SPN | Description | Warning/Alarm FMI |
| --- | --- | --- |
| 190 | Engine speed | 0 |
| 91 | Throttle | 14 |
| 525 | Transmission requested gear | 14 |
| 100 | Oil pressure | 1 |
| 99 | Difference pressure oil filter | 0 |
| 175 | Oil temperature | 0 |
| 98 | Engine oil level | 14 |
| 1381 | Fuel pressure hand pump | 1 |
| 94 | Fuel supply pressure | 1 |
| 174 | Fuel temperature | 0 |
| 1239 | Injection pipe leakage | 14 |
| 97 | Water in fuel indicator | 14 |
| 108 | Atmospheric pressure | 14 |
| 102 | Charge air pressure | 14 |
| 105 | Charge air temperature | 0 |
| 109 | Coolant pressure | 1 |
| 110 | Coolant temperature | 0 |
| 111 | Coolant level | 1 |
| 1209 | Engine exhaust pressure | 0 |
| 5749 | Engine exhaust pressure 2 | 0 |
| 4358 | Aftertreatment 1 SCR differential pressure | 0 |
| 4411 | Aftertreatment 2 SCR differential pressure | 0 |
| 1180 | Exhaust temperature before turbo 1 | 0 |
| 1181 | Exhaust temperature before turbo 2 | 0 |
| 1184 | Exhaust temperature after turbo 1 | 0 |
| 1185 | Exhaust temperature after turbo 2 | 0 |
| 4363 | Aftertreatment 1 SCR outlet temperature | 0 |
| 4415 | Aftertreatment 2 SCR outlet temperature | 0 |
| 1761 | DEF tank level | 1 |
| 3031 | DEF tank temperature | 0 |
| 127 | Gear oil pressure | 1 |
| 126 | Differential pressure of gear oil filter | 0 |
| 177 | Gear oil temperature | 0 |
| 124 | Gear oil level | 1 |
| 2435 | Sea water pressure | 1 |
| 1136 | Temperature MCS | 0 |
| 158 | Battery voltage | 14 |
| 167 | Alternator voltage | 14 |
| 606 | Override | 14 |
| 520192 | Engine fuel return flow pressure | 0 |
| 520194 | Sea water temperature | 0 |
| 520196 | Temperature plug X1 | 1 |
| 520197 | Reduction by partner engine | 14 |
| 520198 | Emergency stop | 14 |
| 520199 | Alarm safety system | 14 |
| 520200 | General electronic error | 14 |
| 520201 | Engine stop by safety system | 14 |
| 520202 | Engine start prevented | 14 |
| 520203 | MAN emergency operation units | 14 |
| 520204 | MAN start/stop unit | 14 |
| 520205 | MAN local operation unit | 14 |
| 520206 | Engine is operating in overload | 0 |
| 520207 | Inducement failure DEF tank level | 14 |
| 520208 | Inducement failure DEF quality | 14 |
| 520209 | Inducement failure dosing system error | 14 |
| 520210 | Inducement failure interrupt of dosing | 14 |
| 520211 | Oil temperature axial bearing | 0 |
| 520212 | Gear lube oil pressure | 1 |

## PDF Anomalies and Ambiguities
The following items appear inconsistent or duplicated in the PDF. Keep as-is unless corroborated by J1939-71 or live data.

| Location | Issue | Note |
| --- | --- | --- |
| 18.2.6 Fluid Level Pressure | Byte 3 "Engine oil level" is labeled SPN 94 | Standard J1939 SPN for engine oil level is 98, but the PDF explicitly shows 94 |
| 18.2.10 Transmission Fluids | Byte 2 is used for both SPN 124 and SPN 126 | Likely a typo, but recorded as shown |
| 18.2.10 Transmission Fluids | "Byte 3-8 default value = 0xFF FF" | This conflicts with listed byte fields; recorded as shown |
| 18.2.17 DM1 multi-packet | Second packet occurrence counter for 3rd fault labeled as Byte 4 | Likely means Byte 8, but recorded as shown |
