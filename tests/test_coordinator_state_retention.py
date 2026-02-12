"""Tests for coordinator merge behavior and invalid value filtering."""

from __future__ import annotations

import json

from custom_components.senquip.__init__ import SenquipDataCoordinator
from custom_components.senquip.const import (
    CONF_DEVICE_ID,
    CONF_PORT_CONFIGS,
    CONF_SELECTED_SIGNALS,
)
from tests.ha_stubs import ConfigEntry, _MQTTModels


def _build_coordinator(selected_signals: list[str]) -> SenquipDataCoordinator:
    entry = ConfigEntry(
        data={
            CONF_DEVICE_ID: "DEV1",
            CONF_SELECTED_SIGNALS: selected_signals,
            CONF_PORT_CONFIGS: {},
        }
    )
    return SenquipDataCoordinator(None, entry)


def _message(payload: dict) -> _MQTTModels.ReceiveMessage:
    return _MQTTModels.ReceiveMessage(topic="senquip/DEV1/data", payload=json.dumps(payload))


def test_missing_signal_does_not_clear_previous_value():
    coordinator = _build_coordinator(["internal.main.vsys", "internal.main.vin"])
    coordinator.data = {
        "internal.main.vsys": 12.3,
        "internal.main.vin": 24.1,
    }

    coordinator._handle_message(_message({"deviceid": "DEV1", "vin": 24.2}))

    assert coordinator.data["internal.main.vsys"] == 12.3
    assert coordinator.data["internal.main.vin"] == 24.2


def test_null_internal_value_is_ignored():
    coordinator = _build_coordinator(["internal.main.vin"])
    coordinator.data = {"internal.main.vin": 24.1}

    coordinator._handle_message(_message({"deviceid": "DEV1", "vin": None}))

    assert coordinator.data["internal.main.vin"] == 24.1


def test_non_finite_internal_value_is_ignored():
    coordinator = _build_coordinator(["internal.main.vin"])
    coordinator.data = {"internal.main.vin": 24.1}

    coordinator._handle_message(_message({"deviceid": "DEV1", "vin": float("nan")}))
    assert coordinator.data["internal.main.vin"] == 24.1

    coordinator._handle_message(_message({"deviceid": "DEV1", "vin": float("inf")}))
    assert coordinator.data["internal.main.vin"] == 24.1


def test_null_event_message_is_ignored():
    coordinator = _build_coordinator(["event.main.last"])
    coordinator.data = {"event.main.last": "Old Event"}

    coordinator._handle_message(
        _message(
            {
                "deviceid": "DEV1",
                "events": [{"topic": "mjs", "msg": None, "lv": 30}],
            }
        )
    )

    assert coordinator.data["event.main.last"] == "Old Event"


def test_valid_update_overwrites_previous_value():
    coordinator = _build_coordinator(["event.main.last"])
    coordinator.data = {"event.main.last": "Old Event"}

    coordinator._handle_message(
        _message(
            {
                "deviceid": "DEV1",
                "events": [{"topic": "mjs", "msg": "New Event", "lv": 30}],
            }
        )
    )

    assert coordinator.data["event.main.last"] == "New Event"
