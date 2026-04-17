"""Stable helper functions for the simulator-backed platform runtime."""

from __future__ import annotations

from pathlib import Path

from ircp_contracts import DeviceStatus, RunEvent, RunEventType, RunPhase, RunState
from ircp_data_pipeline import ArtifactSummary
from ircp_ui_shell import EventLogItem


def storage_base_root(storage_root: Path | None = None) -> Path:
    if storage_root is not None:
        return storage_root.resolve()
    return Path(__file__).resolve().parents[3] / ".local_state"


def bool_vendor_status(status: DeviceStatus, key: str) -> bool:
    return bool(status.vendor_status.get(key, False))


def event_log_item_from_run_event(event: RunEvent) -> EventLogItem:
    return EventLogItem(
        timestamp=event.emitted_at,
        source=event.source,
        message=event.message,
        tone=event_tone(event.event_type),
    )


def event_tone(event_type: RunEventType) -> str:
    if event_type == RunEventType.DEVICE_FAULT_REPORTED:
        return "bad"
    if event_type == RunEventType.RUN_COMPLETED:
        return "good"
    if event_type == RunEventType.RUN_ABORTED:
        return "warn"
    return "neutral"


def phase_tone(phase: RunPhase) -> str:
    if phase == RunPhase.COMPLETED:
        return "good"
    if phase == RunPhase.FAULTED:
        return "bad"
    if phase == RunPhase.RUNNING:
        return "warn"
    return "neutral"


def run_badge_tone(run_phase_label: str) -> str:
    normalized = run_phase_label.lower()
    if "completed" in normalized or "ready" in normalized:
        return "good"
    if "fault" in normalized or "abort" in normalized:
        return "bad"
    if "running" in normalized or "starting" in normalized:
        return "warn"
    return "neutral"


def state_summary(state: RunState) -> str:
    if state.latest_fault is not None:
        return state.latest_fault.message
    if state.failure_reason is not None:
        return state.failure_reason.value
    return state.phase.value


def artifact_summary_line(artifact: ArtifactSummary) -> str:
    summary_bits = [artifact.artifact_id, artifact.relative_path]
    if artifact.stream_name:
        summary_bits.append(f"stream={artifact.stream_name}")
    if artifact.source_role:
        summary_bits.append(f"role={artifact.source_role.value}")
    if artifact.device_kind:
        summary_bits.append(f"device={artifact.device_kind.value}")
    if artifact.related_marker:
        summary_bits.append(f"marker={artifact.related_marker}")
    return " | ".join(summary_bits)
