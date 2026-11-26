"""Persistent DM1 fault log.

Pure-Python state machine (no Home Assistant imports) that turns the stream of
per-payload DM1 reports into a deduplicated history of faults. One entry is kept
per (source address, SPN, FMI). Entries only change on transitions (fault became
active, cleared, or its occurrence count/lamps changed) so an active fault does
not rewrite state on every MQTT payload.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

MAX_FAULT_LOG_ENTRIES = 25

_LAMP_NAMES: dict[str, str] = {
    "protect": "Protect",
    "amber_warning": "Amber Warning",
    "red_stop": "Red Stop",
    "mil": "MIL",
}

_FaultKey = tuple[int, int, int]  # (source_address, spn, fmi)


def _active_lamps(lamps: Any) -> list[str]:
    """Return display names of the lamps reported as Active."""
    if not isinstance(lamps, Mapping):
        return []
    return [name for key, name in _LAMP_NAMES.items() if lamps.get(key) == "Active"]


class DM1FaultLog:
    """History of DM1 faults observed on one CAN port."""

    def __init__(self, max_entries: int = MAX_FAULT_LOG_ENTRIES) -> None:
        self._max_entries = max_entries
        self._entries: dict[_FaultKey, dict[str, Any]] = {}

    @property
    def entries(self) -> list[dict[str, Any]]:
        """Return log entries, most recently activated first."""
        ordered = sorted(
            self._entries.values(),
            key=lambda entry: entry["last_active"],
            reverse=True,
        )
        return [dict(entry, lamps=list(entry["lamps"])) for entry in ordered]

    @property
    def active_count(self) -> int:
        """Return the number of faults currently active."""
        return sum(1 for entry in self._entries.values() if entry["active"])

    def observe(self, reports: Iterable[Mapping[str, Any]], now: datetime) -> bool:
        """Update the log from the DM1 reports in one payload.

        Each report is one decoded DM1 frame (``source_address``, ``active_spn``,
        ``active_fmi``, ``active_fault``, ``occurrence_count``, ``lamps``).
        A fault is cleared only when the same source reports a DM1 frame that no
        longer carries it; sources absent from the payload are left untouched.

        Returns True if the log changed.
        """
        timestamp = now.isoformat(timespec="seconds")
        reporting_sources: set[int] = set()
        current: dict[_FaultKey, Mapping[str, Any]] = {}

        for report in reports:
            source = report.get("source_address")
            spn = report.get("active_spn")
            fmi = report.get("active_fmi")
            if not isinstance(source, int) or not isinstance(spn, int) or not isinstance(fmi, int):
                continue
            reporting_sources.add(source)
            if spn == 0 and fmi == 0:
                continue
            current[(source, spn, fmi)] = report

        changed = False
        for key, report in current.items():
            description = str(report.get("active_fault", ""))
            occurrence_count = report.get("occurrence_count")
            lamps = _active_lamps(report.get("lamps"))
            entry = self._entries.get(key)

            if entry is None:
                self._entries[key] = {
                    "source_address": key[0],
                    "spn": key[1],
                    "fmi": key[2],
                    "description": description,
                    "lamps": lamps,
                    "occurrence_count": occurrence_count,
                    "count": 1,
                    "active": True,
                    "first_seen": timestamp,
                    "last_active": timestamp,
                    "cleared": None,
                }
                changed = True
                continue

            if not entry["active"]:
                entry["active"] = True
                entry["count"] += 1
                entry["last_active"] = timestamp
                entry["cleared"] = None
                changed = True

            for field, value in (
                ("description", description),
                ("lamps", lamps),
                ("occurrence_count", occurrence_count),
            ):
                if entry[field] != value:
                    entry[field] = value
                    changed = True

        for key, entry in self._entries.items():
            if entry["active"] and key[0] in reporting_sources and key not in current:
                entry["active"] = False
                entry["cleared"] = timestamp
                changed = True

        if changed:
            self._trim()
        return changed

    def _trim(self) -> None:
        """Drop the oldest inactive entries beyond the size limit."""
        excess = len(self._entries) - self._max_entries
        if excess <= 0:
            return
        inactive = sorted(
            (key for key, entry in self._entries.items() if not entry["active"]),
            key=lambda key: self._entries[key]["last_active"],
        )
        for key in inactive[:excess]:
            del self._entries[key]

    def as_dict(self) -> dict[str, Any]:
        """Serialize the log for Home Assistant restore storage."""
        return {"entries": self.entries}

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any] | None,
        max_entries: int = MAX_FAULT_LOG_ENTRIES,
    ) -> DM1FaultLog:
        """Rebuild a log from ``as_dict`` output, skipping malformed entries."""
        log = cls(max_entries)
        if not isinstance(data, Mapping):
            return log
        raw_entries = data.get("entries")
        if not isinstance(raw_entries, list):
            return log
        for raw in raw_entries:
            if not isinstance(raw, Mapping):
                continue
            try:
                key = (int(raw["source_address"]), int(raw["spn"]), int(raw["fmi"]))
                entry = {
                    "source_address": key[0],
                    "spn": key[1],
                    "fmi": key[2],
                    "description": str(raw["description"]),
                    "lamps": [str(lamp) for lamp in raw.get("lamps", [])],
                    "occurrence_count": raw.get("occurrence_count"),
                    "count": int(raw["count"]),
                    "active": bool(raw["active"]),
                    "first_seen": str(raw["first_seen"]),
                    "last_active": str(raw["last_active"]),
                    "cleared": raw.get("cleared"),
                }
            except (KeyError, TypeError, ValueError):
                continue
            log._entries[key] = entry
        log._trim()
        return log
