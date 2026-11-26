"""Tests for multi-packet DM1 detection, multi-source DM1 and per-source encoding."""

from pathlib import Path

import pytest

from custom_components.senquip.can_profiles.loader import CANProfile, discover_profiles
from custom_components.senquip.can_protocols.j1939.decoder import J1939Decoder
from custom_components.senquip.can_protocols.j1939.overlay import (
    DM1Config,
    parse_j1939_profile,
)
from custom_components.senquip.can_protocols.j1939.protocol import J1939CANProtocol
from custom_components.senquip.fault_history import DM1FaultLog

PREFIX = "can.can2.j1939.dm1."
ALL_DM1 = {
    PREFIX + field
    for field in (
        "active_fault", "active_fault_count", "protect_lamp", "amber_warning",
        "red_stop", "mil", "active_spn", "active_fmi", "occurrence_count",
    )
}

# DM1 frames from different source addresses
MAN_NO_FAULT = {"id": 0x18FECA00, "data": "C0FF00000000FFFF"}             # SA 0x00
MAN_ESTOP_BE = {"id": 0x18FECA00, "data": "C1FFFE00C201FFFF"}             # SA 0x00, BE SPN 520198
GEARBOX_COOLANT_LE = {"id": 0x18FECA03, "data": "04FF6E000001FFFF"}       # SA 0x03, LE SPN 110, amber
AFTERTREATMENT_UNSUPPORTED = {"id": 0x18FECA3D, "data": "FFFF00000000FFFF"}  # SA 0x3D, all lamps N/A
MAN_BAM_3_DTCS = {"id": 0x1CECFF00, "data": "200E0002FFCAFE00"}          # SA 0x00, 14 bytes
EC1_BAM = {"id": 0x1CECFF00, "data": "20220005FFE3FE00"}                 # BAM for PGN 65251, not DM1


def _man_runtime():
    protocol = J1939CANProtocol()
    profiles = discover_profiles(Path("custom_components/senquip/can_profiles"))
    decoder, errors = protocol.build_decoder([profiles["man_d2862.json"]])
    assert errors == []
    return protocol, decoder


def _decode(frames, selected=ALL_DM1):
    protocol, decoder = _man_runtime()
    values, diagnostics, valid = protocol.decode_runtime(frames, "can2", selected, decoder)
    return values, diagnostics, valid


# ---------------------------------------------------------------------------
# Multi-packet (BAM) DM1 detection
# ---------------------------------------------------------------------------

class TestDM1BAM:
    @pytest.mark.parametrize(
        "data, expected",
        [
            ("200E0002FFCAFE00", 3),   # 2 + 3*4 = 14 bytes
            ("200A0002FFCAFE00", 2),   # MAN PDF trace: 10 bytes
            ("20220005FFE3FE00", None),  # BAM for EC1, not DM1
            ("100E0002FFCAFE00", None),  # RTS, not BAM
            ("20040001FFCAFE00", None),  # implausible size
            ("200E00", None),          # too short
        ],
    )
    def test_decode_dm1_bam(self, data, expected):
        assert J1939Decoder.decode_dm1_bam(bytes.fromhex(data)) == expected

    def test_multi_packet_reported_as_count(self):
        values, diagnostics, valid = _decode([MAN_BAM_3_DTCS])
        assert valid is True
        assert values[PREFIX + "active_fault"] == "3 Active Faults (details not decoded)"
        assert values[PREFIX + "active_fault_count"] == 3
        assert values[PREFIX + "red_stop"] == "Unknown"
        assert diagnostics[0]["dm1"]["multi_packet"] is True

    def test_multi_packet_leaves_spn_fmi_oc_unchanged(self):
        """0 means "no fault", so undecodable faults must not report SPN 0."""
        values, _, _ = _decode([MAN_BAM_3_DTCS])
        assert PREFIX + "active_spn" not in values
        assert PREFIX + "active_fmi" not in values
        assert PREFIX + "occurrence_count" not in values

    def test_single_dtc_bam_is_singular(self):
        values, _, _ = _decode([{"id": 0x1CECFF00, "data": "20060001FFCAFE00"}])
        assert values[PREFIX + "active_fault"] == "1 Active Fault (details not decoded)"

    def test_non_dm1_bam_ignored(self):
        values, diagnostics, _ = _decode([EC1_BAM])
        assert not any(key.startswith(PREFIX) for key in values)
        assert "dm1" not in diagnostics[0]

    def test_latest_frame_per_source_wins(self):
        values, _, _ = _decode([MAN_BAM_3_DTCS, MAN_NO_FAULT])
        assert values[PREFIX + "active_fault"] == "No Active Fault"
        assert values[PREFIX + "active_fault_count"] == 0
        values, _, _ = _decode([MAN_NO_FAULT, MAN_BAM_3_DTCS])
        assert values[PREFIX + "active_fault_count"] == 3


