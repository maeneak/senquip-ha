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

    def test_profile_with_states_mapping(self, tmp_path: Path):
        """Profile SPN with a states mapping is parsed correctly."""
        _write_json(
            tmp_path / "gearbox.json",
            {
                "name": "Gearbox Test",
                "base_protocol": "j1939",
                "protocol_data": {
                    "j1939": {
                        "pgns": {
                            "65308": {
                                "name": "Aux MAN Engine",
                                "acronym": "MAN_AUX",
                                "length": 8,
                                "spns": [800005],
                            }
                        },
                        "spns": {
                            "800005": {
                                "name": "Gearbox Status",
                                "pgn": 65308,
                                "start_byte": 1,
                                "start_bit": 1,
                                "bit_length": 6,
                                "resolution": 1,
                                "offset": 0,
                                "unit": "",
                                "states": {
                                    "1": "Neutral",
                                    "4": "Forward",
                                    "16": "Reverse",
                                },
                            }
                        },
                    }
                },
            },
        )
        profiles = discover_profiles(tmp_path)
        pgn_db, spn_db, _ = parse_j1939_profile(profiles["gearbox.json"])
        assert 800005 in spn_db
        assert spn_db[800005].states == {1: "Neutral", 4: "Forward", 16: "Reverse"}

    def test_man_profile_gearbox_spn(self):
        """Real MAN profile includes gearbox SPN 800005 with states."""
        repo_root = Path(__file__).resolve().parents[1]
        profile_path = (
            repo_root / "custom_components" / "senquip" / "can_profiles" / "man_d2862.json"
        )
        profiles = discover_profiles(profile_path.parent)
        _, spn_db, _ = parse_j1939_profile(profiles["man_d2862.json"])
        assert 800005 in spn_db
        assert spn_db[800005].states is not None
        assert spn_db[800005].states[4] == "Forward"

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

