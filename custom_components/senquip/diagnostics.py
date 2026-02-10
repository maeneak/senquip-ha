"""Diagnostics support for the Senquip Telemetry integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_MQTT_TOPIC,
    CONF_PORT_CONFIGS,
    CONF_SELECTED_SIGNALS,
    DOMAIN,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    can_diag = coordinator.diagnostics
    can_summary: dict[str, Any] = {}

    for port, port_data in can_diag.items():
        protocol = port_data.get("protocol")
        frames = port_data.get("frames", [])
        known_frames = [frame for frame in frames if frame.get("known")]
        unknown_frames = [frame for frame in frames if not frame.get("known")]

        null_spns: list[dict[str, Any]] = []
        for frame in known_frames:
            for spn_id, spn_info in frame.get("spns", {}).items():
                if spn_info.get("value") is None:
                    null_spns.append(
                        {
                            "spn": spn_id,
                            "name": spn_info.get("name", "Unknown"),
                            "pgn": frame.get("pgn"),
                            "pgn_acronym": frame.get("pgn_acronym", ""),
                        }
                    )

        can_summary[port] = {
            "protocol": protocol,
            "total_frames": len(frames),
            "known_frames": len(known_frames),
            "unknown_frames": len(unknown_frames),
            "frames": frames,
            "unavailable_spns": null_spns,
        }

    return {
        "config": {
            "device_id": entry.data.get(CONF_DEVICE_ID),
            "device_name": entry.data.get(CONF_DEVICE_NAME),
            "mqtt_topic": entry.data.get(CONF_MQTT_TOPIC),
            "selected_signals": entry.data.get(CONF_SELECTED_SIGNALS, []),
            "port_configs": entry.data.get(CONF_PORT_CONFIGS, {}),
        },
        "current_values": coordinator.data or {},
        "can_bus": can_summary,
    }

