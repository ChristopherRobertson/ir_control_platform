"""Concrete supported-v1 simulator-backed orchestration services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Callable, Mapping

from ircp_contracts import (
    ArtifactSourceRole,
    ConfigurationScalar,
    DeviceConfiguration,
    DeviceFault,
    DeviceKind,
    DeviceLifecycleState,
    DeviceStatus,
    ExperimentPreset,
    ExperimentRecipe,
    FaultCategory,
    FaultSeverity,
    PicoMonitoringMode,
    PreflightReport,
    PumpProbeAcquisitionSummary,
    ReadinessCheck,
    ReadinessState,
    RunEvent,
    RunEventType,
    RunFailureReason,
    RunPhase,
    RunState,
    SessionManifest,
    SessionStatus,
    TimingMarker,
    TimingSummary,
    TimingSummaryEntry,
    ValidationIssue,
    ValidationSeverity,
    summarize_mux_routes,
    summarize_pico_capture,
)
from ircp_data_pipeline import SessionOpenRequest, SessionReplayer, SessionStore

from .boundaries import (
    LiveDataPoint,
    PreflightValidator,
    RunCoordinator,
    RunMonitor,
    RunTimeline,
    SupportedV1DriverBundle,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_timing_summary(recipe: ExperimentRecipe) -> TimingSummary:
    entries = (
        TimingSummaryEntry(
            label="Pump fire",
            marker=recipe.timing.master.pump_fire_command.marker,
            offset_ns=recipe.timing.master.pump_fire_command.offset_ns,
        ),
        TimingSummaryEntry(
            label="Pump Q-switch",
            marker=recipe.timing.master.pump_qswitch_command.marker,
            offset_ns=recipe.timing.master.pump_qswitch_command.offset_ns,
        ),
        TimingSummaryEntry(
            label="Master to slave trigger",
            marker=recipe.timing.master.master_to_slave_trigger.marker,
            offset_ns=recipe.timing.master.master_to_slave_trigger.offset_ns,
        ),
        TimingSummaryEntry(
            label="Probe trigger",
            marker=recipe.timing.slave.probe_trigger.marker,
            offset_ns=recipe.timing.slave.probe_trigger.offset_ns,
        ),
        TimingSummaryEntry(
            label="Probe process trigger",
            marker=recipe.timing.slave.probe_process_trigger.marker,
            offset_ns=recipe.timing.slave.probe_process_trigger.offset_ns,
        ),
        TimingSummaryEntry(
            label="Probe enable window",
            marker=recipe.timing.slave.probe_enable_window.marker,
            offset_ns=recipe.timing.slave.probe_enable_window.start_offset_ns,
        ),
    )
    return TimingSummary(
        t0_label=recipe.timing.t0_label,
        master_device_id=recipe.timing.master.device_identity.value,
        slave_device_id=recipe.timing.slave.device_identity.value,
        cycle_period_ns=recipe.timing.master.cycle_period_ns,
        entries=entries,
    )


def build_pump_probe_summary(recipe: ExperimentRecipe) -> PumpProbeAcquisitionSummary:
    return PumpProbeAcquisitionSummary(
        pump_shots_before_probe=recipe.pump_shots_before_probe,
        probe_timing_mode=recipe.probe_timing_mode,
        acquisition_timing_mode=recipe.timing.acquisition_timing_mode,
        acquisition_reference_marker=recipe.timing.acquisition_reference_marker,
    )


def _status_to_issue(device_status: DeviceStatus, *, blocking: bool) -> ValidationIssue | None:
    if device_status.connected and device_status.ready and not device_status.reported_faults:
        return None
    if device_status.reported_faults:
        latest_fault = device_status.reported_faults[-1]
        return ValidationIssue(
            code=latest_fault.code,
            severity=ValidationSeverity.ERROR if blocking else ValidationSeverity.WARNING,
            message=latest_fault.message,
            source=device_status.device_kind.value,
            blocking=blocking and latest_fault.blocking,
            related_device_id=device_status.device_id,
        )
    if not device_status.connected:
        return ValidationIssue(
            code=f"{device_status.device_kind.value}_offline",
            severity=ValidationSeverity.ERROR if blocking else ValidationSeverity.WARNING,
            message=f"{device_status.device_kind.value} is offline.",
            source=device_status.device_kind.value,
            blocking=blocking,
            related_device_id=device_status.device_id,
        )
    if not device_status.ready:
        return ValidationIssue(
            code=f"{device_status.device_kind.value}_not_ready",
            severity=ValidationSeverity.ERROR if blocking else ValidationSeverity.WARNING,
            message=f"{device_status.device_kind.value} is connected but not ready.",
            source=device_status.device_kind.value,
            blocking=blocking,
            related_device_id=device_status.device_id,
        )
    return None


def _readiness_state(issue: ValidationIssue | None) -> ReadinessState:
    if issue is None:
        return ReadinessState.PASS
    return ReadinessState.BLOCK if issue.blocking else ReadinessState.WARN


class StepOutcome(str, Enum):
    CONTINUE = "continue"
    COMPLETE = "complete"
    FAULT = "fault"


@dataclass(frozen=True)
class RunEventTemplate:
    event_type: RunEventType
    source: str
    message: str
    payload: Mapping[str, ConfigurationScalar] = field(default_factory=dict)


@dataclass(frozen=True)
class RawArtifactTemplate:
    device_kind: DeviceKind
    stream_name: str
    relative_path: str
    record_count: int
    source_role: ArtifactSourceRole
    content_type: str = "application/vnd.apache.parquet"
    mux_output_target: str | None = None
    related_marker: str | None = None
    metadata: Mapping[str, ConfigurationScalar] = field(default_factory=dict)


@dataclass(frozen=True)
class RunStepTemplate:
    phase: RunPhase
    active_step: str
    progress_fraction: float
    message: str
    events: tuple[RunEventTemplate, ...]
    live_data_points: tuple[LiveDataPoint, ...] = ()
    raw_artifacts: tuple[RawArtifactTemplate, ...] = ()
    outcome: StepOutcome = StepOutcome.CONTINUE
    latest_fault: DeviceFault | None = None
    failure_reason: RunFailureReason | None = None


@dataclass(frozen=True)
class RunExecutionPlan:
    steps: tuple[RunStepTemplate, ...]


RunPlanFactory = Callable[[ExperimentRecipe, str, str], RunExecutionPlan]


@dataclass(frozen=True)
class RunCaptureHandles:
    hf2_capture_id: str
    pico_capture_id: str | None = None


class SupportedV1PreflightValidator(PreflightValidator):
    """Deterministic preflight evaluator for the supported-v1 slice."""

    async def validate(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        drivers: SupportedV1DriverBundle,
    ) -> PreflightReport:
        checked_at = _utc_now()
        timing_summary = build_timing_summary(recipe)
        pump_probe_summary = build_pump_probe_summary(recipe)
        mux_summary = summarize_mux_routes(recipe.mux_route_selection)
        pico_summary = summarize_pico_capture(recipe.pico_secondary_capture)

        statuses = await _collect_driver_statuses(drivers)
        lookup = {status.device_id: status for status in statuses}

        recipe_check = ReadinessCheck(
            check_id="recipe-shape",
            target=recipe.recipe_id,
            state=ReadinessState.PASS,
            checked_at=checked_at,
            summary="Recipe shape matches the supported-v1 experiment model.",
        )
        preset_check = ReadinessCheck(
            check_id="preset-scope",
            target=preset.name if preset else "default",
            state=ReadinessState.PASS,
            checked_at=checked_at,
            summary="Preset scope stays within the supported-v1 configuration surface.",
        )

        device_checks = [
            self._build_device_check(lookup["mircat-qcl"], checked_at, blocking=True),
            self._build_device_check(lookup["hf2li-primary"], checked_at, blocking=True),
            self._build_device_check(lookup["t660-2-master"], checked_at, blocking=True),
            self._build_device_check(lookup["t660-1-slave"], checked_at, blocking=True),
            self._build_device_check(lookup["arduino-mux"], checked_at, blocking=True),
        ]

        pico_status = lookup["picoscope-5244d"]
        if recipe.pico_secondary_capture.mode == PicoMonitoringMode.DISABLED:
            device_checks.append(
                ReadinessCheck(
                    check_id="picoscope-status",
                    target=pico_status.device_id,
                    state=ReadinessState.PASS,
                    checked_at=checked_at,
                    summary="Secondary PicoScope monitoring is disabled for this recipe.",
                )
            )
        else:
            device_checks.append(
                self._build_device_check(pico_status, checked_at, blocking=False)
            )

        checks = (recipe_check, preset_check, *device_checks)
        ready_to_start = all(check.state != ReadinessState.BLOCK for check in checks)
        return PreflightReport(
            recipe_id=recipe.recipe_id,
            generated_at=checked_at,
            checks=checks,
            ready_to_start=ready_to_start,
            timing_summary=timing_summary,
            pump_probe_summary=pump_probe_summary,
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=mux_summary,
            pico_summary=pico_summary,
        )

    def _build_device_check(
        self,
        device_status: DeviceStatus,
        checked_at: datetime,
        *,
        blocking: bool,
    ) -> ReadinessCheck:
        issue = _status_to_issue(device_status, blocking=blocking)
        return ReadinessCheck(
            check_id=f"{device_status.device_id}-status",
            target=device_status.device_id,
            state=_readiness_state(issue),
            checked_at=checked_at,
            summary=device_status.status_summary,
            issues=(issue,) if issue is not None else (),
        )


class InMemoryRunCoordinator(RunCoordinator, RunMonitor):
    """Single-path simulator-backed run authority for supported-v1."""

    def __init__(
        self,
        drivers: SupportedV1DriverBundle,
        session_store: SessionStore,
        session_replayer: SessionReplayer,
        preflight_validator: PreflightValidator,
        run_plan_factory: RunPlanFactory,
    ) -> None:
        self._drivers = drivers
        self._session_store = session_store
        self._session_replayer = session_replayer
        self._preflight_validator = preflight_validator
        self._run_plan_factory = run_plan_factory
        self._run_counter = 0
        self._session_manifests: dict[str, SessionManifest] = {}
        self._run_timelines: dict[str, RunTimeline] = {}
        self._active_captures: dict[str, RunCaptureHandles] = {}

    async def create_session(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        session_id: str | None = None,
        notes: tuple[str, ...] = (),
    ) -> SessionManifest:
        timing_summary = build_timing_summary(recipe)
        pump_probe_summary = build_pump_probe_summary(recipe)
        mux_summary = summarize_mux_routes(recipe.mux_route_selection)
        pico_summary = summarize_pico_capture(recipe.pico_secondary_capture)

        master_configuration = await self._drivers.t660_master.apply_configuration(recipe.timing.master)
        slave_configuration = await self._drivers.t660_slave.apply_configuration(recipe.timing.slave)
        mircat_configuration = await self._drivers.mircat.apply_configuration(recipe.mircat)
        hf2_configuration = await self._drivers.hf2li.apply_configuration(recipe.hf2_primary_acquisition)
        mux_configuration = await self._drivers.mux.apply_configuration(recipe.mux_route_selection)

        device_config_snapshot = [
            master_configuration,
            slave_configuration,
            mircat_configuration,
            hf2_configuration,
            mux_configuration,
        ]

        pico_status = await self._drivers.picoscope.get_status()
        if recipe.pico_secondary_capture.mode != PicoMonitoringMode.DISABLED and pico_status.connected:
            pico_configuration = await self._drivers.picoscope.apply_configuration(recipe.pico_secondary_capture)
            device_config_snapshot.append(pico_configuration)

        device_status_snapshot = await _collect_driver_statuses(self._drivers)
        manifest = await self._session_store.create_session_manifest(
            recipe=recipe,
            preset=preset,
            calibration_references=recipe.calibration_references,
            device_config_snapshot=tuple(device_config_snapshot),
            device_status_snapshot=device_status_snapshot,
            timing_summary=timing_summary,
            pump_probe_summary=pump_probe_summary,
            selected_markers=recipe.timing.selected_digital_markers,
            mux_route_snapshot=recipe.mux_route_selection,
            mux_summary=mux_summary,
            pico_capture_snapshot=recipe.pico_secondary_capture,
            pico_summary=pico_summary,
            time_to_wavenumber_mapping=recipe.time_to_wavenumber_mapping,
            session_id=session_id,
            notes=notes,
        )

        created_at = _utc_now()
        bootstrap_events = (
            RunEvent(
                event_id=f"{manifest.session_id}-event-session-created",
                run_id=f"{manifest.session_id}-bootstrap",
                event_type=RunEventType.SESSION_CREATED,
                emitted_at=created_at,
                source="session",
                message="Session opened.",
                phase=RunPhase.STARTING,
                session_id=manifest.session_id,
                timing_summary=timing_summary,
                pump_probe_summary=pump_probe_summary,
                selected_markers=recipe.timing.selected_digital_markers,
                mux_summary=mux_summary,
                pico_summary=pico_summary,
            ),
            RunEvent(
                event_id=f"{manifest.session_id}-event-config-applied",
                run_id=f"{manifest.session_id}-bootstrap",
                event_type=RunEventType.DEVICE_CONFIGURATION_APPLIED,
                emitted_at=created_at,
                source="experiment",
                message="MIRcat and HF2LI settings staged.",
                phase=RunPhase.STARTING,
                session_id=manifest.session_id,
                timing_summary=timing_summary,
                pump_probe_summary=pump_probe_summary,
                selected_markers=recipe.timing.selected_digital_markers,
                mux_summary=mux_summary,
                pico_summary=pico_summary,
            ),
        )
        for event in bootstrap_events:
            manifest = await self._session_store.append_event(manifest.session_id, event)
        self._session_manifests[manifest.session_id] = manifest
        return manifest

    async def start_run(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        session_id: str,
    ) -> RunState:
        if session_id not in self._session_manifests:
            raise KeyError(f"Session {session_id} must exist before start_run().")

        preflight = await self._preflight_validator.validate(recipe, preset, self._drivers)
        if not preflight.ready_to_start:
            raise ValueError("Cannot start run while preflight is blocked.")

        self._run_counter += 1
        run_id = f"run-{self._run_counter:03d}"

        session_manifest = await self._session_store.update_session_status(session_id, SessionStatus.ACTIVE)
        await self._drivers.t660_master.arm_outputs()
        await self._drivers.t660_slave.arm_outputs()
        await self._drivers.mircat.arm()
        hf2_capture = await self._drivers.hf2li.start_capture(recipe.hf2_primary_acquisition, session_id)

        pico_capture_id: str | None = None
        if recipe.pico_secondary_capture.mode != PicoMonitoringMode.DISABLED:
            pico_status = await self._drivers.picoscope.get_status()
            if pico_status.connected and pico_status.ready:
                pico_capture = await self._drivers.picoscope.start_capture(
                    recipe.pico_secondary_capture,
                    session_id,
                )
                pico_capture_id = pico_capture.capture_id if pico_capture is not None else None

        await self._drivers.mircat.start_recipe(recipe.mircat, recipe.probe_timing_mode)
        self._active_captures[run_id] = RunCaptureHandles(
            hf2_capture_id=hf2_capture.capture_id,
            pico_capture_id=pico_capture_id,
        )

        timeline_events = list(session_manifest.event_timeline)
        timeline_states: list[RunState] = []
        timeline_live_data: list[LiveDataPoint] = []
        latest_fault: DeviceFault | None = None
        failure_reason: RunFailureReason | None = None

        plan = self._run_plan_factory(recipe, session_id, run_id)
        for step_index, step in enumerate(plan.steps, start=1):
            step_events: list[RunEvent] = []
            for event_template in step.events:
                event = RunEvent(
                    event_id=f"{run_id}-event-{step_index}-{event_template.event_type.value}",
                    run_id=run_id,
                    event_type=event_template.event_type,
                    emitted_at=_utc_now(),
                    source=event_template.source,
                    message=event_template.message,
                    phase=step.phase,
                    session_id=session_id,
                    device_fault=step.latest_fault,
                    failure_reason=step.failure_reason,
                    timing_summary=preflight.timing_summary,
                    pump_probe_summary=preflight.pump_probe_summary,
                    selected_markers=preflight.selected_markers,
                    mux_summary=preflight.mux_summary,
                    pico_summary=preflight.pico_summary,
                    payload=dict(event_template.payload),
                )
                session_manifest = await self._session_store.append_event(session_id, event)
                step_events.append(event)
                timeline_events.append(event)

            raw_artifact_events = [
                event for event in step_events if event.event_type == RunEventType.RAW_ARTIFACT_REGISTERED
            ]
            for artifact_index, artifact_template in enumerate(step.raw_artifacts, start=1):
                from ircp_contracts import RawDataArtifact  # local import keeps this module focused

                registration_event = (
                    raw_artifact_events[artifact_index - 1]
                    if artifact_index - 1 < len(raw_artifact_events)
                    else None
                )
                artifact = RawDataArtifact(
                    artifact_id=f"{run_id}-raw-{step_index}-{artifact_index}",
                    session_id=session_id,
                    device_kind=artifact_template.device_kind,
                    stream_name=artifact_template.stream_name,
                    relative_path=artifact_template.relative_path,
                    created_at=_utc_now(),
                    record_count=artifact_template.record_count,
                    content_type=artifact_template.content_type,
                    source_role=artifact_template.source_role,
                    mux_output_target=artifact_template.mux_output_target,
                    related_marker=artifact_template.related_marker,
                    registered_by_event_id=(
                        registration_event.event_id if registration_event is not None else None
                    ),
                    metadata=dict(artifact_template.metadata),
                )
                session_manifest = await self._session_store.persist_raw_artifact(
                    session_id,
                    artifact,
                    _build_raw_artifact_rows(step.live_data_points, artifact_template),
                )

            if step.live_data_points:
                timeline_live_data.extend(step.live_data_points)

            latest_fault = step.latest_fault or latest_fault
            failure_reason = step.failure_reason or failure_reason
            run_state = RunState(
                run_id=run_id,
                recipe_id=recipe.recipe_id,
                phase=step.phase,
                updated_at=_utc_now(),
                session_id=session_id,
                active_step=step.active_step,
                progress_fraction=step.progress_fraction,
                preflight=preflight,
                timing_summary=preflight.timing_summary,
                pump_probe_summary=preflight.pump_probe_summary,
                selected_markers=preflight.selected_markers,
                mux_summary=preflight.mux_summary,
                pico_summary=preflight.pico_summary,
                latest_fault=latest_fault,
                failure_reason=failure_reason,
                last_event_id=timeline_events[-1].event_id if timeline_events else None,
            )
            timeline_states.append(run_state)

        final_state = timeline_states[-1]
        final_status = _phase_to_session_status(final_state.phase)
        if final_status in {SessionStatus.COMPLETED, SessionStatus.FAULTED, SessionStatus.ABORTED}:
            session_manifest = await self._session_store.finalize_session(
                session_id,
                final_status,
                ended_at=final_state.updated_at,
                failure_reason=failure_reason,
                latest_fault=latest_fault,
                final_event=timeline_events[-1] if timeline_events else None,
                note=final_state.active_step,
            )
        elif final_status != session_manifest.status:
            session_manifest = await self._session_store.update_session_status(session_id, final_status)

        if final_state.phase in {RunPhase.COMPLETED, RunPhase.FAULTED, RunPhase.ABORTED}:
            await self._teardown_run(run_id)

        device_status_snapshot = await _collect_driver_statuses(self._drivers)
        if latest_fault is not None:
            device_status_snapshot = _replace_status_with_fault(device_status_snapshot, latest_fault)
        session_manifest = await self._session_store.update_device_snapshots(
            session_id,
            device_status_snapshot=device_status_snapshot,
        )
        self._session_manifests[session_id] = session_manifest
        self._run_timelines[run_id] = RunTimeline(
            run_id=run_id,
            states=tuple(timeline_states),
            events=tuple(timeline_events),
            live_data_points=tuple(timeline_live_data),
        )

        return final_state

    async def get_run_state(self, run_id: str) -> RunState:
        timeline = self._require_timeline(run_id)
        return timeline.states[-1]

    async def report_device_fault(self, run_id: str, fault: DeviceFault) -> RunEvent:
        timeline = self._require_timeline(run_id)
        latest_state = timeline.states[-1]
        return RunEvent(
            event_id=f"{run_id}-reported-fault",
            run_id=run_id,
            event_type=RunEventType.DEVICE_FAULT_REPORTED,
            emitted_at=_utc_now(),
            source="experiment-engine",
            message=fault.message,
            phase=RunPhase.FAULTED,
            session_id=latest_state.session_id,
            device_fault=fault,
            failure_reason=RunFailureReason.DEVICE_FAULT,
            timing_summary=latest_state.timing_summary,
            pump_probe_summary=latest_state.pump_probe_summary,
            selected_markers=latest_state.selected_markers,
            mux_summary=latest_state.mux_summary,
            pico_summary=latest_state.pico_summary,
        )

    async def abort_run(
        self,
        run_id: str,
        reason: RunFailureReason = RunFailureReason.OPERATOR_ABORT,
    ) -> RunState:
        timeline = self._require_timeline(run_id)
        previous = timeline.states[-1]
        aborted = RunState(
            run_id=run_id,
            recipe_id=previous.recipe_id,
            phase=RunPhase.ABORTED,
            updated_at=_utc_now(),
            session_id=previous.session_id,
            active_step="aborted",
            progress_fraction=previous.progress_fraction,
            preflight=previous.preflight,
            timing_summary=previous.timing_summary,
            pump_probe_summary=previous.pump_probe_summary,
            selected_markers=previous.selected_markers,
            mux_summary=previous.mux_summary,
            pico_summary=previous.pico_summary,
            latest_fault=previous.latest_fault,
            failure_reason=reason,
            last_event_id=f"{run_id}-event-aborted",
        )
        aborted_event = RunEvent(
            event_id=f"{run_id}-event-aborted",
            run_id=run_id,
            event_type=RunEventType.RUN_ABORTED,
            emitted_at=aborted.updated_at,
            source="experiment",
            message="Experiment aborted.",
            phase=RunPhase.ABORTED,
            session_id=previous.session_id,
            device_fault=previous.latest_fault,
            failure_reason=reason,
            timing_summary=previous.timing_summary,
            pump_probe_summary=previous.pump_probe_summary,
            selected_markers=previous.selected_markers,
            mux_summary=previous.mux_summary,
            pico_summary=previous.pico_summary,
        )
        timeline_events = (*timeline.events, aborted_event)
        self._run_timelines[run_id] = RunTimeline(
            run_id=run_id,
            states=(*timeline.states, aborted),
            events=timeline_events,
            live_data_points=timeline.live_data_points,
        )
        if previous.session_id is not None:
            await self._session_store.append_event(previous.session_id, aborted_event)
            session_manifest = await self._session_store.finalize_session(
                previous.session_id,
                SessionStatus.ABORTED,
                ended_at=aborted.updated_at,
                failure_reason=reason,
                latest_fault=previous.latest_fault,
                final_event=aborted_event,
                note="aborted",
            )
            await self._teardown_run(run_id)
            session_manifest = await self._session_store.update_device_snapshots(
                previous.session_id,
                device_status_snapshot=await _collect_driver_statuses(self._drivers),
            )
            self._session_manifests[previous.session_id] = session_manifest
        else:
            await self._teardown_run(run_id)
        return aborted

    async def reopen_session(self, session_id: str) -> SessionManifest:
        result = await self._session_replayer.open_session(
            SessionOpenRequest(session_id=session_id, requested_at=_utc_now(), reopen_for_replay=True)
        )
        return result.manifest

    async def get_run_timeline(self, run_id: str) -> RunTimeline:
        return self._require_timeline(run_id)

    def _require_timeline(self, run_id: str) -> RunTimeline:
        try:
            return self._run_timelines[run_id]
        except KeyError as exc:
            raise KeyError(f"Unknown run id: {run_id}") from exc

    async def _teardown_run(self, run_id: str) -> None:
        capture_handles = self._active_captures.pop(run_id, None)
        if capture_handles is not None:
            await self._drivers.hf2li.stop_capture(capture_handles.hf2_capture_id)
            if capture_handles.pico_capture_id is not None:
                await self._drivers.picoscope.stop_capture(capture_handles.pico_capture_id)
        await self._drivers.mircat.stop_recipe()
        await self._drivers.mircat.disarm()
        await self._drivers.t660_slave.stop_outputs()
        await self._drivers.t660_master.stop_outputs()


async def _collect_driver_statuses(drivers: SupportedV1DriverBundle) -> tuple[DeviceStatus, ...]:
    return (
        await drivers.mircat.get_status(),
        await drivers.hf2li.get_status(),
        await drivers.t660_master.get_status(),
        await drivers.t660_slave.get_status(),
        await drivers.mux.get_status(),
        await drivers.picoscope.get_status(),
    )


def _replace_status_with_fault(
    statuses: tuple[DeviceStatus, ...],
    fault: DeviceFault,
) -> tuple[DeviceStatus, ...]:
    return tuple(
        device_status_from_fault(status.device_id, status.device_kind, fault)
        if status.device_id == fault.device_id
        else status
        for status in statuses
    )


def _stream_metadata(stream_name: str) -> dict[str, object]:
    if stream_name.startswith("hf2.demod") and stream_name.count(".") >= 2:
        _prefix, demod_token, component = stream_name.split(".", 2)
        try:
            demod_index: int | str | None = int(demod_token.removeprefix("demod"))
        except ValueError:
            demod_index = demod_token.removeprefix("demod")
        return {
            "demod_index": demod_index,
            "component_name": component,
            "channel_name": None,
        }
    if stream_name.startswith("pico.") and "." in stream_name:
        _prefix, channel_name = stream_name.split(".", 1)
        return {
            "demod_index": None,
            "component_name": None,
            "channel_name": channel_name,
        }
    return {
        "demod_index": None,
        "component_name": None,
        "channel_name": None,
    }


def _build_raw_artifact_rows(
    live_data_points: tuple[LiveDataPoint, ...],
    artifact_template: RawArtifactTemplate,
) -> tuple[dict[str, object], ...]:
    matching_points = tuple(
        point
        for point in live_data_points
        if point.stream_name == artifact_template.stream_name
        and point.source_role == artifact_template.source_role
    )
    if len(matching_points) != artifact_template.record_count:
        raise ValueError(
            "Raw artifact payload row count does not match the artifact template: "
            f"{artifact_template.relative_path} expected {artifact_template.record_count}, "
            f"got {len(matching_points)}."
        )
    stream_metadata = _stream_metadata(artifact_template.stream_name)
    return tuple(
        {
            "acquisition_index": index,
            "sample_id": point.sample_id,
            "captured_at": point.captured_at.isoformat(),
            "device_kind": artifact_template.device_kind.value,
            "stream_name": point.stream_name,
            "axis_label": point.axis_label,
            "axis_units": point.axis_units,
            "axis_value": point.axis_value,
            "value": point.value,
            "units": point.units,
            "source_role": point.source_role.value,
            "mux_output_target": artifact_template.mux_output_target,
            "related_marker": artifact_template.related_marker,
            "metadata_json": json.dumps(dict(point.metadata or {}), sort_keys=True),
            **stream_metadata,
        }
        for index, point in enumerate(matching_points, start=1)
    )


def build_live_data_points(
    run_id: str,
    stream_name: str,
    axis_label: str,
    axis_units: str,
    values: tuple[tuple[float, float], ...],
    *,
    source_role: ArtifactSourceRole = ArtifactSourceRole.PRIMARY_RAW,
    units: str = "V",
) -> tuple[LiveDataPoint, ...]:
    """Create deterministic live-data points from axis/value tuples."""

    captured_at = _utc_now()
    return tuple(
        LiveDataPoint(
            sample_id=f"{run_id}-{stream_name}-{index}",
            captured_at=captured_at,
            stream_name=stream_name,
            axis_label=axis_label,
            axis_units=axis_units,
            axis_value=axis_value,
            value=value,
            units=units,
            source_role=source_role,
        )
        for index, (axis_value, value) in enumerate(values, start=1)
    )


def build_fault(
    *,
    fault_id: str,
    device_id: str,
    device_kind: DeviceKind,
    code: str,
    message: str,
    vendor_code: str,
    vendor_message: str,
    context: Mapping[str, ConfigurationScalar] | None = None,
) -> DeviceFault:
    return DeviceFault(
        fault_id=fault_id,
        device_id=device_id,
        device_kind=device_kind,
        category=FaultCategory.VENDOR,
        severity=FaultSeverity.ERROR,
        code=code,
        message=message,
        detected_at=_utc_now(),
        vendor_code=vendor_code,
        vendor_message=vendor_message,
        context=dict(context or {}),
    )


def device_status_from_fault(device_id: str, device_kind: DeviceKind, fault: DeviceFault) -> DeviceStatus:
    return DeviceStatus(
        device_id=device_id,
        device_kind=device_kind,
        lifecycle_state=DeviceLifecycleState.FAULTED,
        connected=True,
        ready=False,
        busy=False,
        updated_at=_utc_now(),
        status_summary=fault.message,
        reported_faults=(fault,),
    )


def _phase_to_session_status(phase: RunPhase) -> SessionStatus:
    if phase == RunPhase.COMPLETED:
        return SessionStatus.COMPLETED
    if phase == RunPhase.FAULTED:
        return SessionStatus.FAULTED
    if phase == RunPhase.ABORTED:
        return SessionStatus.ABORTED
    return SessionStatus.ACTIVE
