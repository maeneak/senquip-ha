"""Tests for device and CAN port connectivity detection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from custom_components.senquip.binary_sensor import (
    SenquipCANPortConnectivitySensor,
    SenquipDeviceConnectivitySensor,
)


class _FakeCoordinator:
    """Minimal coordinator stub for binary sensor tests."""

    def __init__(self):
        self._device_online = False
        self._can_port_available: dict[str, bool] = {}

    def is_device_online(self) -> bool:
        return self._device_online

    def is_can_port_available(self, port_id: str) -> bool:
        return self._can_port_available.get(port_id, True)


# ---------------------------------------------------------------------------
# Device connectivity sensor
# ---------------------------------------------------------------------------


class TestDeviceConnectivity:
    def test_offline_by_default(self):
        coord = _FakeCoordinator()
        sensor = SenquipDeviceConnectivitySensor(coord, "dev1", "My Senquip")
        assert sensor.is_on is False

    def test_online_when_device_online(self):
        coord = _FakeCoordinator()
        coord._device_online = True
        sensor = SenquipDeviceConnectivitySensor(coord, "dev1", "My Senquip")
        assert sensor.is_on is True

    def test_unique_id(self):
        coord = _FakeCoordinator()
        sensor = SenquipDeviceConnectivitySensor(coord, "dev1", "My Senquip")
        assert sensor._attr_unique_id == "dev1_connectivity"

    def test_name(self):
        coord = _FakeCoordinator()
        sensor = SenquipDeviceConnectivitySensor(coord, "dev1", "My Senquip")
        assert sensor._attr_name == "Connectivity"


# ---------------------------------------------------------------------------
# CAN port connectivity sensor
# ---------------------------------------------------------------------------


class TestCANPortConnectivity:
    def test_offline_when_device_offline(self):
        coord = _FakeCoordinator()
        coord._device_online = False
        coord._can_port_available["can1"] = True
        sensor = SenquipCANPortConnectivitySensor(coord, "dev1", "My Senquip", "can1")
        assert sensor.is_on is False

    def test_offline_when_port_has_no_data(self):
        coord = _FakeCoordinator()
        coord._device_online = True
        coord._can_port_available["can1"] = False
        sensor = SenquipCANPortConnectivitySensor(coord, "dev1", "My Senquip", "can1")
        assert sensor.is_on is False

    def test_online_when_device_online_and_port_has_data(self):
        coord = _FakeCoordinator()
        coord._device_online = True
        coord._can_port_available["can1"] = True
        sensor = SenquipCANPortConnectivitySensor(coord, "dev1", "My Senquip", "can1")
        assert sensor.is_on is True

    def test_unique_id_includes_port(self):
        coord = _FakeCoordinator()
        sensor = SenquipCANPortConnectivitySensor(coord, "dev1", "My Senquip", "can2")
        assert sensor._attr_unique_id == "dev1_can2_connectivity"


# ---------------------------------------------------------------------------
# Coordinator staleness timer
# ---------------------------------------------------------------------------


class TestCoordinatorStaleness:
    def _make_coordinator(self):
        """Create a coordinator with mocked HA dependencies."""
        from custom_components.senquip import SenquipDataCoordinator
        from tests.ha_stubs import ConfigEntry

        entry = ConfigEntry(
            data={
                "device_id": "test_dev",
                "mqtt_topic": "senquip/test",
                "selected_signals": [],
                "port_configs": {},
            }
        )
        hass = MagicMock()
        return SenquipDataCoordinator(hass, entry, {})

    def test_device_starts_offline(self):
        coord = self._make_coordinator()
        assert coord.is_device_online() is False

    def test_handle_message_sets_online(self):
        coord = self._make_coordinator()
        msg = MagicMock()
        msg.payload = '{"deviceid": "test_dev", "vsys": 12.5}'

        with patch(
            "custom_components.senquip.async_call_later", return_value=lambda: None
        ):
            coord._handle_message(msg)

        assert coord.is_device_online() is True

    def test_mark_device_offline(self):
        coord = self._make_coordinator()
        coord._device_online = True
        coord._can_port_available["can1"] = True
        coord._can_port_available["can2"] = True
        coord.data = {}

        coord._mark_device_offline()

        assert coord.is_device_online() is False
        assert coord._can_port_available["can1"] is False
        assert coord._can_port_available["can2"] is False

    def test_timer_cancelled_on_new_message(self):
        coord = self._make_coordinator()
        cancel_mock = MagicMock()
        coord._offline_timer = cancel_mock

        msg = MagicMock()
        msg.payload = '{"deviceid": "test_dev", "vsys": 12.5}'

        with patch(
            "custom_components.senquip.async_call_later", return_value=lambda: None
        ):
            coord._handle_message(msg)

        cancel_mock.assert_called_once()

    def test_timer_cancelled_on_unsubscribe(self):
        import asyncio

        coord = self._make_coordinator()
        cancel_mock = MagicMock()
        coord._offline_timer = cancel_mock

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coord.async_unsubscribe())
        finally:
            loop.close()

        cancel_mock.assert_called_once()
        assert coord._offline_timer is None
