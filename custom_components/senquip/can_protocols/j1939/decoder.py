"""J1939 CAN bus decoder."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .database import PGN_DATABASE, SPN_DATABASE, PGNDefinition, SPNDefinition
from .overlay import DM1Config

_LOGGER = logging.getLogger(__name__)

# DM1 — Diagnostic Message 1 (Active Diagnostic Trouble Codes)
DM1_PGN = 65226

# Standard J1939-73 Failure Mode Identifiers
FMI_DESCRIPTIONS: dict[int, str] = {
    0: "Data Valid - Above Normal Range",
    1: "Data Valid - Below Normal Range",
    2: "Data Erratic/Incorrect",
    3: "Voltage Above Normal",
    4: "Voltage Below Normal",
    5: "Current Below Normal",
    6: "Current Above Normal",
    7: "Mechanical System Not Responding",
    8: "Abnormal Frequency/Period/Width",
    9: "Abnormal Update Rate",
    10: "Abnormal Rate of Change",
    11: "Root Cause Not Known",
    12: "Bad Intelligent Device or Component",
    13: "Out of Calibration",
    14: "Special Instructions",
    15: "Data Valid - Above Normal Range (Least Severe)",
    16: "Data Valid - Above Normal Range (Moderately Severe)",
    17: "Data Valid - Below Normal Range (Least Severe)",
    18: "Data Valid - Below Normal Range (Moderately Severe)",
    19: "Received Network Data in Error",
    20: "Data Drifted High",
    21: "Data Drifted Low",
    31: "Condition Exists",
}


@dataclass(frozen=True)
class DM1Result:
    """Decoded DM1 (Diagnostic Message 1) frame."""

    lamp_protect: bool
    lamp_amber: bool
    lamp_red: bool
    lamp_mil: bool
    active_spn: int
    active_fmi: int
    occurrence_count: int


class J1939Decoder:
    """Decode J1939 CAN bus frames into physical values."""

    def __init__(
        self,
        pgn_database: dict[int, PGNDefinition] | None = None,
        spn_database: dict[int, SPNDefinition] | None = None,
        dm1_config: DM1Config | None = None,
    ) -> None:
        """Initialize decoder with optional custom databases.

        Args:
            pgn_database: Custom PGN database. Defaults to built-in PGN_DATABASE.
            spn_database: Custom SPN database. Defaults to built-in SPN_DATABASE.
            dm1_config: Optional DM1 configuration from a profile.
        """
        self._pgn_db = pgn_database if pgn_database is not None else PGN_DATABASE
        self._spn_db = spn_database if spn_database is not None else SPN_DATABASE
        self._dm1_config = dm1_config

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
    def decode_spn(spn_def: SPNDefinition, data_bytes: bytes) -> float | str | None:
        """Decode a single SPN value from CAN data bytes.

        Returns None if the value indicates 'not available' (all bits = 1)
        or 'error indicator' (all bits = 1 except LSB = 0).
        For SPNs with a ``states`` mapping, returns the matching state string
        instead of a numeric physical value (or None if the raw value has no
        matching state).
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

        # State-mapped SPNs return a human-readable string
        if spn_def.states is not None:
            return spn_def.states.get(raw_value)

        # Apply resolution and offset
        physical_value = (raw_value * spn_def.resolution) + spn_def.offset

        return round(physical_value, 4)

    @staticmethod
    def decode_dm1(
        data_bytes: bytes, big_endian_spn: bool = False
    ) -> DM1Result | None:
        """Decode a DM1 (Diagnostic Message 1) single frame.

        DM1 format (J1939-73):
          Byte 1: Lamp status (2-bit fields)
          Byte 2: Reserved (0xFF)
          Bytes 3-6: DTC (SPN + FMI + OC)
          Bytes 7-8: 0xFFFF padding (single-DTC frame)

        Args:
            data_bytes: Raw CAN data (8 bytes).
            big_endian_spn: If True, decode SPN using big-endian (MAN).
                            If False, use standard J1939 little-endian.

        Returns:
            DM1Result or None if data is too short.
        """
        if len(data_bytes) < 6:
            return None

        # Byte 1: Lamp status — 2-bit fields
        lamp_byte = data_bytes[0]
        lamp_protect = (lamp_byte & 0x04) != 0  # bits 3-4 (value != 0b00)
        lamp_amber = (lamp_byte & 0x10) != 0  # bits 5-6
        lamp_red = (lamp_byte & 0x40) != 0  # bits 7-8
        lamp_mil = (lamp_byte & 0x01) != 0  # bits 1-2

        # Bytes 3-6 (0-indexed: 2-5): DTC
        byte3 = data_bytes[2]
        byte4 = data_bytes[3]
        byte5 = data_bytes[4]
        byte6 = data_bytes[5] if len(data_bytes) > 5 else 0

        if big_endian_spn:
            # MAN encoding: SPN is big-endian across bytes 3-5
            spn = (byte3 << 11) | (byte4 << 3) | (byte5 >> 5)
        else:
            # Standard J1939 little-endian SPN encoding
            spn = byte3 | (byte4 << 8) | ((byte5 >> 5) << 16)

        fmi = byte5 & 0x1F
        occurrence_count = byte6 & 0x7F

        # Check for "no fault" — all DTC bytes are 0x00 or 0xFF
        if byte3 == 0 and byte4 == 0 and (byte5 >> 5) == 0 and fmi == 0:
            spn = 0
            fmi = 0

        return DM1Result(
            lamp_protect=lamp_protect,
            lamp_amber=lamp_amber,
            lamp_red=lamp_red,
            lamp_mil=lamp_mil,
            active_spn=spn,
            active_fmi=fmi,
            occurrence_count=occurrence_count,
        )

    def get_fault_description(
        self,
        spn: int,
        fmi: int,
        custom_fault_spns: dict[int, str] | None = None,
    ) -> str:
        """Build a human-readable fault description.

        Looks up the SPN name from (in order):
        1. The SPN database (standard SPNs)
        2. The custom_fault_spns dict (manufacturer-proprietary SPNs)
        3. Falls back to "Unknown SPN {num}"

        Returns:
            e.g. "SPN 520198: Emergency Stop (FMI 2: Data Erratic/Incorrect)"
        """
        if spn == 0 and fmi == 0:
            return "No Active Fault"

        # Look up SPN name
        spn_def = self._spn_db.get(spn)
        if spn_def is not None:
            spn_name = spn_def.name
        elif custom_fault_spns and spn in custom_fault_spns:
            spn_name = custom_fault_spns[spn]
        else:
            spn_name = f"Unknown SPN {spn}"

        fmi_desc = FMI_DESCRIPTIONS.get(fmi, f"FMI {fmi}")

        return f"SPN {spn}: {spn_name} (FMI {fmi}: {fmi_desc})"

    def is_dm1_big_endian(self, port: str) -> bool:
        """Check if DM1 SPN encoding should be big-endian for a given port."""
        if self._dm1_config is None:
            return False
        if self._dm1_config.spn_encoding != "big_endian":
            return False
        # If ports list is empty, apply to all ports
        if not self._dm1_config.ports:
            return True
        return port in self._dm1_config.ports

    def get_dm1_custom_fault_spns(self) -> dict[int, str]:
        """Return the custom fault SPN names from DM1 config."""
        if self._dm1_config is None:
            return {}
        return self._dm1_config.custom_fault_spns

    def get_pgn_info(self, can_id: int) -> PGNDefinition | None:
        """Look up PGN definition for a CAN ID."""
        _, pgn, _ = self.extract_pgn(can_id)
        return self._pgn_db.get(pgn)

    def get_pgn_def(self, pgn_num: int) -> PGNDefinition | None:
        """Look up PGN definition by number."""
        return self._pgn_db.get(pgn_num)

    def get_spn_def(self, spn_num: int) -> SPNDefinition | None:
        """Look up SPN definition by number."""
        return self._spn_db.get(spn_num)

    def decode_frame(self, can_id: int, hex_data: str) -> dict[int, float | str | None]:
        """Decode all known SPNs from a single CAN frame.

        Args:
            can_id: 29-bit CAN ID as decimal integer.
            hex_data: Data payload as hex string (e.g., "3FFFCD883927F4FF").

        Returns:
            Dict mapping SPN number to decoded physical value.
            Empty dict if PGN is unknown.
        """
        _, pgn, _ = self.extract_pgn(can_id)

        # Skip DM1 frames — they are handled separately via decode_dm1()
        if pgn == DM1_PGN:
            return {}

        pgn_def = self._pgn_db.get(pgn)
        if pgn_def is None:
            _LOGGER.debug("Unknown PGN %d (0x%04X) from CAN ID %d", pgn, pgn, can_id)
            return {}

        try:
            data_bytes = bytes.fromhex(hex_data)
        except ValueError:
            _LOGGER.warning("Invalid hex data for CAN ID %d: %s", can_id, hex_data)
            return {}

        results: dict[int, float | str | None] = {}
        for spn_num in pgn_def.spns:
            spn_def = self._spn_db.get(spn_num)
            if spn_def is None:
                continue
            value = self.decode_spn(spn_def, data_bytes)
            results[spn_num] = value

        return results

    def decode_can_port(
        self, frames: list[dict], port: str = ""
    ) -> tuple[dict[int, float | str | None], DM1Result | None]:
        """Decode all frames from a CAN port.

        Args:
            frames: List of {"id": int, "data": str} dicts from JSON payload.
            port: Port name (e.g. "can1", "can2") for DM1 encoding selection.

        Returns:
            Tuple of (spn_values, dm1_result).
            spn_values: Dict mapping SPN number to decoded value.
            dm1_result: Decoded DM1 if a DM1 frame was found, else None.
        """
        all_spns: dict[int, float | str | None] = {}
        dm1_result: DM1Result | None = None

        for frame in frames:
            can_id = frame.get("id")
            hex_data = frame.get("data")
            if can_id is None or hex_data is None:
                continue

            # Check for DM1 frame
            _, pgn, _ = self.extract_pgn(can_id)
            if pgn == DM1_PGN:
                try:
                    data_bytes = bytes.fromhex(hex_data)
                except ValueError:
                    continue
                big_endian = self.is_dm1_big_endian(port)
                dm1_result = self.decode_dm1(data_bytes, big_endian_spn=big_endian)
                continue

            decoded = self.decode_frame(can_id, hex_data)
            all_spns.update(decoded)

        return all_spns, dm1_result
