"""Helpers for canonical Senquip signal keys and legacy compatibility."""

from __future__ import annotations

from typing import Any, Mapping

from .const import CAN_PORTS, CONF_SELECTED_SIGNALS

LEGACY_SELECTED_SENSORS_KEY = "selected_sensors"


def to_canonical_signal_key(signal_key: str) -> str:
    """Convert legacy signal keys to canonical form."""
    key = signal_key.strip()
    if not key:
        return key

    # Already canonical
    if key.startswith("internal.main.") or key.startswith("can.") or key.startswith("event.main."):
        return key

    # Legacy internal/event keys
    if key.startswith("internal."):
        return f"internal.main.{key.removeprefix('internal.')}"
    if key == "events.last":
        return "event.main.last"

    # Legacy CAN keys: can1.spn190, can2.raw.65308, can1.dm1.active_fault
    for port_id in CAN_PORTS:
        prefix = f"{port_id}."
        if not key.startswith(prefix):
            continue
        suffix = key.removeprefix(prefix)
        if suffix.startswith("spn"):
            return f"can.{port_id}.j1939.{suffix}"
        if suffix.startswith("raw.") or suffix.startswith("dm1."):
            return f"can.{port_id}.j1939.{suffix}"

    return key


def normalize_selected_signals(entry_data: Mapping[str, Any]) -> list[str]:
    """Return selected signal keys in canonical form.

    Supports both current `selected_signals` and legacy `selected_sensors`.
    """
    raw_selected = entry_data.get(CONF_SELECTED_SIGNALS)
    if not isinstance(raw_selected, list):
        raw_selected = entry_data.get(LEGACY_SELECTED_SENSORS_KEY, [])
    if not isinstance(raw_selected, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_selected:
        canonical = to_canonical_signal_key(str(item))
        if canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)

    return normalized
