"""Tests for the Senquip J1939 decoder."""

import pytest

from custom_components.senquip.can_protocols.j1939.decoder import J1939Decoder
from custom_components.senquip.can_protocols.j1939.database import (
    PGN_DATABASE,
    SPN_DATABASE,
    SPNDefinition,
)


@pytest.fixture
def decoder():
    """Create a J1939Decoder instance."""
    return J1939Decoder()


# ---------------------------------------------------------------------------
# PGN extraction
# ---------------------------------------------------------------------------

class TestExtractPGN:
    """Test CAN ID → PGN extraction."""

    @pytest.mark.parametrize(
        "can_id, expected_pgn, description",
        [
            (217056256, 61444, "EEC1 — 0x0CF00400"),
            (217056000, 61443, "EEC2 — 0x0CF00300"),
            (0x18FEEE00, 65262, "ET1 — constructed"),
            (419360512, 65263, "EFL/P1 — 0x18FEEF00"),
            (0x18FEF100, 65265, "CCVS1 — constructed"),
            (419357952, 65253, "HOURS — 0x18FEE500"),
            (419358976, 65257, "LFC — 0x18FEE900"),
            (419362304, 65270, "IC1 — 0x18FEF600"),
            (419358208, 65254, "TD — 0x18FEE600"),
            (419362560, 65271, "VEP1 — 0x18FEF700"),
            (419372032, 65308, "Proprietary — 0x18FF1C00"),
            (419361280, 65266, "LFE1 — 0x18FEF200"),
        ],
    )
    def test_known_pgns_from_example_data(self, can_id, expected_pgn, description):
        """PGN extraction matches the verification table in J1939_DECODER.md."""
        _, pgn, _ = J1939Decoder.extract_pgn(can_id)
        assert pgn == expected_pgn, f"Failed for {description}"

    def test_source_address_extraction(self):
        """Source address is the low byte of the CAN ID."""
        _, _, source = J1939Decoder.extract_pgn(217056256)
        assert source == 0x00

    def test_priority_extraction(self):
        """Priority extracted from bits 28-26."""
        priority, _, _ = J1939Decoder.extract_pgn(217056256)
        # 0x0CF00400 → bits 28-26 = 0b011 = 3
        assert priority == 3

    def test_pdu1_pgn_excludes_destination(self):
        """For PF < 240, PS (destination) is NOT part of the PGN."""
        # CAN ID with PF=0xEC (236 < 240), PS=0xFF → PGN should be 0xEC00 = 60416
        can_id = 0x18ECFF00  # priority=6, PF=0xEC, PS=0xFF, SA=0x00
        _, pgn, _ = J1939Decoder.extract_pgn(can_id)
        assert pgn == 60416  # (0 << 16) | (0xEC << 8) = 60416


# ---------------------------------------------------------------------------
# SPN decoding — verified against J1939_DECODER.md example data
# ---------------------------------------------------------------------------

