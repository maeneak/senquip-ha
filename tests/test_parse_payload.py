"""Tests for SenquipDataCoordinator._parse_payload."""

import pytest

from custom_components.senquip.j1939_decoder import J1939Decoder


# We test _parse_payload logic directly by reimplementing the same algorithm
# used in SenquipDataCoordinator._parse_payload without needing a full HA
# environment.  This validates the pure data-transformation logic.


def _parse_payload(payload: dict, selected: set[str]) -> dict:
    """Standalone reimplementation of SenquipDataCoordinator._parse_payload.

    This mirrors __init__.py exactly so we can unit-test without HA.
    """
    decoder = J1939Decoder()
    data: dict = {}

    for key, value in payload.items():
        if key in ("deviceid", "ts", "time"):
            continue

        if key in ("can1", "can2") and isinstance(value, list):
            for frame in value:
                can_id = frame.get("id")
                hex_data = frame.get("data")
                if can_id is None or hex_data is None:
                    continue
                decoded = decoder.decode_frame(can_id, hex_data)
                for spn_num, spn_value in decoded.items():
                    sensor_key = f"{key}.spn{spn_num}"
                    if sensor_key in selected:
                        data[sensor_key] = spn_value
                if not decoded:
                    _, pgn, _ = decoder.extract_pgn(can_id)
                    raw_key = f"{key}.raw.{pgn}"
                    if raw_key in selected:
                        data[raw_key] = hex_data

        elif key == "events" and isinstance(value, list):
            if "events.last" in selected and value:
                last_event = value[-1]
                if isinstance(last_event, dict):
                    data["events.last"] = last_event.get("msg", "")

        elif key.startswith("cp") and key[2:].isdigit():
            sensor_key = f"custom.{key}"
            if sensor_key in selected:
                data[sensor_key] = value

        elif isinstance(value, (int, float, str)):
            sensor_key = f"internal.{key}"
            if sensor_key in selected:
                data[sensor_key] = value

    return data


# ---------------------------------------------------------------------------
# Example payload from example.json (device HE8EV12LF)
# ---------------------------------------------------------------------------

EXAMPLE_PAYLOAD = {
    "deviceid": "HE8EV12LF",
    "vsys": 4.17,
    "vin": 28.27,
    "ambient": 38.45,
    "light": 0,
    "movement_hrs": 0,
    "state": 0,
    "accel_x": 1.06,
    "accel_y": -0.01,
    "accel_z": -0.07,
    "roll": -0.5,
    "pitch": -86.1,
    "angle": 86.1,
    "motion": 392,
    "ts": 1770527194.9,
    "time": 1770527195,
    "wifi_ip": "192.168.100.179",
    "wifi_rssi": -23,
    "cp18": 504,
    "cp19": 86,
    "cp28": 1841,
    "can2": [
        {"id": 217056256, "data": "3FFFCD883927F4FF"},  # EEC1
        {"id": 419357952, "data": "5F27000000000000"},  # HOURS
        {"id": 419360256, "data": "A0FFFFB3FFFF9CFA"},  # ET1 (0x18FEEE00)
        {"id": 419372032, "data": "C4F0FFFF00FF00FF"},  # Unknown PGN 65308
    ],
}


class TestParsePayloadInternal:
    """Test internal/flat sensor extraction."""

    def test_selected_internal_included(self):
        selected = {"internal.vsys", "internal.vin", "internal.ambient"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert result["internal.vsys"] == 4.17
        assert result["internal.vin"] == 28.27
        assert result["internal.ambient"] == 38.45

    def test_unselected_internal_excluded(self):
        selected = {"internal.vsys"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert "internal.vin" not in result
        assert "internal.ambient" not in result

    def test_metadata_fields_skipped(self):
        selected = {"internal.deviceid", "internal.ts", "internal.time"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert result == {}

    def test_string_internal(self):
        selected = {"internal.wifi_ip"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert result["internal.wifi_ip"] == "192.168.100.179"


class TestParsePayloadCAN:
    """Test CAN frame decoding in _parse_payload."""

    def test_known_spn_decoded(self):
        selected = {"can2.spn190", "can2.spn247"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert result["can2.spn190"] == 1841.0
        assert result["can2.spn247"] == 503.95

    def test_unselected_spn_excluded(self):
        selected = {"can2.spn190"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert "can2.spn247" not in result

    def test_raw_unknown_pgn(self):
        selected = {"can2.raw.65308"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert result["can2.raw.65308"] == "C4F0FFFF00FF00FF"

    def test_raw_pgn_not_emitted_for_known_pgns(self):
        """Known PGNs produce SPN keys, not raw keys."""
        selected = {"can2.raw.61444"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert "can2.raw.61444" not in result

    def test_coolant_temp(self):
        selected = {"can2.spn110"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert result["can2.spn110"] == 120


class TestParsePayloadCustom:
    """Test custom parameter extraction."""

    def test_selected_custom_params(self):
        selected = {"custom.cp18", "custom.cp28"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert result["custom.cp18"] == 504
        assert result["custom.cp28"] == 1841

    def test_unselected_custom_excluded(self):
        selected = {"custom.cp18"}
        result = _parse_payload(EXAMPLE_PAYLOAD, selected)
        assert "custom.cp19" not in result


class TestParsePayloadEvents:
    """Test event extraction."""

    def test_events_last(self):
        payload = {
            **EXAMPLE_PAYLOAD,
            "events": [
                {"topic": "mjs", "msg": "CPU Threshold Exceeded", "lv": 30}
            ],
        }
        selected = {"events.last"}
        result = _parse_payload(payload, selected)
        assert result["events.last"] == "CPU Threshold Exceeded"

    def test_events_empty_list(self):
        payload = {**EXAMPLE_PAYLOAD, "events": []}
        selected = {"events.last"}
        result = _parse_payload(payload, selected)
        assert "events.last" not in result

    def test_events_not_selected(self):
        payload = {
            **EXAMPLE_PAYLOAD,
            "events": [{"topic": "t", "msg": "hello", "lv": 1}],
        }
        selected = set()
        result = _parse_payload(payload, selected)
        assert "events.last" not in result

    def test_events_last_takes_last_item(self):
        payload = {
            **EXAMPLE_PAYLOAD,
            "events": [
                {"msg": "first"},
                {"msg": "second"},
                {"msg": "third"},
            ],
        }
        selected = {"events.last"}
        result = _parse_payload(payload, selected)
        assert result["events.last"] == "third"


class TestParsePayloadEdgeCases:
    """Edge case tests."""

    def test_empty_payload(self):
        result = _parse_payload({}, {"internal.vsys"})
        assert result == {}

    def test_missing_can_frame_fields(self):
        payload = {"can1": [{"id": 217056256}, {"data": "AABB"}, {}]}
        result = _parse_payload(payload, {"can1.spn190"})
        assert result == {}

    def test_non_dict_non_list_values_ignored(self):
        """Nested dicts/lists (that aren't CAN/events) are ignored."""
        payload = {"nested": {"a": 1}, "also_nested": [1, 2, 3]}
        result = _parse_payload(payload, {"internal.nested"})
        assert result == {}

    def test_array_payload_not_handled_by_parse(self):
        """_parse_payload expects a dict (array unwrap is in _handle_message)."""
        result = _parse_payload({"vsys": 4.0}, {"internal.vsys"})
        assert result["internal.vsys"] == 4.0
