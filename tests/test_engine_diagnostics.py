"""Tests for engine diagnostics: starter mode, controlling device, gearbox, fault events.

Frames are taken from a capture of the MAN D2862 engines on 2026-11-27.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.senquip import SenquipDataCoordinator
from custom_components.senquip.can_profiles.loader import discover_profiles
from custom_components.senquip.can_protocols.j1939.protocol import J1939CANProtocol
from custom_components.senquip.const import EVENT_DM1_FAULT, SensorDeviceClass
from custom_components.senquip.fault_history import DM1FaultLog
from custom_components.senquip.fault_history import (
    FAULT_LOG_FORMAT,
    big_endian_spn_to_little_endian,
    fault_history_store_key,
)
from custom_components.senquip.sensor import SenquipDM1FaultHistorySensor, _resolve_sensor_meta
from tests.ha_stubs import DEVICE_REGISTRY, ConfigEntry, Store

@pytest.fixture(autouse=True)
def _clean_store():
    Store.saved.clear()
    yield
    Store.saved.clear()


EEC1_ID = 0x0CF00400
GEARBOX_ID = 0x18FF1C00
T0 = datetime(2026, 11, 27, 2, 40, tzinfo=timezone.utc)


def _profiles():
    return discover_profiles(Path("custom_components/senquip/can_profiles"))


def _man_decoder():
    protocol = J1939CANProtocol()
    decoder, errors = protocol.build_decoder([_profiles()["man_d2862.json"]])
    assert errors == []
    return protocol, decoder


class _CoordinatorStub:
    def __init__(self):
        self._runtime = _man_decoder()

    def get_can_runtime(self, port_id):
        return self._runtime


# ---------------------------------------------------------------------------
# EEC1: engine starter mode (SPN 1675) and controlling device (SPN 1483)
# ---------------------------------------------------------------------------

class TestEEC1Diagnostics:
    @pytest.mark.parametrize(
        "data, starter_mode",
        [
            ("0FFF7D000027F1FF", "Starter Active, Gear Not Engaged"),  # starboard, stopped
            ("2FFF83501427F4FF", "Inhibited: Engine Running"),  # starboard, idling
            ("4FFFAA002627F0FF", "Start Not Requested"),  # port, running
            ("0FFF7D000027F6FF", "Inhibited: Driveline Engaged"),
            ("0FFF7D000027FFFF", None),  # not available
            ("0FFF7D000027FEFF", None),  # error indicator
            ("0FFF7D000027F9FF", None),  # reserved
        ],
    )
    def test_starter_mode(self, data, starter_mode):
        _, decoder = _man_decoder()
        assert decoder.decode_frame(EEC1_ID, data)[1675] == starter_mode

    def test_controlling_device_address(self):
        _, decoder = _man_decoder()
        assert decoder.decode_frame(EEC1_ID, "0FFF7D000027F1FF")[1483] == 0x27
        assert decoder.decode_frame(EEC1_ID, "0FFF7D0000FFF1FF")[1483] is None

    def test_starter_mode_is_enum_sensor(self):
        meta = _resolve_sensor_meta("can.can2.j1939.spn1675", _CoordinatorStub())
        assert meta.name == "Engine Starter Mode (EEC1)"
        assert meta.device_class == SensorDeviceClass.ENUM
        assert meta.state_class is None
        assert "Inhibited: Engine Not Ready" in meta.options

    def test_controlling_device_not_a_measurement(self):
        """An address must not get long-term statistics."""
        meta = _resolve_sensor_meta("can.can2.j1939.spn1483", _CoordinatorStub())
        assert meta.name == "Source Address of Controlling Device (EEC1)"
        assert meta.state_class is None

    def test_discovered_from_eec1(self):
        protocol, decoder = _man_decoder()
        signals = protocol.discover_signals(
            [{"id": EEC1_ID, "data": "0FFF7D000027F1FF"}], "can2", decoder
        )
        by_key = {s.key: s for s in signals}
        assert by_key["can.can2.j1939.spn1675"].sample_value == "Starter Active, Gear Not Engaged"
        assert by_key["can.can2.j1939.spn1675"].default_selected is True
        assert by_key["can.can2.j1939.spn1483"].sample_value == 0x27


# ---------------------------------------------------------------------------
# MAN gearbox status (PGN 65308 byte 1: neutral / forward / reverse flags)
# ---------------------------------------------------------------------------

class TestGearboxStatus:
    @pytest.mark.parametrize(
        "byte1, expected",
        [
            ("C0", "Not Reported"),  # port engine in gear; starboard after power-up
            ("C1", "Neutral"),
            ("C4", "Forward"),
            ("D0", "Reverse"),
            ("C5", None),  # neutral and forward together: not a valid position
            ("FF", None),  # not available
        ],
    )
    def test_decode(self, byte1, expected):
        _, decoder = _man_decoder()
        assert decoder.decode_frame(GEARBOX_ID, byte1 + "F0FFFF00FF00FF")[800005] == expected

    def test_not_reported_is_an_option(self):
        meta = _resolve_sensor_meta("can.can2.j1939.spn800005", _CoordinatorStub())
        assert meta.options == ["Not Reported", "Neutral", "Forward", "Reverse"]


# ---------------------------------------------------------------------------
# Fault transitions and HA events
# ---------------------------------------------------------------------------

def _report(spn, fmi=14, source=0, lamps=None, oc=1):
    return {
        "source_address": source,
        "multi_packet": False,
        "dtc_count": 0 if spn == 0 else 1,
        "active_spn": spn,
        "active_fmi": fmi if spn else 0,
        "active_fault": f"SPN {spn}" if spn else "No Active Fault",
        "occurrence_count": oc,
        "lamps": lamps or {"red_stop": "Active"},
    }


class TestFaultTransitions:
    def test_activate_clear_reactivate(self):
        log = DM1FaultLog()
        log.observe([_report(520202)], T0)
        [raised] = log.pop_transitions()
        assert raised["status"] == "active"
        assert (raised["spn"], raised["fmi"], raised["count"]) == (520202, 14, 1)
        assert raised["lamps"] == ["Red Stop"]
        assert log.pop_transitions() == []

        log.observe([_report(520202)], T0 + timedelta(seconds=5))
        assert log.pop_transitions() == []  # still active: no transition

        log.observe([_report(0)], T0 + timedelta(seconds=10))
        [cleared] = log.pop_transitions()
        assert cleared["status"] == "cleared"
        assert cleared["cleared"] is not None

        log.observe([_report(520202, oc=2)], T0 + timedelta(minutes=24))
        [again] = log.pop_transitions()
        assert again["status"] == "active"
        assert again["count"] == 2
        assert again["occurrence_count"] == 2  # snapshot taken after the update

    def test_lamp_change_is_not_a_transition(self):
        log = DM1FaultLog()
        log.observe([_report(100, fmi=1, lamps={"amber_warning": "Active"})], T0)
        log.pop_transitions()
        assert log.observe([_report(100, fmi=1, lamps={"red_stop": "Active"})], T0) is True
        assert log.pop_transitions() == []

    def test_multi_packet_transitions(self):
        log = DM1FaultLog()
        log.observe([{"source_address": 0, "multi_packet": True, "dtc_count": 3,
                      "active_fault": "3 Active Faults (details not decoded)"}], T0)
        [raised] = log.pop_transitions()
        assert raised["status"] == "active" and raised["spn"] is None
        log.observe([_report(0)], T0 + timedelta(seconds=45))
        assert [t["status"] for t in log.pop_transitions()] == ["cleared"]

    def test_restored_log_has_no_transitions(self):
        log = DM1FaultLog()
        log.observe([_report(520202)], T0)
        assert DM1FaultLog.from_dict(log.as_dict()).pop_transitions() == []


def _coordinator(profiles=("man_d2862.json",)):
    entry = ConfigEntry(data={
        "device_id": "HE8EV12LF",
        "device_name": "Starboard Senquip Quad",
        "mqtt_topic": "senquip/quad/stbd/json",
        "selected_signals": ["can.can2.j1939.dm1.active_fault"],
        "port_configs": {"can2": {
            "family": "can", "active": True, "protocol": "j1939",
            "profiles": list(profiles),
        }},
    })
    return SenquipDataCoordinator(MagicMock(), entry, _profiles())


def _dm1_payload(data):
    return {"deviceid": "HE8EV12LF", "can2": [{"id": 0x18FECA00, "data": data}]}


def _fired(coord):
    return [
        c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == EVENT_DM1_FAULT
    ]


class TestFaultEvents:
    def test_events_fired_on_raise_and_clear(self):
        coord = _coordinator()
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "HE8EV12LF", "Starboard Senquip Quad")
        sensor.entity_id = "sensor.d2862_le466_starboard_dm1_fault_history"

        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor._handle_coordinator_update()
        [raised] = _fired(coord)
        assert raised["status"] == "active"
        assert raised["spn"] == 520202 and raised["fmi"] == 14
        assert raised["description"].startswith("SPN 520202: Engine Start Prevented")
        assert raised["lamps"] == ["Red Stop"]
        assert raised["senquip_id"] == "HE8EV12LF"
        assert raised["port"] == "can2"
        assert raised["device_name"] == "Starboard Senquip Quad"
        assert raised["entity_id"] == "sensor.d2862_le466_starboard_dm1_fault_history"

        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor._handle_coordinator_update()
        assert len(_fired(coord)) == 1  # unchanged fault: no new event

        coord._parse_payload(_dm1_payload("C0FF00000000FFFF"))
        sensor._handle_coordinator_update()
        assert [e["status"] for e in _fired(coord)] == ["active", "cleared"]

    def test_event_uses_registry_device_name(self, monkeypatch):
        coord = _coordinator()
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "HE8EV12LF", "Starboard Senquip Quad")
        sensor.registry_entry = MagicMock(device_id="abc123")
        monkeypatch.setitem(
            DEVICE_REGISTRY.devices, "abc123",
            SimpleNamespace(name_by_user="D2862 LE466 (Starboard)", name="Senquip CAN 2"),
        )
        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor._handle_coordinator_update()
        [raised] = _fired(coord)
        assert raised["device_id"] == "abc123"
        assert raised["device_name"] == "D2862 LE466 (Starboard)"

    def test_event_falls_back_to_registry_name(self, monkeypatch):
        coord = _coordinator()
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "HE8EV12LF", "Starboard Senquip Quad")
        sensor.registry_entry = MagicMock(device_id="abc123")
        monkeypatch.setitem(
            DEVICE_REGISTRY.devices, "abc123", SimpleNamespace(name_by_user=None, name="Senquip CAN 2"),
        )
        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor._handle_coordinator_update()
        assert _fired(coord)[0]["device_name"] == "Senquip CAN 2"

    def test_state_written_before_event(self):
        """Automations triggered by the event must see the updated log."""
        coord = _coordinator()
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "HE8EV12LF", "Starboard Senquip Quad")
        writes_at_fire = []
        coord.hass.bus.async_fire.side_effect = lambda *a: writes_at_fire.append(sensor.state_writes)
        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor._handle_coordinator_update()
        assert writes_at_fire == [1]

    def test_event_without_registry_entry_has_no_device_id(self):
        """Without a registry entry the config entry's device name is used."""
        coord = _coordinator()
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "HE8EV12LF", "Starboard Senquip Quad")
        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor._handle_coordinator_update()
        assert _fired(coord)[0]["device_id"] is None

    def test_pending_payload_at_startup_fires_event(self):
        coord = _coordinator()
        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "HE8EV12LF", "Starboard Senquip Quad")
        asyncio.run(sensor.async_added_to_hass())
        assert [e["status"] for e in _fired(coord)] == ["active"]


