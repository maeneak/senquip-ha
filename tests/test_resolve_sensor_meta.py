"""Tests for sensor metadata resolution with canonical keys."""

from custom_components.senquip.can_protocols.j1939.protocol import J1939CANProtocol
from custom_components.senquip.sensor import _resolve_sensor_meta


class _CoordinatorStub:
    def __init__(self):
        protocol = J1939CANProtocol()
        self._can_runtime = {"can1": (protocol, protocol.build_decoder([]))}


class TestResolveInternal:
    def test_known_internal(self):
        meta = _resolve_sensor_meta("internal.main.vsys", _CoordinatorStub())
        assert meta.name == "System Voltage"
        assert meta.unit is not None

    def test_unknown_internal(self):
        meta = _resolve_sensor_meta("internal.main.some_custom_field", _CoordinatorStub())
        assert meta.name == "Some Custom Field"


class TestResolveCAN:
    def test_known_spn(self):
        meta = _resolve_sensor_meta("can.can1.j1939.spn190", _CoordinatorStub())
        assert "Engine Speed" in meta.name
        assert meta.unit == "rpm"

    def test_raw_pgn(self):
        meta = _resolve_sensor_meta("can.can1.j1939.raw.65308", _CoordinatorStub())
        assert "PGN 65308" in meta.name

    def test_dm1_field(self):
        meta = _resolve_sensor_meta("can.can1.j1939.dm1.active_fault", _CoordinatorStub())
        assert "DM1 Active Fault" in meta.name


class TestResolveEvent:
    def test_event(self):
        meta = _resolve_sensor_meta("event.main.last", _CoordinatorStub())
        assert meta.name == "Last Event"

