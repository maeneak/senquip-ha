"""J1939 profile loader for custom manufacturer definitions.

Loads JSON-based J1939 profiles that override or extend the built-in database.
Profiles are stored in the j1939_custom/ directory.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .j1939_database import PGNDefinition, SPNDefinition

_LOGGER = logging.getLogger(__name__)


def discover_profiles(custom_dir: Path) -> dict[str, str]:
    """Discover available J1939 profiles in the custom directory.

    Args:
        custom_dir: Path to the j1939_custom directory.

    Returns:
        Dictionary mapping filename to profile display name.
        Example: {"man_d2862.json": "MAN D2862-LE466"}
    """
    profiles: dict[str, str] = {}

    if not custom_dir.exists() or not custom_dir.is_dir():
        return profiles

    for file_path in custom_dir.glob("*.json"):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
                name = data.get("name", file_path.stem)
                profiles[file_path.name] = name
        except (json.JSONDecodeError, OSError) as err:
            _LOGGER.warning("Failed to read profile %s: %s", file_path.name, err)

    return profiles


def load_profile(
    filepath: Path,
) -> tuple[dict[int, PGNDefinition], dict[int, SPNDefinition]]:
    """Load a J1939 profile from JSON file.

    Args:
        filepath: Path to the JSON profile file.

    Returns:
        Tuple of (pgn_database, spn_database) containing parsed definitions.

    Raises:
        ValueError: If the profile is invalid or missing required fields.
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the JSON is malformed.
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    pgns_data = data.get("pgns", {})
    spns_data = data.get("spns", {})

    if not isinstance(pgns_data, dict):
        raise ValueError(
            f"Invalid profile {filepath.name}: 'pgns' must be a dictionary"
        )
    if not isinstance(spns_data, dict):
        raise ValueError(
            f"Invalid profile {filepath.name}: 'spns' must be a dictionary"
        )

    pgn_db: dict[int, PGNDefinition] = {}
    spn_db: dict[int, SPNDefinition] = {}

    # Parse PGNs
    for pgn_str, pgn_obj in pgns_data.items():
        try:
            pgn_num = int(pgn_str)
            if not isinstance(pgn_obj, dict):
                raise ValueError("PGN definition must be an object")
            for field in ("name", "acronym", "length", "spns"):
                if field not in pgn_obj:
                    raise ValueError(f"Missing required field '{field}'")
            if not isinstance(pgn_obj["name"], str):
                raise ValueError("PGN 'name' must be a string")
            if not isinstance(pgn_obj["acronym"], str):
                raise ValueError("PGN 'acronym' must be a string")
            if not isinstance(pgn_obj["length"], int):
                raise ValueError("PGN 'length' must be an integer")
            if not isinstance(pgn_obj["spns"], list):
                raise ValueError("PGN 'spns' must be a list")
            if not all(isinstance(spn, int) for spn in pgn_obj["spns"]):
                raise ValueError("PGN 'spns' entries must be integers")
            pgn_def = PGNDefinition(
                pgn=pgn_num,
                name=pgn_obj["name"],
                acronym=pgn_obj["acronym"],
                length=pgn_obj["length"],
                spns=tuple(pgn_obj["spns"]),
            )
            pgn_db[pgn_num] = pgn_def
        except (KeyError, ValueError, TypeError) as err:
            raise ValueError(
                f"Invalid PGN definition for {pgn_str} in {filepath.name}: {err}"
            ) from err

    # Parse SPNs
    for spn_str, spn_obj in spns_data.items():
        try:
            spn_num = int(spn_str)
            if not isinstance(spn_obj, dict):
                raise ValueError("SPN definition must be an object")
            required_fields = (
                "name",
                "pgn",
                "start_byte",
                "start_bit",
                "bit_length",
                "resolution",
                "offset",
                "unit",
            )
            for field in required_fields:
                if field not in spn_obj:
                    raise ValueError(f"Missing required field '{field}'")
            if not isinstance(spn_obj["name"], str):
                raise ValueError("SPN 'name' must be a string")
            if not isinstance(spn_obj["pgn"], int):
                raise ValueError("SPN 'pgn' must be an integer")
            if not isinstance(spn_obj["start_byte"], int):
                raise ValueError("SPN 'start_byte' must be an integer")
            if not isinstance(spn_obj["start_bit"], int):
                raise ValueError("SPN 'start_bit' must be an integer")
            if not isinstance(spn_obj["bit_length"], int):
                raise ValueError("SPN 'bit_length' must be an integer")
            if not isinstance(spn_obj["resolution"], (int, float)):
                raise ValueError("SPN 'resolution' must be a number")
            if not isinstance(spn_obj["offset"], (int, float)):
                raise ValueError("SPN 'offset' must be a number")
            if not isinstance(spn_obj["unit"], str):
                raise ValueError("SPN 'unit' must be a string")
            min_value = spn_obj.get("min_value")
            max_value = spn_obj.get("max_value")
            if min_value is not None and not isinstance(min_value, (int, float)):
                raise ValueError("SPN 'min_value' must be a number")
            if max_value is not None and not isinstance(max_value, (int, float)):
                raise ValueError("SPN 'max_value' must be a number")
            spn_def = SPNDefinition(
                spn=spn_num,
                name=spn_obj["name"],
                pgn=spn_obj["pgn"],
                start_byte=spn_obj["start_byte"],
                start_bit=spn_obj["start_bit"],
                bit_length=spn_obj["bit_length"],
                resolution=spn_obj["resolution"],
                offset=spn_obj["offset"],
                unit=spn_obj["unit"],
                min_value=min_value,
                max_value=max_value,
            )
            spn_db[spn_num] = spn_def
        except (KeyError, ValueError, TypeError) as err:
            raise ValueError(
                f"Invalid SPN definition for {spn_str} in {filepath.name}: {err}"
            ) from err

    # Validate cross-references
    missing_spn_refs: list[tuple[int, int]] = []
    for pgn_num, pgn_def in pgn_db.items():
        for spn_num in pgn_def.spns:
            if spn_num not in spn_db:
                missing_spn_refs.append((pgn_num, spn_num))

    missing_pgn_refs: list[tuple[int, int]] = []
    for spn_num, spn_def in spn_db.items():
        if spn_def.pgn not in pgn_db:
            missing_pgn_refs.append((spn_num, spn_def.pgn))

    if missing_spn_refs:
        pgn_num, spn_num = missing_spn_refs[0]
        raise ValueError(
            "Invalid profile %s: PGN %d references SPN %d which is not defined"
            % (filepath.name, pgn_num, spn_num)
        )
    if missing_pgn_refs:
        spn_num, pgn_num = missing_pgn_refs[0]
        raise ValueError(
            "Invalid profile %s: SPN %d references PGN %d which is not defined"
            % (filepath.name, spn_num, pgn_num)
        )

    return pgn_db, spn_db


def merge_databases(
    base_pgn: dict[int, PGNDefinition],
    base_spn: dict[int, SPNDefinition],
    profile_paths: list[Path],
) -> tuple[dict[int, PGNDefinition], dict[int, SPNDefinition]]:
    """Merge base databases with custom profiles.

    Custom profiles override built-in definitions. Later profiles in the list
    override earlier ones.

    Args:
        base_pgn: Built-in PGN database.
        base_spn: Built-in SPN database.
        profile_paths: List of profile file paths to merge.

    Returns:
        Tuple of (merged_pgn_db, merged_spn_db).
    """
    merged_pgn = dict(base_pgn)
    merged_spn = dict(base_spn)

    for profile_path in profile_paths:
        try:
            custom_pgn, custom_spn = load_profile(profile_path)
            merged_pgn.update(custom_pgn)
            merged_spn.update(custom_spn)
            _LOGGER.debug("Loaded J1939 profile: %s", profile_path.name)
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as err:
            _LOGGER.error("Failed to load profile %s: %s", profile_path.name, err)

    return merged_pgn, merged_spn
