"""Tests for integration diagnostics payload shaping."""

from __future__ import annotations

import asyncio

from custom_components.senquip.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_MQTT_TOPIC,
    DIAGNOSTICS_MAX_FRAMES,
    DOMAIN,
)
from custom_components.senquip.diagnostics import async_get_config_entry_diagnostics
from tests.ha_stubs import ConfigEntry


class _CoordinatorStub:
    def __init__(self, diagnostics, data):
        self.diagnostics = diagnostics
        self.data = data


class _HassStub:
    def __init__(self, coordinator, entry_id: str):
        self.data = {DOMAIN: {entry_id: coordinator}}


def test_diagnostics_frame_cap_keeps_total_counts():
    entry = ConfigEntry(
        data={
            CONF_DEVICE_ID: "DEV1",
            CONF_DEVICE_NAME: "Dev",
            CONF_MQTT_TOPIC: "senquip/DEV1/data",
        },
        entry_id="entry1",
    )
    frames = [
        {
            "can_id": idx,
            "known": idx % 2 == 0,
            "spns": {"110": {"value": None if idx == 0 else 1, "name": "Engine Coolant Temp"}},
            "pgn": 65262,
            "pgn_acronym": "ET1",
        }
        for idx in range(DIAGNOSTICS_MAX_FRAMES + 10)
    ]
    coordinator = _CoordinatorStub(
        diagnostics={
            "can1": {
                "protocol": "j1939",
                "frames": frames,
            }
        },
        data={"internal.main.vin": 28.1},
    )
    hass = _HassStub(coordinator, entry.entry_id)

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(async_get_config_entry_diagnostics(hass, entry))
    finally:
        loop.close()

    can1 = result["can_bus"]["can1"]
    assert can1["total_frames"] == DIAGNOSTICS_MAX_FRAMES + 10
    assert can1["known_frames"] + can1["unknown_frames"] == DIAGNOSTICS_MAX_FRAMES + 10
    assert len(can1["frames"]) == DIAGNOSTICS_MAX_FRAMES
    assert can1["frames"][0]["can_id"] == 10