# ---------------------------------------------------------------------------
# Multiple DM1 sources on one port
# ---------------------------------------------------------------------------

class TestMultiSourceDM1:
    def test_single_source_unchanged(self):
        values, _, _ = _decode([MAN_ESTOP_BE])
        assert values[PREFIX + "active_fault"].startswith("SPN 520198: Emergency Stop")
        assert values[PREFIX + "active_fault_count"] == 1
        assert values[PREFIX + "protect_lamp"] == "Active"
        assert values[PREFIX + "mil"] == "Not Available"
        assert values[PREFIX + "active_spn"] == 520198

    def test_unsupported_lamps_do_not_hide_active_lamp(self):
        """An ECU reporting N/A lamps must not mask another ECU's Active lamp."""
        values, _, _ = _decode([GEARBOX_COOLANT_LE, AFTERTREATMENT_UNSUPPORTED])
        assert values[PREFIX + "amber_warning"] == "Active"
        assert values[PREFIX + "red_stop"] == "Off"
        assert values[PREFIX + "active_fault"].startswith("SPN 110:")

    def test_all_faults_listed(self):
        values, _, _ = _decode([MAN_ESTOP_BE, GEARBOX_COOLANT_LE])
        fault = values[PREFIX + "active_fault"]
        assert fault.startswith("2 Active Faults: SPN 520198")
        assert "SPN 110" in fault
        assert values[PREFIX + "active_fault_count"] == 2
        assert values[PREFIX + "protect_lamp"] == "Active"
        assert values[PREFIX + "amber_warning"] == "Active"

    def test_decoded_and_multi_packet_sources_combined(self):
        values, _, _ = _decode([MAN_BAM_3_DTCS, GEARBOX_COOLANT_LE])
        assert values[PREFIX + "active_fault_count"] == 4
        assert values[PREFIX + "active_fault"].startswith("4 Active Faults: SPN 110")
        assert values[PREFIX + "amber_warning"] == "Active"
        assert values[PREFIX + "red_stop"] == "Unknown"

    def test_source_missing_from_payload_is_remembered(self):
        """Another BAM in the shared TP.CM slot must not drop the source's faults."""
        protocol, decoder = _man_runtime()
        run = lambda frames: protocol.decode_runtime(frames, "can2", ALL_DM1, decoder)[0]
        values = run([MAN_BAM_3_DTCS, GEARBOX_COOLANT_LE])
        assert values[PREFIX + "active_fault_count"] == 4
        # Next payload: SA 0x00's TP.CM slot holds an EC1 BAM instead
        values = run([EC1_BAM, GEARBOX_COOLANT_LE])
        assert values[PREFIX + "active_fault_count"] == 4
        assert values[PREFIX + "red_stop"] == "Unknown"

    def test_source_dropped_after_missed_payloads(self):
        protocol, decoder = _man_runtime()
        run = lambda frames: protocol.decode_runtime(frames, "can2", ALL_DM1, decoder)[0]
        run([MAN_BAM_3_DTCS, GEARBOX_COOLANT_LE])
        for _ in range(5):
            assert run([GEARBOX_COOLANT_LE])[PREFIX + "active_fault_count"] == 4
        assert run([GEARBOX_COOLANT_LE])[PREFIX + "active_fault_count"] == 1

    def test_payload_without_dm1_emits_nothing(self):
        protocol, decoder = _man_runtime()
        protocol.decode_runtime([MAN_ESTOP_BE], "can2", ALL_DM1, decoder)
        values, _, _ = protocol.decode_runtime(
            [{"id": 217056256, "data": "3FFFCD883927F4FF"}], "can2", ALL_DM1, decoder
        )
        assert not any(key.startswith(PREFIX) for key in values)

    def test_long_description_truncated_to_state_limit(self):
        frames = [
            {"id": 0x18FECA00 | sa, "data": "04FF6E000001FFFF"} for sa in range(1, 12)
        ]
        values, _, _ = _decode(frames)
        assert len(values[PREFIX + "active_fault"]) == 255
        assert values[PREFIX + "active_fault"].endswith("...")

    def test_only_selected_keys_emitted(self):
        values, _, _ = _decode([MAN_ESTOP_BE], selected={PREFIX + "red_stop"})
        assert values == {PREFIX + "red_stop": "Off"}


# ---------------------------------------------------------------------------
# Per-source big-endian SPN encoding
# ---------------------------------------------------------------------------

