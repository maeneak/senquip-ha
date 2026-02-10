"""Tests for generic CAN profile loading and J1939 overlay parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.senquip.can_profiles.loader import discover_profiles
from custom_components.senquip.can_protocols.j1939.database import PGN_DATABASE, SPN_DATABASE
from custom_components.senquip.can_protocols.j1939.overlay import (
    merge_j1939_databases,
    parse_j1939_profile,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestDiscoverProfiles:
    def test_empty_directory(self, tmp_path: Path):
        assert discover_profiles(tmp_path) == {}

    def test_single_profile(self, tmp_path: Path):
        _write_json(
            tmp_path / "test.json",
            {
                "name": "Test Profile",
                "base_protocol": "j1939",
                "protocol_data": {"j1939": {"pgns": {}, "spns": {}}},
            },
        )
        profiles = discover_profiles(tmp_path)
        assert profiles["test.json"].name == "Test Profile"
        assert profiles["test.json"].base_protocol == "j1939"

    def test_invalid_profile_is_skipped(self, tmp_path: Path):
        _write_json(tmp_path / "invalid.json", {"name": "Broken"})
        profiles = discover_profiles(tmp_path)
        assert profiles == {}


class TestJ1939Overlay:
    def test_parse_man_profile(self):
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = (
            repo_root
            / "custom_components"
            / "senquip"
            / "can_profiles"
            / "man_d2862.json"
        )
        profiles = discover_profiles(profile_path.parent)
        profile = profiles["man_d2862.json"]

        pgn_db, _, dm1_config = parse_j1939_profile(profile)
        assert pgn_db[65271].spns == (167, 168)
        assert dm1_config is not None
        assert dm1_config.spn_encoding == "big_endian"

    def test_merge_overrides_base_database(self):
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = (
            repo_root
            / "custom_components"
            / "senquip"
            / "can_profiles"
            / "man_d2862.json"
        )
        profiles = discover_profiles(profile_path.parent)
        profile = profiles["man_d2862.json"]

        merged_pgn, merged_spn, dm1_config, errors = merge_j1939_databases(
            PGN_DATABASE,
            SPN_DATABASE,
            [profile],
        )
        assert merged_pgn[65271].spns == (167, 168)
        assert 800001 in merged_spn
        assert dm1_config is not None
        assert errors == []

    def test_cross_reference_validation_raises(self, tmp_path: Path):
        _write_json(
            tmp_path / "bad.json",
            {
                "name": "Bad",
                "base_protocol": "j1939",
                "protocol_data": {
                    "j1939": {
                        "pgns": {
                            "100": {
                                "name": "Test PGN",
                                "acronym": "TP",
                                "length": 8,
                                "spns": [1],
                            }
                        },
                        "spns": {},
                    }
                },
            },
        )
        profiles = discover_profiles(tmp_path)
        with pytest.raises(ValueError):
            parse_j1939_profile(profiles["bad.json"])

