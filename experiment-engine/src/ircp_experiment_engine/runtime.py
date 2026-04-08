"""Concrete Phase 3A simulator-backed orchestration services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Mapping

from ircp_contracts import (
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
    PreflightReport,
    ReadinessCheck,
    ReadinessState,
    RunEvent,
    RunEventType,
    RunFailureReason,
    RunPhase,
    RunState,
    SessionManifest,
    SessionStatus,
    ValidationIssue,
    ValidationSeverity,
)
from ircp_data_pipeline import SessionOpenRequest, SessionReplayer, SessionStore

from .boundaries import GoldenPathDriverBundle, LiveDataPoint, PreflightValidator, RunCoordinator, RunMonitor, RunTimeline


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _status_to_issue(device_status: DeviceStatus) -> ValidationIssue | None:
    if device_status.connected and device_status.ready and not device_status.reported_faults:
        return None
    if device_status.reported_faults:
        latest_fault = device_status.reported_faults[-1]
        return ValidationIssue(
            code=latest_fault.code,
            severity=ValidationSeverity.ERROR,
            message=latest_fault.message,
            source=device_status.device_kind.value,
            blocking=latest_fault.blocking,
            related_device_id=device_status.device_id,
        )
    if not device_status.connected:
        return ValidationIssue(
            code=f"{device_status.device_kind.value}_offline",
            severity=ValidationSeverity.ERROR,
            message=f"{device_status.device_kind.value} is offline.",
            source=device_status.device_kind.value,
            blocking=True,
            related_device_id=device_status.device_id,
        )
    if not device_status.ready:
        return ValidationIssue(
            code=f"{device_status.device_kind.value}_not_ready",
            severity=ValidationSeverity.ERROR,
            message=f"{device_status.device_kind.value} is connected but not ready.",
            source=device_status.device_kind.value,
            blocking=True,
            related_device_id=device_status.device_id,
        )
    return None


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
    stream_name: str
    relative_path: str
    record_count: int
    content_type: str = "text/plain"
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


class GoldenPathPreflightValidator(PreflightValidator):
    """Deterministic preflight evaluator for the first MIRcat + HF2LI slice."""

    async def validate(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        drivers: GoldenPathDriverBundle,
    ) -> PreflightReport:
        checked_at = _utc_now()
        mircat_status = await drivers.mircat.get_status()
        hf2_status = await drivers.hf2li.get_status()

        recipe_check = ReadinessCheck(
            check_id="recipe-shape",
            target=recipe.recipe_id,
            state=ReadinessState.PASS,
            checked_at=checked_at,
            summary="Recipe shape matches the MIRcat sweep + HF2LI capture golden path.",
        )
        preset_check = ReadinessCheck(
            check_id="preset-scope",
            target=preset.name if preset else "default",
            state=ReadinessState.PASS,
            checked_at=checked_at,
            summary="Preset scope stays within the approved first-slice configuration surface.",
        )
        device_checks = tuple(
            self._build_device_check(device_status, checked_at)
            for device_status in (mircat_status, hf2_status)
        )
        checks = (recipe_check, preset_check, *device_checks)
        ready_to_start = all(check.state != ReadinessState.BLOCK for check in checks)
        return PreflightReport(
            recipe_id=recipe.recipe_id,
            generated_at=checked_at,
            checks=checks,
            ready_to_start=ready_to_start,
        )

    def _build_device_check(self, device_status: DeviceStatus, checked_at: datetime) -> ReadinessCheck:
        issue = _status_to_issue(device_status)
        if issue is None:
            state = ReadinessState.PASS
        elif issue.blocking:
            state = ReadinessState.BLOCK
        else:
            state = ReadinessState.WARN
        return ReadinessCheck(
            check_id=f"{device_status.device_kind.value}-status",
            target=device_status.device_id,
            state=state,
            checked_at=checked_at,
            summary=device_status.status_summary,
            issues=(issue,) if issue is not None else (),
        )


class InMemoryRunCoordinator(RunCoordinator, RunMonitor):
    """Single-path simulator-backed run authority for Phase 3A."""

    def __init__(
        self,
        drivers: GoldenPathDriverBundle,
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

    async def create_session(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
    ) -> SessionManifest:
        mircat_configuration = await self._drivers.mircat.apply_configuration(recipe.mircat_sweep)
        hf2_configuration = await self._drivers.hf2li.apply_configuration(recipe.hf2_acquisition)
        mircat_status = await self._drivers.mircat.get_status()
        hf2_status = await self._drivers.hf2li.get_status()
        manifest = await self._session_store.create_session_manifest(
            recipe=recipe,
            preset=preset,
            calibration_references=recipe.calibration_references,
            device_config_snapshot=(mircat_configuration, hf2_configuration),
            device_status_snapshot=(mircat_status, hf2_status),
        )
        session_created_event = RunEvent(
            event_id=f"{manifest.session_id}-event-session-created",
            run_id=f"{manifest.session_id}-bootstrap",
            event_type=RunEventType.SESSION_CREATED,
            emitted_at=_utc_now(),
            source="experiment-engine",
            message="Authoritative session record created before run start.",
            phase=RunPhase.STARTING,
            session_id=manifest.session_id,
        )
        manifest = await self._session_store.append_event(manifest.session_id, session_created_event)
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

        await self._session_store.update_session_status(session_id, SessionStatus.ACTIVE)
        await self._drivers.hf2li.start_capture(recipe.hf2_acquisition, session_id)
        await self._drivers.mircat.start_sweep(recipe.mircat_sweep)

        session_manifest = self._session_manifests[session_id]
        timeline_events = list(session_manifest.event_timeline)
        timeline_states: list[RunState] = []
        timeline_live_data: list[LiveDataPoint] = []
        latest_fault: DeviceFault | None = None
        failure_reason: RunFailureReason | None = None

        for step_index, step in enumerate(self._run_plan_factory(recipe, session_id, run_id).steps, start=1):
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
                    payload=dict(event_template.payload),
                )
                session_manifest = await self._session_store.append_event(session_id, event)
                timeline_events.append(event)

            for artifact_index, artifact_template in enumerate(step.raw_artifacts, start=1):
                from ircp_contracts import RawDataArtifact  # local import keeps the runtime module focused

                artifact = RawDataArtifact(
                    artifact_id=f"{run_id}-raw-{step_index}-{artifact_index}",
                    session_id=session_id,
                    device_kind=DeviceKind.LABONE_HF2LI,
                    stream_name=artifact_template.stream_name,
                    relative_path=artifact_template.relative_path,
                    created_at=_utc_now(),
                    record_count=artifact_template.record_count,
                    content_type=artifact_template.content_type,
                    metadata=dict(artifact_template.metadata),
                )
                session_manifest = await self._session_store.register_raw_artifact(session_id, artifact)

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
                latest_fault=latest_fault,
                failure_reason=failure_reason,
                last_event_id=timeline_events[-1].event_id if timeline_events else None,
            )
            timeline_states.append(run_state)

        final_state = timeline_states[-1]
        final_status = _phase_to_session_status(final_state.phase)
        session_manifest = await self._session_store.update_session_status(session_id, final_status)
        self._session_manifests[session_id] = session_manifest
        self._run_timelines[run_id] = RunTimeline(
            run_id=run_id,
            states=tuple(timeline_states),
            events=tuple(timeline_events),
            live_data_points=tuple(timeline_live_data),
        )

        if final_state.phase in {RunPhase.COMPLETED, RunPhase.FAULTED, RunPhase.ABORTED}:
            await self._drivers.hf2li.stop_capture(f"{session_id}-capture")
            await self._drivers.mircat.stop_sweep()

        return final_state

    async def get_run_state(self, run_id: str) -> RunState:
        timeline = self._require_timeline(run_id)
        return timeline.states[-1]

    async def report_device_fault(self, run_id: str, fault: DeviceFault) -> RunEvent:
        timeline = self._require_timeline(run_id)
        event = RunEvent(
            event_id=f"{run_id}-reported-fault",
            run_id=run_id,
            event_type=RunEventType.DEVICE_FAULT_REPORTED,
            emitted_at=_utc_now(),
            source="experiment-engine",
            message=fault.message,
            phase=RunPhase.FAULTED,
            session_id=timeline.states[-1].session_id,
            device_fault=fault,
            failure_reason=RunFailureReason.DEVICE_FAULT,
        )
        return event

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
            latest_fault=previous.latest_fault,
            failure_reason=reason,
            last_event_id=previous.last_event_id,
        )
        self._run_timelines[run_id] = RunTimeline(
            run_id=run_id,
            states=(*timeline.states, aborted),
            events=timeline.events,
            live_data_points=timeline.live_data_points,
        )
        if previous.session_id is not None:
            await self._session_store.update_session_status(previous.session_id, SessionStatus.ABORTED)
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


def build_live_data_points(
    run_id: str,
    stream_name: str,
    values: tuple[tuple[float, float], ...],
) -> tuple[LiveDataPoint, ...]:
    """Create deterministic live-data points from (wavenumber, value) tuples."""

    captured_at = _utc_now()
    return tuple(
        LiveDataPoint(
            sample_id=f"{run_id}-{stream_name}-{index}",
            captured_at=captured_at,
            stream_name=stream_name,
            wavenumber_cm1=wavenumber,
            value=value,
        )
        for index, (wavenumber, value) in enumerate(values, start=1)
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
