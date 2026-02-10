"""Registry for implemented CAN protocols."""

from __future__ import annotations

from .base import CANProtocol
from .j1939.protocol import J1939CANProtocol
from .raw import RawCANProtocol

_PROTOCOLS: dict[str, CANProtocol] = {
    "j1939": J1939CANProtocol(),
    "nmea2000": RawCANProtocol("nmea2000", "NMEA 2000 (Raw)"),
    "iso11783": RawCANProtocol("iso11783", "ISO 11783 (Raw)"),
    "canopen": RawCANProtocol("canopen", "CANopen (Raw)"),
}


def get_can_protocol(protocol_id: str) -> CANProtocol | None:
    """Return a CAN protocol adapter by id."""
    return _PROTOCOLS.get(protocol_id)


def list_can_protocol_options() -> list[tuple[str, str]]:
    """Return protocol id/label options for config selectors."""
    return [(proto.protocol_id, proto.display_name) for proto in _PROTOCOLS.values()]