class TestDecodeSPN:
    """Test individual SPN value extraction."""

    def test_spn190_engine_speed(self, decoder):
        """SPN 190: bytes 4-5 = [0x88, 0x39], LE=14728, ×0.125 = 1841.0 rpm."""
        data = bytes.fromhex("3FFFCD883927F4FF")
        spn_def = SPN_DATABASE[190]
        result = decoder.decode_spn(spn_def, data)
        assert result == 1841.0

    def test_spn513_actual_torque(self, decoder):
        """SPN 513: byte 3 = 0xCD=205, +(-125) = 80%."""
        data = bytes.fromhex("3FFFCD883927F4FF")
        spn_def = SPN_DATABASE[513]
        result = decoder.decode_spn(spn_def, data)
        assert result == 80

    def test_spn110_coolant_temp(self, decoder):
        """SPN 110: byte 1 = 0xA0=160, +(-40) = 120 °C."""
        data = bytes.fromhex("A0FFFFB3FFFF9CFA")
        spn_def = SPN_DATABASE[110]
        result = decoder.decode_spn(spn_def, data)
        assert result == 120

    def test_spn84_vehicle_speed(self, decoder):
        """SPN 84: bytes 2-3 = [0x0F, 0x32], LE=12815, ×(1/256) ≈ 50.0586."""
        data = bytes.fromhex("FF0F32000000FFFF")
        spn_def = SPN_DATABASE[84]
        result = decoder.decode_spn(spn_def, data)
        assert result is not None
        assert abs(result - 50.0586) < 0.01

    def test_spn247_total_hours(self, decoder):
        """SPN 247: bytes 1-4 = [0x5F, 0x27, 0x00, 0x00], LE=10079, ×0.05 = 503.95 h."""
        data = bytes.fromhex("5F27000000000000")
        spn_def = SPN_DATABASE[247]
        result = decoder.decode_spn(spn_def, data)
        assert result == 503.95

    def test_spn250_total_fuel(self, decoder):
        """SPN 250: bytes 1-4 = [0xE2, 0x02, 0x00, 0x00], LE=738, ×0.5 = 369.0 L."""
        data = bytes.fromhex("E2020000BC1E0200")
        spn_def = SPN_DATABASE[250]
        result = decoder.decode_spn(spn_def, data)
        assert result == 369.0

    def test_spn182_trip_fuel(self, decoder):
        """SPN 182: bytes 5-8 = [0xBC, 0x1E, 0x02, 0x00], LE=138940, ×0.5 = 69470.0 L."""
        data = bytes.fromhex("E2020000BC1E0200")
        spn_def = SPN_DATABASE[182]
        result = decoder.decode_spn(spn_def, data)
        assert result == 69470.0

    def test_not_available_returns_none(self, decoder):
        """All-ones (0xFF for 8-bit) means 'not available' → None."""
        data = bytes.fromhex("FFFFFFFFFFFFFFFF")
        spn_def = SPN_DATABASE[110]  # 8-bit SPN
        result = decoder.decode_spn(spn_def, data)
        assert result is None

    def test_error_indicator_returns_none(self, decoder):
        """0xFE for 8-bit means 'error indicator' → None."""
        data = bytes.fromhex("FE00000000000000")
        spn_def = SPN_DATABASE[110]  # offset -40, so raw 0xFE=254 → error
        result = decoder.decode_spn(spn_def, data)
        assert result is None

    def test_bounds_check_returns_none(self, decoder):
        """Data too short for SPN byte range → None."""
        data = bytes.fromhex("AABB")  # only 2 bytes
        spn_def = SPN_DATABASE[190]  # starts at byte 4
        result = decoder.decode_spn(spn_def, data)
        assert result is None

    def test_sub_byte_extraction_torque_mode(self, decoder):
        """SPN 899: 4-bit field at byte 1, bits 1-4."""
        data = bytes.fromhex("3FFFCD883927F4FF")
        spn_def = SPN_DATABASE[899]
        result = decoder.decode_spn(spn_def, data)
        # 0x3F & 0x0F = 0x0F = 15 → all bits set → not available
        assert result is None

    def test_sub_byte_bit_position(self, decoder):
        """SPN 596 (Cruise Control Enable): byte 4, start_bit=3, 2 bits."""
        # Byte 4 = 0x0C = 0b00001100 → bits 3-4 (shift by 2) = 0b11 = 3 → not available
        data = bytes.fromhex("FF0F320C0000FFFF")
        spn_def = SPN_DATABASE[596]
        result = decoder.decode_spn(spn_def, data)
        assert result is None  # all bits set for 2-bit


# ---------------------------------------------------------------------------
# Frame decoding
# ---------------------------------------------------------------------------

class TestDecodeFrame:
    """Test full frame decoding."""

    def test_eec1_frame(self, decoder):
        """Decode all SPNs from an EEC1 frame."""
        results = decoder.decode_frame(217056256, "3FFFCD883927F4FF")
        assert 190 in results  # Engine Speed
        assert results[190] == 1841.0
        assert 513 in results  # Actual Torque
        assert results[513] == 80

    def test_hours_frame(self, decoder):
        """Decode HOURS frame — verify total hours."""
        results = decoder.decode_frame(419357952, "5F27000000000000")
        assert 247 in results
        assert results[247] == 503.95

    def test_lfc_frame(self, decoder):
        """Decode LFC frame — total fuel and trip fuel."""
        results = decoder.decode_frame(419358976, "E2020000BC1E0200")
        assert results[250] == 369.0
        assert results[182] == 69470.0

    def test_unknown_pgn_returns_empty(self, decoder):
        """Unknown PGN yields an empty dict."""
        results = decoder.decode_frame(419372032, "C4F0FFFF00FF00FF")
        assert results == {}

    def test_invalid_hex_returns_empty(self, decoder):
        """Invalid hex string returns empty dict."""
        results = decoder.decode_frame(217056256, "ZZZZ")
        assert results == {}

    def test_et1_coolant_temp(self, decoder):
        """ET1 frame: SPN 110 = 120°C."""
        # CAN ID 0x18FEEE00 → PGN 65262 (ET1)
        results = decoder.decode_frame(0x18FEEE00, "A0FFFFB3FFFF9CFA")
        assert results[110] == 120

    def test_ccvs1_vehicle_speed(self, decoder):
        """CCVS1 frame: SPN 84 ≈ 50.06 km/h."""
        # CAN ID 0x18FEF100 → PGN 65265 (CCVS1)
        results = decoder.decode_frame(0x18FEF100, "FF0F32000000FFFF")
        assert results[84] is not None
        assert abs(results[84] - 50.0586) < 0.01


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------

