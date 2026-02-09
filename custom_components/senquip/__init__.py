"""The Senquip Telemetry integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_DEVICE_ID,
    CONF_J1939_PROFILES,
    CONF_MQTT_TOPIC,
    CONF_SELECTED_SENSORS,
    DOMAIN,
    PLATFORMS,
)
from .j1939_database import PGN_DATABASE, SPN_DATABASE
from .j1939_decoder import J1939Decoder
from .j1939_profile_loader import merge_databases

_LOGGER = logging.getLogger(__name__)


class SenquipDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate MQTT data for a single Senquip device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Senquip {entry.data[CONF_DEVICE_ID]}",
        )
        self._entry = entry
        self._device_id: str = entry.data[CONF_DEVICE_ID]
        self._selected: set[str] = set(entry.data[CONF_SELECTED_SENSORS])

        # Load J1939 profiles and merge with built-in database
        profile_names = entry.data.get(CONF_J1939_PROFILES, [])
        custom_dir = Path(__file__).parent / "j1939_custom"
        profile_paths = [custom_dir / name for name in profile_names]

        self._pgn_db, self._spn_db = merge_databases(
            PGN_DATABASE, SPN_DATABASE, profile_paths
        )
        self._decoder = J1939Decoder(self._pgn_db, self._spn_db)

        self._unsubscribe: Any = None
        self.diagnostics: dict[str, Any] = {}

    async def async_subscribe(self) -> None:
        """Subscribe to the device's MQTT topic."""
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            _LOGGER.error("MQTT client not available")
            return

        self._unsubscribe = await mqtt.async_subscribe(
            self.hass,
            self._entry.data[CONF_MQTT_TOPIC],
            self._handle_message,
            qos=0,
        )
        _LOGGER.debug(
            "Subscribed to %s for device %s",
            self._entry.data[CONF_MQTT_TOPIC],
            self._device_id,
        )

    async def async_unsubscribe(self) -> None:
        """Unsubscribe from MQTT."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    @callback
    def _handle_message(self, msg: mqtt.models.ReceiveMessage) -> None:
        """Process an incoming MQTT message."""
        try:
            payload = json.loads(msg.payload)
        except (json.JSONDecodeError, ValueError):
            _LOGGER.warning("Invalid JSON on topic %s", msg.topic)
            return

        # Handle array payloads (shouldn't happen per config, but be safe)
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and item.get("deviceid") == self._device_id:
                    payload = item
                    break
            else:
                return

        if not isinstance(payload, dict):
            return

        data = self._parse_payload(payload)
        self.async_set_updated_data(data)

    def _parse_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse raw JSON into a flat {sensor_key: value} dict."""
        data: dict[str, Any] = {}
        diag: dict[str, Any] = {}

        for key, value in payload.items():
            # Skip metadata fields
            if key in ("deviceid", "ts", "time"):
                continue

            # CAN ports — decode J1939 frames
            if key in ("can1", "can2") and isinstance(value, list):
                port_diag: list[dict[str, Any]] = []

                for frame in value:
                    can_id = frame.get("id")
                    hex_data = frame.get("data")
                    if can_id is None or hex_data is None:
                        continue

                    _, pgn, source = self._decoder.extract_pgn(can_id)
                    pgn_def = self._decoder.get_pgn_info(can_id)
                    decoded = self._decoder.decode_frame(can_id, hex_data)

                    frame_diag: dict[str, Any] = {
                        "can_id": can_id,
                        "can_id_hex": f"0x{can_id:08X}",
                        "pgn": pgn,
                        "pgn_hex": f"0x{pgn:04X}",
                        "source_address": source,
                        "data": hex_data,
                        "known": pgn_def is not None,
                    }

                    if pgn_def:
                        frame_diag["pgn_name"] = pgn_def.name
                        frame_diag["pgn_acronym"] = pgn_def.acronym
                        spns: dict[str, Any] = {}
                        for spn_num, spn_value in decoded.items():
                            spn_def = self._decoder.get_spn_def(spn_num)
                            spn_entry: dict[str, Any] = {"value": spn_value}
                            if spn_def:
                                spn_entry["name"] = spn_def.name
                                spn_entry["unit"] = spn_def.unit
                            spns[str(spn_num)] = spn_entry
                        frame_diag["spns"] = spns

                    port_diag.append(frame_diag)

                    # Normal sensor data extraction
                    for spn_num, spn_value in decoded.items():
                        sensor_key = f"{key}.spn{spn_num}"
                        if sensor_key in self._selected:
                            data[sensor_key] = spn_value

                    # Raw unknown PGNs
                    if not decoded:
                        raw_key = f"{key}.raw.{pgn}"
                        if raw_key in self._selected:
                            data[raw_key] = hex_data

                if port_diag:
                    diag[key] = port_diag

            # Events — store last event message
            elif key == "events" and isinstance(value, list):
                if "events.last" in self._selected and value:
                    last_event = value[-1]
                    if isinstance(last_event, dict):
                        data["events.last"] = last_event.get("msg", "")

            # Internal/flat sensors
            elif isinstance(value, (int, float, str)):
                sensor_key = f"internal.{key}"
                if sensor_key in self._selected:
                    data[sensor_key] = value

        self.diagnostics = diag
        return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Senquip Telemetry from a config entry."""
    coordinator = SenquipDataCoordinator(hass, entry)
    await coordinator.async_subscribe()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Senquip config entry."""
    coordinator: SenquipDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_unsubscribe()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
