"""J1939 CAN bus decoder.

Extracts PGNs from 29-bit CAN IDs and decodes SPNs from raw data payloads
using the definitions in j1939_database.py.
"""

from __future__ import annotations

import logging

from .j1939_database import PGN_DATABASE, SPN_DATABASE, PGNDefinition, SPNDefinition

_LOGGER = logging.getLogger(__name__)


class J1939Decoder:
    """Decode J1939 CAN bus frames into physical values."""

    def __init__(
        self,
        pgn_database: dict[int, PGNDefinition] | None = None,
        spn_database: dict[int, SPNDefinition] | None = None,
    ) -> None:
        """Initialize decoder with optional custom databases.

        Args:
            pgn_database: Custom PGN database. Defaults to built-in PGN_DATABASE.
            spn_database: Custom SPN database. Defaults to built-in SPN_DATABASE.
        """
        self._pgn_db = pgn_database if pgn_database is not None else PGN_DATABASE
        self._spn_db = spn_database if spn_database is not None else SPN_DATABASE

    @staticmethod
    def extract_pgn(can_id: int) -> tuple[int, int, int]:
        """Extract priority, PGN, and source address from a 29-bit CAN ID.

        Args:
            can_id: 29-bit extended CAN identifier as a decimal integer.

        Returns:
            Tuple of (priority, pgn, source_address).
        """
        source = can_id & 0xFF
        pf = (can_id >> 16) & 0xFF
        ps = (can_id >> 8) & 0xFF
        dp = (can_id >> 24) & 0x01
        priority = (can_id >> 26) & 0x7

        if pf >= 240:
            # PDU2 (broadcast): Group Extension is part of PGN
            pgn = (dp << 16) | (pf << 8) | ps
        else:
            # PDU1 (peer-to-peer): PS is destination address, not part of PGN
            pgn = (dp << 16) | (pf << 8)

        return priority, pgn, source

    @staticmethod
    def decode_spn(spn_def: SPNDefinition, data_bytes: bytes) -> float | None:
        """Decode a single SPN value from CAN data bytes.

        Returns None if the value indicates 'not available' (all bits = 1)
        or 'error indicator' (all bits = 1 except LSB = 0).
        """
        start_idx = spn_def.start_byte - 1  # Convert to 0-indexed
        byte_count = (spn_def.bit_length + 7) // 8

        # Bounds check
        if start_idx + byte_count > len(data_bytes):
            return None

        # Read bytes — J1939 uses little-endian for multi-byte values
        raw_bytes = data_bytes[start_idx : start_idx + byte_count]
        raw_value = int.from_bytes(raw_bytes, byteorder="little")

        # Sub-byte or non-byte-aligned extraction
        if spn_def.bit_length < 8 or spn_def.start_bit > 1:
            shift = spn_def.start_bit - 1
            mask = (1 << spn_def.bit_length) - 1
            raw_value = (raw_value >> shift) & mask

        # Not-available: all bits set to 1
        not_available = (1 << spn_def.bit_length) - 1
        if raw_value == not_available:
            return None

        # Error indicator: all bits = 1 except LSB = 0
        error_indicator = not_available - 1
        if raw_value == error_indicator:
            return None

        # Apply resolution and offset
        physical_value = (raw_value * spn_def.resolution) + spn_def.offset

        return round(physical_value, 4)

    def get_pgn_info(self, can_id: int) -> PGNDefinition | None:
        """Look up PGN definition for a CAN ID."""
        _, pgn, _ = self.extract_pgn(can_id)
        return self._pgn_db.get(pgn)

    def get_spn_def(self, spn_num: int) -> SPNDefinition | None:
        """Look up SPN definition by number."""
        return self._spn_db.get(spn_num)

    def decode_frame(self, can_id: int, hex_data: str) -> dict[int, float | None]:
        """Decode all known SPNs from a single CAN frame.

        Args:
            can_id: 29-bit CAN ID as decimal integer.
            hex_data: Data payload as hex string (e.g., "3FFFCD883927F4FF").

        Returns:
            Dict mapping SPN number to decoded physical value.
            Empty dict if PGN is unknown.
        """
        _, pgn, _ = self.extract_pgn(can_id)

        pgn_def = self._pgn_db.get(pgn)
        if pgn_def is None:
            _LOGGER.debug("Unknown PGN %d (0x%04X) from CAN ID %d", pgn, pgn, can_id)
            return {}

        try:
            data_bytes = bytes.fromhex(hex_data)
        except ValueError:
            _LOGGER.warning("Invalid hex data for CAN ID %d: %s", can_id, hex_data)
            return {}

        results: dict[int, float | None] = {}
        for spn_num in pgn_def.spns:
            spn_def = self._spn_db.get(spn_num)
            if spn_def is None:
                continue
            value = self.decode_spn(spn_def, data_bytes)
            results[spn_num] = value

        return results

    def decode_can_port(
        self, frames: list[dict]
    ) -> dict[int, float | None]:
        """Decode all frames from a CAN port.

        Args:
            frames: List of {"id": int, "data": str} dicts from JSON payload.

        Returns:
            Dict mapping SPN number to decoded value. If the same SPN appears
            in multiple frames, the last value wins.
        """
        all_spns: dict[int, float | None] = {}

        for frame in frames:
            can_id = frame.get("id")
            hex_data = frame.get("data")
            if can_id is None or hex_data is None:
                continue
            decoded = self.decode_frame(can_id, hex_data)
            all_spns.update(decoded)

        return all_spns
