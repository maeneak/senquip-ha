"""Config flow for Senquip Telemetry integration."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .can_profiles.loader import CANProfile, discover_profiles
from .can_protocols.registry import get_can_protocol, list_can_protocol_options
from .const import (
    CAN_PORTS,
    CAN_PROFILE_DIR,
    CAN_PROTOCOL_J1939,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_MQTT_TOPIC,
    CONF_PORT_CONFIGS,
    CONF_SELECTED_SIGNALS,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    KNOWN_INTERNAL_SENSORS,
    KNOWN_PORT_FAMILIES,
    PortConfig,
    build_default_port_configs,
    deserialize_port_configs,
    serialize_port_configs,
)
from .signal_keys import normalize_selected_signals

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required("device_name"): str,
        vol.Required("mqtt_topic"): str,
    }
)


@dataclass
class DiscoveredSignal:
    """A signal discovered during MQTT discovery."""

    key: str
    name: str
    sample_value: Any
    unit: str | None
    default_selected: bool


@dataclass
class DiscoveredPort:
    """Active/inactive state for a known Senquip port."""

    port_id: str
    family: str
    active: bool


def _profile_dir() -> Path:
    return Path(__file__).parent / CAN_PROFILE_DIR


def _detect_active_ports(payload: dict[str, Any]) -> dict[str, bool]:
    active = {port_id: False for port_id in KNOWN_PORT_FAMILIES}

    for key, value in payload.items():
        if key in ("deviceid", "ts", "time"):
            continue

        if key in CAN_PORTS and isinstance(value, list):
            active[key] = True
            continue

        if isinstance(value, (int, float, str)):
            active["internal"] = True
            if key.startswith("gps_") or key in ("lat", "lon", "latitude", "longitude"):
                active["gps"] = True
            if key.startswith("ble"):
                active["ble"] = True
            if key.startswith("serial1"):
                active["serial1"] = True
            if key.startswith("input1"):
                active["input1"] = True
            if key.startswith("input2"):
                active["input2"] = True
            if key.startswith("output1"):
                active["output1"] = True
            if key.startswith("current1"):
                active["current1"] = True
            if key.startswith("current2"):
                active["current2"] = True
            continue

        if key in active:
            active[key] = True

    return active


def _build_decoder_for_port(
    port_config: PortConfig,
    available_profiles: dict[str, CANProfile],
) -> tuple[Any, Any, list[str]] | None:
    if port_config.protocol is None:
        return None
    protocol = get_can_protocol(port_config.protocol)
    if protocol is None:
        return None
    selected_profiles: list[CANProfile] = []
    for profile_name in port_config.profiles:
        profile = available_profiles.get(profile_name)
        if profile is None:
            continue
        if profile.base_protocol != port_config.protocol:
            continue
        selected_profiles.append(profile)
    decoder, errors = protocol.build_decoder(selected_profiles)
    return protocol, decoder, errors


def _classify_payload(
    payload: dict[str, Any],
    port_configs: dict[str, PortConfig],
    available_profiles: dict[str, CANProfile] | None = None,
) -> tuple[dict[str, list[DiscoveredSignal]], set[str]]:
    """Classify payload fields into discoverable signal categories."""
    available_profiles = available_profiles or {}
    discovered: dict[str, list[DiscoveredSignal]] = {}
    active_can_ports: set[str] = set()

    for key, value in payload.items():
        if key in ("deviceid", "ts", "time"):
            continue

        if key in CAN_PORTS and isinstance(value, list):
            config = port_configs.get(key)
            if config is None or not config.active:
                continue
            protocol_decoder = _build_decoder_for_port(config, available_profiles)
            if protocol_decoder is None:
                continue
            protocol, decoder, profile_errors = protocol_decoder
            for err_msg in profile_errors:
                _LOGGER.warning("Port %s: %s", key, err_msg)
            signals = protocol.discover_signals(value, key, decoder)
            discovered[key.upper()] = [
                DiscoveredSignal(
                    key=signal.key,
                    name=signal.name,
                    sample_value=signal.sample_value,
                    unit=signal.unit,
                    default_selected=signal.default_selected,
                )
                for signal in signals
            ]
            active_can_ports.add(key)
            continue

        if key == "events" and isinstance(value, list):
            sample_msg = ""
            if value:
                last_event = value[-1]
                if isinstance(last_event, dict):
                    sample_msg = last_event.get("msg", "")
            discovered["Events"] = [
                DiscoveredSignal(
                    key="event.main.last",
                    name="Last Event",
                    sample_value=sample_msg,
                    unit=None,
                    default_selected=True,
                )
            ]
            continue

        if isinstance(value, (int, float, str)):
            meta = KNOWN_INTERNAL_SENSORS.get(key)
            name = meta.name if meta else key.replace("_", " ").title()
            unit = meta.unit if meta else None
            discovered.setdefault("Internal", []).append(
                DiscoveredSignal(
                    key=f"internal.main.{key}",
                    name=name,
                    sample_value=value,
                    unit=unit,
                    default_selected=True,
                )
            )

    return discovered, active_can_ports


class SenquipConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Senquip Telemetry."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "SenquipOptionsFlow":
        return SenquipOptionsFlow(config_entry)

    def __init__(self) -> None:
        self._device_name = ""
        self._mqtt_topic = ""
        self._device_id = ""
        self._device_payload: dict[str, Any] | None = None
        self._discovered_signals: dict[str, list[DiscoveredSignal]] = {}
        self._discovered_ports: dict[str, DiscoveredPort] = {}
        self._available_profiles: dict[str, CANProfile] = {}
        self._port_configs = build_default_port_configs()
        self._discovery_task: asyncio.Task | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._device_name = user_input["device_name"]
            self._mqtt_topic = user_input["mqtt_topic"]
            if not self._mqtt_topic.strip():
                errors["mqtt_topic"] = "invalid_topic"
            else:
                return await self.async_step_discover()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                self._async_discover(),
                "Senquip MQTT discovery",
            )

        if not self._discovery_task.done():
            return self.async_show_progress(
                step_id="discover",
                progress_action="discovering",
                progress_task=self._discovery_task,
            )

        try:
            await self._discovery_task
        except (TimeoutError, Exception):
            _LOGGER.exception("Discovery failed")
            self._discovery_task = None
            return self.async_show_progress_done(next_step_id="discovery_failed")

        self._discovery_task = None
        return self.async_show_progress_done(next_step_id="configure_ports")

    async def async_step_discovery_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._discovery_task = None
            return await self.async_step_discover()
        return self.async_show_form(step_id="discovery_failed")

    async def async_step_configure_ports(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        active_can_ports = [
            port_id
            for port_id in CAN_PORTS
            if self._port_configs.get(port_id, PortConfig("", False)).active
        ]
        if not active_can_ports:
            if self._device_payload is not None and not self._discovered_signals:
                self._discovered_signals, _ = _classify_payload(
                    self._device_payload,
                    self._port_configs,
                    self._available_profiles,
                )
            return await self.async_step_select_signals()

        if not self._available_profiles:
            self._available_profiles = await self.hass.async_add_executor_job(
                discover_profiles, _profile_dir()
            )

        if user_input is not None:
            for port in active_can_ports:
                protocol = str(user_input.get(f"protocol_{port}", CAN_PROTOCOL_J1939))
                raw_profiles = user_input.get(f"profiles_{port}", [])
                selected_profiles = raw_profiles if isinstance(raw_profiles, list) else []
                allowed_profiles = {
                    profile_name
                    for profile_name, profile in self._available_profiles.items()
                    if profile.base_protocol == protocol
                }
                filtered_profiles = tuple(
                    profile for profile in selected_profiles if profile in allowed_profiles
                )
                self._port_configs[port] = PortConfig(
                    family="can",
                    active=True,
                    protocol=protocol,
                    profiles=filtered_profiles,
                )

            if self._device_payload is not None:
                self._discovered_signals, _ = _classify_payload(
                    self._device_payload,
                    self._port_configs,
                    self._available_profiles,
                )
            return await self.async_step_select_signals()

        protocol_options = [
            SelectOptionDict(value=protocol_id, label=label)
            for protocol_id, label in list_can_protocol_options()
        ]

        protocol_display = dict(list_can_protocol_options())
        all_profile_options = [
            SelectOptionDict(
                value=filename,
                label=f"{profile.name} ({protocol_display.get(profile.base_protocol, profile.base_protocol)})",
            )
            for filename, profile in sorted(
                self._available_profiles.items(),
                key=lambda item: item[1].name.lower(),
            )
        ]
        all_profile_filenames = {opt["value"] for opt in all_profile_options}

        schema_dict: dict[Any, Any] = {}

        for port in active_can_ports:
            config = self._port_configs[port]
            protocol_id = config.protocol or CAN_PROTOCOL_J1939
            schema_dict[vol.Required(f"protocol_{port}", default=protocol_id)] = SelectSelector(
                SelectSelectorConfig(
                    options=protocol_options,
                    multiple=False,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

            current_profiles = [
                profile_name
                for profile_name in config.profiles
                if profile_name in all_profile_filenames
            ]
            schema_dict[vol.Optional(f"profiles_{port}", default=current_profiles)] = SelectSelector(
                SelectSelectorConfig(
                    options=all_profile_options,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )

        return self.async_show_form(
            step_id="configure_ports",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_select_signals(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            selected = user_input.get("selected_signals", [])
            return self.async_create_entry(
                title=self._device_name,
                data={
                    CONF_MQTT_TOPIC: self._mqtt_topic,
                    CONF_DEVICE_ID: self._device_id,
                    CONF_DEVICE_NAME: self._device_name,
                    CONF_SELECTED_SIGNALS: selected,
                    CONF_PORT_CONFIGS: serialize_port_configs(self._port_configs),
                },
            )

        options: list[SelectOptionDict] = []
        defaults: list[str] = []
        for category, signals in self._discovered_signals.items():
            for signal in signals:
                sample = signal.sample_value
                if sample is not None and signal.unit:
                    label = f"{category}: {signal.name} ({sample} {signal.unit})"
                elif sample is not None:
                    label = f"{category}: {signal.name} ({sample})"
                else:
                    label = f"{category}: {signal.name}"
                options.append(SelectOptionDict(value=signal.key, label=label))
                if signal.default_selected:
                    defaults.append(signal.key)

        total_count = sum(len(items) for items in self._discovered_signals.values())
        schema = vol.Schema(
            {
                vol.Required("selected_signals", default=defaults): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="select_signals",
            data_schema=schema,
            description_placeholders={
                "signal_count": str(total_count),
                "device_id": self._device_id,
            },
        )

    async def _async_discover(self) -> None:
        received = asyncio.Event()
        payload_holder: dict[str, Any] = {}

        @callback
        def on_message(msg: mqtt.models.ReceiveMessage) -> None:
            try:
                payload_holder["data"] = json.loads(msg.payload)
                received.set()
            except (json.JSONDecodeError, ValueError):
                _LOGGER.debug("Non-JSON message on %s during discovery", msg.topic)

        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            raise RuntimeError("MQTT client not available")

        unsub = await mqtt.async_subscribe(self.hass, self._mqtt_topic, on_message, qos=0)
        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                await received.wait()
        finally:
            unsub()

        raw_payload = payload_holder["data"]
        if isinstance(raw_payload, list):
            if not raw_payload:
                raise RuntimeError("Empty array received")
            device_payload = raw_payload[0]
        else:
            device_payload = raw_payload
        if not isinstance(device_payload, dict):
            raise RuntimeError("Unexpected payload format")

        self._device_id = str(device_payload.get("deviceid", "unknown"))
        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured()

        self._device_payload = device_payload
        active_ports = _detect_active_ports(device_payload)
        self._port_configs = build_default_port_configs(active_ports)
        self._discovered_ports = {
            port_id: DiscoveredPort(
                port_id=port_id,
                family=config.family,
                active=config.active,
            )
            for port_id, config in self._port_configs.items()
        }
        self._discovered_signals, _ = _classify_payload(device_payload, self._port_configs, {})


class SenquipOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Senquip Telemetry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._device_payload: dict[str, Any] | None = None
        self._device_id = str(config_entry.data.get(CONF_DEVICE_ID, "unknown"))
        self._discovered_signals: dict[str, list[DiscoveredSignal]] = {}
        self._available_profiles: dict[str, CANProfile] = {}
        self._port_configs = deserialize_port_configs(config_entry.data.get(CONF_PORT_CONFIGS))
        self._discovery_task: asyncio.Task | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_discover()

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                self._async_discover(),
                "Senquip MQTT options discovery",
            )

        if not self._discovery_task.done():
            return self.async_show_progress(
                step_id="discover",
                progress_action="discovering",
                progress_task=self._discovery_task,
            )

        try:
            await self._discovery_task
        except (TimeoutError, Exception):
            _LOGGER.exception("Options discovery failed")
            self._discovery_task = None
            return self.async_show_progress_done(next_step_id="discovery_failed")

        self._discovery_task = None
        return self.async_show_progress_done(next_step_id="configure_ports")

    async def async_step_discovery_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._discovery_task = None
            return await self.async_step_discover()
        return self.async_show_form(step_id="discovery_failed")

    async def async_step_configure_ports(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        active_can_ports = [
            port_id
            for port_id in CAN_PORTS
            if self._port_configs.get(port_id, PortConfig("", False)).active
        ]

        if not active_can_ports:
            return await self.async_step_select_signals()

        if not self._available_profiles:
            self._available_profiles = await self.hass.async_add_executor_job(
                discover_profiles, _profile_dir()
            )

        if user_input is not None:
            for port in active_can_ports:
                protocol = str(user_input.get(f"protocol_{port}", CAN_PROTOCOL_J1939))
                raw_profiles = user_input.get(f"profiles_{port}", [])
                selected_profiles = raw_profiles if isinstance(raw_profiles, list) else []
                allowed_profiles = {
                    profile_name
                    for profile_name, profile in self._available_profiles.items()
                    if profile.base_protocol == protocol
                }
                self._port_configs[port] = PortConfig(
                    family="can",
                    active=True,
                    protocol=protocol,
                    profiles=tuple(profile for profile in selected_profiles if profile in allowed_profiles),
                )

            if self._device_payload is not None:
                self._discovered_signals, _ = _classify_payload(
                    self._device_payload,
                    self._port_configs,
                    self._available_profiles,
                )
            return await self.async_step_select_signals()

        protocol_options = [
            SelectOptionDict(value=protocol_id, label=label)
            for protocol_id, label in list_can_protocol_options()
        ]

        protocol_display = dict(list_can_protocol_options())
        all_profile_options = [
            SelectOptionDict(
                value=filename,
                label=f"{profile.name} ({protocol_display.get(profile.base_protocol, profile.base_protocol)})",
            )
            for filename, profile in sorted(
                self._available_profiles.items(),
                key=lambda item: item[1].name.lower(),
            )
        ]
        all_profile_filenames = {opt["value"] for opt in all_profile_options}

        schema_dict: dict[Any, Any] = {}
        for port in active_can_ports:
            config = self._port_configs[port]
            protocol_id = config.protocol or CAN_PROTOCOL_J1939
            schema_dict[vol.Required(f"protocol_{port}", default=protocol_id)] = SelectSelector(
                SelectSelectorConfig(
                    options=protocol_options,
                    multiple=False,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
            current_profiles = [
                profile_name
                for profile_name in config.profiles
                if profile_name in all_profile_filenames
            ]
            schema_dict[vol.Optional(f"profiles_{port}", default=current_profiles)] = SelectSelector(
                SelectSelectorConfig(
                    options=all_profile_options,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )

        return self.async_show_form(
            step_id="configure_ports",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_select_signals(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            selected = user_input.get("selected_signals", [])
            new_data = {
                **self._config_entry.data,
                CONF_SELECTED_SIGNALS: selected,
                CONF_PORT_CONFIGS: serialize_port_configs(self._port_configs),
            }
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        current_selected = set(normalize_selected_signals(self._config_entry.data))
        options: list[SelectOptionDict] = []
        defaults: list[str] = []
        for category, signals in self._discovered_signals.items():
            for signal in signals:
                sample = signal.sample_value
                if sample is not None and signal.unit:
                    label = f"{category}: {signal.name} ({sample} {signal.unit})"
                elif sample is not None:
                    label = f"{category}: {signal.name} ({sample})"
                else:
                    label = f"{category}: {signal.name}"
                options.append(SelectOptionDict(value=signal.key, label=label))
                if signal.key in current_selected or (
                    not current_selected and signal.default_selected
                ):
                    defaults.append(signal.key)

        total_count = sum(len(items) for items in self._discovered_signals.values())
        schema = vol.Schema(
            {
                vol.Required("selected_signals", default=defaults): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="select_signals",
            data_schema=schema,
            description_placeholders={
                "signal_count": str(total_count),
                "device_id": self._device_id,
            },
        )

    async def _async_discover(self) -> None:
        received = asyncio.Event()
        payload_holder: dict[str, Any] = {}
        mqtt_topic = self._config_entry.data[CONF_MQTT_TOPIC]

        @callback
        def on_message(msg: mqtt.models.ReceiveMessage) -> None:
            try:
                payload_holder["data"] = json.loads(msg.payload)
                received.set()
            except (json.JSONDecodeError, ValueError):
                pass

        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            raise RuntimeError("MQTT client not available")

        unsub = await mqtt.async_subscribe(self.hass, mqtt_topic, on_message, qos=0)
        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                await received.wait()
        finally:
            unsub()

        raw_payload = payload_holder["data"]
        if isinstance(raw_payload, list):
            if not raw_payload:
                raise RuntimeError("Empty array received")
            device_payload = None
            for item in raw_payload:
                if isinstance(item, dict) and item.get("deviceid") == self._device_id:
                    device_payload = item
                    break
            if device_payload is None:
                device_payload = raw_payload[0]
        else:
            device_payload = raw_payload
        if not isinstance(device_payload, dict):
            raise RuntimeError("Unexpected payload format")

        self._device_payload = device_payload
        active_ports = _detect_active_ports(device_payload)
        for port_id, config in list(self._port_configs.items()):
            self._port_configs[port_id] = PortConfig(
                family=config.family,
                active=active_ports.get(port_id, config.active),
                protocol=config.protocol,
                profiles=config.profiles,
            )
        self._discovered_signals, _ = _classify_payload(device_payload, self._port_configs, {})

