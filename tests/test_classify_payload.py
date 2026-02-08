"""Tests for config flow _classify_payload."""

import pytest

from custom_components.senquip.config_flow import _classify_payload, DiscoveredSensor


# ---------------------------------------------------------------------------
# Example payloads
# ---------------------------------------------------------------------------

EXAMPLE_PAYLOAD = {
    "deviceid": "HE8EV12LF",
    "vsys": 4.17,
    "vin": 28.27,
    "ambient": 38.45,
    "light": 0,
    "state": 0,
    "accel_x": 1.06,
    "wifi_ip": "192.168.100.179",
    "wifi_rssi": -23,
    "ts": 1770527194.9,
    "time": 1770527195,
    "cp18": 504,
    "cp28": 1841,
    "can2": [
        {"id": 217056256, "data": "3FFFCD883927F4FF"},  # EEC1
        {"id": 419357952, "data": "5F27000000000000"},  # HOURS
        {"id": 419372032, "data": "C4F0FFFF00FF00FF"},  # Unknown PGN 65308
    ],
    "events": [
        {"topic": "mjs", "msg": "CPU Threshold Exceeded", "lv": 30}
    ],
}


class TestClassifyInternal:
    """Test internal sensor classification."""

    def test_known_internal_sensors_discovered(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        internal = result.get("Internal", [])
        keys = {s.key for s in internal}
        assert "internal.vsys" in keys
        assert "internal.vin" in keys
        assert "internal.ambient" in keys
        assert "internal.wifi_ip" in keys

    def test_known_sensor_uses_metadata_name(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        internal = result["Internal"]
        vsys = next(s for s in internal if s.key == "internal.vsys")
        assert vsys.name == "System Voltage"

    def test_unknown_internal_uses_title_case(self):
        payload = {"some_field": 42}
        result = _classify_payload(payload)
        internal = result["Internal"]
        assert internal[0].name == "Some Field"

    def test_metadata_fields_excluded(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        internal = result.get("Internal", [])
        keys = {s.key for s in internal}
        assert "internal.deviceid" not in keys
        assert "internal.ts" not in keys
        assert "internal.time" not in keys

    def test_internal_default_selected(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        for sensor in result["Internal"]:
            assert sensor.default_selected is True

    def test_sample_values_captured(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        internal = result["Internal"]
        vsys = next(s for s in internal if s.key == "internal.vsys")
        assert vsys.sample_value == 4.17

    def test_known_sensor_has_unit(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        internal = result["Internal"]
        vsys = next(s for s in internal if s.key == "internal.vsys")
        assert vsys.unit is not None  # Volt


class TestClassifyCAN:
    """Test CAN sensor classification."""

    def test_known_pgn_produces_spn_sensors(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        can2 = result.get("CAN2", [])
        keys = {s.key for s in can2}
        assert "can2.spn190" in keys  # Engine Speed
        assert "can2.spn247" in keys  # Total Hours

    def test_spn_sensor_has_name_with_acronym(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        can2 = result["CAN2"]
        spn190 = next(s for s in can2 if s.key == "can2.spn190")
        assert "Engine Speed" in spn190.name
        assert "EEC1" in spn190.name

    def test_spn_sample_value(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        can2 = result["CAN2"]
        spn190 = next(s for s in can2 if s.key == "can2.spn190")
        assert spn190.sample_value == 1841.0

    def test_spn_with_none_value_not_default_selected(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        can2 = result["CAN2"]
        none_spns = [s for s in can2 if s.sample_value is None and s.key.startswith("can2.spn")]
        for s in none_spns:
            assert s.default_selected is False

    def test_spn_with_value_default_selected(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        can2 = result["CAN2"]
        spn190 = next(s for s in can2 if s.key == "can2.spn190")
        assert spn190.default_selected is True

    def test_unknown_pgn_produces_raw_sensor(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        can2 = result["CAN2"]
        raw = [s for s in can2 if "raw" in s.key]
        assert len(raw) >= 1
        raw65308 = next(s for s in raw if "65308" in s.key)
        assert raw65308.default_selected is False
        assert "Unknown PGN" in raw65308.name

    def test_duplicate_spns_deduplicated(self):
        """Same PGN appearing twice should not create duplicate SPN sensors."""
        payload = {
            "can1": [
                {"id": 217056256, "data": "3FFFCD883927F4FF"},
                {"id": 217056256, "data": "3FFFCD883927F4FF"},  # duplicate
            ]
        }
        result = _classify_payload(payload)
        can1 = result.get("CAN1", [])
        spn190_count = sum(1 for s in can1 if s.key == "can1.spn190")
        assert spn190_count == 1


class TestClassifyCustom:
    """Test custom parameter classification."""

    def test_custom_params_discovered(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        custom = result.get("Custom", [])
        keys = {s.key for s in custom}
        assert "custom.cp18" in keys
        assert "custom.cp28" in keys

    def test_custom_param_name(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        custom = result["Custom"]
        cp18 = next(s for s in custom if s.key == "custom.cp18")
        assert cp18.name == "Parameter 18"

    def test_custom_default_selected(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        for s in result["Custom"]:
            assert s.default_selected is True

    def test_custom_sample_value(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        custom = result["Custom"]
        cp18 = next(s for s in custom if s.key == "custom.cp18")
        assert cp18.sample_value == 504


class TestClassifyEvents:
    """Test events classification."""

    def test_events_discovered(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        events = result.get("Events", [])
        assert len(events) == 1
        assert events[0].key == "events.last"

    def test_events_sample_message(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        events = result["Events"]
        assert events[0].sample_value == "CPU Threshold Exceeded"

    def test_events_default_selected(self):
        result = _classify_payload(EXAMPLE_PAYLOAD)
        assert result["Events"][0].default_selected is True

    def test_no_events_key_if_missing(self):
        payload = {"vsys": 4.0}
        result = _classify_payload(payload)
        assert "Events" not in result


class TestClassifyEdgeCases:
    """Edge case tests for classification."""

    def test_empty_payload(self):
        result = _classify_payload({})
        assert result == {}

    def test_only_metadata(self):
        result = _classify_payload({"deviceid": "X", "ts": 1, "time": 2})
        assert result == {}

    def test_empty_can_list(self):
        result = _classify_payload({"can1": []})
        assert "CAN1" not in result

    def test_missing_frame_fields(self):
        result = _classify_payload({"can1": [{"id": 1}, {"data": "AA"}, {}]})
        # No valid frames → no CAN1 category
        assert "CAN1" not in result

    def test_empty_events_list(self):
        result = _classify_payload({"events": []})
        events = result.get("Events", [])
        assert len(events) == 1
        assert events[0].sample_value == ""

    def test_non_numeric_non_str_values_ignored(self):
        """Dict/list values that aren't CAN/events are ignored."""
        result = _classify_payload({"nested": {"a": 1}})
        assert "Internal" not in result
