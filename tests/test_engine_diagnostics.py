"""Tests for engine diagnostics: starter mode, controlling device, gearbox, fault events.

Frames are taken from a capture of the MAN D2862 engines on 2026-11-27.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.senquip import SenquipDataCoordinator
from custom_components.senquip.can_profiles.loader import discover_profiles
from custom_components.senquip.can_protocols.j1939.protocol import J1939CANProtocol
from custom_components.senquip.const import EVENT_DM1_FAULT, SensorDeviceClass
from custom_components.senquip.fault_history import DM1FaultLog
from custom_components.senquip import sensor as sensor_module
from custom_components.senquip.sensor import SenquipDM1FaultHistorySensor, _resolve_sensor_meta
from tests.ha_stubs import ConfigEntry

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
            ("C0", "No Position"),  # port engine in gear; starboard after power-up
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

    def test_no_position_is_an_option(self):
        meta = _resolve_sensor_meta("can.can2.j1939.spn800005", _CoordinatorStub())
        assert meta.options == ["No Position", "Neutral", "Forward", "Reverse"]


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


def _coordinator():
    entry = ConfigEntry(data={
        "device_id": "HE8EV12LF",
        "device_name": "Starboard Senquip Quad",
        "mqtt_topic": "senquip/quad/stbd/json",
        "selected_signals": ["can.can2.j1939.dm1.active_fault"],
        "port_configs": {"can2": {
            "family": "can", "active": True, "protocol": "j1939",
            "profiles": ["man_d2862.json"],
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
        device = MagicMock(name_by_user="D2862 LE466 (Starboard)")
        registry = MagicMock()
        registry.async_get.return_value = device
        monkeypatch.setattr(sensor_module.dr, "async_get", MagicMock(return_value=registry), raising=False)

        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor._handle_coordinator_update()
        [raised] = _fired(coord)
        assert raised["device_id"] == "abc123"
        assert raised["device_name"] == "D2862 LE466 (Starboard)"
        registry.async_get.assert_called_once_with("abc123")

    def test_pending_payload_at_startup_fires_event(self):
        coord = _coordinator()
        coord._parse_payload(_dm1_payload("D0FF0AF0EE01FFFF"))
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "HE8EV12LF", "Starboard Senquip Quad")
        import asyncio
        asyncio.run(sensor.async_added_to_hass())
        assert [e["status"] for e in _fired(coord)] == ["active"]
