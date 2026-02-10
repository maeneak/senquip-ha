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

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_J1939_PROFILES,
    CONF_MQTT_TOPIC,
    CONF_SELECTED_SENSORS,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    KNOWN_INTERNAL_SENSORS,
)
from .j1939_database import PGN_DATABASE, SPN_DATABASE
from .j1939_decoder import DM1_PGN, J1939Decoder
from .j1939_profile_loader import discover_profiles, merge_databases

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required("device_name"): str,
        vol.Required("mqtt_topic"): str,
    }
)


@dataclass
class DiscoveredSensor:
    """A sensor discovered during MQTT discovery."""

    key: str
    name: str
    sample_value: Any
    unit: str | None
    default_selected: bool


class SenquipConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Senquip Telemetry."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SenquipOptionsFlow:
        """Get the options flow for this handler."""
        return SenquipOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._device_name: str = ""
        self._mqtt_topic: str = ""
        self._device_id: str = ""
        self._device_payload: dict[str, Any] | None = None
        self._discovered_sensors: dict[str, list[DiscoveredSensor]] = {}
        self._available_profiles: dict[str, str] = {}
        self._selected_profiles: dict[str, list[str]] = {}  # Per-port profiles
        self._active_ports: set[str] = set()  # Track which CAN ports have frames
        self._discovery_task: asyncio.Task | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Collect device name and MQTT topic."""
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
        """Step 2: Subscribe to MQTT and discover sensors."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                self._async_discover_sensors(),
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
        return self.async_show_progress_done(next_step_id="select_profiles")

    async def async_step_discovery_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle discovery failure — offer retry."""
        if user_input is not None:
            # User clicked submit to retry
            self._discovery_task = None
            return await self.async_step_discover()

        return self.async_show_form(step_id="discovery_failed")

    async def async_step_select_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Select optional J1939 profile overrides per CAN port."""
        if user_input is not None:
            # Store per-port profile selections
            self._selected_profiles = {}
            for port in self._active_ports:
                key = f"profiles_{port}"
                self._selected_profiles[port] = user_input.get(key, [])

            # Rebuild sensors with per-port profiles
            if self._device_payload is not None:
                self._discovered_sensors, _ = _classify_payload_with_profiles(
                    self._device_payload,
                    self._selected_profiles,
                )
            return await self.async_step_select_sensors()

        custom_dir = Path(__file__).parent / "j1939_custom"
        self._available_profiles = discover_profiles(custom_dir)

        if not self._available_profiles:
            # No profiles available, skip to sensor selection
            self._selected_profiles = {port: [] for port in self._active_ports}
            if self._device_payload is not None and not self._discovered_sensors:
                self._discovered_sensors, _ = _classify_payload_with_profiles(
                    self._device_payload,
                    self._selected_profiles,
                )
            return await self.async_step_select_sensors()

        # Build schema with one multi-select per active port
        options = [
            SelectOptionDict(value=filename, label=display_name)
            for filename, display_name in sorted(
                self._available_profiles.items(), key=lambda item: item[1].lower()
            )
        ]

        schema_dict = {}
        for port in sorted(self._active_ports):
            port_label = port.upper().replace("CAN", "CAN ")
            schema_dict[vol.Optional(f"profiles_{port}", default=[])] = SelectSelector(
                SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )

        return self.async_show_form(
            step_id="select_profiles",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_select_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Present discovered sensors for user selection."""
        if user_input is not None:
            selected = user_input.get("selected_sensors", [])
            return self.async_create_entry(
                title=self._device_name,
                data={
                    CONF_MQTT_TOPIC: self._mqtt_topic,
                    CONF_DEVICE_ID: self._device_id,
                    CONF_DEVICE_NAME: self._device_name,
                    CONF_SELECTED_SENSORS: selected,
                    CONF_J1939_PROFILES: self._selected_profiles,
                },
            )

        # Build option list from discovered sensors
        options: list[SelectOptionDict] = []
        defaults: list[str] = []

        for category, sensors in self._discovered_sensors.items():
            for sensor in sensors:
                sample = sensor.sample_value
                if sample is not None and sensor.unit:
                    label = f"{category}: {sensor.name} ({sample} {sensor.unit})"
                elif sample is not None:
                    label = f"{category}: {sensor.name} ({sample})"
                else:
                    label = f"{category}: {sensor.name}"

                options.append(SelectOptionDict(value=sensor.key, label=label))

                if sensor.default_selected:
                    defaults.append(sensor.key)

        total_count = sum(len(s) for s in self._discovered_sensors.values())

        schema = vol.Schema(
            {
                vol.Required("selected_sensors", default=defaults): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="select_sensors",
            data_schema=schema,
            description_placeholders={
                "sensor_count": str(total_count),
                "device_id": self._device_id,
            },
        )

    async def _async_discover_sensors(self) -> None:
        """Subscribe to MQTT topic and classify the first received message."""
        received = asyncio.Event()
        payload_holder: dict[str, Any] = {}

        @callback
        def on_message(msg: mqtt.models.ReceiveMessage) -> None:
            """Handle incoming discovery message."""
            try:
                data = json.loads(msg.payload)
                payload_holder["data"] = data
                received.set()
            except (json.JSONDecodeError, ValueError):
                _LOGGER.debug("Non-JSON message on %s during discovery", msg.topic)

        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            raise RuntimeError("MQTT client not available")

        unsub = await mqtt.async_subscribe(
            self.hass, self._mqtt_topic, on_message, qos=0
        )

        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                await received.wait()
        finally:
            unsub()

        raw_payload = payload_holder["data"]

        # Handle array payloads
        if isinstance(raw_payload, list):
            if not raw_payload:
                raise RuntimeError("Empty array received")
            device_payload = raw_payload[0]
        else:
            device_payload = raw_payload

        if not isinstance(device_payload, dict):
            raise RuntimeError("Unexpected payload format")

        self._device_id = str(device_payload.get("deviceid", "unknown"))

        # Prevent duplicate device entries
        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured()

        # Classify all fields and track active ports
        self._device_payload = device_payload
        self._discovered_sensors, self._active_ports = _classify_payload(device_payload)


def _build_profile_decoder(profile_names: list[str]) -> J1939Decoder:
    """Return a decoder using the selected profile overrides."""
    if not profile_names:
        return J1939Decoder()

    custom_dir = Path(__file__).parent / "j1939_custom"
    profile_paths = [custom_dir / name for name in profile_names]
    pgn_db, spn_db, dm1_config = merge_databases(
        PGN_DATABASE, SPN_DATABASE, profile_paths
    )
    return J1939Decoder(pgn_db, spn_db, dm1_config)


def _classify_payload_with_profiles(
    payload: dict[str, Any],
    profiles_per_port: dict[str, list[str]],
) -> tuple[dict[str, list[DiscoveredSensor]], set[str]]:
    """Classify payload with per-port profile support.

    Args:
        payload: The MQTT payload to classify
        profiles_per_port: Dict mapping port names to list of profile filenames

    Returns:
        Tuple of (discovered sensors dict, active ports set)
    """
    discovered: dict[str, list[DiscoveredSensor]] = {}
    active_ports: set[str] = set()

    # Build per-port decoders
    port_decoders: dict[str, J1939Decoder] = {}
    for port, profile_names in profiles_per_port.items():
        port_decoders[port] = _build_profile_decoder(profile_names)

    # Process each CAN port with its own decoder
    for key, value in payload.items():
        # Skip metadata
        if key in ("deviceid", "ts", "time"):
            continue

        # CAN ports
        if key in ("can1", "can2") and isinstance(value, list):
            active_ports.add(key)
            decoder = port_decoders.get(key, J1939Decoder())
            category = key.upper()
            sensors: list[DiscoveredSensor] = []
            seen_spns: set[int] = set()

            # Iterate frames and decode with port-specific decoder
            for frame in value:
                can_id = frame.get("id")
                hex_data = frame.get("data")
                if can_id is None or hex_data is None:
                    continue

                _, pgn, _ = decoder.extract_pgn(can_id)
                pgn_def = decoder.get_pgn_info(can_id)

                # Skip DM1 frames (will be added separately below)
                if pgn == DM1_PGN:
                    continue

                # Decode normal frames using port-specific decoder
                decoded = decoder.decode_frame(can_id, hex_data)

                if decoded:
                    for spn_num, spn_value in decoded.items():
                        if spn_num in seen_spns:
                            continue
                        seen_spns.add(spn_num)
                        spn_def = decoder._spn_db.get(spn_num)
                        acronym = pgn_def.acronym if pgn_def else ""
                        sensors.append(
                            DiscoveredSensor(
                                key=f"{key}.spn{spn_num}",
                                name=f"{spn_def.name} — {acronym}" if spn_def else f"SPN {spn_num}",
                                sample_value=spn_value,
                                unit=spn_def.unit if spn_def else None,
                                default_selected=spn_value is not None,
                            )
                        )
                else:
                    # Unknown PGN
                    sensors.append(
                        DiscoveredSensor(
                            key=f"{key}.raw.{pgn}",
                            name=f"Unknown PGN {pgn} (0x{pgn:04X})",
                            sample_value=hex_data[:16] + ("..." if len(hex_data) > 16 else ""),
                            unit=None,
                            default_selected=False,
                        )
                    )

            # Always add DM1 sensors (Option 3)
            dm1_sensors = [
                DiscoveredSensor(
                    key=f"{key}.dm1.active_fault",
                    name="DM1 Active Fault",
                    sample_value="No Active Fault",
                    unit=None,
                    default_selected=True,
                ),
                DiscoveredSensor(
                    key=f"{key}.dm1.protect_lamp",
                    name="DM1 Protect Lamp",
                    sample_value="Off",
                    unit=None,
                    default_selected=True,
                ),
                DiscoveredSensor(
                    key=f"{key}.dm1.amber_warning",
                    name="DM1 Amber Warning",
                    sample_value="Off",
                    unit=None,
                    default_selected=True,
                ),
                DiscoveredSensor(
                    key=f"{key}.dm1.red_stop",
                    name="DM1 Red Stop",
                    sample_value="Off",
                    unit=None,
                    default_selected=True,
                ),
                DiscoveredSensor(
                    key=f"{key}.dm1.mil",
                    name="DM1 MIL Lamp",
                    sample_value="Off",
                    unit=None,
                    default_selected=False,
                ),
                DiscoveredSensor(
                    key=f"{key}.dm1.active_spn",
                    name="DM1 Active SPN",
                    sample_value=0,
                    unit=None,
                    default_selected=False,
                ),
                DiscoveredSensor(
                    key=f"{key}.dm1.active_fmi",
                    name="DM1 Active FMI",
                    sample_value=0,
                    unit=None,
                    default_selected=False,
                ),
                DiscoveredSensor(
                    key=f"{key}.dm1.occurrence_count",
                    name="DM1 Occurrence Count",
                    sample_value=0,
                    unit=None,
                    default_selected=False,
                ),
            ]
            sensors.extend(dm1_sensors)

            discovered[category] = sensors

        # Events
        elif key == "events" and isinstance(value, list):
            sample_msg = ""
            if value and isinstance(value[0], dict):
                sample_msg = value[0].get("msg", "")
            discovered["Events"] = [
                DiscoveredSensor(
                    key="events.last",
                    name="Last Event",
                    sample_value=sample_msg,
                    unit=None,
                    default_selected=True,
                )
            ]

        # Internal sensors
        elif isinstance(value, (int, float, str)):
            meta = KNOWN_INTERNAL_SENSORS.get(key)
            name = meta.name if meta else key.replace("_", " ").title()
            unit = meta.unit if meta else None
            discovered.setdefault("Internal", []).append(
                DiscoveredSensor(
                    key=f"internal.{key}",
                    name=name,
                    sample_value=value,
                    unit=unit,
                    default_selected=True,
                )
            )

    return discovered, active_ports


def _classify_payload(
    payload: dict[str, Any],
    decoder: J1939Decoder | None = None,
) -> tuple[dict[str, list[DiscoveredSensor]], set[str]]:
    """Classify all payload fields into sensor categories.

    Returns:
        Tuple of (discovered sensors dict, active ports set)
    """
    result: dict[str, list[DiscoveredSensor]] = {}
    active_ports: set[str] = set()
    if decoder is None:
        decoder = J1939Decoder()

    for key, value in payload.items():
        # Skip metadata
        if key in ("deviceid", "ts", "time"):
            continue

        # CAN ports
        if key in ("can1", "can2") and isinstance(value, list):
            active_ports.add(key)  # Track this port as active
            category = key.upper()
            sensors: list[DiscoveredSensor] = []
            seen_spns: set[int] = set()
            has_dm1 = False

            for frame in value:
                can_id = frame.get("id")
                hex_data = frame.get("data")
                if can_id is None or hex_data is None:
                    continue

                _, pgn, _ = decoder.extract_pgn(can_id)

                # DM1 frame — flag for DM1 sensor discovery
                if pgn == DM1_PGN:
                    has_dm1 = True
                    continue

                decoded = decoder.decode_frame(can_id, hex_data)
                pgn_info = decoder.get_pgn_info(can_id)

                if decoded:
                    for spn_num, spn_value in decoded.items():
                        if spn_num in seen_spns:
                            continue
                        seen_spns.add(spn_num)

                        spn_def = decoder.get_spn_def(spn_num)
                        if spn_def is None:
                            continue

                        acronym = pgn_info.acronym if pgn_info else "?"
                        sensors.append(
                            DiscoveredSensor(
                                key=f"{key}.spn{spn_num}",
                                name=f"{spn_def.name} — {acronym}",
                                sample_value=spn_value,
                                unit=spn_def.unit,
                                default_selected=spn_value is not None,
                            )
                        )
                else:
                    # Unknown PGN
                    sensors.append(
                        DiscoveredSensor(
                            key=f"{key}.raw.{pgn}",
                            name=f"Unknown PGN {pgn} (0x{pgn:04X})",
                            sample_value=hex_data[:16]
                            + ("..." if len(hex_data) > 16 else ""),
                            unit=None,
                            default_selected=False,
                        )
                    )

            # Always add DM1 sensors for fault monitoring (Option 3)
            # DM1 frames may not be broadcast during discovery but will appear during faults
            dm1_sensors = [
                    DiscoveredSensor(
                        key=f"{key}.dm1.active_fault",
                        name="DM1 Active Fault",
                        sample_value="No Active Fault",
                        unit=None,
                        default_selected=True,
                    ),
                    DiscoveredSensor(
                        key=f"{key}.dm1.protect_lamp",
                        name="DM1 Protect Lamp",
                        sample_value="Off",
                        unit=None,
                        default_selected=True,
                    ),
                    DiscoveredSensor(
                        key=f"{key}.dm1.amber_warning",
                        name="DM1 Amber Warning",
                        sample_value="Off",
                        unit=None,
                        default_selected=True,
                    ),
                    DiscoveredSensor(
                        key=f"{key}.dm1.red_stop",
                        name="DM1 Red Stop",
                        sample_value="Off",
                        unit=None,
                        default_selected=True,
                    ),
                    DiscoveredSensor(
                        key=f"{key}.dm1.mil",
                        name="DM1 MIL Lamp",
                        sample_value="Off",
                        unit=None,
                        default_selected=False,
                    ),
                    DiscoveredSensor(
                        key=f"{key}.dm1.active_spn",
                        name="DM1 Active SPN",
                        sample_value=0,
                        unit=None,
                        default_selected=False,
                    ),
                    DiscoveredSensor(
                        key=f"{key}.dm1.active_fmi",
                        name="DM1 Active FMI",
                        sample_value=0,
                        unit=None,
                        default_selected=False,
                    ),
                    DiscoveredSensor(
                        key=f"{key}.dm1.occurrence_count",
                        name="DM1 Occurrence Count",
                        sample_value=0,
                        unit=None,
                        default_selected=False,
                    ),
                ]
            sensors.extend(dm1_sensors)

            if sensors:
                result[category] = sensors

        # Events
        elif key == "events" and isinstance(value, list):
            sample_msg = ""
            if value and isinstance(value[0], dict):
                sample_msg = value[0].get("msg", "")
            result["Events"] = [
                DiscoveredSensor(
                    key="events.last",
                    name="Last Event",
                    sample_value=sample_msg,
                    unit=None,
                    default_selected=True,
                )
            ]

        # Internal sensors
        elif isinstance(value, (int, float, str)):
            meta = KNOWN_INTERNAL_SENSORS.get(key)
            name = meta.name if meta else key.replace("_", " ").title()
            unit = meta.unit if meta else None
            result.setdefault("Internal", []).append(
                DiscoveredSensor(
                    key=f"internal.{key}",
                    name=name,
                    sample_value=value,
                    unit=unit,
                    default_selected=True,
                )
            )

    return result, active_ports


class SenquipOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Senquip Telemetry (re-discover & re-select sensors)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._device_payload: dict[str, Any] | None = None
        self._discovered_sensors: dict[str, list[DiscoveredSensor]] = {}
        self._available_profiles: dict[str, str] = {}
        # Load existing per-port profiles (dict format)
        profiles_config = config_entry.data.get(CONF_J1939_PROFILES, {})
        self._selected_profiles: dict[str, list[str]] = profiles_config if isinstance(profiles_config, dict) else {}
        self._active_ports: set[str] = set()
        self._discovery_task: asyncio.Task | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start the options flow — trigger MQTT discovery."""
        return await self.async_step_discover()

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Subscribe to MQTT and re-discover sensors."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(
                self._async_discover_sensors(),
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
        return self.async_show_progress_done(next_step_id="select_profiles")

    async def async_step_discovery_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle discovery failure — offer retry."""
        if user_input is not None:
            self._discovery_task = None
            return await self.async_step_discover()

        return self.async_show_form(step_id="discovery_failed")

    async def async_step_select_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select J1939 profile overrides per CAN port for options flow."""
        if user_input is not None:
            # Store per-port profile selections
            self._selected_profiles = {}
            for port in self._active_ports:
                key = f"profiles_{port}"
                self._selected_profiles[port] = user_input.get(key, [])

            # Rebuild sensors with per-port profiles
            if self._device_payload is not None:
                self._discovered_sensors, _ = _classify_payload_with_profiles(
                    self._device_payload,
                    self._selected_profiles,
                )
            return await self.async_step_select_sensors()

        custom_dir = Path(__file__).parent / "j1939_custom"
        self._available_profiles = discover_profiles(custom_dir)

        if not self._available_profiles:
            # No profiles available, skip to sensor selection
            self._selected_profiles = {port: [] for port in self._active_ports}
            if self._device_payload is not None and not self._discovered_sensors:
                self._discovered_sensors, _ = _classify_payload_with_profiles(
                    self._device_payload,
                    self._selected_profiles,
                )
            return await self.async_step_select_sensors()

        # Build schema with one multi-select per active port
        options = [
            SelectOptionDict(value=filename, label=display_name)
            for filename, display_name in sorted(
                self._available_profiles.items(), key=lambda item: item[1].lower()
            )
        ]

        schema_dict = {}
        for port in sorted(self._active_ports):
            port_label = port.upper().replace("CAN", "CAN ")
            current_profiles = self._selected_profiles.get(port, [])
            schema_dict[vol.Optional(f"profiles_{port}", default=current_profiles)] = SelectSelector(
                SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )

        return self.async_show_form(
            step_id="select_profiles",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_select_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Present discovered sensors for user re-selection."""
        if user_input is not None:
            selected = user_input.get("selected_sensors", [])
            # Update config entry data with new sensor selection
            new_data = {
                **self._config_entry.data,
                CONF_SELECTED_SENSORS: selected,
                CONF_J1939_PROFILES: self._selected_profiles,
            }
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            # Signal reload so entities are re-created
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        # Build option list from discovered sensors
        current_selected = set(self._config_entry.data.get(CONF_SELECTED_SENSORS, []))
        options: list[SelectOptionDict] = []
        defaults: list[str] = []

        for category, sensors in self._discovered_sensors.items():
            for sensor in sensors:
                sample = sensor.sample_value
                if sample is not None and sensor.unit:
                    label = f"{category}: {sensor.name} ({sample} {sensor.unit})"
                elif sample is not None:
                    label = f"{category}: {sensor.name} ({sample})"
                else:
                    label = f"{category}: {sensor.name}"

                options.append(SelectOptionDict(value=sensor.key, label=label))

                # Default to currently-selected sensors, falling back to discovery defaults
                if sensor.key in current_selected or (
                    not current_selected and sensor.default_selected
                ):
                    defaults.append(sensor.key)

        total_count = sum(len(s) for s in self._discovered_sensors.values())

        schema = vol.Schema(
            {
                vol.Required("selected_sensors", default=defaults): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="select_sensors",
            data_schema=schema,
            description_placeholders={
                "sensor_count": str(total_count),
                "device_id": self._config_entry.data.get(CONF_DEVICE_ID, "unknown"),
            },
        )

    async def _async_discover_sensors(self) -> None:
        """Subscribe to MQTT topic and classify the first received message."""
        received = asyncio.Event()
        payload_holder: dict[str, Any] = {}
        mqtt_topic = self._config_entry.data[CONF_MQTT_TOPIC]

        @callback
        def on_message(msg: mqtt.models.ReceiveMessage) -> None:
            try:
                data = json.loads(msg.payload)
                payload_holder["data"] = data
                received.set()
            except (json.JSONDecodeError, ValueError):
                pass

        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            raise RuntimeError("MQTT client not available")

        unsub = await mqtt.async_subscribe(
            self.hass, mqtt_topic, on_message, qos=0
        )

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

        # Re-use the classify logic from the main config flow
        self._device_payload = device_payload
        self._discovered_sensors, self._active_ports = _classify_payload(device_payload)
