"""Tests for multi-packet DM1 detection, multi-source DM1 and per-source encoding."""

from pathlib import Path

import pytest

from custom_components.senquip.can_profiles.loader import CANProfile, discover_profiles
from custom_components.senquip.can_protocols.j1939.decoder import (
    DM1SourceTracker,
    J1939Decoder,
)
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
MAN_ESTOP = {"id": 0x18FECA00, "data": "C1FF06F0E201FFFF"}                # SA 0x00, SPN 520198 FMI 2
# Captured from the starboard D2862 on 2026-11-27 (Red Stop, SPN 520202 FMI 14)
MAN_START_PREVENTED = {"id": 0x18FECA00, "data": "D0FF0AF0EE01FFFF"}
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

    def test_multi_packet_spn_fmi_unknown(self):
        """0 means "no fault", so undecodable faults report SPN/FMI as Unknown."""
        values, _, _ = _decode([MAN_BAM_3_DTCS])
        assert values[PREFIX + "active_spn"] == "Unknown"
        assert values[PREFIX + "active_fmi"] == "Unknown"
        # Occurrence count is a numeric measurement: left unchanged
        assert PREFIX + "occurrence_count" not in values

    def test_single_dtc_bam_is_singular(self):
        values, _, _ = _decode([{"id": 0x1CECFF00, "data": "20060001FFCAFE00"}])
        assert values[PREFIX + "active_fault"] == "1 Active Fault (details not decoded)"

    def test_non_dm1_bam_ignored(self):
        values, diagnostics, _ = _decode([EC1_BAM])
        assert not any(key.startswith(PREFIX) for key in values)
        assert "dm1" not in diagnostics[0]

    @pytest.mark.parametrize(
        "frames",
        [[MAN_BAM_3_DTCS, MAN_NO_FAULT], [MAN_NO_FAULT, MAN_BAM_3_DTCS]],
    )
    def test_multi_packet_beats_single_frame_in_same_payload(self, frames):
        """Payload order is slot order, not time, so precedence must not depend on it."""
        values, _, _ = _decode(frames)
        assert values[PREFIX + "active_fault_count"] == 3
        assert values[PREFIX + "red_stop"] == "Unknown"


# ---------------------------------------------------------------------------
# Multiple DM1 sources on one port
# ---------------------------------------------------------------------------

class TestMultiSourceDM1:
    def test_single_source_unchanged(self):
        values, _, _ = _decode([MAN_ESTOP])
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
        values, _, _ = _decode([MAN_ESTOP, GEARBOX_COOLANT_LE])
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

    def test_payloads_without_dm1_age_sources(self):
        """Sources age on every port payload, not only DM1-bearing ones."""
        protocol, decoder = _man_runtime()
        run = lambda frames: protocol.decode_runtime(frames, "can2", ALL_DM1, decoder)[0]
        run([MAN_ESTOP, GEARBOX_COOLANT_LE])
        for _ in range(6):
            run([{"id": 217056256, "data": "3FFFCD883927F4FF"}])  # EEC1 only
        values = run([GEARBOX_COOLANT_LE])
        assert values[PREFIX + "active_fault_count"] == 1
        assert values[PREFIX + "protect_lamp"] == "Off"

    def test_source_dropped_after_missed_payloads(self):
        protocol, decoder = _man_runtime()
        run = lambda frames: protocol.decode_runtime(frames, "can2", ALL_DM1, decoder)[0]
        run([MAN_BAM_3_DTCS, GEARBOX_COOLANT_LE])
        for _ in range(5):
            assert run([GEARBOX_COOLANT_LE])[PREFIX + "active_fault_count"] == 4
        assert run([GEARBOX_COOLANT_LE])[PREFIX + "active_fault_count"] == 1

    def test_payload_without_dm1_emits_nothing(self):
        protocol, decoder = _man_runtime()
        protocol.decode_runtime([MAN_ESTOP], "can2", ALL_DM1, decoder)
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
        values, _, _ = _decode([MAN_ESTOP], selected={PREFIX + "red_stop"})
        assert values == {PREFIX + "red_stop": "Off"}


# ---------------------------------------------------------------------------
# Per-source big-endian SPN encoding
# ---------------------------------------------------------------------------

