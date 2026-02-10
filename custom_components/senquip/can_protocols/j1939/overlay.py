"""J1939 profile overlay parsing and database merge helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ...can_profiles.loader import CANProfile
from .database import PGNDefinition, SPNDefinition

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DM1Config:
    """Configuration for DM1 (Diagnostic Message 1) decoding."""

    spn_encoding: str = "little_endian"
    ports: tuple[str, ...] = ()
    custom_fault_spns: dict[int, str] = field(default_factory=dict)


def _validate_pgn_data(
    pgns_data: dict[str, Any],
    profile_name: str,
) -> dict[int, PGNDefinition]:
    parsed: dict[int, PGNDefinition] = {}
    for pgn_str, pgn_obj in pgns_data.items():
        try:
            pgn_num = int(pgn_str)
            if not isinstance(pgn_obj, dict):
                raise ValueError("PGN definition must be an object")
            for req_field in ("name", "acronym", "length", "spns"):
                if req_field not in pgn_obj:
                    raise ValueError(f"Missing required field '{req_field}'")
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
            parsed[pgn_num] = PGNDefinition(
                pgn=pgn_num,
                name=pgn_obj["name"],
                acronym=pgn_obj["acronym"],
                length=pgn_obj["length"],
                spns=tuple(pgn_obj["spns"]),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError(
                f"Invalid PGN definition for {pgn_str} in {profile_name}: {err}"
            ) from err
    return parsed


def _validate_spn_data(
    spns_data: dict[str, Any],
    profile_name: str,
) -> dict[int, SPNDefinition]:
    parsed: dict[int, SPNDefinition] = {}
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
    for spn_str, spn_obj in spns_data.items():
        try:
            spn_num = int(spn_str)
            if not isinstance(spn_obj, dict):
                raise ValueError("SPN definition must be an object")
            for req_field in required_fields:
                if req_field not in spn_obj:
                    raise ValueError(f"Missing required field '{req_field}'")
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
            parsed[spn_num] = SPNDefinition(
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
        except (KeyError, TypeError, ValueError) as err:
            raise ValueError(
                f"Invalid SPN definition for {spn_str} in {profile_name}: {err}"
            ) from err
    return parsed


def _parse_dm1_config(dm1_data: Any, profile_name: str) -> DM1Config | None:
    if dm1_data is None:
        return None
    if not isinstance(dm1_data, dict):
        _LOGGER.warning("Invalid dm1 section in %s: must be an object", profile_name)
        return None

    spn_encoding = dm1_data.get("spn_encoding", "little_endian")
    if spn_encoding not in ("little_endian", "big_endian"):
        _LOGGER.warning("Invalid dm1.spn_encoding in %s: %s", profile_name, spn_encoding)
        spn_encoding = "little_endian"

    ports_raw = dm1_data.get("ports", [])
    if not isinstance(ports_raw, list):
        ports_raw = []
    ports = tuple(str(item) for item in ports_raw)

    custom_fault_spns: dict[int, str] = {}
    faults_raw = dm1_data.get("custom_fault_spns", {})
    if isinstance(faults_raw, dict):
        for spn_str, name in faults_raw.items():
            try:
                custom_fault_spns[int(spn_str)] = str(name)
            except (TypeError, ValueError):
                pass

    return DM1Config(
        spn_encoding=spn_encoding,
        ports=ports,
        custom_fault_spns=custom_fault_spns,
    )


def parse_j1939_profile(
    profile: CANProfile,
) -> tuple[dict[int, PGNDefinition], dict[int, SPNDefinition], DM1Config | None]:
    """Parse and validate a J1939 section from a generic CAN profile."""

    section = profile.protocol_data.get("j1939", {})
    if not isinstance(section, dict):
        raise ValueError(f"Invalid profile {profile.filename}: j1939 section must be an object")

    pgns_data = section.get("pgns", {})
    spns_data = section.get("spns", {})
    if not isinstance(pgns_data, dict):
        raise ValueError(f"Invalid profile {profile.filename}: 'pgns' must be a dictionary")
    if not isinstance(spns_data, dict):
        raise ValueError(f"Invalid profile {profile.filename}: 'spns' must be a dictionary")

    pgn_db = _validate_pgn_data(pgns_data, profile.filename)
    spn_db = _validate_spn_data(spns_data, profile.filename)

    for pgn_num, pgn_def in pgn_db.items():
        for spn_num in pgn_def.spns:
            if spn_num not in spn_db:
                raise ValueError(
                    f"Invalid profile {profile.filename}: PGN {pgn_num} references SPN {spn_num} which is not defined"
                )
    for spn_num, spn_def in spn_db.items():
        if spn_def.pgn not in pgn_db:
            raise ValueError(
                f"Invalid profile {profile.filename}: SPN {spn_num} references PGN {spn_def.pgn} which is not defined"
            )

    dm1_config = _parse_dm1_config(section.get("dm1"), profile.filename)
    return pgn_db, spn_db, dm1_config


def merge_j1939_databases(
    base_pgn: dict[int, PGNDefinition],
    base_spn: dict[int, SPNDefinition],
    profiles: list[CANProfile],
) -> tuple[dict[int, PGNDefinition], dict[int, SPNDefinition], DM1Config | None]:
    """Merge base databases with J1939 sections from selected profiles."""

    merged_pgn = dict(base_pgn)
    merged_spn = dict(base_spn)
    dm1_config: DM1Config | None = None

    for profile in profiles:
        if profile.base_protocol != "j1939":
            continue
        try:
            custom_pgn, custom_spn, profile_dm1 = parse_j1939_profile(profile)
            merged_pgn.update(custom_pgn)
            merged_spn.update(custom_spn)
            if profile_dm1 is not None:
                dm1_config = profile_dm1
            _LOGGER.debug("Loaded J1939 profile: %s", profile.filename)
        except ValueError as err:
            _LOGGER.error("Failed to load profile %s: %s", profile.filename, err)

    return merged_pgn, merged_spn, dm1_config

