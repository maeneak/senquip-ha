"""Tests for raw-only CAN protocol adapters."""

from custom_components.senquip.can_protocols.registry import get_can_protocol


def test_raw_protocol_discovery():
    protocol = get_can_protocol("nmea2000")
    assert protocol is not None
    signals = protocol.discover_signals(
        [
            {"id": 217056256, "data": "3FFFCD883927F4FF"},
            {"id": 419357952, "data": "5F27000000000000"},
        ],
        "can1",
        None,
    )
    keys = {signal.key for signal in signals}
    assert "can.can1.nmea2000.raw.61444" in keys
    assert "can.can1.nmea2000.raw.65253" in keys


def test_raw_protocol_runtime_decode():
    protocol = get_can_protocol("canopen")
    assert protocol is not None
    selected = {"can.can2.canopen.raw.61444"}
    values, diagnostics = protocol.decode_runtime(
        [{"id": 217056256, "data": "3FFFCD883927F4FF"}],
        "can2",
        selected,
        None,
    )
    assert values["can.can2.canopen.raw.61444"] == "3FFFCD883927F4FF"
    assert diagnostics[0]["mode"] == "raw"

