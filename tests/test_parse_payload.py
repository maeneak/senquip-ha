"""Tests for protocol runtime decoding and canonical key extraction."""

from pathlib import Path

from custom_components.senquip.can_profiles.loader import discover_profiles
from custom_components.senquip.can_protocols.j1939.protocol import J1939CANProtocol


EXAMPLE_PAYLOAD = {
    "deviceid": "HE8EV12LF",
    "vsys": 4.17,
    "vin": 28.27,
    "ambient": 38.45,
    "can2": [
        {"id": 217056256, "data": "3FFFCD883927F4FF"},
        {"id": 419357952, "data": "5F27000000000000"},
        {"id": 419372032, "data": "C4F0FFFF00FF00FF"},
    ],
    "events": [{"topic": "mjs", "msg": "CPU Threshold Exceeded", "lv": 30}],
}


def _build_decoder(with_man_profile: bool = False):
    protocol = J1939CANProtocol()
    profiles = discover_profiles(Path("custom_components/senquip/can_profiles"))
    selected = [profiles["man_d2862.json"]] if with_man_profile else []
    decoder, _errors = protocol.build_decoder(selected)
    return protocol, decoder


class TestRuntimeDecode:
    def test_known_spn_values(self):
        protocol, decoder = _build_decoder()
        selected = {"can.can2.j1939.spn190", "can.can2.j1939.spn247"}
        values, _ = protocol.decode_runtime(EXAMPLE_PAYLOAD["can2"], "can2", selected, decoder)
        assert values["can.can2.j1939.spn190"] == 1841.0
        assert values["can.can2.j1939.spn247"] == 503.95

    def test_unknown_pgn_raw_value(self):
        protocol, decoder = _build_decoder()
        selected = {"can.can2.j1939.raw.65308"}
        values, _ = protocol.decode_runtime(EXAMPLE_PAYLOAD["can2"], "can2", selected, decoder)
        assert values["can.can2.j1939.raw.65308"] == "C4F0FFFF00FF00FF"

    def test_man_profile_decodes_proprietary_spn(self):
        protocol, decoder = _build_decoder(with_man_profile=True)
        selected = {"can.can2.j1939.spn800001"}
        values, diagnostics = protocol.decode_runtime(EXAMPLE_PAYLOAD["can2"], "can2", selected, decoder)
        assert "can.can2.j1939.spn800001" not in values
        assert any("800001" in frame.get("spns", {}) for frame in diagnostics)

    def test_dm1_keys_emitted_when_selected(self):
        protocol, decoder = _build_decoder(with_man_profile=True)
        frames = [{"id": 419351040, "data": "44FFFE00C201FFFF"}]
        selected = {"can.can2.j1939.dm1.active_fault", "can.can2.j1939.dm1.active_spn"}
        values, _ = protocol.decode_runtime(frames, "can2", selected, decoder)
        assert "can.can2.j1939.dm1.active_fault" in values
        assert "can.can2.j1939.dm1.active_spn" in values

    def test_unavailable_spn_not_emitted_in_runtime_values(self):
        protocol, decoder = _build_decoder()
        frames = [{"id": 0x18FEEE00, "data": "FFFFFFFFFFFFFFFF"}]
        selected = {"can.can2.j1939.spn110"}
        values, diagnostics = protocol.decode_runtime(frames, "can2", selected, decoder)

        assert "can.can2.j1939.spn110" not in values
        assert diagnostics[0]["spns"]["110"]["value"] is None
