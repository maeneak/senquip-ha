"""Tests for config flow step behavior."""

import asyncio
from pathlib import Path

from custom_components.senquip.can_profiles.loader import discover_profiles
from custom_components.senquip.config_flow import DiscoveredSignal, SenquipConfigFlow
from custom_components.senquip.const import build_default_port_configs


def test_configure_ports_shows_active_can_fields():
    flow = SenquipConfigFlow()
    flow._port_configs = build_default_port_configs({"can1": True})
    flow._available_profiles = discover_profiles(Path("custom_components/senquip/can_profiles"))
    result = asyncio.run(flow.async_step_configure_ports())

    assert result["step_id"] == "configure_ports"
    schema = result["data_schema"]
    assert "protocol_can1" in schema
    assert "profiles_can1" in schema


def test_configure_ports_skips_when_no_active_can():
    flow = SenquipConfigFlow()
    flow._device_id = "DEV001"
    flow._port_configs = build_default_port_configs({"internal": True})
    flow._discovered_signals = {
        "Internal": [
            DiscoveredSignal(
                key="internal.main.vsys",
                name="System Voltage",
                sample_value=12.0,
                unit="V",
                default_selected=True,
            )
        ]
    }
    result = asyncio.run(flow.async_step_configure_ports())
    assert result["step_id"] == "select_signals"


def test_select_signals_persists_new_schema():
    flow = SenquipConfigFlow()
    flow._device_name = "Device A"
    flow._device_id = "DEV001"
    flow._mqtt_topic = "senquip/test/topic"
    flow._port_configs = build_default_port_configs({"can1": True, "internal": True})
    result = asyncio.run(
        flow.async_step_select_signals(
            {"selected_signals": ["internal.main.vsys", "can.can1.j1939.spn190"]}
        )
    )
    assert result["data"]["selected_signals"] == [
        "internal.main.vsys",
        "can.can1.j1939.spn190",
    ]
    assert "port_configs" in result["data"]
