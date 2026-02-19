"""Shared CAN protocol interfaces and datatypes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProtocolDiscoveredSignal:
    """Discovered signal metadata returned by a CAN protocol."""

    key: str
    name: str
    sample_value: Any
    unit: str | None
    default_selected: bool


class CANProtocol(Protocol):
    """Interface implemented by all CAN protocol handlers."""

    protocol_id: str
    display_name: str

    def build_decoder(self, profiles: list[Any]) -> tuple[Any, list[str]]:
        """Build a runtime decoder from selected profiles.

        Returns (decoder, errors) where *errors* is a list of human-readable
        strings describing any profiles that failed to load.
        """

    def discover_signals(
        self, frames: list[dict[str, Any]], port_id: str, decoder: Any
    ) -> list[ProtocolDiscoveredSignal]:
        """Return discoverable signals from sample CAN frames."""

    def decode_runtime(
        self,
        frames: list[dict[str, Any]],
        port_id: str,
        selected_signals: set[str],
        decoder: Any,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
        """Decode runtime values, diagnostics, and port availability for one port."""

    def resolve_signal_meta(self, signal_key: str, decoder: Any) -> Any:
        """Resolve protocol-specific metadata for a signal key."""

