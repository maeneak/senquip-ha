"""Tests for config flow step behavior."""

import asyncio
from pathlib import Path
from unittest.mock import patch

from custom_components.senquip.can_profiles.loader import discover_profiles
from custom_components.senquip.config_flow import (
    DiscoveredSignal,
    SenquipConfigFlow,
    SenquipOptionsFlow,
)
from custom_components.senquip.const import build_default_port_configs
from custom_components.senquip.signal_keys import LEGACY_SELECTED_SENSORS_KEY


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


def test_options_select_signals_defaults_match_legacy_selected_keys():
    class _Entry:
        def __init__(self) -> None:
            self.data = {
                LEGACY_SELECTED_SENSORS_KEY: [
                    "internal.vsys",
                    "can1.spn190",
                    "events.last",
                ]
            }

    flow = SenquipOptionsFlow(_Entry())
    flow._discovered_signals = {
        "Internal": [
            DiscoveredSignal(
                key="internal.main.vsys",
                name="System Voltage",
                sample_value=12.1,
                unit="V",
                default_selected=False,
            )
        ],
        "CAN1": [
            DiscoveredSignal(
                key="can.can1.j1939.spn190",
                name="Engine Speed (EEC1)",
                sample_value=1500,
                unit="rpm",
                default_selected=False,
            )
        ],
        "Events": [
            DiscoveredSignal(
                key="event.main.last",
                name="Last Event",
                sample_value="CPU threshold exceeded",
                unit=None,
                default_selected=False,
            )
        ],
    }

    with patch(
        "custom_components.senquip.config_flow.normalize_selected_signals",
        return_value=[
            "internal.main.vsys",
            "can.can1.j1939.spn190",
            "event.main.last",
        ],
    ) as normalize:
        result = asyncio.run(flow.async_step_select_signals())

    assert result["step_id"] == "select_signals"
    normalize.assert_called_once_with(flow._config_entry.data)
