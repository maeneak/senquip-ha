"""Tests for the DM1 fault history log and its sensor entity."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from custom_components.senquip import SenquipDataCoordinator, async_remove_entry
from custom_components.senquip.can_profiles.loader import discover_profiles
from custom_components.senquip.fault_history import DM1FaultLog, fault_history_store_key
from custom_components.senquip.sensor import (
    SenquipDM1FaultHistorySensor,
    async_setup_entry,
)
from tests.ha_stubs import ConfigEntry, Store


@pytest.fixture(autouse=True)
def _clear_store():
    Store.saved.clear()
    yield
    Store.saved.clear()

T0 = datetime(2026, 11, 27, 8, 0, 0, tzinfo=timezone.utc)
MAN_SA = 0x27
OTHER_SA = 0x3D

_NO_LAMPS = {"protect": "Off", "amber_warning": "Off", "red_stop": "Off", "mil": "Not Available"}


def _report(source=MAN_SA, spn=0, fmi=0, oc=0, desc="No Active Fault", lamps=None):
    return {
        "source_address": source,
        "active_spn": spn,
        "active_fmi": fmi,
        "active_fault": desc,
        "occurrence_count": oc,
        "lamps": lamps if lamps is not None else _NO_LAMPS,
    }


EMERGENCY_STOP = _report(
    spn=520198,
    fmi=2,
    oc=1,
    desc="SPN 520198: Emergency Stop (FMI 2: Data Erratic/Incorrect)",
    lamps={"protect": "Active", "amber_warning": "Off", "red_stop": "Off", "mil": "Not Available"},
)


# ---------------------------------------------------------------------------
# DM1FaultLog
# ---------------------------------------------------------------------------

class TestDM1FaultLog:
    def test_new_fault_logged(self):
        log = DM1FaultLog()
        assert log.observe([EMERGENCY_STOP], T0) is True
        [entry] = log.entries
        assert entry["spn"] == 520198
        assert entry["fmi"] == 2
        assert entry["source_address"] == MAN_SA
        assert entry["lamps"] == ["Protect"]
        assert entry["active"] is True
        assert entry["count"] == 1
        assert entry["first_seen"] == entry["last_activated"] == "2026-11-27T08:00:00+00:00"
        assert entry["cleared"] is None
        assert log.active_count == 1

    def test_no_fault_frames_log_nothing(self):
        log = DM1FaultLog()
        assert log.observe([_report()], T0) is False
        assert log.entries == []

    def test_still_active_fault_is_not_a_change(self):
        log = DM1FaultLog()
        log.observe([EMERGENCY_STOP], T0)
        assert log.observe([EMERGENCY_STOP], T0 + timedelta(seconds=5)) is False
        assert log.entries[0]["last_activated"] == "2026-11-27T08:00:00+00:00"

    def test_cleared_when_same_source_reports_no_fault(self):
        log = DM1FaultLog()
        log.observe([EMERGENCY_STOP], T0)
        assert log.observe([_report()], T0 + timedelta(minutes=1)) is True
        entry = log.entries[0]
        assert entry["active"] is False
        assert entry["cleared"] == "2026-11-27T08:01:00+00:00"
        assert log.active_count == 0

    def test_not_cleared_by_other_source_or_missing_dm1(self):
        log = DM1FaultLog()
        log.observe([EMERGENCY_STOP], T0)
        assert log.observe([], T0 + timedelta(minutes=1)) is False
        assert log.observe([_report(source=OTHER_SA)], T0 + timedelta(minutes=2)) is False
        assert log.entries[0]["active"] is True

    def test_reactivation_increments_count(self):
        log = DM1FaultLog()
        log.observe([EMERGENCY_STOP], T0)
        log.observe([_report()], T0 + timedelta(minutes=1))
        assert log.observe([dict(EMERGENCY_STOP, occurrence_count=2)], T0 + timedelta(minutes=2)) is True
        [entry] = log.entries
        assert entry["active"] is True
        assert entry["count"] == 2
        assert entry["occurrence_count"] == 2
        assert entry["first_seen"] == "2026-11-27T08:00:00+00:00"
        assert entry["last_activated"] == "2026-11-27T08:02:00+00:00"
        assert entry["cleared"] is None

    def test_occurrence_count_change_while_active_is_recorded(self):
        log = DM1FaultLog()
        log.observe([EMERGENCY_STOP], T0)
        assert log.observe([dict(EMERGENCY_STOP, occurrence_count=3)], T0 + timedelta(seconds=5)) is True
        assert log.entries[0]["occurrence_count"] == 3
        assert log.entries[0]["count"] == 1

    def test_faults_from_two_sources_tracked_separately(self):
        log = DM1FaultLog()
        other = _report(source=OTHER_SA, spn=110, fmi=0, oc=1, desc="Coolant")
        log.observe([EMERGENCY_STOP, other], T0)
        assert log.active_count == 2
        # MAN clears; other source still reports its fault
        log.observe([_report(), other], T0 + timedelta(minutes=1))
        active = {(e["source_address"], e["spn"]) for e in log.entries if e["active"]}
        assert active == {(OTHER_SA, 110)}

    def test_entries_ordered_most_recent_first(self):
        log = DM1FaultLog()
        log.observe([_report(spn=100, fmi=1, desc="Oil")], T0)
        log.observe([_report(spn=110, fmi=0, desc="Coolant")], T0 + timedelta(minutes=1))
        assert [e["spn"] for e in log.entries] == [110, 100]

    def test_trim_drops_oldest_inactive_and_keeps_active(self):
        log = DM1FaultLog(max_entries=3)
        # Long-running active fault from another source, logged first (oldest)
        log.observe([_report(source=OTHER_SA, spn=1, fmi=1, desc="Long")], T0)
        for i in range(2, 6):
            log.observe([_report(spn=i, fmi=1, desc=f"F{i}")], T0 + timedelta(minutes=i))
        spns = {e["spn"] for e in log.entries}
        assert len(log.entries) == 3
        assert 1 in spns  # active entry kept despite being oldest
        assert spns == {1, 4, 5}

    def test_trim_keeps_recently_cleared_long_running_fault(self):
        """Eviction uses most recent activity, not activation time."""
        log = DM1FaultLog(max_entries=3)
        log.observe([_report(source=OTHER_SA, spn=999, fmi=1, desc="Long")], T0)
        for i in range(1, 4):
            log.observe([_report(spn=i, fmi=1, desc=f"F{i}")], T0 + timedelta(hours=i))
        log.observe([_report()], T0 + timedelta(hours=4))  # MAN fault 3 clears
        log.observe([_report(source=OTHER_SA)], T0 + timedelta(days=5))  # 999 clears
        log.observe([_report(spn=50, fmi=1, desc="New")], T0 + timedelta(days=5, minutes=1))
        spns = {e["spn"] for e in log.entries}
        assert 999 in spns
        assert spns == {999, 3, 50}

    def test_last_frame_per_source_wins_within_payload(self):
        log = DM1FaultLog()
        log.observe([EMERGENCY_STOP], T0)
        assert log.observe([EMERGENCY_STOP, _report()], T0 + timedelta(seconds=5)) is True
        assert log.entries[0]["active"] is False
        # And a fault in the last frame is logged even if an earlier frame had none
        log2 = DM1FaultLog()
        log2.observe([_report(), EMERGENCY_STOP], T0)
        assert log2.active_count == 1

    def test_subsecond_activations_order_most_recent_first(self):
        log = DM1FaultLog()
        log.observe([_report(spn=10, fmi=1, desc="A")], T0)
        log.observe([_report(source=OTHER_SA, spn=20, fmi=1, desc="B")], T0 + timedelta(milliseconds=500))
        assert [e["spn"] for e in log.entries] == [20, 10]
        restored = DM1FaultLog.from_dict(log.as_dict())
        assert [e["spn"] for e in restored.entries] == [20, 10]

    def test_round_trip_serialization(self):
        log = DM1FaultLog()
        log.observe([EMERGENCY_STOP], T0)
        log.observe([_report()], T0 + timedelta(minutes=1))
        restored = DM1FaultLog.from_dict(log.as_dict())
        assert restored.entries == log.entries
        # Restored log keeps tracking the same key
        assert restored.observe([EMERGENCY_STOP], T0 + timedelta(minutes=2)) is True
        assert restored.entries[0]["count"] == 2

    def test_from_dict_skips_malformed(self):
        good = DM1FaultLog()
        good.observe([EMERGENCY_STOP], T0)
        data = {"entries": [{"spn": "bad"}, "junk", *good.as_dict()["entries"]]}
        assert len(DM1FaultLog.from_dict(data).entries) == 1
        assert DM1FaultLog.from_dict(None).entries == []
        assert DM1FaultLog.from_dict({"entries": "nope"}).entries == []


# ---------------------------------------------------------------------------
# Coordinator + entity integration
# ---------------------------------------------------------------------------

def _man_profiles():
    return discover_profiles(Path("custom_components/senquip/can_profiles"))


def _coordinator(selected):
    entry = ConfigEntry(
        data={
            "device_id": "test_dev",
            "device_name": "Test",
            "mqtt_topic": "senquip/test",
            "selected_signals": selected,
            "port_configs": {
                "can1": {"family": "can", "active": True, "protocol": "j1939", "profiles": []},
                "can2": {
                    "family": "can",
                    "active": True,
                    "protocol": "j1939",
                    "profiles": ["man_d2862.json"],
                },
            },
        }
    )
    return entry, SenquipDataCoordinator(MagicMock(), entry, _man_profiles())


def _payload(can2_dm1):
    return {
        "deviceid": "test_dev",
        "can2": [
            {"id": 217056256, "data": "3FFFCD883927F4FF"},
            {"id": 0x1CFECA27, "data": can2_dm1},
        ],
    }


class TestCoordinatorDM1Reports:
    def test_reports_collected_without_dm1_signals_selected(self):
        _, coord = _coordinator(["can.can2.j1939.spn190"])
        coord._parse_payload(_payload("C1FFFE00C201FFFF"))
        [report] = coord.get_dm1_reports("can2")
        assert report["source_address"] == MAN_SA
        assert report["active_spn"] == 520198
        assert report["active_fmi"] == 2
        assert report["lamps"]["protect"] == "Active"
        assert coord.get_dm1_reports("can1") == []

    def test_reports_reset_when_payload_has_no_dm1(self):
        _, coord = _coordinator(["can.can2.j1939.spn190"])
        coord._parse_payload(_payload("C1FFFE00C201FFFF"))
        coord._parse_payload({"deviceid": "test_dev", "can2": [{"id": 217056256, "data": "3FFFCD883927F4FF"}]})
        assert coord.get_dm1_reports("can2") == []


class TestFaultHistorySensor:
    def test_created_only_for_ports_with_dm1_selected(self):
        entry, coord = _coordinator(["can.can1.j1939.spn190", "can.can2.j1939.dm1.active_fault"])
        hass = MagicMock()
        hass.data = {"senquip": {entry.entry_id: coord}}
        added = []
        asyncio.run(async_setup_entry(hass, entry, added.extend))
        history = [e for e in added if isinstance(e, SenquipDM1FaultHistorySensor)]
        assert len(history) == 1
        assert history[0]._attr_unique_id == "test_dev_can.can2.j1939.dm1.fault_history"

    def test_logs_and_clears_from_coordinator_updates(self):
        _, coord = _coordinator(["can.can2.j1939.dm1.active_fault"])
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        assert sensor.native_value == 0
        assert sensor.available is True

        coord._parse_payload(_payload("C1FFFE00C201FFFF"))
        sensor._handle_coordinator_update()
        assert sensor.native_value == 1
        attrs = sensor.extra_state_attributes
        assert attrs["active_faults"] == 1
        assert attrs["last_fault"].startswith("SPN 520198: Emergency Stop")
        assert attrs["faults"][0]["lamps"] == ["Protect"]

        coord._parse_payload(_payload("C0FF00000000FFFF"))
        sensor._handle_coordinator_update()
        attrs = sensor.extra_state_attributes
        assert sensor.native_value == 1
        assert attrs["active_faults"] == 0
        assert attrs["faults"][0]["cleared"] is not None

    def test_state_written_only_on_change(self):
        _, coord = _coordinator(["can.can2.j1939.dm1.active_fault"])
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        coord._parse_payload(_payload("C0FF00000000FFFF"))
        sensor._handle_coordinator_update()
        assert sensor.state_writes == 0
        coord._parse_payload(_payload("C1FFFE00C201FFFF"))
        sensor._handle_coordinator_update()
        sensor._handle_coordinator_update()
        assert sensor.state_writes == 1

    def test_faults_attribute_excluded_from_recorder(self):
        assert "faults" in SenquipDM1FaultHistorySensor._unrecorded_attributes

    def test_payload_before_entity_added_is_logged(self):
        _, coord = _coordinator(["can.can2.j1939.dm1.active_fault"])
        coord._parse_payload(_payload("C1FFFE00C201FFFF"))
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        asyncio.run(sensor.async_added_to_hass())
        assert sensor.extra_state_attributes["active_faults"] == 1

    def test_saved_to_store_on_change_and_loaded_on_startup(self):
        _, coord = _coordinator(["can.can2.j1939.dm1.active_fault"])
        original = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        coord._parse_payload(_payload("C0FF00000000FFFF"))
        original._handle_coordinator_update()
        assert original._store.save_calls == 0  # nothing changed, nothing saved
        coord._parse_payload(_payload("C1FFFE00C201FFFF"))
        original._handle_coordinator_update()
        assert original._store.save_calls == 1
        assert original._store.key == fault_history_store_key("test_dev", "can2")
        assert original._store.kwargs.get("atomic_writes") is True
        original._store.flush()

        # A new entity (e.g. after restart) loads the log from .storage
        coord._dm1_reports = {}
        restored = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        asyncio.run(restored.async_added_to_hass())
        assert restored.native_value == 1
        assert restored.extra_state_attributes["faults"] == original.extra_state_attributes["faults"]

    def test_migrates_log_from_restore_state(self):
        """A log kept in restore-state data by 0.6.0 is moved into .storage."""
        legacy = DM1FaultLog()
        legacy.observe([EMERGENCY_STOP], T0)
        _, coord = _coordinator(["can.can2.j1939.dm1.active_fault"])
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        sensor._stub_last_extra_data = MagicMock(as_dict=MagicMock(return_value=legacy.as_dict()))
        asyncio.run(sensor.async_added_to_hass())
        assert sensor.native_value == 1
        sensor._store.flush()
        assert Store.saved[fault_history_store_key("test_dev", "can2")] == legacy.as_dict()

    def test_update_during_load_does_not_overwrite_history(self):
        """A payload landing while .storage is read must not save the empty log."""
        stored = DM1FaultLog()
        for spn in (100, 110, 520198):
            stored.observe([_report(spn=spn, fmi=1, desc=f"F{spn}")], T0 + timedelta(minutes=spn % 7))
        key = fault_history_store_key("test_dev", "can2")
        Store.saved[key] = stored.as_dict()

        _, coord = _coordinator(["can.can2.j1939.dm1.active_fault"])
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        real_load = sensor._store.async_load

        async def load_with_racing_update():
            # The last stored fault is still active; a payload repeating it arrives mid-load
            coord._dm1_reports = {"can2": [_report(spn=520198, fmi=1, desc="F520198")]}
            sensor._handle_coordinator_update()
            return await real_load()

        sensor._store.async_load = load_with_racing_update
        asyncio.run(sensor.async_added_to_hass())
        sensor._store.flush()
        assert len(Store.saved[key]["entries"]) == 3
        assert sensor.native_value == 3

    def test_pending_save_flushed_on_removal(self):
        """Removal writes immediately so no delayed save lands after deletion."""
        _, coord = _coordinator(["can.can2.j1939.dm1.active_fault"])
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        coord._parse_payload(_payload("C1FFFE00C201FFFF"))
        sensor._handle_coordinator_update()
        key = fault_history_store_key("test_dev", "can2")
        assert key not in Store.saved  # still pending
        asyncio.run(sensor.async_will_remove_from_hass())
        assert len(Store.saved[key]["entries"]) == 1
        asyncio.run(async_remove_entry(MagicMock(), ConfigEntry(data={"device_id": "test_dev"})))
        sensor._store.flush()  # nothing pending any more
        assert key not in Store.saved

    def test_store_preferred_over_restore_state(self):
        stored = DM1FaultLog()
        stored.observe([EMERGENCY_STOP], T0)
        Store.saved[fault_history_store_key("test_dev", "can2")] = stored.as_dict()
        _, coord = _coordinator(["can.can2.j1939.dm1.active_fault"])
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        sensor._stub_last_extra_data = MagicMock(as_dict=MagicMock(return_value={"entries": []}))
        asyncio.run(sensor.async_added_to_hass())
        assert sensor.native_value == 1

    def test_multi_packet_dm1_logged_and_cleared(self):
        _, coord = _coordinator(["can.can2.j1939.dm1.active_fault"])
        sensor = SenquipDM1FaultHistorySensor(coord, "can2", "test_dev", "Test")
        # MAN at SA 0x00 announces a 3-DTC DM1 (14 bytes) via BAM
        coord._parse_payload({"deviceid": "test_dev", "can2": [
            {"id": 0x1CECFF00, "data": "200E0002FFCAFE00"},
        ]})
        sensor._handle_coordinator_update()
        [entry] = sensor.extra_state_attributes["faults"]
        assert entry["spn"] is None and entry["fmi"] is None
        assert entry["source_address"] == 0x00
        assert entry["description"] == "3 Active Faults (details not decoded)"
        assert entry["active"] is True
        # Back to a single-frame no-fault DM1 from the same source clears it
        coord._parse_payload({"deviceid": "test_dev", "can2": [
            {"id": 0x18FECA00, "data": "C0FF00000000FFFF"},
        ]})
        sensor._handle_coordinator_update()
        assert sensor.extra_state_attributes["faults"][0]["active"] is False


class TestRemoveEntry:
    def test_remove_entry_deletes_fault_logs(self):
        Store.saved[fault_history_store_key("test_dev", "can1")] = {"entries": []}
        Store.saved[fault_history_store_key("test_dev", "can2")] = {"entries": []}
        Store.saved[fault_history_store_key("other_dev", "can2")] = {"entries": []}
        entry = ConfigEntry(data={"device_id": "test_dev"})
        asyncio.run(async_remove_entry(MagicMock(), entry))
        assert list(Store.saved) == [fault_history_store_key("other_dev", "can2")]
