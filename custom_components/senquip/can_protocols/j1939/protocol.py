"""J1939 protocol adapter for generic CAN architecture."""

from __future__ import annotations

import time
from typing import Any

from ...const import SPN_STATE_CLASS_OVERRIDES, SPN_UNIT_TO_HA, EntityCategory, SensorDeviceClass, SensorMeta, SensorStateClass
from ...can_profiles.loader import CANProfile
from ..base import ProtocolDiscoveredSignal
from .database import PGN_DATABASE, SPN_DATABASE
from .decoder import (
    DM1_PGN,
    TP_CM_PGN,
    J1939Decoder,
    dm1_fault_count_text,
    dm1_lamp_state,
)
from .overlay import merge_j1939_databases


_DM1_META: dict[str, SensorMeta] = {
    "active_fault": SensorMeta(
        name="DM1 Active Fault", state_class=None, icon="mdi:engine",
    ),
    "protect_lamp": SensorMeta(
        name="DM1 Protect Lamp", state_class=None, icon="mdi:alert-circle",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "amber_warning": SensorMeta(
        name="DM1 Amber Warning", state_class=None, icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "red_stop": SensorMeta(
        name="DM1 Red Stop", state_class=None, icon="mdi:alert-octagon",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "mil": SensorMeta(
        name="DM1 MIL Lamp", state_class=None, icon="mdi:engine-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "active_spn": SensorMeta(
        name="DM1 Active SPN", state_class=None, icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "active_fmi": SensorMeta(
        name="DM1 Active FMI", state_class=None, icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "occurrence_count": SensorMeta(
        name="DM1 Occurrence Count",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "active_fault_count": SensorMeta(
        name="DM1 Active Fault Count",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:alert-circle-check-outline",
    ),
}

_DM1_LAMP_FIELDS: dict[str, str] = {
    "protect": "protect_lamp",
    "amber_warning": "amber_warning",
    "red_stop": "red_stop",
    "mil": "mil",
}

# When sources disagree, the port-level lamp shows the most severe state
_LAMP_SEVERITY: dict[str, int] = {"Active": 3, "Unknown": 2, "Off": 1, "Not Available": 0}

_MAX_STATE_LENGTH = 255


def _combine_dm1_reports(port_id: str, reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine the latest DM1 report from each source into port-level values."""
    prefix = f"can.{port_id}.j1939.dm1."
    values: dict[str, Any] = {}

    for lamp, field in _DM1_LAMP_FIELDS.items():
        states = [
            report["lamps"].get(lamp, "Unknown") if report.get("lamps") else "Unknown"
            for report in reports
        ]
        values[prefix + field] = max(states, key=lambda state: _LAMP_SEVERITY.get(state, 2))

    total = sum(report["dtc_count"] for report in reports)
    decoded = [r for r in reports if not r["multi_packet"] and r["dtc_count"] > 0]

    if total == 0:
        description = "No Active Fault"
    elif total == 1 and decoded:
        description = decoded[0]["active_fault"]
    elif decoded:
        description = dm1_fault_count_text(total, ": ") + "; ".join(
            r["active_fault"] for r in decoded
        )
    else:
        description = dm1_fault_count_text(total, " (details not decoded)")
    if len(description) > _MAX_STATE_LENGTH:
        description = description[: _MAX_STATE_LENGTH - 3] + "..."

    values[prefix + "active_fault"] = description
    values[prefix + "active_fault_count"] = total
    if decoded:
        first = decoded[0]
        values[prefix + "active_spn"] = first["active_spn"]
        values[prefix + "active_fmi"] = first["active_fmi"]
        values[prefix + "occurrence_count"] = first["occurrence_count"]
    elif total == 0:
        values[prefix + "active_spn"] = 0
        values[prefix + "active_fmi"] = 0
        values[prefix + "occurrence_count"] = 0
    else:
        # Faults are active but none could be decoded (multi-packet only).
        # 0 would mean "no fault", so report SPN/FMI as Unknown. Occurrence
        # count is a measurement (numeric only) and is left unchanged.
        values[prefix + "active_spn"] = "Unknown"
        values[prefix + "active_fmi"] = "Unknown"
    return values


class J1939CANProtocol:
    """Protocol adapter implementing J1939 decoding/discovery."""

    protocol_id = "j1939"
    display_name = "J1939"

    def build_decoder(self, profiles: list[CANProfile]) -> tuple[J1939Decoder, list[str]]:
        pgn_db, spn_db, dm1_config, errors = merge_j1939_databases(PGN_DATABASE, SPN_DATABASE, profiles)
        return J1939Decoder(pgn_db, spn_db, dm1_config), errors

    def discover_signals(
        self,
        frames: list[dict[str, Any]],
        port_id: str,
        decoder: J1939Decoder,
    ) -> list[ProtocolDiscoveredSignal]:
        discovered: list[ProtocolDiscoveredSignal] = []
        seen_spns: set[int] = set()

        for frame in frames:
            can_id = frame.get("id")
            hex_data = frame.get("data")
            if can_id is None or hex_data is None:
                continue

            _, pgn, _ = decoder.extract_pgn(can_id)
            if pgn == DM1_PGN:
                continue

            decoded = decoder.decode_frame(can_id, hex_data)
            pgn_info = decoder.get_pgn_info(can_id)
            acronym = pgn_info.acronym if pgn_info else ""

            if decoded:
                for spn_num, spn_value in decoded.items():
                    if spn_num in seen_spns:
                        continue
                    seen_spns.add(spn_num)
                    spn_def = decoder.get_spn_def(spn_num)
                    name = f"SPN {spn_num}"
                    unit = None
                    if spn_def is not None:
                        name = spn_def.name
                        unit = spn_def.unit
                        if acronym:
                            name = f"{spn_def.name} ({acronym})"
                    discovered.append(
                        ProtocolDiscoveredSignal(
                            key=f"can.{port_id}.j1939.spn{spn_num}",
                            name=name,
                            sample_value=spn_value,
                            unit=unit,
                            default_selected=spn_value is not None,
                        )
                    )
            else:
                discovered.append(
                    ProtocolDiscoveredSignal(
                        key=f"can.{port_id}.j1939.raw.{pgn}",
                        name=f"Unknown PGN {pgn} (0x{pgn:04X})",
                        sample_value=hex_data[:16] + ("..." if len(hex_data) > 16 else ""),
                        unit=None,
                        default_selected=False,
                    )
                )

        discovered.extend(
            [
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.j1939.dm1.active_fault",
                    name="DM1 Active Fault",
                    sample_value="No Active Fault",
                    unit=None,
                    default_selected=True,
                ),
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.j1939.dm1.active_fault_count",
                    name="DM1 Active Fault Count",
                    sample_value=0,
                    unit=None,
                    default_selected=True,
                ),
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.j1939.dm1.protect_lamp",
                    name="DM1 Protect Lamp",
                    sample_value="Off",
                    unit=None,
                    default_selected=True,
                ),
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.j1939.dm1.amber_warning",
                    name="DM1 Amber Warning",
                    sample_value="Off",
                    unit=None,
                    default_selected=True,
                ),
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.j1939.dm1.red_stop",
                    name="DM1 Red Stop",
                    sample_value="Off",
                    unit=None,
                    default_selected=True,
                ),
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.j1939.dm1.mil",
                    name="DM1 MIL Lamp",
                    sample_value="Off",
                    unit=None,
                    default_selected=False,
                ),
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.j1939.dm1.active_spn",
                    name="DM1 Active SPN",
                    sample_value=0,
                    unit=None,
                    default_selected=False,
                ),
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.j1939.dm1.active_fmi",
                    name="DM1 Active FMI",
                    sample_value=0,
                    unit=None,
                    default_selected=False,
                ),
                ProtocolDiscoveredSignal(
                    key=f"can.{port_id}.j1939.dm1.occurrence_count",
                    name="DM1 Occurrence Count",
                    sample_value=0,
                    unit=None,
                    default_selected=False,
                ),
            ]
        )
        return discovered

    def decode_runtime(
        self,
        frames: list[dict[str, Any]],
        port_id: str,
        selected_signals: set[str],
        decoder: J1939Decoder,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
        values: dict[str, Any] = {}
        diagnostics: list[dict[str, Any]] = []
        has_valid_data = False
        # DM1 report per source address in this payload (multi-packet wins)
        dm1_by_source: dict[int, dict[str, Any]] = {}

        for frame in frames:
            can_id = frame.get("id")
            hex_data = frame.get("data")
            if can_id is None or hex_data is None:
                continue

            _, pgn, source = decoder.extract_pgn(can_id)
            pgn_def = decoder.get_pgn_info(can_id)
            frame_diag: dict[str, Any] = {
                "protocol": self.protocol_id,
                "can_id": can_id,
                "can_id_hex": f"0x{can_id:08X}",
                "pgn": pgn,
                "pgn_hex": f"0x{pgn:04X}",
                "source_address": source,
                "data": hex_data,
                "known": pgn_def is not None or pgn == DM1_PGN,
            }

            if pgn == DM1_PGN:
                try:
                    dm1_bytes = bytes.fromhex(hex_data)
                except ValueError:
                    diagnostics.append(frame_diag)
                    continue

                big_endian = decoder.is_dm1_big_endian(port_id, source)
                dm1 = decoder.decode_dm1(dm1_bytes, big_endian_spn=big_endian)
                if dm1 is not None:
                    has_valid_data = True
                    custom_faults = decoder.get_dm1_custom_fault_spns(port_id, source)
                    fault_desc = decoder.get_fault_description(
                        dm1.active_spn,
                        dm1.active_fmi,
                        custom_faults,
                    )
                    has_fault = not (dm1.active_spn == 0 and dm1.active_fmi == 0)
                    report = {
                        "multi_packet": False,
                        "dtc_count": 1 if has_fault else 0,
                        "active_spn": dm1.active_spn,
                        "active_fmi": dm1.active_fmi,
                        "active_fault": fault_desc,
                        "occurrence_count": dm1.occurrence_count,
                        "encoding": "big_endian" if big_endian else "little_endian",
                        "lamps": {
                            "protect": dm1_lamp_state(dm1.lamp_protect),
                            "amber_warning": dm1_lamp_state(dm1.lamp_amber),
                            "red_stop": dm1_lamp_state(dm1.lamp_red),
                            "mil": dm1_lamp_state(dm1.lamp_mil),
                        },
                    }
                    frame_diag["pgn_name"] = "DM1 - Active DTCs"
                    frame_diag["pgn_acronym"] = "DM1"
                    frame_diag["dm1"] = report
                    # Payload order is CAN-ID slot order, not time order. If a
                    # source sent both a single frame and a BAM this interval,
                    # its state changed mid-interval; report the multi-packet
                    # one (more faults) and let the next payload settle it.
                    previous = dm1_by_source.get(source)
                    if previous is None or not previous["multi_packet"]:
                        dm1_by_source[source] = report
                diagnostics.append(frame_diag)
                continue

            if pgn == TP_CM_PGN:
                try:
                    dtc_count = decoder.decode_dm1_bam(bytes.fromhex(hex_data))
                except ValueError:
                    dtc_count = None
                if dtc_count is not None:
                    has_valid_data = True
                    report = {
                        "multi_packet": True,
                        "dtc_count": dtc_count,
                        "active_spn": None,
                        "active_fmi": None,
                        "active_fault": dm1_fault_count_text(dtc_count, " (details not decoded)"),
                        "occurrence_count": None,
                        "lamps": None,
                    }
                    frame_diag["dm1"] = report
                    dm1_by_source[source] = report

            decoded = decoder.decode_frame(can_id, hex_data)
            if pgn_def is not None:
                frame_diag["pgn_name"] = pgn_def.name
                frame_diag["pgn_acronym"] = pgn_def.acronym
                spns: dict[str, Any] = {}
                for spn_num, spn_value in decoded.items():
                    if spn_value is not None:
                        has_valid_data = True
                    spn_def = decoder.get_spn_def(spn_num)
                    spn_entry: dict[str, Any] = {"value": spn_value}
                    if spn_def is not None:
                        spn_entry["name"] = spn_def.name
                        spn_entry["unit"] = spn_def.unit
                    spns[str(spn_num)] = spn_entry
                frame_diag["spns"] = spns

            for spn_num, spn_value in decoded.items():
                key = f"can.{port_id}.j1939.spn{spn_num}"
                if key in selected_signals and spn_value is not None:
                    values[key] = spn_value
            if not decoded:
                raw_key = f"can.{port_id}.j1939.raw.{pgn}"
                if raw_key in selected_signals:
                    values[raw_key] = hex_data
            diagnostics.append(frame_diag)

        # Age sources on every payload; publish only when this payload had DM1
        reports = decoder.dm1_tracker.update(dm1_by_source, time.monotonic())
        if dm1_by_source:
            combined = _combine_dm1_reports(port_id, reports)
            for key, value in combined.items():
                if key in selected_signals:
                    values[key] = value

        return values, diagnostics, has_valid_data

    def resolve_signal_meta(self, signal_key: str, decoder: J1939Decoder) -> SensorMeta:
        if ".spn" in signal_key:
            spn_num = int(signal_key.rsplit(".spn", 1)[1])
            spn_def = decoder.get_spn_def(spn_num)
            if spn_def is None:
                return SensorMeta(name=f"SPN {spn_num}")
            pgn_def = decoder.get_pgn_def(spn_def.pgn)
            acronym = pgn_def.acronym if pgn_def else ""
            name = spn_def.name if not acronym else f"{spn_def.name} ({acronym})"
            if spn_def.states is not None:
                return SensorMeta(
                    name=name,
                    device_class=SensorDeviceClass.ENUM,
                    state_class=None,
                    unit=None,
                    options=list(spn_def.states.values()),
                )
            mapping = SPN_UNIT_TO_HA.get(spn_def.unit)
            if mapping:
                device_class, unit, state_class = mapping
            else:
                device_class, unit, state_class = (
                    None,
                    spn_def.unit or None,
                    SensorStateClass.MEASUREMENT,
                )
            state_class = SPN_STATE_CLASS_OVERRIDES.get(spn_num, state_class)
            return SensorMeta(
                name=name,
                device_class=device_class,
                state_class=state_class,
                unit=unit,
            )

        if ".raw." in signal_key:
            pgn = signal_key.rsplit(".raw.", 1)[1]
            return SensorMeta(name=f"PGN {pgn} (Raw)", state_class=None, icon="mdi:numeric")

        if ".dm1." in signal_key:
            field = signal_key.rsplit(".dm1.", 1)[1]
            return _DM1_META.get(
                field,
                SensorMeta(
                    name=f"DM1 {field}", state_class=None,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
            )

        return SensorMeta(name=signal_key, state_class=None)

