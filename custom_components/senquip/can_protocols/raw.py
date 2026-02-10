"""Raw CAN protocol adapters for protocols without decoders yet."""

from __future__ import annotations

from typing import Any

from ..const import SensorMeta
from .base import ProtocolDiscoveredSignal


def _extract_pgn(can_id: int) -> tuple[int, int, int]:
    """Extract priority, PGN, and source from a 29-bit CAN id."""
    source = can_id & 0xFF
    pf = (can_id >> 16) & 0xFF
    ps = (can_id >> 8) & 0xFF
    dp = (can_id >> 24) & 0x01
    priority = (can_id >> 26) & 0x7
    if pf >= 240:
        pgn = (dp << 16) | (pf << 8) | ps
    else:
        pgn = (dp << 16) | (pf << 8)
    return priority, pgn, source


class RawCANProtocol:
    """Protocol adapter that exposes raw frames only."""

    def __init__(self, protocol_id: str, display_name: str) -> None:
        self.protocol_id = protocol_id
        self.display_name = display_name

    def build_decoder(self, profiles: list[Any]) -> Any:
        """No decoder state required for raw mode."""
        del profiles
        return None

    def discover_signals(
        self,
        frames: list[dict[str, Any]],
        port_id: str,
        decoder: Any,
    ) -> list[ProtocolDiscoveredSignal]:
        """Discover one raw signal per seen PGN."""
        del decoder
        discovered: list[ProtocolDiscoveredSignal] = []
        seen_pgns: set[int] = set()

        for frame in frames:
            can_id = frame.get("id")
            hex_data = frame.get("data")
            if can_id is None or hex_data is None:
                continue
            _, pgn, _ = _extract_pgn(can_id)
            if pgn in seen_pgns:
                continue
            seen_pgns.add(pgn)
            discovered.append(
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.{self.protocol_id}.raw.{pgn}",
                    name=f"Raw PGN {pgn} (0x{pgn:04X})",
                    sample_value=hex_data[:16] + ("..." if len(hex_data) > 16 else ""),
                    unit=None,
                    default_selected=True,
                )
            )
        return discovered

    def decode_runtime(
        self,
        frames: list[dict[str, Any]],
        port_id: str,
        selected_signals: set[str],
        decoder: Any,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Emit selected raw frame payloads and basic diagnostics."""
        del decoder
        values: dict[str, Any] = {}
        diagnostics: list[dict[str, Any]] = []

        for frame in frames:
            can_id = frame.get("id")
            hex_data = frame.get("data")
            if can_id is None or hex_data is None:
                continue

            priority, pgn, source = _extract_pgn(can_id)
            signal_key = f"can.{port_id}.{self.protocol_id}.raw.{pgn}"
            if signal_key in selected_signals:
                values[signal_key] = hex_data

            diagnostics.append(
                {
                    "protocol": self.protocol_id,
                    "can_id": can_id,
                    "can_id_hex": f"0x{can_id:08X}",
                    "priority": priority,
                    "pgn": pgn,
                    "pgn_hex": f"0x{pgn:04X}",
                    "source_address": source,
                    "data": hex_data,
                    "known": False,
                    "mode": "raw",
                }
            )

        return values, diagnostics

    def resolve_signal_meta(self, signal_key: str, decoder: Any) -> SensorMeta:
        """Resolve metadata for raw-only protocol signal keys."""
        del decoder
        if ".raw." in signal_key:
            pgn = signal_key.rsplit(".raw.", 1)[1]
            return SensorMeta(
                name=f"Raw PGN {pgn}",
                state_class=None,
                icon="mdi:numeric",
            )
        return SensorMeta(name=signal_key, state_class=None)

