"""Tests for the J1939 profile loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.senquip.j1939_database import (
    PGN_DATABASE,
    SPN_DATABASE,
    PGNDefinition,
    SPNDefinition,
)
from custom_components.senquip.j1939_profile_loader import (
    discover_profiles,
    load_profile,
    merge_databases,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestDiscoverProfiles:
    """Tests for discover_profiles()."""

    def test_empty_directory(self, tmp_path: Path):
        assert discover_profiles(tmp_path) == {}

    def test_single_profile(self, tmp_path: Path):
        profile_path = tmp_path / "test.json"
        _write_json(profile_path, {"name": "Test Profile"})
        assert discover_profiles(tmp_path) == {"test.json": "Test Profile"}

    def test_multiple_profiles(self, tmp_path: Path):
        _write_json(tmp_path / "alpha.json", {"name": "Alpha"})
        _write_json(tmp_path / "beta.json", {})
        profiles = discover_profiles(tmp_path)
        assert profiles["alpha.json"] == "Alpha"
        assert profiles["beta.json"] == "beta"


class TestLoadProfile:
    """Tests for load_profile()."""

    def test_valid_profile(self, tmp_path: Path):
        profile = {
            "name": "Test",
            "pgns": {
                "100": {
                    "name": "Test PGN",
                    "acronym": "TPGN",
                    "length": 8,
                    "spns": [1],
                }
            },
            "spns": {
                "1": {
                    "name": "Test SPN",
                    "pgn": 100,
                    "start_byte": 1,
                    "start_bit": 1,
                    "bit_length": 8,
                    "resolution": 1,
                    "offset": 0,
                    "unit": "V",
                }
            },
        }
        profile_path = tmp_path / "valid.json"
        _write_json(profile_path, profile)

        pgn_db, spn_db = load_profile(profile_path)
        assert pgn_db[100].acronym == "TPGN"
        assert spn_db[1].unit == "V"

    def test_missing_required_field(self, tmp_path: Path):
        profile = {
            "pgns": {
                "100": {
                    "name": "Test PGN",
                    "length": 8,
                    "spns": [1],
                }
            },
            "spns": {},
        }
        profile_path = tmp_path / "missing.json"
        _write_json(profile_path, profile)

        with pytest.raises(ValueError):
            load_profile(profile_path)

    def test_invalid_types(self, tmp_path: Path):
        profile = {
            "pgns": {
                "100": {
                    "name": "Test PGN",
                    "acronym": "TPGN",
                    "length": "8",
                    "spns": ["1"],
                }
            },
            "spns": {
                "1": {
                    "name": "Test SPN",
                    "pgn": "100",
                    "start_byte": 1,
                    "start_bit": 1,
                    "bit_length": 8,
                    "resolution": 1,
                    "offset": 0,
                    "unit": "V",
                }
            },
        }
        profile_path = tmp_path / "invalid.json"
        _write_json(profile_path, profile)

        with pytest.raises(ValueError):
            load_profile(profile_path)


class TestMergeDatabases:
    """Tests for merge_databases()."""

    def test_override_replaces_pgn(self, tmp_path: Path):
        base_pgn = {
            100: PGNDefinition(
                pgn=100, name="Base", acronym="BASE", length=8, spns=(1,)
            ),
            200: PGNDefinition(
                pgn=200, name="Other", acronym="OTH", length=8, spns=(2,)
            ),
        }
        base_spn = {
            1: SPNDefinition(
                spn=1,
                name="Base SPN",
                pgn=100,
                start_byte=1,
                start_bit=1,
                bit_length=8,
                resolution=1,
                offset=0,
                unit="V",
            ),
            2: SPNDefinition(
                spn=2,
                name="Other SPN",
                pgn=200,
                start_byte=1,
                start_bit=1,
                bit_length=8,
                resolution=1,
                offset=0,
                unit="A",
            ),
        }

        profile = {
            "pgns": {
                "100": {
                    "name": "Override",
                    "acronym": "OVR",
                    "length": 8,
                    "spns": [3],
                }
            },
            "spns": {
                "3": {
                    "name": "Override SPN",
                    "pgn": 100,
                    "start_byte": 2,
                    "start_bit": 1,
                    "bit_length": 8,
                    "resolution": 1,
                    "offset": 0,
                    "unit": "V",
                }
            },
        }
        profile_path = tmp_path / "override.json"
        _write_json(profile_path, profile)

        merged_pgn, merged_spn = merge_databases(
            base_pgn, base_spn, [profile_path]
        )
        assert merged_pgn[100].spns == (3,)
        assert merged_pgn[200].spns == (2,)
        assert 1 in merged_spn
        assert 3 in merged_spn

    def test_man_profile_override(self):
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = (
            repo_root
            / "custom_components"
            / "senquip"
            / "j1939_custom"
            / "man_d2862.json"
        )

        pgn_db, _ = load_profile(profile_path)
        assert pgn_db[65271].spns == (167, 168)

        merged_pgn, _ = merge_databases(
            PGN_DATABASE, SPN_DATABASE, [profile_path]
        )
        assert merged_pgn[65271].spns == (167, 168)
