"""Tests for CAN protocol registry."""

from custom_components.senquip.can_protocols.registry import (
    get_can_protocol,
    list_can_protocol_options,
)


def test_registry_contains_j1939():
    protocol = get_can_protocol("j1939")
    assert protocol is not None
    assert protocol.protocol_id == "j1939"


def test_protocol_options_expose_only_implemented():
    options = list_can_protocol_options()
    assert options == [
        ("j1939", "J1939"),
        ("nmea2000", "NMEA 2000 (Raw)"),
        ("iso11783", "ISO 11783 (Raw)"),
        ("canopen", "CANopen (Raw)"),
    ]
