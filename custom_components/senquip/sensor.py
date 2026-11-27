"""Sensor platform for the Senquip Telemetry integration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import SenquipDataCoordinator

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CAN_PORTS,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_SELECTED_SIGNALS,
    DOMAIN,
    EVENT_DM1_FAULT,
    KNOWN_INTERNAL_SENSORS,
    PORT_DISPLAY_NAMES,
    SensorMeta,
)
from .fault_history import (
    FAULT_HISTORY_SAVE_DELAY,
    FAULT_HISTORY_STORE_VERSION,
    FAULT_LOG_FORMAT,
    DM1FaultLog,
    fault_history_store_key,
)

_LOGGER = logging.getLogger(__name__)

def _resolve_sensor_meta(sensor_key: str, coordinator: SenquipDataCoordinator) -> SensorMeta:
    """Determine HA sensor attributes from a canonical signal key."""
    if sensor_key.startswith("internal.main."):
        json_key = sensor_key.removeprefix("internal.main.")
        if json_key in KNOWN_INTERNAL_SENSORS:
            return KNOWN_INTERNAL_SENSORS[json_key]
        return SensorMeta(name=json_key.replace("_", " ").title())

    if sensor_key == "event.main.last":
        return SensorMeta(
            name="Last Event",
            state_class=None,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:alert-circle-outline",
        )

    if sensor_key.startswith("can."):
        parts = sensor_key.split(".")
        if len(parts) < 4:
            return SensorMeta(name=sensor_key, state_class=None)
        port_id = parts[1]
        runtime = coordinator.get_can_runtime(port_id)
        if runtime is None:
            return SensorMeta(name=sensor_key, state_class=None)
        protocol, decoder = runtime
        return protocol.resolve_signal_meta(sensor_key, decoder)

    return SensorMeta(name=sensor_key)


def _build_device_info(
    sensor_key: str,
    device_id: str,
    device_name: str,
) -> DeviceInfo:
    """Return DeviceInfo for the base device or a port sub-device."""
    parts = sensor_key.split(".")

    if len(parts) >= 2:
        category = parts[0]
        port_id = parts[1]

        if category == "can" and port_id in PORT_DISPLAY_NAMES:
            return DeviceInfo(
                identifiers={(DOMAIN, f"{device_id}_{port_id}")},
                name=device_name,
                model=PORT_DISPLAY_NAMES[port_id],
                manufacturer="Senquip",
                via_device=(DOMAIN, device_id),
            )

        if category == "internal" and port_id == "main":
            return DeviceInfo(
                identifiers={(DOMAIN, device_id)},
                name=device_name,
                manufacturer="Senquip",
                model="QUAD-C2",
            )

        if port_id in PORT_DISPLAY_NAMES and port_id != "internal":
            return DeviceInfo(
                identifiers={(DOMAIN, f"{device_id}_{port_id}")},
                name=device_name,
                model=PORT_DISPLAY_NAMES[port_id],
                manufacturer="Senquip",
                via_device=(DOMAIN, device_id),
            )

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer="Senquip",
        model="QUAD-C2",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Senquip sensor entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    device_id: str = entry.data[CONF_DEVICE_ID]
    device_name: str = entry.data[CONF_DEVICE_NAME]
    selected: list[str] = entry.data[CONF_SELECTED_SIGNALS]

    entities: list[SensorEntity] = []
    for sensor_key in selected:
        meta = _resolve_sensor_meta(sensor_key, coordinator)
        entities.append(
            SenquipSensorEntity(
                coordinator=coordinator,
                sensor_key=sensor_key,
                sensor_meta=meta,
                device_id=device_id,
                device_name=device_name,
            )
        )

    for port_id in CAN_PORTS:
        runtime = coordinator.get_can_runtime(port_id)
        if runtime is None or runtime[0].protocol_id != "j1939":
            continue
        dm1_prefix = f"can.{port_id}.j1939.dm1."
        if any(key.startswith(dm1_prefix) for key in selected):
            entities.append(
                SenquipDM1FaultHistorySensor(coordinator, port_id, device_id, device_name)
            )

    if entities:
        async_add_entities(entities)


class SenquipSensorEntity(CoordinatorEntity, SensorEntity):
    """A single sensor value from a Senquip telemetry device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: SenquipDataCoordinator,
        sensor_key: str,
        sensor_meta: SensorMeta,
        device_id: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_name = sensor_meta.name

        if sensor_meta.device_class is not None:
            self._attr_device_class = sensor_meta.device_class
        if sensor_meta.state_class is not None:
            self._attr_state_class = sensor_meta.state_class
        if sensor_meta.unit is not None:
            self._attr_native_unit_of_measurement = sensor_meta.unit
        if sensor_meta.entity_category is not None:
            self._attr_entity_category = sensor_meta.entity_category
        if sensor_meta.icon is not None:
            self._attr_icon = sensor_meta.icon
        if sensor_meta.options is not None:
            self._attr_options = sensor_meta.options

        self._attr_device_info = _build_device_info(sensor_key, device_id, device_name)

    @property
    def available(self) -> bool:
        """Return whether the sensor is available."""
        if not self.coordinator.is_device_online():
            return False
        if self._sensor_key.startswith("can."):
            parts = self._sensor_key.split(".")
            if len(parts) >= 2:
                port_id = parts[1]
                if not self.coordinator.is_can_port_available(port_id):
                    return False
        return True

    @property
    def native_value(self) -> StateType:
        """Return current sensor value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._sensor_key)



class SenquipDM1FaultHistorySensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Persistent log of DM1 faults seen on a J1939 CAN port.

    State is the number of logged faults; the log itself is exposed in the
    ``faults`` attribute. The log is saved to its own .storage file shortly
    after every change so it survives restarts and power loss.
    ``RestoreEntity`` is kept only to migrate logs saved by 0.6.0.

    Each fault becoming active or clearing fires an ``EVENT_DM1_FAULT`` event.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:clipboard-text-clock"
    # The full log is persisted in .storage; recording it on every change would
    # bloat the database. Count, active_faults and last_fault are recorded.
    _unrecorded_attributes = frozenset({"faults"})

    def __init__(
        self,
        coordinator: SenquipDataCoordinator,
        port_id: str,
        device_id: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._port_id = port_id
        self._device_id = device_id
        self._device_name = device_name
        signal_key = f"can.{port_id}.j1939.dm1.fault_history"
        self._attr_unique_id = f"{device_id}_{signal_key}"
        self._attr_name = "DM1 Fault History"
        self._attr_device_info = _build_device_info(signal_key, device_id, device_name)
        self._log = DM1FaultLog()
        self._store: Store = Store(
            coordinator.hass,
            FAULT_HISTORY_STORE_VERSION,
            fault_history_store_key(device_id, port_id),
            atomic_writes=True,
        )

    async def async_added_to_hass(self) -> None:
        """Load the persisted fault log, then start listening for updates.

        Loading first means no coordinator update can land on the empty
        placeholder log while the file is being read.
        """
        stored = await self._store.async_load()
        if stored is not None:
            self._log = DM1FaultLog.from_dict(stored)
            if stored.get("format", 1) < FAULT_LOG_FORMAT and self._convert_big_endian_spns():
                self._schedule_save()
        else:
            # Migrate a log that 0.6.0 kept in restore-state data
            last_extra = await self.async_get_last_extra_data()
            if last_extra is not None:
                self._log = DM1FaultLog.from_dict(last_extra.as_dict())
                self._convert_big_endian_spns()
                self._schedule_save()
        await super().async_added_to_hass()
        # Catch a payload that arrived before this entity was listening
        if self._observe_latest():
            self._schedule_save()
            self._fire_transitions()

    async def async_will_remove_from_hass(self) -> None:
        """Flush any pending save so it cannot land after the file is deleted."""
        await super().async_will_remove_from_hass()
        await self._store.async_save(self._log.as_dict())

    def _convert_big_endian_spns(self) -> bool:
        """Correct SPNs that 0.6.0-0.7.0 decoded big-endian.

        Those versions decoded DM1 big-endian wherever the MAN profile's DM1
        options applied; the engines send the standard layout, so the logged
        SPNs (and descriptions) were wrong.
        """
        runtime = self.coordinator.get_can_runtime(self._port_id)
        if runtime is None:
            return False
        decoder = runtime[1]
        port = self._port_id
        return self._log.convert_big_endian_spns(
            lambda source: decoder.dm1_options_apply(port, source),
            lambda source, spn, fmi: decoder.get_fault_description(
                spn, fmi, decoder.get_dm1_custom_fault_spns(port, source)
            ),
        )

    def _schedule_save(self) -> None:
        """Write the log to .storage after a short delay.

        The data is read when the write happens, so it is always the current log.
        """
        self._store.async_delay_save(lambda: self._log.as_dict(), FAULT_HISTORY_SAVE_DELAY)

    def _observe_latest(self) -> bool:
        """Feed the latest payload's DM1 frames into the log."""
        return self._log.observe(
            self.coordinator.get_dm1_reports(self._port_id),
            datetime.now(timezone.utc),
        )

    def _fire_transitions(self) -> None:
        """Fire an event for each fault that became active or cleared."""
        transitions = self._log.pop_transitions()
        if not transitions:
            return
        registry_entry = getattr(self, "registry_entry", None)
        ha_device_id = registry_entry.device_id if registry_entry else None
        device_name = self._device_name
        if ha_device_id:
            device = dr.async_get(self.coordinator.hass).async_get(ha_device_id)
            if device is not None:
                device_name = device.name_by_user or device.name or device_name
        for transition in transitions:
            self.coordinator.hass.bus.async_fire(
                EVENT_DM1_FAULT,
                {
                    **transition,
                    "device_id": ha_device_id,
                    "device_name": device_name,
                    "senquip_id": self._device_id,
                    "port": self._port_id,
                    "entity_id": getattr(self, "entity_id", None),
                },
            )

    @property
    def available(self) -> bool:
        """The log is history, so it stays available while the device is offline."""
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the log; write state only when it changed."""
        if self._observe_latest():
            self._schedule_save()
            self._fire_transitions()
            self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        """Return the number of logged faults."""
        return len(self._log.entries)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the fault log."""
        entries = self._log.entries
        latest = entries[0] if entries else None
        return {
            "active_faults": self._log.active_count,
            "last_fault": latest["description"] if latest else None,
            "last_fault_time": latest["last_activated"] if latest else None,
            "faults": entries,
        }