class TestPerSourceEncoding:
    def test_man_profile_sources(self):
        profiles = discover_profiles(Path("custom_components/senquip/can_profiles"))
        _, _, dm1 = parse_j1939_profile(profiles["man_d2862.json"])
        assert dm1.source_addresses == (0, 1, 39)

    def test_man_profile_decodes_little_endian(self):
        """Live MAN DM1 uses the standard layout, not the PDF's big-endian example."""
        _, diagnostics, _ = _decode([MAN_ESTOP, GEARBOX_COOLANT_LE])
        by_source = {d["source_address"]: d["dm1"] for d in diagnostics}
        assert by_source[0x00]["encoding"] == "little_endian"
        assert by_source[0x00]["active_spn"] == 520198
        assert by_source[0x03]["encoding"] == "little_endian"
        assert by_source[0x03]["active_spn"] == 110

    def test_captured_start_prevented_fault(self):
        """Regression: this frame was shown as "Unknown SPN 22407" under big-endian."""
        values, _, _ = _decode([MAN_START_PREVENTED])
        assert values[PREFIX + "active_spn"] == 520202
        assert values[PREFIX + "active_fmi"] == 14
        assert values[PREFIX + "active_fault"] == (
            "SPN 520202: Engine Start Prevented (FMI 14: Special Instructions)"
        )
        assert values[PREFIX + "red_stop"] == "Active"
        assert values[PREFIX + "protect_lamp"] == "Off"

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

    def test_null_filters_mean_all(self):
        _, _, dm1 = parse_j1939_profile(CANProfile(
            filename="null.json", name="Null", base_protocol="j1939", description="",
            protocol_data={"j1939": {"dm1": {
                "spn_encoding": "big_endian", "ports": None, "source_addresses": None,
            }}},
        ))
        assert dm1.ports is None and dm1.source_addresses is None
        assert J1939Decoder(dm1_config=dm1).is_dm1_big_endian("can1", 7) is True

    @pytest.mark.parametrize("ports", ["can2", [], [2]])
    def test_unusable_ports_match_no_port(self, ports):
        _, _, dm1 = parse_j1939_profile(CANProfile(
            filename="p.json", name="P", base_protocol="j1939", description="",
            protocol_data={"j1939": {"dm1": {"spn_encoding": "big_endian", "ports": ports}}},
        ))
        assert dm1.ports == ()
        decoder = J1939Decoder(dm1_config=dm1)
        assert decoder.is_dm1_big_endian("can1", 0) is False
        assert decoder.is_dm1_big_endian("can2", 0) is False

    @pytest.mark.parametrize("sources", [["0x00"], 0, "0x27", []])
    def test_unusable_source_addresses_match_no_source(self, sources):
        """A given-but-unusable filter must never widen to every source."""
        profile = CANProfile(
            filename="bad.json",
            name="Bad",
            base_protocol="j1939",
            description="",
            protocol_data={"j1939": {"dm1": {
                "spn_encoding": "big_endian",
                "source_addresses": sources,
                "custom_fault_spns": {"520198": "Emergency Stop"},
            }}},
        )
        _, _, dm1 = parse_j1939_profile(profile)
        assert dm1.source_addresses == ()
        decoder = J1939Decoder(dm1_config=dm1)
        assert decoder.is_dm1_big_endian("can2", 3) is False
        assert decoder.get_dm1_custom_fault_spns("can2", 3) == {}

    def test_omitted_source_addresses_match_all(self):
        _, _, dm1 = parse_j1939_profile(CANProfile(
            filename="all.json", name="All", base_protocol="j1939", description="",
            protocol_data={"j1939": {"dm1": {"spn_encoding": "big_endian"}}},
        ))
        assert dm1.source_addresses is None
        assert J1939Decoder(dm1_config=dm1).is_dm1_big_endian("can2", 3) is True

    def test_custom_fault_names_only_for_profile_sources(self):
        """A non-MAN ECU's proprietary SPN must not get a MAN fault name."""
        # Gearbox at SA 0x03 sends proprietary SPN 520198 / FMI 2, little-endian
        gearbox_520198 = {"id": 0x18FECA03, "data": "04FF06F0E201FFFF"}
        _, diagnostics, _ = _decode([gearbox_520198])
        assert diagnostics[0]["dm1"]["active_spn"] == 520198
        assert "Emergency Stop" not in diagnostics[0]["dm1"]["active_fault"]
        assert "Unknown SPN 520198" in diagnostics[0]["dm1"]["active_fault"]
        # The MAN engine (SA 0x00) still gets the profile's name
        _, diagnostics, _ = _decode([MAN_ESTOP])
        assert "Emergency Stop" in diagnostics[0]["dm1"]["active_fault"]


# ---------------------------------------------------------------------------
# DM1SourceTracker
# ---------------------------------------------------------------------------

