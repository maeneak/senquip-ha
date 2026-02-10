"""Tests for config-flow port detection and configuration defaults."""

from custom_components.senquip.config_flow import _detect_active_ports
from custom_components.senquip.const import build_default_port_configs


def test_detect_active_can_ports():
    payload = {"can1": [{"id": 1, "data": "AA"}], "vsys": 12.0}
    active = _detect_active_ports(payload)
    assert active["can1"] is True
    assert active["internal"] is True
    assert active["can2"] is False


def test_default_port_configs_include_scaffolded_ports():
    configs = build_default_port_configs({"can1": True, "internal": True})
    expected_ports = {
        "internal",
        "can1",
        "can2",
        "serial1",
        "input1",
        "input2",
        "output1",
        "current1",
        "current2",
        "ble",
        "gps",
    }
    assert set(configs) == expected_ports
    assert configs["can1"].active is True
    assert configs["can1"].protocol == "j1939"

