"""Deterministic MIRcat + HF2LI simulator fixtures for Phase 3A."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ircp_contracts import (
    CONTRACT_VERSION,
    CalibrationReference,
    ConfigurationFieldDefinition,
    ConfigurationValueKind,
    DeviceCapability,
    DeviceConfiguration,
    DeviceFault,
    DeviceKind,
    DeviceLifecycleState,
    DeviceStatus,
    ExperimentPreset,
    ExperimentRecipe,
    HF2AcquisitionRecipe,
    HF2DemodulatorConfiguration,
    HF2SampleComponent,
    HF2StreamSelection,
    MircatLaserMode,
    MircatSweepRecipe,
    RawDataArtifact,
    RunEvent,
    RunEventType,
    RunFailureReason,
    RunPhase,
    SessionManifest,
    SessionStatus,
)
from ircp_drivers import HF2CaptureHandle, HF2CapabilityProfile, LabOneHF2Driver, MircatCapabilityProfile, MircatDriver
from ircp_experiment_engine.runtime import (
    RawArtifactTemplate,
    RunEventTemplate,
    RunExecutionPlan,
    RunPlanFactory,
    RunStepTemplate,
    StepOutcome,
    build_fault,
    build_live_data_points,
)

from .boundaries import GoldenPathSimulatorBundle, SimulatorCatalog


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _recipe_defaults() -> ExperimentRecipe:
    return ExperimentRecipe(
        recipe_id="mircat-hf2-golden-path",
        title="MIRcat sweep with HF2LI capture",
        mircat_sweep=MircatSweepRecipe(
            start_wavenumber_cm1=1700.0,
            end_wavenumber_cm1=1800.0,
            scan_speed_cm1_per_s=5.0,
            scan_count=1,
            bidirectional=False,
            laser_mode=MircatLaserMode.PULSED,
        ),
        hf2_acquisition=HF2AcquisitionRecipe(
            stream_selections=(
                HF2StreamSelection(demod_index=0, component=HF2SampleComponent.R),
            ),
            demodulators=(
                HF2DemodulatorConfiguration(demod_index=0, sample_rate_hz=224.9),
            ),
            capture_interval_seconds=0.05,
        ),
        session_label="Golden path scaffold",
        calibration_references=(
            CalibrationReference(
                calibration_id="mircat-hf2-baseline",
                version="phase3a.v1",
                kind="baseline",
                location="simulators/fixtures/calibration/mircat_hf2_baseline.json",
            ),
        ),
    )


def _preset_defaults(recipe: ExperimentRecipe) -> ExperimentPreset:
    return ExperimentPreset(
        preset_id="preset-mircat-hf2-default",
        name="Golden path default",
        recipe=recipe,
        description="Single MIRcat sweep with one HF2 demodulator capture.",
    )


def _mircat_capability() -> MircatCapabilityProfile:
    return MircatCapabilityProfile(
        capability=DeviceCapability(
            device_kind=DeviceKind.MIRCAT,
            model="Daylight MIRcat (simulated)",
            supported_actions=("arm", "tune", "start_sweep", "stop_sweep"),
            configuration_fields=(
                ConfigurationFieldDefinition(
                    key="start_wavenumber_cm1",
                    value_kind=ConfigurationValueKind.FLOAT,
                    required=True,
                    description="Sweep start wavenumber.",
                    units="cm^-1",
                ),
                ConfigurationFieldDefinition(
                    key="end_wavenumber_cm1",
                    value_kind=ConfigurationValueKind.FLOAT,
                    required=True,
                    description="Sweep end wavenumber.",
                    units="cm^-1",
                ),
                ConfigurationFieldDefinition(
                    key="scan_speed_cm1_per_s",
                    value_kind=ConfigurationValueKind.FLOAT,
                    required=True,
                    description="Sweep speed.",
                    units="cm^-1/s",
                ),
            ),
            notes=("Phase 3A supports MIRcat sweep mode only.",),
        )
    )


def _hf2_capability() -> HF2CapabilityProfile:
    return HF2CapabilityProfile(
        capability=DeviceCapability(
            device_kind=DeviceKind.LABONE_HF2LI,
            model="Zurich Instruments HF2LI (simulated)",
            supported_actions=("start_capture", "stop_capture", "zero_demod_phase"),
            stream_components=_stream_components(),
            notes=("Phase 3A exposes the typed capture surface only.",),
        )
    )


def _stream_components() -> tuple[str, ...]:
    return tuple(component.value for component in HF2SampleComponent)


def _base_status(
    *,
    device_id: str,
    device_kind: DeviceKind,
    summary: str,
    lifecycle_state: DeviceLifecycleState = DeviceLifecycleState.IDLE,
    connected: bool = True,
    ready: bool = True,
    busy: bool = False,
) -> DeviceStatus:
    return DeviceStatus(
        device_id=device_id,
        device_kind=device_kind,
        lifecycle_state=lifecycle_state,
        connected=connected,
        ready=ready,
        busy=busy,
        updated_at=_utc_now(),
        status_summary=summary,
    )


class SimulatedMircatDriver(MircatDriver):
    device_kind = DeviceKind.MIRCAT

    def __init__(
        self,
        *,
        device_id: str,
        initial_status: DeviceStatus,
        active_faults: tuple[DeviceFault, ...] = (),
    ) -> None:
        self._device_id = device_id
        self._status = initial_status
        self._capability = _mircat_capability()
        self._active_faults = tuple(active_faults)
        self._configuration_counter = 0

    async def connect(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Connected and ready for MIRcat sweep preflight.",
        )
        return self._status

    async def disconnect(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Disconnected.",
            lifecycle_state=DeviceLifecycleState.DISCONNECTED,
            connected=False,
            ready=False,
        )
        return self._status

    async def get_capability(self) -> MircatCapabilityProfile:
        return self._capability

    async def get_status(self) -> DeviceStatus:
        return self._status

    async def apply_configuration(self, configuration: MircatSweepRecipe) -> DeviceConfiguration:
        self._configuration_counter += 1
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Sweep recipe applied.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return DeviceConfiguration(
            configuration_id=f"{self._device_id}-cfg-{self._configuration_counter}",
            device_id=self._device_id,
            device_kind=self.device_kind,
            applied_at=_utc_now(),
            settings={
                "start_wavenumber_cm1": configuration.start_wavenumber_cm1,
                "end_wavenumber_cm1": configuration.end_wavenumber_cm1,
                "scan_speed_cm1_per_s": configuration.scan_speed_cm1_per_s,
                "scan_count": configuration.scan_count,
                "bidirectional": configuration.bidirectional,
                "laser_mode": configuration.laser_mode.value,
            },
        )

    async def get_active_faults(self) -> tuple[DeviceFault, ...]:
        return self._active_faults

    async def arm(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Armed for a future sweep.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return self._status

    async def disarm(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Disarmed and idle.",
        )
        return self._status

    async def tune_to_wavenumber(self, wavenumber_cm1: float) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary=f"Tuned to {wavenumber_cm1:.1f} cm^-1.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return self._status

    async def set_emission_enabled(self, enabled: bool) -> DeviceStatus:
        action = "enabled" if enabled else "disabled"
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary=f"Emission {action}.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return self._status

    async def start_sweep(self, recipe: MircatSweepRecipe) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary=(
                f"Sweeping {recipe.start_wavenumber_cm1:.1f}-{recipe.end_wavenumber_cm1:.1f} cm^-1."
            ),
            lifecycle_state=DeviceLifecycleState.RUNNING,
            ready=False,
            busy=True,
        )
        return self._status

    async def stop_sweep(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Sweep stopped. Ready for the next preflight.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return self._status


class SimulatedHF2Driver(LabOneHF2Driver):
    device_kind = DeviceKind.LABONE_HF2LI

    def __init__(
        self,
        *,
        device_id: str,
        initial_status: DeviceStatus,
    ) -> None:
        self._device_id = device_id
        self._status = initial_status
        self._capability = _hf2_capability()
        self._configuration_counter = 0

    async def connect(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Connected and waiting for capture configuration.",
        )
        return self._status

    async def disconnect(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Disconnected.",
            lifecycle_state=DeviceLifecycleState.DISCONNECTED,
            connected=False,
            ready=False,
        )
        return self._status

    async def get_capability(self) -> HF2CapabilityProfile:
        return self._capability

    async def get_status(self) -> DeviceStatus:
        return self._status

    async def apply_configuration(self, configuration: HF2AcquisitionRecipe) -> DeviceConfiguration:
        self._configuration_counter += 1
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="HF2 acquisition configured.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return DeviceConfiguration(
            configuration_id=f"{self._device_id}-cfg-{self._configuration_counter}",
            device_id=self._device_id,
            device_kind=self.device_kind,
            applied_at=_utc_now(),
            settings={
                "capture_interval_seconds": configuration.capture_interval_seconds,
                "streams": ",".join(
                    f"demod{selection.demod_index}.{selection.component.value}"
                    for selection in configuration.stream_selections
                ),
                "demodulators": ",".join(
                    str(demod.demod_index) for demod in configuration.demodulators
                ),
            },
        )

    async def get_active_faults(self) -> tuple[DeviceFault, ...]:
        return ()

    async def start_capture(self, recipe: HF2AcquisitionRecipe, session_id: str) -> HF2CaptureHandle:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Capturing demodulator streams for the golden path run.",
            lifecycle_state=DeviceLifecycleState.RUNNING,
            ready=False,
            busy=True,
        )
        return HF2CaptureHandle(
            capture_id=f"{session_id}-capture",
            session_id=session_id,
            selected_streams=tuple(
                f"demod{selection.demod_index}.{selection.component.value}"
                for selection in recipe.stream_selections
            ),
            started_at=_utc_now(),
        )

    async def stop_capture(self, capture_id: str) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary="Capture stopped. Session artifacts are available for reopen.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return self._status

    async def zero_demod_phase(self, demod_index: int) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary=f"Demodulator {demod_index} phase zeroed.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return self._status


@dataclass(frozen=True)
class Phase3AScenarioContext:
    scenario_id: str
    label: str
    description: str
    bundle: GoldenPathSimulatorBundle
    recipe: ExperimentRecipe
    preset: ExperimentPreset
    run_plan_factory: RunPlanFactory
    initial_manifests: tuple[SessionManifest, ...] = ()


class Phase3ASimulatorCatalog(SimulatorCatalog):
    """Catalog of deterministic simulator scenarios for the first UI slice."""

    def __init__(self) -> None:
        self._contexts = {
            context.scenario_id: context for context in (
                _build_nominal_context(),
                _build_blocked_context(),
                _build_faulted_context(),
            )
        }

    async def create_bundle(self, scenario_id: str) -> GoldenPathSimulatorBundle:
        return self._require_context(scenario_id).bundle

    def get_context(self, scenario_id: str) -> Phase3AScenarioContext:
        return self._require_context(scenario_id)

    def list_contexts(self) -> tuple[Phase3AScenarioContext, ...]:
        return tuple(self._contexts.values())

    def _require_context(self, scenario_id: str) -> Phase3AScenarioContext:
        try:
            return self._contexts[scenario_id]
        except KeyError as exc:
            raise KeyError(f"Unknown simulator scenario: {scenario_id}") from exc


def _build_nominal_context() -> Phase3AScenarioContext:
    recipe = _recipe_defaults()
    preset = _preset_defaults(recipe)
    mircat = SimulatedMircatDriver(
        device_id="mircat-sim-1",
        initial_status=_base_status(
            device_id="mircat-sim-1",
            device_kind=DeviceKind.MIRCAT,
            summary="Connected and ready for MIRcat sweep preflight.",
        ),
    )
    hf2 = SimulatedHF2Driver(
        device_id="hf2-sim-1",
        initial_status=_base_status(
            device_id="hf2-sim-1",
            device_kind=DeviceKind.LABONE_HF2LI,
            summary="Connected and ready for HF2 capture preflight.",
        ),
    )
    saved_session = _build_saved_session(recipe, preset)
    return Phase3AScenarioContext(
        scenario_id="nominal",
        label="Nominal",
        description="Happy-path simulator flow for MIRcat sweep plus HF2LI capture.",
        bundle=GoldenPathSimulatorBundle(
            scenario_id="nominal",
            mircat=mircat,
            hf2li=hf2,
            description="Nominal simulator bundle.",
        ),
        recipe=recipe,
        preset=preset,
        run_plan_factory=_build_nominal_plan,
        initial_manifests=(saved_session,),
    )


def _build_blocked_context() -> Phase3AScenarioContext:
    recipe = _recipe_defaults()
    preset = _preset_defaults(recipe)
    mircat = SimulatedMircatDriver(
        device_id="mircat-sim-blocked",
        initial_status=_base_status(
            device_id="mircat-sim-blocked",
            device_kind=DeviceKind.MIRCAT,
            summary="MIRcat simulator intentionally offline for blocked-preflight coverage.",
            lifecycle_state=DeviceLifecycleState.DISCONNECTED,
            connected=False,
            ready=False,
        ),
    )
    hf2 = SimulatedHF2Driver(
        device_id="hf2-sim-blocked",
        initial_status=_base_status(
            device_id="hf2-sim-blocked",
            device_kind=DeviceKind.LABONE_HF2LI,
            summary="HF2 simulator connected and ready.",
        ),
    )
    return Phase3AScenarioContext(
        scenario_id="blocked",
        label="Blocked",
        description="Preflight blocked because MIRcat is offline.",
        bundle=GoldenPathSimulatorBundle(
            scenario_id="blocked",
            mircat=mircat,
            hf2li=hf2,
            description="Blocked preflight simulator bundle.",
        ),
        recipe=recipe,
        preset=preset,
        run_plan_factory=_build_nominal_plan,
    )


def _build_faulted_context() -> Phase3AScenarioContext:
    recipe = _recipe_defaults()
    preset = _preset_defaults(recipe)
    mircat = SimulatedMircatDriver(
        device_id="mircat-sim-fault",
        initial_status=_base_status(
            device_id="mircat-sim-fault",
            device_kind=DeviceKind.MIRCAT,
            summary="Connected and ready for the fault-injection scenario.",
        ),
    )
    hf2 = SimulatedHF2Driver(
        device_id="hf2-sim-fault",
        initial_status=_base_status(
            device_id="hf2-sim-fault",
            device_kind=DeviceKind.LABONE_HF2LI,
            summary="Connected and ready for the fault-injection scenario.",
        ),
    )
    return Phase3AScenarioContext(
        scenario_id="faulted",
        label="Faulted",
        description="Nominal start followed by an explicit HF2 vendor fault.",
        bundle=GoldenPathSimulatorBundle(
            scenario_id="faulted",
            mircat=mircat,
            hf2li=hf2,
            description="Faulted run simulator bundle.",
        ),
        recipe=recipe,
        preset=preset,
        run_plan_factory=_build_faulted_plan,
    )


def _build_nominal_plan(recipe: ExperimentRecipe, session_id: str, run_id: str) -> RunExecutionPlan:
    live_points = build_live_data_points(
        run_id,
        "demod0.r",
        (
            (recipe.mircat_sweep.start_wavenumber_cm1, 0.14),
            (1725.0, 0.18),
            (1750.0, 0.23),
            (1775.0, 0.19),
            (recipe.mircat_sweep.end_wavenumber_cm1, 0.17),
        ),
    )
    return RunExecutionPlan(
        steps=(
            RunStepTemplate(
                phase=RunPhase.STARTING,
                active_step="hf2_capture_armed",
                progress_fraction=0.1,
                message="HF2 capture armed before the MIRcat sweep begins.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RUN_STARTED,
                        source="experiment-engine",
                        message="HF2 capture started and MIRcat sweep launch is next.",
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.RUNNING,
                active_step="mircat_sweep",
                progress_fraction=0.55,
                message="MIRcat sweep is active and HF2 data is streaming.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.DEVICE_STATUS_CHANGED,
                        source="drivers.mircat",
                        message="MIRcat sweep is running against the configured wavenumber range.",
                    ),
                    RunEventTemplate(
                        event_type=RunEventType.RAW_ARTIFACT_REGISTERED,
                        source="data-pipeline",
                        message="Raw HF2 capture artifact registered against the active session.",
                    ),
                ),
                live_data_points=live_points,
                raw_artifacts=(
                    RawArtifactTemplate(
                        stream_name="demod0.r",
                        relative_path=f"sessions/{session_id}/raw/hf2/demod0_r.txt",
                        record_count=len(live_points),
                        metadata={"capture_interval_seconds": recipe.hf2_acquisition.capture_interval_seconds},
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.COMPLETED,
                active_step="session_complete",
                progress_fraction=1.0,
                message="The nominal simulator run completed and can be reopened from Results.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RUN_COMPLETED,
                        source="experiment-engine",
                        message="MIRcat sweep and HF2 capture completed successfully.",
                    ),
                ),
                live_data_points=live_points,
                outcome=StepOutcome.COMPLETE,
            ),
        )
    )


def _build_faulted_plan(recipe: ExperimentRecipe, session_id: str, run_id: str) -> RunExecutionPlan:
    live_points = build_live_data_points(
        run_id,
        "demod0.r",
        (
            (recipe.mircat_sweep.start_wavenumber_cm1, 0.14),
            (1730.0, 0.20),
            (1755.0, 0.27),
        ),
    )
    fault = build_fault(
        fault_id=f"{run_id}-hf2-overload",
        device_id="hf2-sim-fault",
        device_kind=DeviceKind.LABONE_HF2LI,
        code="hf2_capture_overload",
        message="HF2 capture faulted during the nominal sweep path.",
        vendor_code="LABONE:OVERLOAD",
        vendor_message="Simulated demodulator overload during capture.",
        context={"stream_name": "demod0.r"},
    )
    return RunExecutionPlan(
        steps=(
            RunStepTemplate(
                phase=RunPhase.STARTING,
                active_step="hf2_capture_armed",
                progress_fraction=0.1,
                message="HF2 capture armed before the MIRcat sweep begins.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RUN_STARTED,
                        source="experiment-engine",
                        message="Fault-injection scenario started on the canonical path.",
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.RUNNING,
                active_step="mircat_sweep",
                progress_fraction=0.45,
                message="The simulator progresses through the same single-path start sequence.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RAW_ARTIFACT_REGISTERED,
                        source="data-pipeline",
                        message="Partial raw HF2 capture artifact registered before the fault.",
                    ),
                ),
                live_data_points=live_points,
                raw_artifacts=(
                    RawArtifactTemplate(
                        stream_name="demod0.r",
                        relative_path=f"sessions/{session_id}/raw/hf2/demod0_r_partial.txt",
                        record_count=len(live_points),
                        metadata={"fault_injected": True},
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.FAULTED,
                active_step="faulted",
                progress_fraction=0.45,
                message="HF2 vendor fault surfaced explicitly and the run stopped.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.DEVICE_FAULT_REPORTED,
                        source="drivers.labone_hf2",
                        message="HF2 reported a simulated overload fault.",
                    ),
                ),
                live_data_points=live_points,
                outcome=StepOutcome.FAULT,
                latest_fault=fault,
                failure_reason=RunFailureReason.DEVICE_FAULT,
            ),
        )
    )


def _build_saved_session(recipe: ExperimentRecipe, preset: ExperimentPreset) -> SessionManifest:
    created_at = _utc_now()
    raw_artifact = RawDataArtifact(
        artifact_id="saved-session-raw-1",
        session_id="saved-session-001",
        device_kind=DeviceKind.LABONE_HF2LI,
        stream_name="demod0.r",
        relative_path="sessions/saved-session-001/raw/hf2/demod0_r.txt",
        created_at=created_at,
        record_count=5,
    )
    event = RunEvent(
        event_id="saved-session-event-complete",
        run_id="saved-run-001",
        event_type=RunEventType.RUN_COMPLETED,
        emitted_at=created_at,
        source="experiment-engine",
        message="Saved simulator session completed previously.",
        phase=RunPhase.COMPLETED,
        session_id="saved-session-001",
    )
    mircat_configuration = DeviceConfiguration(
        configuration_id="saved-mircat-config",
        device_id="mircat-sim-1",
        device_kind=DeviceKind.MIRCAT,
        applied_at=created_at,
        settings={
            "start_wavenumber_cm1": recipe.mircat_sweep.start_wavenumber_cm1,
            "end_wavenumber_cm1": recipe.mircat_sweep.end_wavenumber_cm1,
            "scan_speed_cm1_per_s": recipe.mircat_sweep.scan_speed_cm1_per_s,
        },
        version=CONTRACT_VERSION,
    )
    hf2_configuration = DeviceConfiguration(
        configuration_id="saved-hf2-config",
        device_id="hf2-sim-1",
        device_kind=DeviceKind.LABONE_HF2LI,
        applied_at=created_at,
        settings={"capture_interval_seconds": recipe.hf2_acquisition.capture_interval_seconds},
        version=CONTRACT_VERSION,
    )
    return SessionManifest(
        session_id="saved-session-001",
        version=CONTRACT_VERSION,
        created_at=created_at,
        updated_at=created_at,
        status=SessionStatus.COMPLETED,
        recipe_snapshot=recipe,
        device_config_snapshot=(mircat_configuration, hf2_configuration),
        calibration_references=recipe.calibration_references,
        raw_artifacts=(raw_artifact,),
        event_timeline=(event,),
        processing_outputs=(),
        analysis_outputs=(),
        export_artifacts=(),
        preset_snapshot=preset,
        device_status_snapshot=(
            _base_status(
                device_id="mircat-sim-1",
                device_kind=DeviceKind.MIRCAT,
                summary="Completed saved-session fixture.",
            ),
            _base_status(
                device_id="hf2-sim-1",
                device_kind=DeviceKind.LABONE_HF2LI,
                summary="Completed saved-session fixture.",
            ),
        ),
        notes=("Saved session fixture for Results reopen scaffolding.",),
    )
