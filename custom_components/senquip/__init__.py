"""The Senquip Telemetry integration."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .can_profiles.loader import discover_profiles
from .can_protocols.registry import get_can_protocol
from .const import (
    CAN_PORTS,
    CAN_PROFILE_DIR,
    CONF_DEVICE_ID,
    CONF_MQTT_TOPIC,
    CONF_PORT_CONFIGS,
    CONF_SELECTED_SIGNALS,
    DOMAIN,
    PLATFORMS,
    deserialize_port_configs,
)

_LOGGER = logging.getLogger(__name__)


class SenquipDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate MQTT data for a single Senquip device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Senquip {entry.data[CONF_DEVICE_ID]}",
        )
        self._entry = entry
        self._device_id: str = entry.data[CONF_DEVICE_ID]
        self._selected: set[str] = set(entry.data[CONF_SELECTED_SIGNALS])
        self._port_configs = deserialize_port_configs(entry.data.get(CONF_PORT_CONFIGS))
        self._available_profiles = discover_profiles(Path(__file__).parent / CAN_PROFILE_DIR)

        self._can_runtime: dict[str, tuple[Any, Any]] = {}
        self._profile_errors: dict[str, list[str]] = {}
        for port in CAN_PORTS:
            config = self._port_configs.get(port)
            if config is None or not config.active or config.protocol is None:
                continue
            protocol = get_can_protocol(config.protocol)
            if protocol is None:
                _LOGGER.warning("Unsupported protocol %s on %s", config.protocol, port)
                continue
            selected_profiles = []
            for profile_name in config.profiles:
                profile = self._available_profiles.get(profile_name)
                if profile is None:
                    continue
                if profile.base_protocol != config.protocol:
                    continue
                selected_profiles.append(profile)
            decoder, errors = protocol.build_decoder(selected_profiles)
            if errors:
                self._profile_errors[port] = errors
                for err_msg in errors:
                    _LOGGER.error("Port %s: %s", port, err_msg)
            self._can_runtime[port] = (protocol, decoder)

        self._unsubscribe: Any = None
        self.diagnostics: dict[str, Any] = {}

    def get_can_runtime(self, port_id: str) -> tuple[Any, Any] | None:
        """Return protocol/decoder tuple for a CAN port if available."""
        return self._can_runtime.get(port_id)

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
        updates = self._sanitize_updates(data)

        current_data: dict[str, Any] = {}
        if isinstance(self.data, dict):
            current_data = self.data

        merged_data = dict(current_data)
        merged_data.update(updates)
        self.async_set_updated_data(merged_data)

    @staticmethod
    def _is_valid_state_value(value: Any) -> bool:
        """Return whether a parsed value can be published as sensor state."""
        if value is None:
            return False
        if isinstance(value, float) and not math.isfinite(value):
            return False
        return isinstance(value, (str, int, float, bool))

    def _sanitize_updates(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Filter invalid values from a partial payload update."""
        return {
            key: value
            for key, value in updates.items()
            if self._is_valid_state_value(value)
        }

    def _parse_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse raw JSON into a flat {signal_key: value} dict."""
        data: dict[str, Any] = {}
        diag: dict[str, Any] = {}

        for key, value in payload.items():
            if key in ("deviceid", "ts", "time"):
                continue

            if key in CAN_PORTS and isinstance(value, list):
                runtime = self._can_runtime.get(key)
                if runtime is None:
                    continue
                protocol, decoder = runtime
                port_values, port_diag = protocol.decode_runtime(
                    value,
                    key,
                    self._selected,
                    decoder,
                )
                data.update(port_values)
                if port_diag:
                    diag[key] = {
                        "protocol": protocol.protocol_id,
                        "frames": port_diag,
                    }
                continue

            if key == "events" and isinstance(value, list):
                if "event.main.last" in self._selected and value:
                    last_event = value[-1]
                    if isinstance(last_event, dict):
                        msg_value = last_event.get("msg")
                        if msg_value is not None:
                            data["event.main.last"] = str(msg_value)
                continue

            if isinstance(value, (int, float, str)):
                signal_key = f"internal.main.{key}"
                if signal_key in self._selected:
                    data[signal_key] = value

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

