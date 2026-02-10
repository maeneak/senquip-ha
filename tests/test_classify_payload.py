"""Tests for config flow payload classification."""

from pathlib import Path

from custom_components.senquip.can_profiles.loader import discover_profiles
from custom_components.senquip.config_flow import _classify_payload
from custom_components.senquip.const import PortConfig, build_default_port_configs


EXAMPLE_PAYLOAD = {
    "deviceid": "HE8EV12LF",
    "vsys": 4.17,
    "vin": 28.27,
    "ambient": 38.45,
    "cp28": 1841,
    "can2": [
        {"id": 217056256, "data": "3FFFCD883927F4FF"},
        {"id": 419357952, "data": "5F27000000000000"},
        {"id": 419372032, "data": "C4F0FFFF00FF00FF"},
    ],
    "events": [{"topic": "mjs", "msg": "CPU Threshold Exceeded", "lv": 30}],
}


def _profiles():
    return discover_profiles(Path("custom_components/senquip/can_profiles"))


class TestClassifyInternal:
    def test_internal_signals_use_canonical_keys(self):
        port_configs = build_default_port_configs({"internal": True})
        result, _ = _classify_payload(EXAMPLE_PAYLOAD, port_configs, {})
        internal = result["Internal"]
        keys = {signal.key for signal in internal}
        assert "internal.main.vsys" in keys
        assert "internal.main.cp28" in keys


class TestClassifyCAN:
    def test_can_signals_use_canonical_keys(self):
        port_configs = build_default_port_configs({"can2": True})
        result, active_ports = _classify_payload(EXAMPLE_PAYLOAD, port_configs, _profiles())
        can2 = result["CAN2"]
        keys = {signal.key for signal in can2}
        assert "can.can2.j1939.spn190" in keys
        assert "can.can2.j1939.spn247" in keys
        assert "can.can2.j1939.raw.65308" in keys
        assert "can.can2.j1939.dm1.active_fault" in keys
        assert active_ports == {"can2"}

    def test_can_profiles_are_applied(self):
        port_configs = build_default_port_configs({"can2": True})
        port_configs["can2"] = PortConfig(
            family="can",
            active=True,
            protocol="j1939",
            profiles=("man_d2862.json",),
        )
        payload = {
            "can2": [{"id": 419372032, "data": "C4F0FFFF00FF00FF"}],
        }
        result, _ = _classify_payload(payload, port_configs, _profiles())
        keys = {signal.key for signal in result["CAN2"]}
        assert "can.can2.j1939.spn800001" in keys


class TestClassifyEvents:
    def test_events_key(self):
        port_configs = build_default_port_configs({"internal": True})
        result, _ = _classify_payload(EXAMPLE_PAYLOAD, port_configs, {})
        assert result["Events"][0].key == "event.main.last"