class TestDM1SourceTracker:
    def test_drops_after_more_than_max_missed(self):
        tracker = DM1SourceTracker(max_missed=2)
        tracker.update({1: {"id": 1}})
        assert tracker.update({}) == ([{"id": 1}], False)
        assert tracker.update({}) == ([{"id": 1}], False)
        assert tracker.update({}) == ([], True)

    def test_refresh_resets_counter(self):
        tracker = DM1SourceTracker(max_missed=1)
        tracker.update({1: {"v": 1}})
        tracker.update({})
        tracker.update({1: {"v": 2}})
        assert tracker.update({}) == ([{"v": 2}], False)

    def test_reset_forgets_sources(self):
        tracker = DM1SourceTracker()
        tracker.update({1: {"v": 1}})
        tracker.reset()
        assert tracker.update({}) == ([], False)


class TestDM1StateLifecycle:
    def test_last_source_aging_out_is_published(self):
        """The last silent source must not freeze its faults on the port."""
        protocol, decoder = _man_runtime()
        eec1_only = [{"id": 217056256, "data": "3FFFCD883927F4FF"}]
        run = lambda frames: protocol.decode_runtime(frames, "can2", ALL_DM1, decoder)[0]
        assert run([MAN_BAM_3_DTCS])[PREFIX + "active_fault_count"] == 3
        for _ in range(5):
            assert not any(k.startswith(PREFIX) for k in run(eec1_only))
        values = run(eec1_only)
        assert values[PREFIX + "active_fault"] == "No DM1 Received"
        assert values[PREFIX + "red_stop"] == "Unknown"
        assert values[PREFIX + "active_spn"] == "Unknown"
        assert PREFIX + "active_fault_count" not in values  # numeric: left unchanged

    def test_device_offline_resets_dm1_sources(self):
        """An ECU switched off overnight must not reappear in the morning."""
        from unittest.mock import MagicMock
        from custom_components.senquip import SenquipDataCoordinator
        from tests.ha_stubs import ConfigEntry

        selected = sorted(ALL_DM1)
        entry = ConfigEntry(data={
            "device_id": "dev", "mqtt_topic": "t", "selected_signals": selected,
            "port_configs": {"can2": {
                "family": "can", "active": True, "protocol": "j1939",
                "profiles": ["man_d2862.json"],
            }},
        })
        profiles = discover_profiles(Path("custom_components/senquip/can_profiles"))
        coord = SenquipDataCoordinator(MagicMock(), entry, profiles)
        engine2_red_stop = {"id": 0x18FECA01, "data": "D1FF06F0E201FFFF"}
        coord._parse_payload({"deviceid": "dev", "can2": [MAN_NO_FAULT, engine2_red_stop]})
        coord._mark_device_offline()
        values = coord._parse_payload({"deviceid": "dev", "can2": [MAN_NO_FAULT]})
        assert values[PREFIX + "red_stop"] == "Off"
        assert values[PREFIX + "active_fault"] == "No Active Fault"

    def test_port_absent_resets_dm1_sources(self):
        protocol, decoder = _man_runtime()
        protocol.decode_runtime([MAN_ESTOP, GEARBOX_COOLANT_LE], "can2", ALL_DM1, decoder)
        protocol.reset_runtime_state(decoder)
        values, _, _ = protocol.decode_runtime([GEARBOX_COOLANT_LE], "can2", ALL_DM1, decoder)
        assert values[PREFIX + "active_fault_count"] == 1


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

    def test_multi_packet_beats_single_frame_in_fault_log(self):
        from datetime import datetime, timezone
        _, single, _ = _decode([MAN_NO_FAULT])
        _, multi, _ = _decode([MAN_BAM_3_DTCS])
        as_report = lambda diag: {"source_address": diag[0]["source_address"], **diag[0]["dm1"]}
        for order in ([as_report(multi), as_report(single)], [as_report(single), as_report(multi)]):
            log = DM1FaultLog()
            log.observe(order, datetime(2026, 11, 27, tzinfo=timezone.utc))
            assert [e["spn"] for e in log.entries] == [None]
            assert log.active_count == 1

    def test_switch_to_multi_packet_keeps_existing_faults_active(self):
        """Going from 1 DTC to a BAM must not mark the known DTC as cleared."""
        from datetime import datetime, timedelta, timezone
        t0 = datetime(2026, 11, 27, tzinfo=timezone.utc)
        _, single, _ = _decode([MAN_ESTOP])
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
