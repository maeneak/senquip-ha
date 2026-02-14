"""Tests for signal-key canonicalization and legacy compatibility."""

from custom_components.senquip.const import CONF_SELECTED_SIGNALS
from custom_components.senquip.signal_keys import (
    LEGACY_SELECTED_SENSORS_KEY,
    normalize_selected_signals,
    to_canonical_signal_key,
)


def test_to_canonical_signal_key_legacy_internal():
    assert to_canonical_signal_key("internal.vsys") == "internal.main.vsys"


def test_to_canonical_signal_key_legacy_event():
    assert to_canonical_signal_key("events.last") == "event.main.last"


def test_to_canonical_signal_key_legacy_can_spn():
    assert to_canonical_signal_key("can1.spn190") == "can.can1.j1939.spn190"
    assert to_canonical_signal_key("can2.spn247") == "can.can2.j1939.spn247"


def test_to_canonical_signal_key_legacy_can_raw_dm1():
    assert to_canonical_signal_key("can1.raw.65308") == "can.can1.j1939.raw.65308"
    assert (
        to_canonical_signal_key("can2.dm1.active_fault")
        == "can.can2.j1939.dm1.active_fault"
    )


def test_normalize_selected_signals_uses_current_key():
    data = {
        CONF_SELECTED_SIGNALS: [
            "internal.vsys",
            "can1.spn190",
            "event.main.last",
            "can.can1.j1939.spn190",
        ]
    }
    assert normalize_selected_signals(data) == [
        "internal.main.vsys",
        "can.can1.j1939.spn190",
        "event.main.last",
    ]


def test_normalize_selected_signals_falls_back_to_legacy_key():
    data = {
        LEGACY_SELECTED_SENSORS_KEY: [
            "internal.vin",
            "can2.spn110",
            "events.last",
        ]
    }
    assert normalize_selected_signals(data) == [
        "internal.main.vin",
        "can.can2.j1939.spn110",
        "event.main.last",
    ]
