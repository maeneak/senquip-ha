"""Generic CAN profile loader."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CANProfile:
    """Generic CAN profile metadata and payload."""

    filename: str
    name: str
    base_protocol: str
    description: str
    protocol_data: dict[str, dict[str, Any]]


def _load_file(path: Path) -> CANProfile:
    with open(path, encoding="utf-8") as profile_file:
        payload = json.load(profile_file)

    if not isinstance(payload, dict):
        raise ValueError("Profile must be a JSON object")

    name = payload.get("name", path.stem)
    base_protocol = payload.get("base_protocol")
    protocol_data = payload.get("protocol_data")
    description = payload.get("description", "")

    if not isinstance(name, str):
        raise ValueError("'name' must be a string")
    if not isinstance(base_protocol, str) or not base_protocol:
        raise ValueError("'base_protocol' must be a non-empty string")
    if not isinstance(description, str):
        raise ValueError("'description' must be a string")
    if not isinstance(protocol_data, dict):
        raise ValueError("'protocol_data' must be a dictionary")

    normalized_data: dict[str, dict[str, Any]] = {}
    for protocol_id, section in protocol_data.items():
        if not isinstance(protocol_id, str):
            raise ValueError("protocol_data keys must be strings")
        if not isinstance(section, dict):
            raise ValueError(f"protocol_data.{protocol_id} must be an object")
        normalized_data[protocol_id] = section

    return CANProfile(
        filename=path.name,
        name=name,
        base_protocol=base_protocol,
        description=description,
        protocol_data=normalized_data,
    )


def discover_profiles(custom_dir: Path) -> dict[str, CANProfile]:
    """Discover CAN profile files in a directory."""
    profiles: dict[str, CANProfile] = {}
    if not custom_dir.exists() or not custom_dir.is_dir():
        return profiles

    for profile_path in custom_dir.glob("*.json"):
        try:
            profile = _load_file(profile_path)
            profiles[profile.filename] = profile
        except (OSError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.warning("Failed to read profile %s: %s", profile_path.name, err)
    return profiles


def profile_display_map(
    profiles: dict[str, CANProfile],
    base_protocol: str | None = None,
) -> dict[str, str]:
    """Return filename->display-name map, optionally filtered by base protocol."""
    display: dict[str, str] = {}
    for filename, profile in profiles.items():
        if base_protocol is not None and profile.base_protocol != base_protocol:
            continue
        display[filename] = profile.name
    return display

