"""Persistent DM1 fault log.

Pure-Python state machine (no Home Assistant imports) that turns the stream of
per-payload DM1 reports into a deduplicated history of faults. One entry is kept
per (source address, SPN, FMI). Entries only change on transitions (fault became
active, cleared, or its occurrence count/lamps changed) so an active fault does
not rewrite state on every MQTT payload.

A multi-packet DM1 (2+ DTCs, announced by a TP.CM BAM) cannot be reassembled
from Senquip payloads, so it is logged as one entry per source with
``spn``/``fmi`` of None, active until that source sends a single-frame DM1.
While a source is in multi-packet mode its individually known faults stay
active (they cannot be confirmed either way) until a single frame settles them.

Each fault becoming active or clearing is also recorded as a transition, which
the fault history sensor fires as a Home Assistant event.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable, Mapping

MAX_FAULT_LOG_ENTRIES = 25

# Saved log format. 1 (0.6.0-0.7.0): SPNs from the MAN profile's sources were
# decoded big-endian. 2 (0.8.0): every SPN is decoded little-endian.
FAULT_LOG_FORMAT = 2

# Home Assistant Store (.storage) settings for the persisted log
FAULT_HISTORY_STORE_VERSION = 1
FAULT_HISTORY_SAVE_DELAY = 1  # seconds; batches bursts of changes into one write


def fault_history_store_key(device_id: str, port_id: str) -> str:
    """Return the .storage key holding one port's fault log."""
    return f"senquip.dm1_fault_history.{device_id}.{port_id}"


def big_endian_spn_to_little_endian(spn: int) -> int:
    """Re-read an SPN decoded big-endian as the standard little-endian value.

    Big-endian read DTC bytes 3-5 as ``(b3 << 11) | (b4 << 3) | (b5 >> 5)``;
    the standard layout is ``b3 | (b4 << 8) | ((b5 >> 5) << 16)``.
    """
    byte3 = (spn >> 11) & 0xFF
    byte4 = (spn >> 3) & 0xFF
    return byte3 | (byte4 << 8) | ((spn & 0x07) << 16)


_LAMP_NAMES: dict[str, str] = {
    "protect": "Protect",
    "amber_warning": "Amber Warning",
    "red_stop": "Red Stop",
    "mil": "MIL",
}

_FaultKey = tuple[int, int, int]  # (source_address, spn, fmi)