# ---------------------------------------------------------------------------
# Correcting fault logs saved with big-endian SPNs (0.6.0-0.7.0)
# ---------------------------------------------------------------------------

def _entry(source, spn, fmi, description, active=False):
    return {
        "source_address": source,
        "spn": spn,
        "fmi": fmi,
        "description": description,
        "lamps": ["Red Stop"] if spn else [],
        "occurrence_count": 1 if spn else None,
        "count": 2,
        "active": active,
        "first_seen": "2026-11-27T02:40:31.246622+00:00",
        "last_activated": "2026-11-27T03:04:56.228856+00:00",
        "cleared": None if active else "2026-11-27T03:05:06.191136+00:00",
    }


# The starboard log as saved by 0.7.0
LOG_V070 = {"entries": [
    _entry(0, 22407, 14, "SPN 22407: Unknown SPN 22407 (FMI 14: Special Instructions)"),
    _entry(0, None, None, "3 Active Faults (details not decoded)"),
    _entry(3, 110, 0, "SPN 110: Engine Coolant Temperature (FMI 0: Data Valid - Above Normal Range)"),
]}
STORE_KEY = fault_history_store_key("HE8EV12LF", "can2")


def _load_sensor(coord):
    sensor = SenquipDM1FaultHistorySensor(coord, "can2", "HE8EV12LF", "Starboard Senquip Quad")
    asyncio.run(sensor.async_added_to_hass())
    return sensor


