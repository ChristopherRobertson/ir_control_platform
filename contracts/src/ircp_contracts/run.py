"""Validation, readiness, run-state, and run-event contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from .common import (
    ConfigurationScalar,
    PicoMonitoringMode,
    ReadinessState,
    RunCommandType,
    RunEventType,
    RunFailureReason,
    RunPhase,
    TimingMarker,
    ValidationSeverity,
)
from .device import DeviceFault
from .experiment import (
    AcquisitionTimingMode,
    MuxRouteSelection,
    PicoSecondaryCapture,
    ProbeTimingMode,
)


@dataclass(frozen=True)
class TimingSummaryEntry:
    label: str
    marker: TimingMarker
    offset_ns: float


@dataclass(frozen=True)
class TimingSummary:
    t0_label: str
    master_device_id: str
    slave_device_id: str
    cycle_period_ns: float
    entries: tuple[TimingSummaryEntry, ...]


@dataclass(frozen=True)
class PumpProbeAcquisitionSummary:
    pump_shots_before_probe: int
    probe_timing_mode: ProbeTimingMode
    acquisition_timing_mode: AcquisitionTimingMode
    acquisition_reference_marker: TimingMarker | None


@dataclass(frozen=True)
class MuxRoutingSummary:
    route_set_name: str
    channel_a: str
    channel_b: str
    external_trigger: str


@dataclass(frozen=True)
class PicoCaptureSummary:
    mode: PicoMonitoringMode
    trigger_marker: TimingMarker | None
    monitor_enabled: bool
    recording_enabled: bool
    recorded_inputs: tuple[str, ...]


@dataclass(frozen=True)
class RunOutcomeSummary:
    started_at: datetime | None = None
    ended_at: datetime | None = None
    failure_reason: RunFailureReason | None = None
    latest_fault: DeviceFault | None = None
    final_event_id: str | None = None

    def __post_init__(self) -> None:
        if self.started_at is not None and self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("Run outcome end time cannot precede start time.")
        if self.latest_fault is not None and self.failure_reason not in {
            None,
            RunFailureReason.DEVICE_FAULT,
            RunFailureReason.PERSISTENCE_FAILED,
        }:
            raise ValueError("Run outcome faults must use a fault-compatible failure reason.")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: ValidationSeverity
    message: str
    source: str
    blocking: bool
    field_path: str | None = None
    related_device_id: str | None = None


@dataclass(frozen=True)
class ReadinessCheck:
    check_id: str
    target: str
    state: ReadinessState
    checked_at: datetime
    summary: str
    issues: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True)
class PreflightReport:
    recipe_id: str
    generated_at: datetime
    checks: tuple[ReadinessCheck, ...]
    ready_to_start: bool
    timing_summary: TimingSummary
    pump_probe_summary: PumpProbeAcquisitionSummary
    selected_markers: tuple[TimingMarker, ...]
    mux_summary: MuxRoutingSummary
    pico_summary: PicoCaptureSummary

    def __post_init__(self) -> None:
        has_blocking_issue = any(
            check.state == ReadinessState.BLOCK or any(issue.blocking for issue in check.issues)
            for check in self.checks
        )
        if self.ready_to_start and has_blocking_issue:
            raise ValueError("A ready preflight report cannot contain blocking checks or issues.")


@dataclass(frozen=True)
class RunCommand:
    command_type: RunCommandType
    issued_at: datetime
    issued_by: str
    recipe_id: str | None = None
    session_id: str | None = None
    payload: Mapping[str, ConfigurationScalar] = field(default_factory=dict)


@dataclass(frozen=True)
class RunState:
    run_id: str
    recipe_id: str
    phase: RunPhase
    updated_at: datetime
    session_id: str | None = None
    active_step: str | None = None
    progress_fraction: float | None = None
    preflight: PreflightReport | None = None
    timing_summary: TimingSummary | None = None
    pump_probe_summary: PumpProbeAcquisitionSummary | None = None
    selected_markers: tuple[TimingMarker, ...] = ()
    mux_summary: MuxRoutingSummary | None = None
    pico_summary: PicoCaptureSummary | None = None
    latest_fault: DeviceFault | None = None
    failure_reason: RunFailureReason | None = None
    last_event_id: str | None = None

    def __post_init__(self) -> None:
        if self.progress_fraction is None:
            return
        if not 0.0 <= self.progress_fraction <= 1.0:
            raise ValueError("Run progress must stay within [0.0, 1.0].")


@dataclass(frozen=True)
class RunEvent:
    event_id: str
    run_id: str
    event_type: RunEventType
    emitted_at: datetime
    source: str
    message: str
    phase: RunPhase
    session_id: str | None = None
    device_fault: DeviceFault | None = None
    failure_reason: RunFailureReason | None = None
    timing_summary: TimingSummary | None = None
    pump_probe_summary: PumpProbeAcquisitionSummary | None = None
    selected_markers: tuple[TimingMarker, ...] = ()
    mux_summary: MuxRoutingSummary | None = None
    pico_summary: PicoCaptureSummary | None = None
    payload: Mapping[str, ConfigurationScalar] = field(default_factory=dict)


def summarize_mux_routes(routes: MuxRouteSelection) -> MuxRoutingSummary:
    def _format_route(route: object) -> str:
        selection = route
        analog_source = getattr(selection, "analog_source", None)
        digital_marker = getattr(selection, "digital_marker", None)
        if analog_source is not None:
            return str(analog_source.value)
        if digital_marker is not None:
            return str(digital_marker.value)
        return "unconfigured"

    return MuxRoutingSummary(
        route_set_name=routes.route_set_name,
        channel_a=_format_route(routes.channel_a),
        channel_b=_format_route(routes.channel_b),
        external_trigger=_format_route(routes.external_trigger),
    )


def summarize_pico_capture(pico_capture: PicoSecondaryCapture) -> PicoCaptureSummary:
    return PicoCaptureSummary(
        mode=pico_capture.mode,
        trigger_marker=pico_capture.trigger_marker,
        monitor_enabled=pico_capture.mode in {PicoMonitoringMode.MONITOR_ONLY, PicoMonitoringMode.MONITOR_AND_RECORD},
        recording_enabled=pico_capture.mode in {PicoMonitoringMode.RECORD_ONLY, PicoMonitoringMode.MONITOR_AND_RECORD},
        recorded_inputs=tuple(item.value for item in pico_capture.record_inputs),
    )
