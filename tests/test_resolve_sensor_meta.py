"""Tests for sensor metadata resolution with canonical keys."""

from pathlib import Path

from custom_components.senquip.can_profiles.loader import discover_profiles
from custom_components.senquip.can_protocols.j1939.protocol import J1939CANProtocol
from custom_components.senquip.const import EntityCategory, SensorDeviceClass, SensorStateClass
from custom_components.senquip.sensor import _resolve_sensor_meta


class _CoordinatorStub:
    def __init__(self, profiles=None):
        protocol = J1939CANProtocol()
        decoder, _errors = protocol.build_decoder(profiles or [])
        self._can_runtime = {"can1": (protocol, decoder), "can2": (protocol, decoder)}

    def get_can_runtime(self, port_id):
        return self._can_runtime.get(port_id)


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


class TestResolveStateMappedSPN:
    def test_gearbox_status_enum(self):
        """State-mapped SPN resolves as ENUM sensor with options."""
        repo_root = Path(__file__).resolve().parents[1]
        profile_dir = repo_root / "custom_components" / "senquip" / "can_profiles"
        profiles = discover_profiles(profile_dir)
        man_profile = profiles["man_d2862.json"]
        coord = _CoordinatorStub(profiles=[man_profile])

        meta = _resolve_sensor_meta("can.can2.j1939.spn800005", coord)
        assert "Gearbox Status" in meta.name
        assert meta.device_class == SensorDeviceClass.ENUM
        assert meta.state_class is None
        assert meta.unit is None
        assert meta.options is not None
        assert "Forward" in meta.options
        assert "Neutral" in meta.options
        assert "Reverse" in meta.options


class TestSPNStateClassOverrides:
    def test_trip_fuel_is_measurement(self):
        """SPN 182 (Engine Trip Fuel) should be MEASUREMENT, not TOTAL_INCREASING."""
        meta = _resolve_sensor_meta("can.can1.j1939.spn182", _CoordinatorStub())
        assert "Trip Fuel" in meta.name
        assert meta.state_class == SensorStateClass.MEASUREMENT

    def test_time_date_hours_is_measurement(self):
        """SPN 961 (Hours in Time/Date) should be MEASUREMENT, not TOTAL_INCREASING."""
        meta = _resolve_sensor_meta("can.can1.j1939.spn961", _CoordinatorStub())
        assert meta.state_class == SensorStateClass.MEASUREMENT

    def test_total_fuel_remains_total_increasing(self):
        """SPN 250 (Engine Total Fuel Used) should keep TOTAL_INCREASING."""
        meta = _resolve_sensor_meta("can.can1.j1939.spn250", _CoordinatorStub())
        assert "Total Fuel" in meta.name
        assert meta.state_class == SensorStateClass.TOTAL_INCREASING

    def test_total_hours_remains_total_increasing(self):
        """SPN 247 (Engine Total Hours) should keep TOTAL_INCREASING."""
        meta = _resolve_sensor_meta("can.can1.j1939.spn247", _CoordinatorStub())
        assert meta.state_class == SensorStateClass.TOTAL_INCREASING


class TestResolveEvent:
    def test_event(self):
        meta = _resolve_sensor_meta("event.main.last", _CoordinatorStub())
        assert meta.name == "Last Event"
        assert meta.state_class is None
        assert meta.entity_category == EntityCategory.DIAGNOSTIC
        assert meta.icon == "mdi:alert-circle-outline"