class TestBigEndianLogCorrection:
    @pytest.mark.parametrize(
        "big_endian, little_endian",
        # Pairs from the live capture and the MAN PDF table (bytes FE 00 C2, 00 0C 81)
        [(22407, 520202), (520198, 393470), (100, 265216), (0, 0)],
    )
    def test_spn_conversion(self, big_endian, little_endian):
        assert big_endian_spn_to_little_endian(big_endian) == little_endian

    def test_v070_log_corrected_on_load(self):
        Store.saved[STORE_KEY] = LOG_V070
        coord = _coordinator()
        sensor = _load_sensor(coord)
        by_source = {}
        for entry in sensor.extra_state_attributes["faults"]:
            by_source.setdefault(entry["source_address"], []).append(entry)
        man = {e["spn"]: e for e in by_source[0]}
        assert set(man) == {520202, None}
        assert man[520202]["description"] == (
            "SPN 520202: Engine Start Prevented (FMI 14: Special Instructions)"
        )
        assert man[520202]["count"] == 2  # history kept
        # Not a MAN source: never decoded big-endian, left alone
        assert [e["spn"] for e in by_source[3]] == [110]
        assert _fired(coord) == []  # a correction is not a fault transition
        sensor._store.flush()
        assert Store.saved[STORE_KEY]["format"] == FAULT_LOG_FORMAT

    def test_corrected_active_fault_continues_without_events(self):
        """A fault active across the upgrade must not fire a false clear/raise."""
        Store.saved[STORE_KEY] = {"entries": [
            _entry(0, 22407, 14, "SPN 22407: Unknown SPN 22407", active=True),
        ]}
        coord = _coordinator()
        sensor = _load_sensor(coord)
        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor._handle_coordinator_update()
        assert _fired(coord) == []
        [entry] = sensor.extra_state_attributes["faults"]
        assert entry["spn"] == 520202 and entry["active"] is True

    def test_current_format_not_converted(self):
        Store.saved[STORE_KEY] = {"format": FAULT_LOG_FORMAT, "entries": LOG_V070["entries"]}
        sensor = _load_sensor(_coordinator())
        assert 22407 in [e["spn"] for e in sensor.extra_state_attributes["faults"]]
        assert sensor._store.save_calls == 0

    def test_restore_state_log_converted_for_every_source(self):
        """0.6.0 decoded every source on the MAN port big-endian."""
        log_v060 = {"entries": [
            _entry(0, 22407, 14, "SPN 22407: Unknown SPN 22407"),
            # Coolant SPN 110 from a gearbox ECU (bytes 6E 00 00) read big-endian
            _entry(3, 225280, 0, "SPN 225280: Unknown SPN 225280"),
        ]}
        coord = _coordinator()
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "HE8EV12LF", "Starboard Senquip Quad")
        sensor._stub_last_extra_data = MagicMock(as_dict=MagicMock(return_value=log_v060))
        asyncio.run(sensor.async_added_to_hass())
        by_source = {e["source_address"]: e for e in sensor.extra_state_attributes["faults"]}
        assert by_source[0]["spn"] == 520202
        assert by_source[3]["spn"] == 110
        assert by_source[3]["description"].startswith("SPN 110: Engine Coolant Temperature")

    def test_port_without_man_profile_not_converted(self):
        """Only the bundled MAN profile ever decoded big-endian."""
        Store.saved[STORE_KEY] = LOG_V070
        sensor = _load_sensor(_coordinator(profiles=()))
        assert 22407 in [e["spn"] for e in sensor.extra_state_attributes["faults"]]
        assert sensor._store.save_calls == 0

    def test_corrected_spn_equal_to_another_old_spn(self):
        """22407 becomes 520202 while the old 520202 becomes 131582: keep both."""
        log = DM1FaultLog.from_dict({"entries": [
            _entry(0, 22407, 14, "a"),
            _entry(0, 520202, 14, "b", active=True),
        ]})
        assert log.convert_big_endian_spns(lambda s: True, lambda src, spn, fmi: f"SPN {spn}") is True
        by_spn = {e["spn"]: e for e in log.entries}
        assert set(by_spn) == {520202, 131582}
        assert by_spn[131582]["active"] is True
        assert by_spn[520202]["description"] == "SPN 520202"
