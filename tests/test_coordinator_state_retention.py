"""Tests for coordinator merge behavior and invalid value filtering."""

from __future__ import annotations

import json

from custom_components.senquip.__init__ import SenquipDataCoordinator
from custom_components.senquip.const import (
    CONF_DEVICE_ID,
    CONF_PORT_CONFIGS,
    CONF_SELECTED_SIGNALS,
    SensorMeta,
    SensorStateClass,
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
    return SenquipDataCoordinator(None, entry, {})


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


def test_small_total_increasing_regression_is_ignored_for_internal_counter():
    coordinator = _build_coordinator(["internal.main.motion"])
    coordinator.data = {"internal.main.motion": 244.0}

    coordinator._handle_message(_message({"deviceid": "DEV1", "motion": 240}))

    assert coordinator.data["internal.main.motion"] == 244.0


def test_large_total_increasing_drop_is_kept_as_possible_new_cycle():
    coordinator = _build_coordinator(["internal.main.motion"])
    coordinator.data = {"internal.main.motion": 244.0}

    coordinator._handle_message(_message({"deviceid": "DEV1", "motion": 10}))

    assert coordinator.data["internal.main.motion"] == 10


class _ProtocolStub:
    """Stub that always returns a valid SPN value."""

    def decode_runtime(self, _frames, _port_id, _selected_signals, _decoder):
        return {"can.can1.j1939.spn247": 62395000}, [], True

    def resolve_signal_meta(self, _signal_key, _decoder):
        return SensorMeta(
            name="Engine Total Revolutions",
            state_class=SensorStateClass.TOTAL_INCREASING,
            unit="h",
        )


class _EmptyProtocolStub:
    """Stub that returns no valid values (simulates device shutdown)."""

    def decode_runtime(self, _frames, _port_id, _selected_signals, _decoder):
        return {}, [], False

    def resolve_signal_meta(self, _signal_key, _decoder):
        return SensorMeta(name="Engine Speed")


class _ToggleProtocolStub:
    """Stub whose decode_runtime returns can be controlled externally."""

    def __init__(self):
        self.values: dict = {}

    def decode_runtime(self, _frames, _port_id, _selected_signals, _decoder):
        return dict(self.values), [], bool(self.values)

    def resolve_signal_meta(self, _signal_key, _decoder):
        return SensorMeta(name="Engine Speed")


class _AvailableWithoutSelectedSignalsProtocolStub:
    """Stub that reports valid runtime data even when no CAN values are selected."""

    def decode_runtime(self, _frames, _port_id, _selected_signals, _decoder):
        return {}, [], True

    def resolve_signal_meta(self, _signal_key, _decoder):
        return SensorMeta(name="Engine Speed")


def test_small_total_increasing_regression_is_ignored_for_can_counter():
    coordinator = _build_coordinator(["can.can1.j1939.spn247"])
    coordinator._can_runtime = {"can1": (_ProtocolStub(), None)}
    coordinator.data = {"can.can1.j1939.spn247": 62396000.0}

    coordinator._handle_message(
        _message({"deviceid": "DEV1", "can1": [{"id": 1, "data": "00"}]})
    )

    assert coordinator.data["can.can1.j1939.spn247"] == 62396000.0


# ── CAN port availability tracking ──────────────────────────────────────


def test_can_port_unavailable_when_all_spns_invalid():
    """Port with no valid decoded values is marked unavailable."""
    coordinator = _build_coordinator(["can.can1.j1939.spn190"])
    coordinator._can_runtime = {"can1": (_EmptyProtocolStub(), None)}

    coordinator._handle_message(
        _message({"deviceid": "DEV1", "can1": [{"id": 1, "data": "FFFFFFFFFFFFFFFF"}]})
    )

    assert coordinator.is_can_port_available("can1") is False


def test_can_port_available_when_spns_valid():
    """Port with valid decoded values is marked available."""
    coordinator = _build_coordinator(["can.can1.j1939.spn247"])
    coordinator._can_runtime = {"can1": (_ProtocolStub(), None)}

    coordinator._handle_message(
        _message({"deviceid": "DEV1", "can1": [{"id": 1, "data": "00"}]})
    )

    assert coordinator.is_can_port_available("can1") is True


def test_can_port_defaults_to_available_when_unseen():
    """A port that hasn't appeared in any payload defaults to available."""
    coordinator = _build_coordinator(["can.can1.j1939.spn190"])
    assert coordinator.is_can_port_available("can1") is True


def test_can_port_availability_transitions():
    """Port availability updates correctly when device shuts down and restarts."""
    stub = _ToggleProtocolStub()
    coordinator = _build_coordinator(["can.can1.j1939.spn190"])
    coordinator._can_runtime = {"can1": (stub, None)}

    # Device running — valid data
    stub.values = {"can.can1.j1939.spn190": 1841.0}
    coordinator._handle_message(
        _message({"deviceid": "DEV1", "can1": [{"id": 1, "data": "00"}]})
    )
    assert coordinator.is_can_port_available("can1") is True
    assert coordinator.data["can.can1.j1939.spn190"] == 1841.0

    # Device shuts down — no valid data
    stub.values = {}
    coordinator._handle_message(
        _message({"deviceid": "DEV1", "can1": [{"id": 1, "data": "FFFFFFFFFFFFFFFF"}]})
    )
    assert coordinator.is_can_port_available("can1") is False
    assert "can.can1.j1939.spn190" not in coordinator.data

    # Device restarts — valid data again
    stub.values = {"can.can1.j1939.spn190": 900.0}
    coordinator._handle_message(
        _message({"deviceid": "DEV1", "can1": [{"id": 1, "data": "00"}]})
    )
    assert coordinator.is_can_port_available("can1") is True
    assert coordinator.data["can.can1.j1939.spn190"] == 900.0


def test_stale_can_values_cleared_when_port_unavailable():
    """Previous CAN values are removed when port becomes unavailable."""
    stub = _ToggleProtocolStub()
    coordinator = _build_coordinator(
        ["can.can1.j1939.spn190", "can.can1.j1939.spn247", "internal.main.vin"]
    )
    coordinator._can_runtime = {"can1": (stub, None)}

    # Populate with valid CAN and internal data
    stub.values = {
        "can.can1.j1939.spn190": 1841.0,
        "can.can1.j1939.spn247": 503.95,
    }
    coordinator._handle_message(
        _message({"deviceid": "DEV1", "vin": 28.0, "can1": [{"id": 1, "data": "00"}]})
    )
    assert "can.can1.j1939.spn190" in coordinator.data
    assert "can.can1.j1939.spn247" in coordinator.data
    assert coordinator.data["internal.main.vin"] == 28.0

    # CAN device shuts down
    stub.values = {}
    coordinator._handle_message(
        _message({"deviceid": "DEV1", "vin": 28.1, "can1": [{"id": 1, "data": "FF"}]})
    )

    # CAN values cleared, internal values unaffected
    assert "can.can1.j1939.spn190" not in coordinator.data
    assert "can.can1.j1939.spn247" not in coordinator.data
    assert coordinator.data["internal.main.vin"] == 28.1


def test_internal_sensors_unaffected_by_can_port_availability():
    """Internal sensor availability is independent of CAN port state."""
    coordinator = _build_coordinator(["internal.main.vin", "can.can1.j1939.spn190"])
    coordinator._can_runtime = {"can1": (_EmptyProtocolStub(), None)}

    coordinator._handle_message(
        _message({"deviceid": "DEV1", "vin": 28.0, "can1": [{"id": 1, "data": "FF"}]})
    )

    assert coordinator.is_can_port_available("can1") is False
    assert coordinator.data["internal.main.vin"] == 28.0


def test_can_port_availability_not_tied_to_selected_can_entities():
    """Port can be available even if no CAN entities are selected."""
    coordinator = _build_coordinator(["internal.main.vin"])
    coordinator._can_runtime = {"can1": (_AvailableWithoutSelectedSignalsProtocolStub(), None)}

    coordinator._handle_message(
        _message({"deviceid": "DEV1", "vin": 28.0, "can1": [{"id": 1, "data": "00"}]})
    )

    assert coordinator.is_can_port_available("can1") is True
    assert coordinator.data["internal.main.vin"] == 28.0
