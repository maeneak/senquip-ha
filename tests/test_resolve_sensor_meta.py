"""Tests for sensor.py _resolve_sensor_meta."""

import pytest

from custom_components.senquip.sensor import _resolve_sensor_meta
from custom_components.senquip.const import SensorMeta


class TestResolveInternalSensors:
    """Test _resolve_sensor_meta for internal.* keys."""

    def test_known_internal_vsys(self):
        meta = _resolve_sensor_meta("internal.vsys")
        assert meta.name == "System Voltage"
        assert meta.device_class is not None
        assert meta.unit is not None

    def test_known_internal_ambient(self):
        meta = _resolve_sensor_meta("internal.ambient")
        assert meta.name == "Ambient Temperature"

    def test_known_internal_wifi_rssi(self):
        meta = _resolve_sensor_meta("internal.wifi_rssi")
        assert meta.name == "WiFi Signal Strength"
        assert meta.entity_category is not None

    def test_known_internal_wifi_ip(self):
        meta = _resolve_sensor_meta("internal.wifi_ip")
        assert meta.name == "WiFi IP Address"
        assert meta.state_class is None  # Not a measurement

    def test_unknown_internal_uses_title_case(self):
        meta = _resolve_sensor_meta("internal.some_custom_field")
        assert meta.name == "Some Custom Field"
        assert meta.device_class is None


class TestResolveCAN:
    """Test _resolve_sensor_meta for CAN SPN keys."""

    def test_known_spn190(self):
        meta = _resolve_sensor_meta("can2.spn190")
        assert "Engine Speed" in meta.name
        assert "EEC1" in meta.name
        assert meta.unit == "rpm"

    def test_known_spn110(self):
        meta = _resolve_sensor_meta("can1.spn110")
        assert "Coolant" in meta.name or "Engine Coolant" in meta.name
        assert meta.unit is not None

    def test_known_spn84_vehicle_speed(self):
        meta = _resolve_sensor_meta("can2.spn84")
        assert "Vehicle Speed" in meta.name
        assert meta.device_class is not None  # SensorDeviceClass.SPEED

    def test_known_spn247_hours(self):
        meta = _resolve_sensor_meta("can1.spn247")
        assert "Hours" in meta.name
        assert meta.device_class is not None  # DURATION

    def test_unknown_spn(self):
        meta = _resolve_sensor_meta("can2.spn99999")
        assert "SPN 99999" in meta.name
        assert "CAN2" in meta.name

    def test_port_in_name(self):
        meta1 = _resolve_sensor_meta("can1.spn190")
        meta2 = _resolve_sensor_meta("can2.spn190")
        assert "CAN1" in meta1.name
        assert "CAN2" in meta2.name


class TestResolveRawPGN:
    """Test _resolve_sensor_meta for raw PGN keys."""

    def test_raw_pgn(self):
        meta = _resolve_sensor_meta("can2.raw.65308")
        assert "PGN 65308" in meta.name
        assert "Raw" in meta.name
        assert meta.state_class is None

    def test_raw_pgn_can1(self):
        meta = _resolve_sensor_meta("can1.raw.12345")
        assert "CAN1" in meta.name


class TestResolveCustom:
    """Test _resolve_sensor_meta for custom parameter keys."""

    def test_custom_param(self):
        meta = _resolve_sensor_meta("custom.cp18")
        assert meta.name == "Custom Parameter 18"
        assert meta.icon == "mdi:numeric"

    def test_custom_param_high(self):
        meta = _resolve_sensor_meta("custom.cp34")
        assert meta.name == "Custom Parameter 34"


class TestResolveEvents:
    """Test _resolve_sensor_meta for events keys."""

    def test_events_last(self):
        meta = _resolve_sensor_meta("events.last")
        assert meta.name == "Last Event"
        assert meta.state_class is None
        assert meta.entity_category is not None
        assert meta.icon == "mdi:alert-circle-outline"


class TestResolveFallback:
    """Test fallback for completely unknown sensor keys."""

    def test_unknown_key(self):
        meta = _resolve_sensor_meta("totally.unknown.key")
        assert meta.name == "totally.unknown.key"


class TestResolveNewUnitMappings:
    """Test that newly added unit mappings work for LFE1/VEP1 SPNs."""

    def test_spn183_fuel_rate(self):
        meta = _resolve_sensor_meta("can1.spn183")
        assert "Fuel Rate" in meta.name
        assert meta.unit == "L/h"

    def test_spn184_fuel_economy(self):
        meta = _resolve_sensor_meta("can1.spn184")
        assert "Fuel Economy" in meta.name
        assert meta.unit == "km/L"

    def test_spn114_battery_current(self):
        meta = _resolve_sensor_meta("can1.spn114")
        assert "Battery Current" in meta.name
        assert meta.unit == "A"
        assert meta.device_class is not None  # CURRENT