class TestHelpers:
    """Test get_pgn_info, get_spn_def, decode_can_port."""

    def test_get_pgn_info_known(self, decoder):
        """Known CAN ID returns PGNDefinition."""
        info = decoder.get_pgn_info(217056256)
        assert info is not None
        assert info.acronym == "EEC1"

    def test_get_pgn_info_unknown(self, decoder):
        """Unknown PGN returns None."""
        info = decoder.get_pgn_info(419372032)  # Proprietary PGN 65308
        assert info is None

    def test_get_spn_def_known(self, decoder):
        """Known SPN returns definition."""
        spn = decoder.get_spn_def(190)
        assert spn is not None
        assert spn.name == "Engine Speed"

    def test_get_spn_def_unknown(self, decoder):
        """Unknown SPN number returns None."""
        assert decoder.get_spn_def(99999) is None

    def test_decode_can_port(self, decoder):
        """Decode a list of frames from a CAN port."""
        frames = [
            {"id": 217056256, "data": "3FFFCD883927F4FF"},
            {"id": 419357952, "data": "5F27000000000000"},
            {"id": 419372032, "data": "C4F0FFFF00FF00FF"},  # unknown
        ]
        results, dm1_result = decoder.decode_can_port(frames)
        assert results[190] == 1841.0
        assert results[247] == 503.95
        assert dm1_result is None  # No DM1 frames in test data

    def test_decode_can_port_skips_missing_fields(self, decoder):
        """Frames missing id or data are skipped."""
        frames = [
            {"id": 217056256},
            {"data": "AABB"},
            {},
        ]
        results, dm1_result = decoder.decode_can_port(frames)
        assert results == {}
        assert dm1_result is None


# ---------------------------------------------------------------------------
# Database integrity
# ---------------------------------------------------------------------------

class TestDatabaseIntegrity:
    """Ensure PGN/SPN database is self-consistent."""

    def test_all_pgn_spns_exist(self):
        """Every SPN referenced by a PGN must exist in SPN_DATABASE."""
        for pgn_num, pgn_def in PGN_DATABASE.items():
            for spn_num in pgn_def.spns:
                assert spn_num in SPN_DATABASE, (
                    f"PGN {pgn_num} ({pgn_def.acronym}) references SPN {spn_num} "
                    f"which is missing from SPN_DATABASE"
                )

    def test_spn_pgn_backreference(self):
        """Every SPN's .pgn field must match a PGN that lists it."""
        for spn_num, spn_def in SPN_DATABASE.items():
            assert spn_def.pgn in PGN_DATABASE, (
                f"SPN {spn_num} references PGN {spn_def.pgn} "
                f"which is missing from PGN_DATABASE"
            )
            pgn_def = PGN_DATABASE[spn_def.pgn]
            assert spn_num in pgn_def.spns, (
                f"SPN {spn_num} says it belongs to PGN {spn_def.pgn} "
                f"but PGN {pgn_def.acronym} does not list it"
            )

    def test_spn_byte_positions_within_bounds(self):
        """SPN byte ranges must fit within the PGN's declared length."""
        for spn_num, spn_def in SPN_DATABASE.items():
            pgn_def = PGN_DATABASE.get(spn_def.pgn)
            if pgn_def is None:
                continue
            end_byte = spn_def.start_byte - 1 + (spn_def.bit_length + 7) // 8
            assert end_byte <= pgn_def.length, (
                f"SPN {spn_num} ({spn_def.name}) extends to byte {end_byte} "
                f"but PGN {pgn_def.acronym} is only {pgn_def.length} bytes"
            )


class TestCustomDatabases:
    """Verify decoder uses custom database inputs."""

    def test_default_databases_used(self):
        decoder = J1939Decoder()
        assert decoder.get_spn_def(110) is SPN_DATABASE[110]
        assert decoder.get_pgn_info(0x18FEEE00) is PGN_DATABASE[65262]

    def test_custom_spn_database_override(self):
        base = SPN_DATABASE[110]
        custom_spn = dict(SPN_DATABASE)
        custom_spn[110] = SPNDefinition(
            spn=base.spn,
            name=base.name,
            pgn=base.pgn,
            start_byte=base.start_byte,
            start_bit=base.start_bit,
            bit_length=base.bit_length,
            resolution=2,
            offset=base.offset,
            unit=base.unit,
            min_value=base.min_value,
            max_value=base.max_value,
        )

        decoder = J1939Decoder(pgn_database=PGN_DATABASE, spn_database=custom_spn)
        results = decoder.decode_frame(0x18FEEE00, "A0FFFFB3FFFF9CFA")
        assert results[110] == 280.0