# spn/fmi key component for a multi-packet DM1 entry (stored as None)
_MULTI_PACKET = -1


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
        self._transitions: list[dict[str, Any]] = []

    @property
    def entries(self) -> list[dict[str, Any]]:
        """Return log entries, most recently activated first.

        Timestamps keep microseconds so faults from separate payloads never tie.
        """
        ordered = sorted(
            self._entries.values(),
            key=lambda entry: entry["last_activated"],
            reverse=True,
        )
        return [dict(entry, lamps=list(entry["lamps"])) for entry in ordered]

    def pop_transitions(self) -> list[dict[str, Any]]:
        """Return and forget faults that became active or cleared since the last call.

        Each item is a snapshot of the log entry plus ``status`` ("active" or
        "cleared"), in the order the changes were observed.
        """
        transitions, self._transitions = self._transitions, []
        return transitions

    def _record_transition(self, entry: Mapping[str, Any], status: str) -> None:
        self._transitions.append(dict(entry, lamps=list(entry["lamps"]), status=status))

    @property
    def active_count(self) -> int:
        """Return the number of faults currently active."""
        return sum(1 for entry in self._entries.values() if entry["active"])

    def observe(self, reports: Iterable[Mapping[str, Any]], now: datetime) -> bool:
        """Update the log from the DM1 reports in one payload.

        Each report is one decoded DM1 frame (``source_address``, ``active_spn``,
        ``active_fmi``, ``active_fault``, ``occurrence_count``, ``lamps``) or a
        multi-packet announcement (``multi_packet`` true, ``dtc_count``).
        A fault is cleared only when the same source reports a DM1 frame that no
        longer carries it; sources absent from the payload are left untouched.

        Returns True if the log changed.
        """
        timestamp = now.isoformat()

        # A single-frame DM1 carries a source's complete active DTC list, so
        # when one payload holds several frames from a source the last one wins,
        # except that a multi-packet report beats a single frame (payload order
        # is CAN-ID slot order, not time; see protocol.decode_runtime).
        latest_by_source: dict[int, Mapping[str, Any]] = {}
        for report in reports:
            source = report.get("source_address")
            if not isinstance(source, int):
                continue
            if report.get("multi_packet"):
                if not isinstance(report.get("dtc_count"), int):
                    continue
            elif not isinstance(report.get("active_spn"), int) or not isinstance(
                report.get("active_fmi"), int
            ):
                continue
            previous = latest_by_source.get(source)
            if previous is not None and previous.get("multi_packet") and not report.get("multi_packet"):
                continue
            latest_by_source[source] = report

        reporting_sources = set(latest_by_source)
        # A multi-packet DM1 hides which DTCs are active, so a source's
        # individual faults are only cleared by a single-frame DM1 without them
        multi_packet_sources = {
            source for source, report in latest_by_source.items() if report.get("multi_packet")
        }
        current: dict[_FaultKey, Mapping[str, Any]] = {}
        for source, report in latest_by_source.items():
            if report.get("multi_packet"):
                current[(source, _MULTI_PACKET, _MULTI_PACKET)] = report
                continue
            spn = report["active_spn"]
            fmi = report["active_fmi"]
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
                    "spn": None if key[1] == _MULTI_PACKET else key[1],
                    "fmi": None if key[2] == _MULTI_PACKET else key[2],
                    "description": description,
                    "lamps": lamps,
                    "occurrence_count": occurrence_count,
                    "count": 1,
                    "active": True,
                    "first_seen": timestamp,
                    "last_activated": timestamp,
                    "cleared": None,
                }
                self._record_transition(self._entries[key], "active")
                changed = True
                continue

            activated = not entry["active"]
            if activated:
                entry["active"] = True
                entry["count"] += 1
                entry["last_activated"] = timestamp
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
            if activated:
                self._record_transition(entry, "active")

        for key, entry in self._entries.items():
            if key[0] in multi_packet_sources and key[1] != _MULTI_PACKET:
                continue
            if entry["active"] and key[0] in reporting_sources and key not in current:
                entry["active"] = False
                entry["cleared"] = timestamp
                self._record_transition(entry, "cleared")
                changed = True

        if changed:
            self._trim()
        return changed

    def convert_big_endian_spns(
        self,
        was_big_endian: Callable[[int], bool],
        describe: Callable[[int, int, int], str],
    ) -> bool:
        """Re-key entries logged with big-endian SPN decoding (format 1 logs).

        ``was_big_endian(source)`` says whether a source's DM1 was decoded
        big-endian; ``describe(source, spn, fmi)`` gives the new description.
        No transitions are recorded. Returns True if any entry changed.

        Every entry is re-keyed in one pass: the conversion is one-to-one, so
        keys stay unique, but a corrected SPN can equal another entry's old one.
        """
        changed = False
        converted: dict[_FaultKey, dict[str, Any]] = {}
        for key, entry in self._entries.items():
            source, spn, fmi = key
            if spn != _MULTI_PACKET and was_big_endian(source):
                new_spn = big_endian_spn_to_little_endian(spn)
                if new_spn != spn:
                    entry["spn"] = new_spn
                    entry["description"] = describe(source, new_spn, fmi)
                    key = (source, new_spn, fmi)
                    changed = True
            converted[key] = entry
        self._entries = converted
        return changed

    def _trim(self) -> None:
        """Drop the least recently active cleared entries beyond the size limit.

        Active entries are never dropped, so the log can exceed the limit while
        more than ``max_entries`` faults are active.
        """
        excess = len(self._entries) - self._max_entries
        if excess <= 0:
            return
        # Oldest activity first: a cleared fault's last activity is when it cleared
        inactive = sorted(
            (key for key, entry in self._entries.items() if not entry["active"]),
            key=lambda key: self._entries[key]["cleared"] or self._entries[key]["last_activated"],
        )
        for key in inactive[:excess]:
            del self._entries[key]

    def as_dict(self) -> dict[str, Any]:
        """Serialize the log for Home Assistant storage."""
        return {"format": FAULT_LOG_FORMAT, "entries": self.entries}

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
                spn = None if raw["spn"] is None else int(raw["spn"])
                fmi = None if raw["fmi"] is None else int(raw["fmi"])
                key = (
                    int(raw["source_address"]),
                    _MULTI_PACKET if spn is None else spn,
                    _MULTI_PACKET if fmi is None else fmi,
                )
                entry = {
                    "source_address": key[0],
                    "spn": spn,
                    "fmi": fmi,
                    "description": str(raw["description"]),
                    "lamps": [str(lamp) for lamp in raw.get("lamps", [])],
                    "occurrence_count": raw.get("occurrence_count"),
                    "count": int(raw["count"]),
                    "active": bool(raw["active"]),
                    "first_seen": str(raw["first_seen"]),
                    "last_activated": str(raw["last_activated"]),
                    "cleared": raw.get("cleared"),
                }
            except (KeyError, TypeError, ValueError):
                continue
            log._entries[key] = entry
        log._trim()
        return log
