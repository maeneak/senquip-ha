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
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .can_profiles.loader import CANProfile, discover_profiles
from .can_protocols.registry import get_can_protocol
from .const import (
    CAN_PORTS,
    CAN_PROFILE_DIR,
    CONF_DEVICE_ID,
    CONF_MQTT_TOPIC,
    CONF_PORT_CONFIGS,
    CONF_SELECTED_SIGNALS,
    DEVICE_TIMEOUT,
    DOMAIN,
    KNOWN_INTERNAL_SENSORS,
    PLATFORMS,
    TOTAL_INCREASING_REGRESSION_TOLERANCE,
    SensorStateClass,
    deserialize_port_configs,
)
from .signal_keys import LEGACY_SELECTED_SENSORS_KEY, normalize_selected_signals

_LOGGER = logging.getLogger(__name__)


class SenquipDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate MQTT data for a single Senquip device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        available_profiles: dict[str, CANProfile],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Senquip {entry.data[CONF_DEVICE_ID]}",
        )
        self._entry = entry
        self._device_id: str = entry.data[CONF_DEVICE_ID]
        self._selected: set[str] = set(entry.data[CONF_SELECTED_SIGNALS])
        self._port_configs = deserialize_port_configs(entry.data.get(CONF_PORT_CONFIGS))
        self._available_profiles = available_profiles

        self._can_runtime: dict[str, tuple[Any, Any]] = {}
        self._can_port_available: dict[str, bool] = {}
        self._profile_errors: dict[str, list[str]] = {}
        self._state_class_cache: dict[str, SensorStateClass | None] = {}
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
        self._device_online: bool = False
        self._offline_timer: Any = None
        self.diagnostics: dict[str, Any] = {}

    def get_can_runtime(self, port_id: str) -> tuple[Any, Any] | None:
        """Return protocol/decoder tuple for a CAN port if available."""
        return self._can_runtime.get(port_id)

    def is_device_online(self) -> bool:
        """Return whether the device is online (receiving MQTT messages)."""
        return self._device_online

    def is_can_port_available(self, port_id: str) -> bool:
        """Return whether a CAN port is producing valid data."""
        return self._can_port_available.get(port_id, True)

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
        if self._offline_timer is not None:
            self._offline_timer()
            self._offline_timer = None
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    @callback
    def _mark_device_offline(self, _now: Any = None) -> None:
        """Mark device as offline after timeout with no MQTT messages."""
        self._device_online = False
        self._offline_timer = None
        for port_id in self._can_port_available:
            self._can_port_available[port_id] = False
        # Push an update so binary sensors refresh
        if self.data is not None:
            self.async_set_updated_data(self.data)

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

        # Reset watchdog timer
        self._device_online = True
        if self._offline_timer is not None:
            self._offline_timer()
        self._offline_timer = async_call_later(
            self.hass, DEVICE_TIMEOUT, self._mark_device_offline
        )

        data = self._parse_payload(payload)
        current_data: dict[str, Any] = {}
        if isinstance(self.data, dict):
            current_data = self.data

        updates = self._sanitize_updates(data, current_data)

        merged_data = dict(current_data)
        merged_data.update(updates)

        # Remove stale CAN values for ports that are now unavailable
        for port_id, available in self._can_port_available.items():
            if not available:
                prefix = f"can.{port_id}."
                for sig_key in list(merged_data):
                    if sig_key.startswith(prefix):
                        del merged_data[sig_key]

        self.async_set_updated_data(merged_data)

    @staticmethod
    def _is_valid_state_value(value: Any) -> bool:
        """Return whether a parsed value can be published as sensor state."""
        if value is None:
            return False
        if isinstance(value, float) and not math.isfinite(value):
            return False
        return isinstance(value, (str, int, float, bool))

    @staticmethod
    def _is_numeric_state_value(value: Any) -> bool:
        """Return whether a state value can be compared numerically."""
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return math.isfinite(float(value))
        return False

    def _resolve_state_class(self, signal_key: str) -> SensorStateClass | None:
        """Resolve and cache the state class for a signal key."""
        if signal_key in self._state_class_cache:
            return self._state_class_cache[signal_key]

        state_class: SensorStateClass | None = None

        if signal_key.startswith("internal.main."):
            json_key = signal_key.removeprefix("internal.main.")
            meta = KNOWN_INTERNAL_SENSORS.get(json_key)
            if meta is not None:
                state_class = meta.state_class
        elif signal_key.startswith("can."):
            parts = signal_key.split(".")
            if len(parts) >= 4:
                port_id = parts[1]
                runtime = self._can_runtime.get(port_id)
                if runtime is not None:
                    protocol, decoder = runtime
                    meta = protocol.resolve_signal_meta(signal_key, decoder)
                    state_class = meta.state_class

        self._state_class_cache[signal_key] = state_class
        return state_class

    def _is_erroneous_total_increasing_regression(
        self,
        signal_key: str,
        old_value: Any,
        new_value: Any,
    ) -> bool:
        """Return whether a small regression should be ignored for total_increasing."""
        if self._resolve_state_class(signal_key) != SensorStateClass.TOTAL_INCREASING:
            return False
        if not self._is_numeric_state_value(old_value):
            return False
        if not self._is_numeric_state_value(new_value):
            return False

        previous = float(old_value)
        current = float(new_value)
        if current >= previous:
            return False

        # Mirror HA meter-cycle tolerance: treat small drops as noisy regressions.
        if previous > 0 and current > previous * TOTAL_INCREASING_REGRESSION_TOLERANCE:
            _LOGGER.debug(
                "Ignoring small regression for total_increasing sensor %s: %s -> %s",
                signal_key,
                old_value,
                new_value,
            )
            return True
        return False

    def _sanitize_updates(
        self,
        updates: dict[str, Any],
        current_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Filter invalid values from a partial payload update."""
        sanitized: dict[str, Any] = {}
        for key, value in updates.items():
            if not self._is_valid_state_value(value):
                continue
            if key in current_data and self._is_erroneous_total_increasing_regression(
                key,
                current_data[key],
                value,
            ):
                continue
            sanitized[key] = value
        return sanitized

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
                runtime_result = protocol.decode_runtime(
                    value,
                    key,
                    self._selected,
                    decoder,
                )
                if len(runtime_result) == 3:
                    port_values, port_diag, port_has_valid_data = runtime_result
                else:
                    port_values, port_diag = runtime_result
                    port_has_valid_data = bool(port_values)
                data.update(port_values)
                self._can_port_available[key] = port_has_valid_data
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
    normalized_selected = normalize_selected_signals(entry.data)
    legacy_present = LEGACY_SELECTED_SENSORS_KEY in entry.data
    current_selected = entry.data.get(CONF_SELECTED_SIGNALS)
    if legacy_present or current_selected != normalized_selected:
        new_data = dict(entry.data)
        new_data[CONF_SELECTED_SIGNALS] = normalized_selected
        new_data.pop(LEGACY_SELECTED_SENSORS_KEY, None)
        hass.config_entries.async_update_entry(entry, data=new_data)

    available_profiles = await hass.async_add_executor_job(
        discover_profiles, Path(__file__).parent / CAN_PROFILE_DIR
    )
    coordinator = SenquipDataCoordinator(hass, entry, available_profiles)
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