class TestPerSourceEncoding:
    def test_man_profile_sources(self):
        profiles = discover_profiles(Path("custom_components/senquip/can_profiles"))
        _, _, dm1 = parse_j1939_profile(profiles["man_d2862.json"])
        assert dm1.source_addresses == (0, 1, 39)

    def test_other_source_on_man_port_decoded_little_endian(self):
        """A standard ECU sharing can2 with the MAN engine keeps LE SPN decoding."""
        _, diagnostics, _ = _decode([MAN_ESTOP_BE, GEARBOX_COOLANT_LE])
        by_source = {d["source_address"]: d["dm1"] for d in diagnostics}
        assert by_source[0x00]["encoding"] == "big_endian"
        assert by_source[0x00]["active_spn"] == 520198
        assert by_source[0x03]["encoding"] == "little_endian"
        assert by_source[0x03]["active_spn"] == 110

    @pytest.mark.parametrize(
        "config, port, source, expected",
        [
            (DM1Config(spn_encoding="big_endian"), "can1", 5, True),
            (DM1Config(spn_encoding="big_endian", ports=("can2",)), "can1", 0, False),
            (DM1Config(spn_encoding="big_endian", source_addresses=(0, 39)), "can2", 39, True),
            (DM1Config(spn_encoding="big_endian", source_addresses=(0, 39)), "can2", 3, False),
            (DM1Config(spn_encoding="big_endian", source_addresses=(0,)), "can2", None, True),
            (DM1Config(spn_encoding="little_endian", source_addresses=(0,)), "can2", 0, False),
        ],
    )
    def test_is_dm1_big_endian(self, config, port, source, expected):
        assert J1939Decoder(dm1_config=config).is_dm1_big_endian(port, source) is expected

    def test_invalid_source_addresses_ignored(self):
        profile = CANProfile(
            filename="bad.json",
            name="Bad",
            base_protocol="j1939",
            description="",
            protocol_data={"j1939": {"dm1": {
                "spn_encoding": "big_endian",
                "source_addresses": [0, 256, -1, "x", True, 39],
            }}},
        )
        _, _, dm1 = parse_j1939_profile(profile)
        assert dm1.source_addresses == (0, 39)
        assert dm1.spn_encoding == "big_endian"

    def test_all_invalid_source_addresses_disable_big_endian(self):
        """An empty filter means "all", so an all-invalid list must not widen it."""
        profile = CANProfile(
            filename="hex.json",
            name="Hex",
            base_protocol="j1939",
            description="",
            protocol_data={"j1939": {"dm1": {
                "spn_encoding": "big_endian",
                "source_addresses": ["0x00"],
            }}},
        )
        _, _, dm1 = parse_j1939_profile(profile)
        assert dm1.spn_encoding == "little_endian"
        assert J1939Decoder(dm1_config=dm1).is_dm1_big_endian("can2", 3) is False


# ---------------------------------------------------------------------------
# Fault log: multi-packet entries
# ---------------------------------------------------------------------------

class TestFaultLogMultiPacket:
    def test_multi_packet_entry_round_trip(self):
        _, diagnostics, _ = _decode([MAN_BAM_3_DTCS])
        report = {"source_address": 0, **diagnostics[0]["dm1"]}
        from datetime import datetime, timezone
        log = DM1FaultLog()
        assert log.observe([report], datetime(2026, 11, 27, tzinfo=timezone.utc)) is True
        restored = DM1FaultLog.from_dict(log.as_dict())
        assert restored.entries == log.entries
        assert restored.entries[0]["spn"] is None
        # Count change updates the same entry
        bigger = dict(report, dtc_count=4, active_fault="4 Active Faults (details not decoded)")
        assert restored.observe([bigger], datetime(2026, 11, 27, 0, 1, tzinfo=timezone.utc)) is True
        [entry] = restored.entries
        assert entry["description"] == "4 Active Faults (details not decoded)"
        assert entry["count"] == 1

    def test_switch_to_multi_packet_keeps_existing_faults_active(self):
        """Going from 1 DTC to a BAM must not mark the known DTC as cleared."""
        from datetime import datetime, timedelta, timezone
        t0 = datetime(2026, 11, 27, tzinfo=timezone.utc)
        _, single, _ = _decode([MAN_ESTOP_BE])
        _, multi, _ = _decode([MAN_BAM_3_DTCS])
        _, clear, _ = _decode([MAN_NO_FAULT])
        as_report = lambda diag: {"source_address": diag[0]["source_address"], **diag[0]["dm1"]}

        log = DM1FaultLog()
        log.observe([as_report(single)], t0)
        log.observe([as_report(multi)], t0 + timedelta(minutes=1))
        by_spn = {e["spn"]: e for e in log.entries}
        assert by_spn[520198]["active"] is True
        assert by_spn[None]["active"] is True
        # Back to single-frame with the same DTC: no fake clear/re-activate
        log.observe([as_report(single)], t0 + timedelta(minutes=2))
        by_spn = {e["spn"]: e for e in log.entries}
        assert by_spn[520198]["active"] is True
        assert by_spn[520198]["count"] == 1
        assert by_spn[None]["active"] is False
        # A no-fault single frame clears it
        log.observe([as_report(clear)], t0 + timedelta(minutes=3))
        assert log.active_count == 0
