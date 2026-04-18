"""Deterministic supported-v1 simulator fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Mapping

from ircp_contracts import (
    AcquisitionTimingMode,
    AnalogMonitorRoute,
    ArtifactSourceRole,
    CalibrationReference,
    CanonicalTimingBlock,
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
    HF2DemodulatorConfiguration,
    HF2PrimaryAcquisition,
    HF2SampleComponent,
    HF2StreamSelection,
    MircatEmissionMode,
    MircatExperimentConfiguration,
    MircatSpectralMode,
    MircatSweepScan,
    MuxOutputTarget,
    MuxRoute,
    MuxRouteSelection,
    MuxSignalDomain,
    PicoMonitoringMode,
    PicoSecondaryCapture,
    ProbeTimingMode,
    PicoCaptureSnapshot,
    RawDataArtifact,
    RunEvent,
    RunEventType,
    RunFailureReason,
    RunOutcomeSummary,
    RunPhase,
    SessionManifest,
    SessionStatus,
    SessionStatusTimestamp,
    T660MasterTimingConfiguration,
    T660SlaveTimingConfiguration,
    TimeToWavenumberMapping,
    TimingControllerIdentity,
    TimingControllerRole,
    TimingEvent,
    TimingMarker,
    TimingProgramSnapshot,
    TimingWindow,
    summarize_mux_routes,
    summarize_pico_capture,
)
from ircp_drivers import (
    ArduinoMuxCapabilityProfile,
    ArduinoMuxDriver,
    HF2CaptureHandle,
    HF2CapabilityProfile,
    LabOneHF2Driver,
    MircatCapabilityProfile,
    MircatDriver,
    PicoCapabilityProfile,
    PicoCaptureHandle,
    PicoScopeDriver,
    T660CapabilityProfile,
    T660TimingConfiguration,
    T660TimingDriver,
)
from ircp_experiment_engine.runtime import (
    RawArtifactTemplate,
    RunEventTemplate,
    RunExecutionPlan,
    RunPlanFactory,
    RunStepTemplate,
    StepOutcome,
    build_fault,
    build_live_data_points,
    build_pump_probe_summary,
    build_timing_summary,
)

from .boundaries import SimulatorCatalog, SupportedV1SimulatorBundle


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_wavenumber_cm1(value: float | None) -> str:
    if value is None:
        return "the selected wavenumber"
    return f"{value:.2f} cm^-1"


def _recipe_defaults(*, pico_mode: PicoMonitoringMode = PicoMonitoringMode.MONITOR_AND_RECORD) -> ExperimentRecipe:
    calibration = CalibrationReference(
        calibration_id="minimal-baseline-reference",
        version="supported-v1",
        kind="reference_context",
        location="simulators/fixtures/calibration/minimal_baseline_reference.json",
    )
    mapping = TimeToWavenumberMapping(
        mapping_id="mapping-minimal-baseline",
        calibration_reference_id=calibration.calibration_id,
        applicable_spectral_modes=(MircatSpectralMode.SINGLE_WAVELENGTH,),
        start_wavenumber_cm1=1845.0,
        end_wavenumber_cm1=1855.0,
        scan_speed_cm1_per_s=1.0,
        time_origin_offset_ns=0.0,
    )
    return ExperimentRecipe(
        recipe_id="minimal-baseline-experiment",
        title="Minimal baseline continuous acquisition",
        mircat=MircatExperimentConfiguration(
            emission_mode=MircatEmissionMode.CW,
            spectral_mode=MircatSpectralMode.SINGLE_WAVELENGTH,
            preferred_qcl=2,
            single_wavelength_cm1=1850.0,
        ),
        hf2_primary_acquisition=HF2PrimaryAcquisition(
            profile_name="continuous-r",
            stream_selections=(
                HF2StreamSelection(demod_index=0, component=HF2SampleComponent.R),
            ),
            demodulators=(
                HF2DemodulatorConfiguration(
                    demod_index=0,
                    sample_rate_hz=224.9,
                    harmonic=1,
                    time_constant_seconds=0.1,
                ),
            ),
            capture_interval_seconds=0.05,
        ),
        pump_shots_before_probe=0,
        probe_timing_mode=ProbeTimingMode.CONTINUOUS_PROBE,
        timing=_timing_defaults(),
        mux_route_selection=_mux_defaults(),
        pico_secondary_capture=PicoSecondaryCapture(
            mode=PicoMonitoringMode.DISABLED,
            trigger_marker=None,
            trigger_input=MuxOutputTarget.PICO_EXTERNAL_TRIGGER,
            capture_window_ns=None,
            sample_interval_ns=None,
            record_inputs=(),
        ),
        time_to_wavenumber_mapping=mapping,
        session_label="MIRcat 1850 cm^-1 baseline",
        calibration_references=(calibration,),
    )


def _timing_defaults() -> CanonicalTimingBlock:
    return _timing_block_defaults()


def _timing_block_defaults() -> CanonicalTimingBlock:
    return CanonicalTimingBlock(
        t0_label="master_cycle_start",
        master=T660MasterTimingConfiguration(
            device_identity=TimingControllerIdentity.T660_2_MASTER,
            role=TimingControllerRole.MASTER,
            master_clock_hz=10_000_000.0,
            cycle_period_ns=1_000_000.0,
            pump_fire_command=TimingEvent(TimingMarker.PUMP_FIRE_COMMAND, 0.0, 100.0),
            pump_qswitch_command=TimingEvent(TimingMarker.PUMP_QSWITCH_COMMAND, 140_000.0, 100.0),
            master_to_slave_trigger=TimingEvent(
                TimingMarker.MASTER_TO_SLAVE_TRIGGER,
                600_000.0,
                100.0,
            ),
        ),
        slave=T660SlaveTimingConfiguration(
            device_identity=TimingControllerIdentity.T660_1_SLAVE,
            role=TimingControllerRole.SLAVE,
            trigger_source=TimingMarker.MASTER_TO_SLAVE_TRIGGER,
            probe_trigger=TimingEvent(TimingMarker.PROBE_TRIGGER, 620_000.0, 100.0),
            probe_process_trigger=TimingEvent(TimingMarker.PROBE_PROCESS_TRIGGER, 624_000.0, 100.0),
            probe_enable_window=TimingWindow(TimingMarker.PROBE_ENABLE_WINDOW, 610_000.0, 40_000.0),
            slave_timing_marker=TimingEvent(TimingMarker.SLAVE_TIMING_MARKER, 620_000.0, 100.0),
        ),
        acquisition_timing_mode=AcquisitionTimingMode.CONTINUOUS,
        acquisition_reference_marker=None,
        selected_digital_markers=(),
    )


def _mux_defaults() -> MuxRouteSelection:
    return MuxRouteSelection(
        route_set_id="v1-monitor-default",
        route_set_name="HF2 R plus MIRcat trigger",
        channel_a=MuxRoute(
            target=MuxOutputTarget.PICO_CHANNEL_A,
            signal_domain=MuxSignalDomain.ANALOG_MONITOR,
            analog_source=AnalogMonitorRoute.HF2_AUX_R,
        ),
        channel_b=MuxRoute(
            target=MuxOutputTarget.PICO_CHANNEL_B,
            signal_domain=MuxSignalDomain.DIGITAL_MARKER,
            digital_marker=TimingMarker.MIRCAT_TRIGGER_OUT,
        ),
        external_trigger=MuxRoute(
            target=MuxOutputTarget.PICO_EXTERNAL_TRIGGER,
            signal_domain=MuxSignalDomain.DIGITAL_MARKER,
            digital_marker=TimingMarker.NDYAG_FIXED_SYNC,
        ),
    )


def _preset_defaults(recipe: ExperimentRecipe) -> ExperimentPreset:
    return ExperimentPreset(
        preset_id="preset-minimal-baseline",
        name="Minimal baseline default",
        recipe=recipe,
        description="Fixed MIRcat wavenumber with continuous HF2 acquisition and hidden timing support.",
    )


def _mircat_capability() -> MircatCapabilityProfile:
    return MircatCapabilityProfile(
        capability=DeviceCapability(
            device_kind=DeviceKind.MIRCAT,
            model="Daylight MIRcat (simulated)",
            supported_actions=("arm", "set_emission", "start_recipe", "stop_recipe"),
            notes=("Supported v1 simulator exposes pulsed/CW probe control and scan recipes.",),
        )
    )


def _hf2_capability() -> HF2CapabilityProfile:
    return HF2CapabilityProfile(
        capability=DeviceCapability(
            device_kind=DeviceKind.LABONE_HF2LI,
            model="Zurich Instruments HF2LI (simulated)",
            supported_actions=("start_capture", "stop_capture", "zero_demod_phase"),
            stream_components=tuple(component.value for component in HF2SampleComponent),
            notes=("HF2 remains the primary scientific raw-data authority.",),
        )
    )


def _t660_capability(
    *,
    identity: TimingControllerIdentity,
    role: TimingControllerRole,
    model: str,
) -> T660CapabilityProfile:
    return T660CapabilityProfile(
        capability=DeviceCapability(
            device_kind=DeviceKind.T660_TIMING,
            model=model,
            supported_actions=("apply_configuration", "arm_outputs", "stop_outputs"),
            supported_roles=(role.value,),
            notes=("Supported v1 models the Highland timing pair as one family with explicit master/slave roles.",),
        ),
        supported_identities=(identity,),
        supported_roles=(role,),
    )


def _mux_capability() -> ArduinoMuxCapabilityProfile:
    return ArduinoMuxCapabilityProfile(
        capability=DeviceCapability(
            device_kind=DeviceKind.ARDUINO_MUX,
            model="Arduino-controlled MUX (simulated)",
            supported_actions=("apply_configuration", "clear_routes"),
            supported_route_targets=tuple(target.value for target in MuxOutputTarget),
            notes=("The MUX is modeled as a selector rather than a mixed-signal combiner.",),
        )
    )


def _pico_capability() -> PicoCapabilityProfile:
    return PicoCapabilityProfile(
        capability=DeviceCapability(
            device_kind=DeviceKind.PICOSCOPE_5244D,
            model="PicoScope 5244D (simulated)",
            supported_actions=("apply_configuration", "start_capture", "stop_capture"),
            notes=("PicoScope is modeled as a secondary monitor and recording device only.",),
        )
    )


def _base_status(
    *,
    device_id: str,
    device_kind: DeviceKind,
    summary: str,
    lifecycle_state: DeviceLifecycleState = DeviceLifecycleState.IDLE,
    connected: bool = True,
    ready: bool = True,
    busy: bool = False,
    device_role: str | None = None,
    device_identity: str | None = None,
    vendor_status: dict[str, bool | int | float | str] | None = None,
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
        device_role=device_role,
        device_identity=device_identity,
        vendor_status=vendor_status or {},
    )


class SimulatedMircatDriver(MircatDriver):
    device_kind = DeviceKind.MIRCAT

    def __init__(self, *, initial_status: DeviceStatus) -> None:
        self._status = initial_status
        self._capability = _mircat_capability()
        self._configuration_counter = 0
        self._armed = False
        self._emission_enabled = False
        self._scan_active = False
        self._tuned_target_cm1: float | None = None
        self._spectral_mode = MircatSpectralMode.SINGLE_WAVELENGTH.value
        self._tune_state = "idle"

    async def connect(self) -> DeviceStatus:
        self._tune_state = "idle"
        self._status = _base_status(
            device_id="mircat-qcl",
            device_kind=self.device_kind,
            summary="MIRcat connected and idle.",
            vendor_status=self._vendor_status(),
        )
        return self._status

    async def disconnect(self) -> DeviceStatus:
        self._armed = False
        self._emission_enabled = False
        self._scan_active = False
        self._tune_state = "idle"
        self._status = _base_status(
            device_id="mircat-qcl",
            device_kind=self.device_kind,
            summary="MIRcat disconnected.",
            lifecycle_state=DeviceLifecycleState.DISCONNECTED,
            connected=False,
            ready=False,
            vendor_status=self._vendor_status(),
        )
        return self._status

    async def get_capability(self) -> MircatCapabilityProfile:
        return self._capability

    async def get_status(self) -> DeviceStatus:
        return self._status

    async def apply_configuration(self, configuration: MircatExperimentConfiguration) -> DeviceConfiguration:
        self._configuration_counter += 1
        self._scan_active = False
        self._tuned_target_cm1 = configuration.single_wavelength_cm1
        self._spectral_mode = configuration.spectral_mode.value
        self._tune_state = "tuning" if configuration.spectral_mode == MircatSpectralMode.SINGLE_WAVELENGTH else "idle"
        self._status = _base_status(
            device_id="mircat-qcl",
            device_kind=self.device_kind,
            summary=(
                f"MIRcat tuning to {_format_wavenumber_cm1(configuration.single_wavelength_cm1)}."
                if configuration.spectral_mode == MircatSpectralMode.SINGLE_WAVELENGTH
                else f"MIRcat {configuration.spectral_mode.value.replace('_', ' ')} recipe staged."
            ),
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            vendor_status=self._vendor_status(),
        )
        return DeviceConfiguration(
            configuration_id=f"mircat-qcl-cfg-{self._configuration_counter}",
            device_id="mircat-qcl",
            device_kind=self.device_kind,
            applied_at=_utc_now(),
            settings={
                "emission_mode": configuration.emission_mode.value,
                "spectral_mode": configuration.spectral_mode.value,
                "pulse_rate_hz": configuration.pulse_rate_hz or 0.0,
                "preferred_qcl": configuration.preferred_qcl or -1,
            },
        )

    async def get_active_faults(self) -> tuple[DeviceFault, ...]:
        return self._status.reported_faults

    async def arm(self) -> DeviceStatus:
        self._armed = True
        if self._tuned_target_cm1 is not None and not self._scan_active:
            self._tune_state = "tuned"
        self._status = _base_status(
            device_id="mircat-qcl",
            device_kind=self.device_kind,
            summary=(
                f"MIRcat armed at {_format_wavenumber_cm1(self._tuned_target_cm1)}."
                if self._tuned_target_cm1 is not None
                else "MIRcat armed."
            ),
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            vendor_status=self._vendor_status(),
        )
        return self._status

    async def disarm(self) -> DeviceStatus:
        self._armed = False
        self._scan_active = False
        self._tune_state = "idle"
        self._status = _base_status(
            device_id="mircat-qcl",
            device_kind=self.device_kind,
            summary="MIRcat disarmed and idle.",
            vendor_status=self._vendor_status(),
        )
        return self._status

    async def set_emission_enabled(self, enabled: bool) -> DeviceStatus:
        self._emission_enabled = enabled
        if enabled and self._tuned_target_cm1 is not None and not self._scan_active:
            self._tune_state = "tuned"
        self._status = _base_status(
            device_id="mircat-qcl",
            device_kind=self.device_kind,
            summary=(
                f"MIRcat emission {'enabled' if enabled else 'disabled'} at "
                f"{_format_wavenumber_cm1(self._tuned_target_cm1)}."
                if self._tuned_target_cm1 is not None
                else f"MIRcat emission {'enabled' if enabled else 'disabled'}."
            ),
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            vendor_status=self._vendor_status(),
        )
        return self._status

    async def start_recipe(
        self,
        configuration: MircatExperimentConfiguration,
        probe_timing_mode: ProbeTimingMode,
    ) -> DeviceStatus:
        self._scan_active = True
        self._tuned_target_cm1 = configuration.single_wavelength_cm1
        self._spectral_mode = configuration.spectral_mode.value
        self._tune_state = "tuned" if configuration.spectral_mode == MircatSpectralMode.SINGLE_WAVELENGTH else "idle"
        if configuration.spectral_mode == MircatSpectralMode.SINGLE_WAVELENGTH:
            summary = f"MIRcat running at {_format_wavenumber_cm1(configuration.single_wavelength_cm1)}."
        else:
            summary = f"MIRcat {configuration.spectral_mode.value.replace('_', ' ')} active."
        self._status = _base_status(
            device_id="mircat-qcl",
            device_kind=self.device_kind,
            summary=summary,
            lifecycle_state=DeviceLifecycleState.RUNNING,
            ready=False,
            busy=True,
            vendor_status=self._vendor_status(),
        )
        return self._status

    async def stop_recipe(self) -> DeviceStatus:
        self._scan_active = False
        self._tuned_target_cm1 = None
        self._tune_state = "idle"
        self._status = _base_status(
            device_id="mircat-qcl",
            device_kind=self.device_kind,
            summary="MIRcat returned to idle.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            vendor_status=self._vendor_status(),
        )
        return self._status

    def _vendor_status(self) -> dict[str, bool | int | float | str]:
        vendor_status: dict[str, bool | int | float | str] = {
            "armed": self._armed,
            "emission_enabled": self._emission_enabled,
            "scan_active": self._scan_active,
            "spectral_mode": self._spectral_mode,
            "tune_state": self._tune_state,
        }
        if self._tuned_target_cm1 is not None:
            vendor_status["tuned_target_cm1"] = self._tuned_target_cm1
        return vendor_status


class SimulatedHF2Driver(LabOneHF2Driver):
    device_kind = DeviceKind.LABONE_HF2LI

    def __init__(self, *, initial_status: DeviceStatus, active_faults: tuple[DeviceFault, ...] = ()) -> None:
        self._status = initial_status
        self._capability = _hf2_capability()
        self._configuration_counter = 0
        self._active_faults = active_faults
        self._capture_active = False
        self._demod_index = 0
        self._component = HF2SampleComponent.R.value
        self._sample_rate_hz = 0.0
        self._harmonic = 1
        self._time_constant_seconds = 0.1
        self._capture_interval_seconds = 0.0
        self._acquisition_state = "idle"

    async def connect(self) -> DeviceStatus:
        self._acquisition_state = "idle"
        self._status = _base_status(
            device_id="hf2li-primary",
            device_kind=self.device_kind,
            summary="HF2LI connected and acquisition idle.",
            vendor_status=self._vendor_status(),
        )
        return self._status

    async def disconnect(self) -> DeviceStatus:
        self._capture_active = False
        self._acquisition_state = "idle"
        self._status = _base_status(
            device_id="hf2li-primary",
            device_kind=self.device_kind,
            summary="HF2LI disconnected.",
            lifecycle_state=DeviceLifecycleState.DISCONNECTED,
            connected=False,
            ready=False,
            vendor_status=self._vendor_status(),
        )
        return self._status

    async def get_capability(self) -> HF2CapabilityProfile:
        return self._capability

    async def get_status(self) -> DeviceStatus:
        return self._status

    async def apply_configuration(self, configuration: HF2PrimaryAcquisition) -> DeviceConfiguration:
        self._configuration_counter += 1
        self._capture_active = False
        self._acquisition_state = "idle"
        self._demod_index = configuration.demodulators[0].demod_index
        self._component = configuration.stream_selections[0].component.value
        self._sample_rate_hz = configuration.demodulators[0].sample_rate_hz
        self._harmonic = configuration.demodulators[0].harmonic
        self._time_constant_seconds = configuration.demodulators[0].time_constant_seconds or self._time_constant_seconds
        self._capture_interval_seconds = configuration.capture_interval_seconds
        self._status = _base_status(
            device_id="hf2li-primary",
            device_kind=self.device_kind,
            summary="HF2LI continuous acquisition configured.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            vendor_status=self._vendor_status(),
        )
        return DeviceConfiguration(
            configuration_id=f"hf2li-primary-cfg-{self._configuration_counter}",
            device_id="hf2li-primary",
            device_kind=self.device_kind,
            applied_at=_utc_now(),
            settings={
                "profile_name": configuration.profile_name,
                "capture_interval_seconds": configuration.capture_interval_seconds,
            },
        )

    async def get_active_faults(self) -> tuple[DeviceFault, ...]:
        return self._active_faults

    async def start_capture(self, recipe: HF2PrimaryAcquisition, session_id: str) -> HF2CaptureHandle:
        self._capture_active = True
        self._acquisition_state = "running"
        self._status = _base_status(
            device_id="hf2li-primary",
            device_kind=self.device_kind,
            summary=f"HF2LI acquisition running ({recipe.profile_name}).",
            lifecycle_state=DeviceLifecycleState.RUNNING,
            ready=False,
            busy=True,
            vendor_status=self._vendor_status(),
        )
        return HF2CaptureHandle(
            capture_id=f"{session_id}-hf2-capture",
            session_id=session_id,
            selected_streams=tuple(
                f"demod{selection.demod_index}.{selection.component.value}"
                for selection in recipe.stream_selections
            ),
            started_at=_utc_now(),
        )

    async def stop_capture(self, capture_id: str) -> DeviceStatus:
        self._capture_active = False
        self._acquisition_state = "stopped"
        self._status = _base_status(
            device_id="hf2li-primary",
            device_kind=self.device_kind,
            summary="HF2LI acquisition stopped.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            vendor_status=self._vendor_status(),
        )
        return self._status

    async def zero_demod_phase(self, demod_index: int) -> DeviceStatus:
        self._status = _base_status(
            device_id="hf2li-primary",
            device_kind=self.device_kind,
            summary=f"Demodulator {demod_index} phase zeroed.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            vendor_status=self._vendor_status(),
        )
        return self._status

    def _vendor_status(self) -> dict[str, bool | int | float | str]:
        return {
            "capture_active": self._capture_active,
            "acquisition_state": self._acquisition_state,
            "demod_index": self._demod_index,
            "component": self._component,
            "sample_rate_hz": self._sample_rate_hz,
            "harmonic": self._harmonic,
            "time_constant_seconds": self._time_constant_seconds,
            "capture_interval_seconds": self._capture_interval_seconds,
        }


class SimulatedT660Driver(T660TimingDriver):
    device_kind = DeviceKind.T660_TIMING

    def __init__(
        self,
        *,
        device_id: str,
        identity: TimingControllerIdentity,
        role: TimingControllerRole,
        initial_status: DeviceStatus,
    ) -> None:
        self._device_id = device_id
        self._identity = identity
        self._role = role
        self._status = initial_status
        self._capability = _t660_capability(
            identity=identity,
            role=role,
            model=f"Highland {identity.value} (simulated)",
        )
        self._configuration_counter = 0

    async def connect(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary=f"{self._role.value.title()} timing controller connected and ready.",
            device_role=self._role.value,
            device_identity=self._identity.value,
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
            device_role=self._role.value,
            device_identity=self._identity.value,
        )
        return self._status

    async def get_capability(self) -> T660CapabilityProfile:
        return self._capability

    async def get_status(self) -> DeviceStatus:
        return self._status

    async def apply_configuration(self, configuration: T660TimingConfiguration) -> DeviceConfiguration:
        self._configuration_counter += 1
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary=f"{self._role.value.title()} timing applied.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            device_role=self._role.value,
            device_identity=self._identity.value,
        )
        snapshot = (
            TimingProgramSnapshot(
                device_identity=configuration.device_identity,
                role=configuration.role,
                master_clock_hz=configuration.master_clock_hz,
                cycle_period_ns=configuration.cycle_period_ns,
                pump_fire_command=configuration.pump_fire_command,
                pump_qswitch_command=configuration.pump_qswitch_command,
                master_to_slave_trigger=configuration.master_to_slave_trigger,
            )
            if isinstance(configuration, T660MasterTimingConfiguration)
            else TimingProgramSnapshot(
                device_identity=configuration.device_identity,
                role=configuration.role,
                trigger_source=configuration.trigger_source.value,
                probe_trigger=configuration.probe_trigger,
                probe_process_trigger=configuration.probe_process_trigger,
                probe_enable_window=configuration.probe_enable_window,
                slave_timing_marker=configuration.slave_timing_marker,
            )
        )
        return DeviceConfiguration(
            configuration_id=f"{self._device_id}-cfg-{self._configuration_counter}",
            device_id=self._device_id,
            device_kind=self.device_kind,
            applied_at=_utc_now(),
            settings={
                "role": self._role.value,
                "device_identity": self._identity.value,
            },
            timing_program=snapshot,
        )

    async def get_active_faults(self) -> tuple[DeviceFault, ...]:
        return self._status.reported_faults

    async def arm_outputs(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary=f"{self._role.value.title()} timing outputs armed.",
            lifecycle_state=DeviceLifecycleState.RUNNING,
            ready=False,
            busy=True,
            device_role=self._role.value,
            device_identity=self._identity.value,
        )
        return self._status

    async def stop_outputs(self) -> DeviceStatus:
        self._status = _base_status(
            device_id=self._device_id,
            device_kind=self.device_kind,
            summary=f"{self._role.value.title()} timing outputs stopped.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            device_role=self._role.value,
            device_identity=self._identity.value,
        )
        return self._status


class SimulatedArduinoMuxDriver(ArduinoMuxDriver):
    device_kind = DeviceKind.ARDUINO_MUX

    def __init__(self, *, initial_status: DeviceStatus) -> None:
        self._status = initial_status
        self._capability = _mux_capability()
        self._configuration_counter = 0

    async def connect(self) -> DeviceStatus:
        self._status = _base_status(
            device_id="arduino-mux",
            device_kind=self.device_kind,
            summary="MUX controller connected and ready to select scope routes.",
        )
        return self._status

    async def disconnect(self) -> DeviceStatus:
        self._status = _base_status(
            device_id="arduino-mux",
            device_kind=self.device_kind,
            summary="Disconnected.",
            lifecycle_state=DeviceLifecycleState.DISCONNECTED,
            connected=False,
            ready=False,
        )
        return self._status

    async def get_capability(self) -> ArduinoMuxCapabilityProfile:
        return self._capability

    async def get_status(self) -> DeviceStatus:
        return self._status

    async def apply_configuration(self, configuration: MuxRouteSelection) -> DeviceConfiguration:
        self._configuration_counter += 1
        summary = summarize_mux_routes(configuration)
        self._status = DeviceStatus(
            device_id="arduino-mux",
            device_kind=self.device_kind,
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            connected=True,
            ready=True,
            busy=False,
            updated_at=_utc_now(),
            status_summary=f"Routes applied: {summary.channel_a}, {summary.channel_b}, trigger {summary.external_trigger}.",
            mux_route_selection=configuration,
        )
        return DeviceConfiguration(
            configuration_id=f"arduino-mux-cfg-{self._configuration_counter}",
            device_id="arduino-mux",
            device_kind=self.device_kind,
            applied_at=_utc_now(),
            settings={
                "route_set_id": configuration.route_set_id,
                "route_set_name": configuration.route_set_name,
            },
            mux_route_selection=configuration,
        )

    async def get_active_faults(self) -> tuple[DeviceFault, ...]:
        return self._status.reported_faults

    async def clear_routes(self) -> DeviceStatus:
        self._status = _base_status(
            device_id="arduino-mux",
            device_kind=self.device_kind,
            summary="MUX routes cleared.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return self._status


class SimulatedPicoDriver(PicoScopeDriver):
    device_kind = DeviceKind.PICOSCOPE_5244D

    def __init__(self, *, initial_status: DeviceStatus) -> None:
        self._status = initial_status
        self._capability = _pico_capability()
        self._configuration_counter = 0

    async def connect(self) -> DeviceStatus:
        self._status = _base_status(
            device_id="picoscope-5244d",
            device_kind=self.device_kind,
            summary="PicoScope connected and ready for optional monitoring.",
        )
        return self._status

    async def disconnect(self) -> DeviceStatus:
        self._status = _base_status(
            device_id="picoscope-5244d",
            device_kind=self.device_kind,
            summary="Disconnected.",
            lifecycle_state=DeviceLifecycleState.DISCONNECTED,
            connected=False,
            ready=False,
        )
        return self._status

    async def get_capability(self) -> PicoCapabilityProfile:
        return self._capability

    async def get_status(self) -> DeviceStatus:
        return self._status

    async def apply_configuration(self, configuration: PicoSecondaryCapture) -> DeviceConfiguration:
        self._configuration_counter += 1
        summary = summarize_pico_capture(configuration)
        self._status = DeviceStatus(
            device_id="picoscope-5244d",
            device_kind=self.device_kind,
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
            connected=self._status.connected,
            ready=self._status.connected,
            busy=False,
            updated_at=_utc_now(),
            status_summary=f"Pico configured for {summary.mode.value}.",
            pico_capture=PicoCaptureSnapshot(
                mode=summary.mode,
                trigger_marker=summary.trigger_marker.value if summary.trigger_marker else None,
                capture_window_ns=configuration.capture_window_ns,
                sample_interval_ns=configuration.sample_interval_ns,
                record_inputs=summary.recorded_inputs,
            ),
        )
        return DeviceConfiguration(
            configuration_id=f"picoscope-5244d-cfg-{self._configuration_counter}",
            device_id="picoscope-5244d",
            device_kind=self.device_kind,
            applied_at=_utc_now(),
            settings={"mode": configuration.mode.value},
            pico_capture=configuration,
        )

    async def get_active_faults(self) -> tuple[DeviceFault, ...]:
        return self._status.reported_faults

    async def start_capture(
        self,
        configuration: PicoSecondaryCapture,
        session_id: str,
    ) -> PicoCaptureHandle | None:
        if configuration.mode == PicoMonitoringMode.DISABLED:
            return None
        self._status = _base_status(
            device_id="picoscope-5244d",
            device_kind=self.device_kind,
            summary=f"Pico {configuration.mode.value} is active.",
            lifecycle_state=DeviceLifecycleState.RUNNING,
            ready=False,
            busy=True,
        )
        return PicoCaptureHandle(
            capture_id=f"{session_id}-pico-capture",
            session_id=session_id,
            started_at=_utc_now(),
            monitored_inputs=tuple(item.value for item in configuration.record_inputs),
        )

    async def stop_capture(self, capture_id: str) -> DeviceStatus:
        self._status = _base_status(
            device_id="picoscope-5244d",
            device_kind=self.device_kind,
            summary="Pico capture stopped. Secondary monitor artifacts are available when enabled.",
            lifecycle_state=DeviceLifecycleState.CONFIGURED,
        )
        return self._status


@dataclass(frozen=True)
class SimulatorScenarioContext:
    scenario_id: str
    label: str
    description: str
    bundle: SupportedV1SimulatorBundle
    recipe: ExperimentRecipe
    preset: ExperimentPreset
    run_plan_factory: RunPlanFactory
    initial_manifests: tuple[SessionManifest, ...] = ()
    initial_raw_artifact_payloads: Mapping[str, tuple[dict[str, object], ...]] = field(default_factory=dict)


class SupportedV1SimulatorCatalog(SimulatorCatalog):
    """Catalog of deterministic simulator scenarios for the minimal Experiment shell."""

    def __init__(self) -> None:
        self._contexts = {
            context.scenario_id: context
            for context in (
                _build_nominal_context(),
                _build_blocked_timing_context(),
                _build_faulted_context(),
                _build_pico_optional_context(),
            )
        }

    async def create_bundle(self, scenario_id: str) -> SupportedV1SimulatorBundle:
        return self._require_context(scenario_id).bundle

    def get_context(self, scenario_id: str) -> SimulatorScenarioContext:
        return self._require_context(scenario_id)

    def list_contexts(self) -> tuple[SimulatorScenarioContext, ...]:
        return tuple(self._contexts.values())

    def _require_context(self, scenario_id: str) -> SimulatorScenarioContext:
        try:
            return self._contexts[scenario_id]
        except KeyError as exc:
            raise KeyError(f"Unknown simulator scenario: {scenario_id}") from exc


def _build_nominal_context() -> SimulatorScenarioContext:
    recipe = _recipe_defaults()
    preset = _preset_defaults(recipe)
    bundle = _build_bundle(description="Nominal minimal-baseline simulator bundle.")
    saved_session, saved_payloads = _build_saved_session_fixture(recipe, preset)
    return SimulatorScenarioContext(
        scenario_id="nominal",
        label="Nominal",
        description="Fixed MIRcat wavelength with continuous HF2 acquisition.",
        bundle=bundle,
        recipe=recipe,
        preset=preset,
        run_plan_factory=_build_nominal_plan,
        initial_manifests=(saved_session,),
        initial_raw_artifact_payloads=saved_payloads,
    )


def _build_blocked_timing_context() -> SimulatorScenarioContext:
    recipe = _recipe_defaults()
    preset = _preset_defaults(recipe)
    bundle = _build_bundle(
        slave_status=_base_status(
            device_id="t660-1-slave",
            device_kind=DeviceKind.T660_TIMING,
            summary="Slave timing controller intentionally offline for blocked preflight coverage.",
            lifecycle_state=DeviceLifecycleState.DISCONNECTED,
            connected=False,
            ready=False,
            device_role=TimingControllerRole.SLAVE.value,
            device_identity=TimingControllerIdentity.T660_1_SLAVE.value,
        ),
        description="Blocked preflight bundle with missing slave timing controller.",
    )
    return SimulatorScenarioContext(
        scenario_id="blocked_timing",
        label="Blocked Timing",
        description="A hidden timing dependency is unavailable, so the experiment cannot start.",
        bundle=bundle,
        recipe=recipe,
        preset=preset,
        run_plan_factory=_build_nominal_plan,
    )


def _build_faulted_context() -> SimulatorScenarioContext:
    recipe = _recipe_defaults()
    preset = _preset_defaults(recipe)
    bundle = _build_bundle(description="Fault-injection bundle with a deterministic HF2 fault.")
    return SimulatorScenarioContext(
        scenario_id="faulted_hf2",
        label="Faulted HF2",
        description="The experiment starts normally, then faults explicitly on the HF2 path.",
        bundle=bundle,
        recipe=recipe,
        preset=preset,
        run_plan_factory=_build_faulted_plan,
    )


def _build_pico_optional_context() -> SimulatorScenarioContext:
    recipe = _recipe_defaults()
    preset = _preset_defaults(recipe)
    bundle = _build_bundle(
        pico_status=_base_status(
            device_id="picoscope-5244d",
            device_kind=DeviceKind.PICOSCOPE_5244D,
            summary="PicoScope disconnected. The run may proceed without secondary monitoring.",
            lifecycle_state=DeviceLifecycleState.DISCONNECTED,
            connected=False,
            ready=False,
        ),
        description="Optional Pico unavailable bundle.",
    )
    return SimulatorScenarioContext(
        scenario_id="pico_optional",
        label="Pico Optional",
        description="Pico remains outside the main experiment flow for this MVP.",
        bundle=bundle,
        recipe=recipe,
        preset=preset,
        run_plan_factory=_build_nominal_without_pico_plan,
    )


def _build_bundle(
    *,
    slave_status: DeviceStatus | None = None,
    pico_status: DeviceStatus | None = None,
    description: str,
) -> SupportedV1SimulatorBundle:
    return SupportedV1SimulatorBundle(
        scenario_id="supported-v1",
        mircat=SimulatedMircatDriver(
            initial_status=_base_status(
                device_id="mircat-qcl",
                device_kind=DeviceKind.MIRCAT,
                summary="Connected and ready for fixed-wavelength probe control.",
            )
        ),
        hf2li=SimulatedHF2Driver(
            initial_status=_base_status(
                device_id="hf2li-primary",
                device_kind=DeviceKind.LABONE_HF2LI,
                summary="Connected and ready for continuous HF2 acquisition.",
            )
        ),
        t660_master=SimulatedT660Driver(
            device_id="t660-2-master",
            identity=TimingControllerIdentity.T660_2_MASTER,
            role=TimingControllerRole.MASTER,
            initial_status=_base_status(
                device_id="t660-2-master",
                device_kind=DeviceKind.T660_TIMING,
                summary="Master timing controller connected and ready.",
                device_role=TimingControllerRole.MASTER.value,
                device_identity=TimingControllerIdentity.T660_2_MASTER.value,
            ),
        ),
        t660_slave=SimulatedT660Driver(
            device_id="t660-1-slave",
            identity=TimingControllerIdentity.T660_1_SLAVE,
            role=TimingControllerRole.SLAVE,
            initial_status=slave_status
            or _base_status(
                device_id="t660-1-slave",
                device_kind=DeviceKind.T660_TIMING,
                summary="Slave timing controller connected and ready.",
                device_role=TimingControllerRole.SLAVE.value,
                device_identity=TimingControllerIdentity.T660_1_SLAVE.value,
            ),
        ),
        mux=SimulatedArduinoMuxDriver(
            initial_status=_base_status(
                device_id="arduino-mux",
                device_kind=DeviceKind.ARDUINO_MUX,
                summary="MUX controller connected and ready.",
            )
        ),
        picoscope=SimulatedPicoDriver(
            initial_status=pico_status
            or _base_status(
                device_id="picoscope-5244d",
                device_kind=DeviceKind.PICOSCOPE_5244D,
                summary="PicoScope connected and ready for secondary monitoring.",
            )
        ),
        description=description,
    )


def _build_nominal_plan(recipe: ExperimentRecipe, session_id: str, run_id: str) -> RunExecutionPlan:
    hf2_live_points = build_live_data_points(
        run_id,
        "hf2.demod0.r",
        "Elapsed time",
        "s",
        (
            (0.0, 0.14),
            (1.0, 0.18),
            (2.0, 0.23),
            (3.0, 0.19),
            (4.0, 0.17),
        ),
    )
    return RunExecutionPlan(
        steps=(
            RunStepTemplate(
                phase=RunPhase.STARTING,
                active_step="probe_and_acquisition_armed",
                progress_fraction=0.15,
                message="The fixed-wavelength baseline experiment is starting.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RUN_STARTED,
                        source="experiment",
                        message="Experiment started.",
                    ),
                    RunEventTemplate(
                        event_type=RunEventType.DEVICE_STATUS_CHANGED,
                        source="laser",
                        message=f"MIRcat tuned to {_format_wavenumber_cm1(recipe.mircat.single_wavelength_cm1)}.",
                    ),
                    RunEventTemplate(
                        event_type=RunEventType.DEVICE_STATUS_CHANGED,
                        source="laser",
                        message="Emission enabled.",
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.RUNNING,
                active_step="continuous_primary_acquisition",
                progress_fraction=0.6,
                message="Primary HF2LI acquisition is running at the fixed MIRcat wavelength.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.DEVICE_STATUS_CHANGED,
                        source="hf2li",
                        message="Acquisition started.",
                    ),
                    RunEventTemplate(
                        event_type=RunEventType.RAW_ARTIFACT_REGISTERED,
                        source="hf2li",
                        message="HF2LI primary artifact registered.",
                    ),
                ),
                live_data_points=hf2_live_points,
                raw_artifacts=(
                    RawArtifactTemplate(
                        device_kind=DeviceKind.LABONE_HF2LI,
                        stream_name="hf2.demod0.r",
                        relative_path=f"sessions/{session_id}/artifacts/raw/hf2_continuous_r.parquet",
                        record_count=len(hf2_live_points),
                        source_role=ArtifactSourceRole.PRIMARY_RAW,
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.COMPLETED,
                active_step="session_complete",
                progress_fraction=1.0,
                message="The baseline experiment is complete and the session can be reopened.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.DEVICE_STATUS_CHANGED,
                        source="hf2li",
                        message="Acquisition stopped.",
                    ),
                    RunEventTemplate(
                        event_type=RunEventType.RUN_COMPLETED,
                        source="experiment",
                        message="Experiment stopped.",
                    ),
                ),
                live_data_points=hf2_live_points,
                outcome=StepOutcome.COMPLETE,
            ),
        )
    )


def _build_nominal_without_pico_plan(recipe: ExperimentRecipe, session_id: str, run_id: str) -> RunExecutionPlan:
    hf2_live_points = build_live_data_points(
        run_id,
        "hf2.demod0.r",
        "Elapsed time",
        "s",
        (
            (0.0, 0.14),
            (1.0, 0.18),
            (2.0, 0.22),
            (3.0, 0.20),
            (4.0, 0.16),
        ),
    )
    return RunExecutionPlan(
        steps=(
            RunStepTemplate(
                phase=RunPhase.STARTING,
                active_step="probe_and_acquisition_armed",
                progress_fraction=0.15,
                message="The tuned probe and continuous HF2 acquisition are armed for the experiment.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RUN_STARTED,
                        source="experiment-engine",
                        message="The minimal baseline experiment started on the canonical path.",
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.RUNNING,
                active_step="continuous_primary_acquisition",
                progress_fraction=0.65,
                message="HF2 continuous acquisition is recording the primary signal at the tuned wavelength.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RAW_ARTIFACT_REGISTERED,
                        source="data-pipeline",
                        message="Primary HF2 raw capture registered for the active session.",
                    ),
                ),
                live_data_points=hf2_live_points,
                raw_artifacts=(
                    RawArtifactTemplate(
                        device_kind=DeviceKind.LABONE_HF2LI,
                        stream_name="hf2.demod0.r",
                        relative_path=f"sessions/{session_id}/artifacts/raw/hf2_continuous_r.parquet",
                        record_count=len(hf2_live_points),
                        source_role=ArtifactSourceRole.PRIMARY_RAW,
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.COMPLETED,
                active_step="session_complete",
                progress_fraction=1.0,
                message="The experiment completed and can be reopened from Results.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RUN_COMPLETED,
                        source="experiment-engine",
                        message="Fixed-wavelength probing and continuous HF2 acquisition completed successfully.",
                    ),
                ),
                live_data_points=hf2_live_points,
                outcome=StepOutcome.COMPLETE,
            ),
        )
    )


def _build_faulted_plan(recipe: ExperimentRecipe, session_id: str, run_id: str) -> RunExecutionPlan:
    hf2_live_points = build_live_data_points(
        run_id,
        "hf2.demod0.r",
        "Wavenumber",
        "cm^-1",
        (
            (1700.0, 0.14),
            (1730.0, 0.20),
            (1755.0, 0.27),
        ),
    )
    pico_live_points = build_live_data_points(
        run_id,
        "pico.channel_a",
        "Time",
        "ns",
        (
            (0.0, 0.02),
            (150.0, 0.41),
            (600.0, 0.73),
        ),
        source_role=ArtifactSourceRole.SECONDARY_MONITOR,
    )
    fault = build_fault(
        fault_id=f"{run_id}-hf2-overload",
        device_id="hf2li-primary",
        device_kind=DeviceKind.LABONE_HF2LI,
        code="hf2_capture_overload",
        message="HF2 primary capture faulted during the supported-v1 run.",
        vendor_code="LABONE:OVERLOAD",
        vendor_message="Simulated demodulator overload during capture.",
        context={"stream_name": "hf2.demod0.r"},
    )
    return RunExecutionPlan(
        steps=(
            RunStepTemplate(
                phase=RunPhase.STARTING,
                active_step="timing_and_primary_capture_armed",
                progress_fraction=0.15,
                message="The run begins on the same single-path supported-v1 sequence.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RUN_STARTED,
                        source="experiment-engine",
                        message="Fault-injection scenario started on the canonical supported-v1 path.",
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.RUNNING,
                active_step="partial_capture_before_fault",
                progress_fraction=0.45,
                message="Partial primary and secondary artifacts are registered before the explicit HF2 fault.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RAW_ARTIFACT_REGISTERED,
                        source="data-pipeline",
                        message="Partial HF2 primary artifact registered before the fault.",
                    ),
                    RunEventTemplate(
                        event_type=RunEventType.RAW_ARTIFACT_REGISTERED,
                        source="data-pipeline",
                        message="Partial Pico secondary artifact registered before the fault.",
                    ),
                ),
                live_data_points=(*hf2_live_points, *pico_live_points),
                raw_artifacts=(
                    RawArtifactTemplate(
                        device_kind=DeviceKind.LABONE_HF2LI,
                        stream_name="hf2.demod0.r",
                        relative_path=f"sessions/{session_id}/artifacts/raw/hf2_demod0_r_partial.parquet",
                        record_count=len(hf2_live_points),
                        source_role=ArtifactSourceRole.PRIMARY_RAW,
                        metadata={"fault_injected": True},
                    ),
                    RawArtifactTemplate(
                        device_kind=DeviceKind.PICOSCOPE_5244D,
                        stream_name="pico.channel_a",
                        relative_path=f"sessions/{session_id}/artifacts/raw/pico_channel_a_trace_partial.parquet",
                        record_count=len(pico_live_points),
                        source_role=ArtifactSourceRole.SECONDARY_MONITOR,
                        mux_output_target=MuxOutputTarget.PICO_CHANNEL_A.value,
                        related_marker=TimingMarker.NDYAG_FIXED_SYNC.value,
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.FAULTED,
                active_step="faulted",
                progress_fraction=0.45,
                message="The explicit HF2 vendor fault is surfaced and the coordinated run stops.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.DEVICE_FAULT_REPORTED,
                        source="drivers.labone_hf2",
                        message="HF2 reported a simulated overload fault on the canonical path.",
                    ),
                ),
                live_data_points=(*hf2_live_points, *pico_live_points),
                outcome=StepOutcome.FAULT,
                latest_fault=fault,
                failure_reason=RunFailureReason.DEVICE_FAULT,
            ),
        )
    )


def _live_data_points_to_rows(live_data_points, *, device_kind: DeviceKind) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "acquisition_index": index,
            "sample_id": point.sample_id,
            "captured_at": point.captured_at.isoformat(),
            "device_kind": device_kind.value,
            "stream_name": point.stream_name,
            "axis_label": point.axis_label,
            "axis_units": point.axis_units,
            "axis_value": point.axis_value,
            "value": point.value,
            "units": point.units,
            "source_role": point.source_role.value,
            "mux_output_target": None,
            "related_marker": None,
            "metadata_json": json.dumps(dict(point.metadata or {}), sort_keys=True),
            "demod_index": 0 if point.stream_name.startswith("hf2.demod0.") else None,
            "component_name": point.stream_name.rsplit(".", 1)[-1] if point.stream_name.startswith("hf2.") else None,
            "channel_name": point.stream_name.split(".", 1)[1] if point.stream_name.startswith("pico.") else None,
        }
        for index, point in enumerate(live_data_points, start=1)
    )


def _build_saved_session_fixture(
    recipe: ExperimentRecipe,
    preset: ExperimentPreset,
) -> tuple[SessionManifest, dict[str, tuple[dict[str, object], ...]]]:
    manifest = _build_saved_session(recipe, preset)
    hf2_live_points = build_live_data_points(
        "saved-run-001",
        "hf2.demod0.r",
        "Elapsed time",
        "s",
        (
            (0.0, 0.14),
            (1.0, 0.18),
            (2.0, 0.23),
            (3.0, 0.19),
            (4.0, 0.17),
        ),
    )
    return manifest, {
        manifest.raw_artifacts[0].relative_path: _live_data_points_to_rows(
            hf2_live_points,
            device_kind=DeviceKind.LABONE_HF2LI,
        ),
    }


def _build_saved_session(recipe: ExperimentRecipe, preset: ExperimentPreset) -> SessionManifest:
    created_at = _utc_now()
    primary_raw = RawDataArtifact(
        artifact_id="saved-session-primary-raw-1",
        session_id="saved-session-001",
        device_kind=DeviceKind.LABONE_HF2LI,
        stream_name="hf2.demod0.r",
        relative_path="sessions/saved-session-001/artifacts/raw/hf2_continuous_r.parquet",
        created_at=created_at,
        record_count=5,
        content_type="application/vnd.apache.parquet",
        source_role=ArtifactSourceRole.PRIMARY_RAW,
        registered_by_event_id="saved-session-event-primary-raw",
    )
    events = (
        RunEvent(
            event_id="saved-session-event-created",
            run_id="saved-run-001",
            event_type=RunEventType.SESSION_CREATED,
            emitted_at=created_at,
            source="session",
            message="Session opened.",
            phase=RunPhase.STARTING,
            session_id="saved-session-001",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        ),
        RunEvent(
            event_id="saved-session-event-configured",
            run_id="saved-run-001",
            event_type=RunEventType.DEVICE_STATUS_CHANGED,
            emitted_at=created_at,
            source="laser",
            message=f"MIRcat tuned to {_format_wavenumber_cm1(recipe.mircat.single_wavelength_cm1)}.",
            phase=RunPhase.STARTING,
            session_id="saved-session-001",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        ),
        RunEvent(
            event_id="saved-session-event-emission-enabled",
            run_id="saved-run-001",
            event_type=RunEventType.DEVICE_STATUS_CHANGED,
            emitted_at=created_at,
            source="laser",
            message="Emission enabled.",
            phase=RunPhase.STARTING,
            session_id="saved-session-001",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        ),
        RunEvent(
            event_id="saved-session-event-run-started",
            run_id="saved-run-001",
            event_type=RunEventType.RUN_STARTED,
            emitted_at=created_at,
            source="experiment",
            message="Experiment started.",
            phase=RunPhase.STARTING,
            session_id="saved-session-001",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        ),
        RunEvent(
            event_id="saved-session-event-hf2-connected",
            run_id="saved-run-001",
            event_type=RunEventType.DEVICE_STATUS_CHANGED,
            emitted_at=created_at,
            source="hf2li",
            message="HF2LI connected.",
            phase=RunPhase.RUNNING,
            session_id="saved-session-001",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        ),
        RunEvent(
            event_id="saved-session-event-acquisition-started",
            run_id="saved-run-001",
            event_type=RunEventType.DEVICE_STATUS_CHANGED,
            emitted_at=created_at,
            source="hf2li",
            message="Acquisition started.",
            phase=RunPhase.RUNNING,
            session_id="saved-session-001",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        ),
        RunEvent(
            event_id="saved-session-event-primary-raw",
            run_id="saved-run-001",
            event_type=RunEventType.RAW_ARTIFACT_REGISTERED,
            emitted_at=created_at,
            source="hf2li",
            message="HF2LI primary artifact registered.",
            phase=RunPhase.RUNNING,
            session_id="saved-session-001",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        ),
        RunEvent(
            event_id="saved-session-event-acquisition-stopped",
            run_id="saved-run-001",
            event_type=RunEventType.DEVICE_STATUS_CHANGED,
            emitted_at=created_at,
            source="hf2li",
            message="Acquisition stopped.",
            phase=RunPhase.COMPLETED,
            session_id="saved-session-001",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        ),
        RunEvent(
            event_id="saved-session-event-complete",
            run_id="saved-run-001",
            event_type=RunEventType.RUN_COMPLETED,
            emitted_at=created_at,
            source="experiment",
            message="Experiment stopped.",
            phase=RunPhase.COMPLETED,
            session_id="saved-session-001",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        ),
    )
    master_configuration = DeviceConfiguration(
        configuration_id="saved-t660-master-config",
        device_id="t660-2-master",
        device_kind=DeviceKind.T660_TIMING,
        applied_at=created_at,
        settings={"role": TimingControllerRole.MASTER.value},
        timing_program=TimingProgramSnapshot(
            device_identity=recipe.timing.master.device_identity,
            role=recipe.timing.master.role,
            master_clock_hz=recipe.timing.master.master_clock_hz,
            cycle_period_ns=recipe.timing.master.cycle_period_ns,
            pump_fire_command=recipe.timing.master.pump_fire_command,
            pump_qswitch_command=recipe.timing.master.pump_qswitch_command,
            master_to_slave_trigger=recipe.timing.master.master_to_slave_trigger,
        ),
    )
    slave_configuration = DeviceConfiguration(
        configuration_id="saved-t660-slave-config",
        device_id="t660-1-slave",
        device_kind=DeviceKind.T660_TIMING,
        applied_at=created_at,
        settings={"role": TimingControllerRole.SLAVE.value},
        timing_program=TimingProgramSnapshot(
            device_identity=recipe.timing.slave.device_identity,
            role=recipe.timing.slave.role,
            trigger_source=recipe.timing.slave.trigger_source.value,
            probe_trigger=recipe.timing.slave.probe_trigger,
            probe_process_trigger=recipe.timing.slave.probe_process_trigger,
            probe_enable_window=recipe.timing.slave.probe_enable_window,
            slave_timing_marker=recipe.timing.slave.slave_timing_marker,
        ),
    )
    mircat_configuration = DeviceConfiguration(
        configuration_id="saved-mircat-config",
        device_id="mircat-qcl",
        device_kind=DeviceKind.MIRCAT,
        applied_at=created_at,
        settings={
            "emission_mode": recipe.mircat.emission_mode.value,
            "spectral_mode": recipe.mircat.spectral_mode.value,
        },
    )
    hf2_configuration = DeviceConfiguration(
        configuration_id="saved-hf2-config",
        device_id="hf2li-primary",
        device_kind=DeviceKind.LABONE_HF2LI,
        applied_at=created_at,
        settings={"profile_name": recipe.hf2_primary_acquisition.profile_name},
    )
    mux_configuration = DeviceConfiguration(
        configuration_id="saved-mux-config",
        device_id="arduino-mux",
        device_kind=DeviceKind.ARDUINO_MUX,
        applied_at=created_at,
        settings={"route_set_name": recipe.mux_route_selection.route_set_name},
        mux_route_selection=recipe.mux_route_selection,
    )
    return SessionManifest(
        session_id="saved-session-001",
        version="supported-v1",
        created_at=created_at,
        updated_at=created_at,
        status=SessionStatus.COMPLETED,
        recipe_snapshot=recipe,
        device_config_snapshot=(
            master_configuration,
            slave_configuration,
            mircat_configuration,
            hf2_configuration,
            mux_configuration,
        ),
        calibration_references=recipe.calibration_references,
        raw_artifacts=(primary_raw,),
        event_timeline=events,
        processing_outputs=(),
        analysis_outputs=(),
        export_artifacts=(),
        timing_summary=build_timing_summary(recipe),
        pump_probe_summary=build_pump_probe_summary(recipe),
        selected_markers=tuple(marker.value for marker in recipe.timing.selected_digital_markers),
        mux_route_snapshot=recipe.mux_route_selection,
        mux_summary=summarize_mux_routes(recipe.mux_route_selection),
        pico_capture_snapshot=recipe.pico_secondary_capture,
        pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
        time_to_wavenumber_mapping=recipe.time_to_wavenumber_mapping,
        preset_snapshot=preset,
        device_status_snapshot=(
            _base_status(
                device_id="mircat-qcl",
                device_kind=DeviceKind.MIRCAT,
                summary="Completed saved-session fixture.",
            ),
            _base_status(
                device_id="hf2li-primary",
                device_kind=DeviceKind.LABONE_HF2LI,
                summary="Completed saved-session fixture.",
            ),
            _base_status(
                device_id="t660-2-master",
                device_kind=DeviceKind.T660_TIMING,
                summary="Completed saved-session fixture.",
                device_role=TimingControllerRole.MASTER.value,
                device_identity=TimingControllerIdentity.T660_2_MASTER.value,
            ),
            _base_status(
                device_id="t660-1-slave",
                device_kind=DeviceKind.T660_TIMING,
                summary="Completed saved-session fixture.",
                device_role=TimingControllerRole.SLAVE.value,
                device_identity=TimingControllerIdentity.T660_1_SLAVE.value,
            ),
            _base_status(
                device_id="arduino-mux",
                device_kind=DeviceKind.ARDUINO_MUX,
                summary="Completed saved-session fixture.",
            ),
            _base_status(
                device_id="picoscope-5244d",
                device_kind=DeviceKind.PICOSCOPE_5244D,
                summary="Completed saved-session fixture.",
            ),
        ),
        status_timestamps=(
            SessionStatusTimestamp(status=SessionStatus.PLANNED, recorded_at=created_at, note="fixture created"),
            SessionStatusTimestamp(status=SessionStatus.ACTIVE, recorded_at=created_at, note="fixture running"),
            SessionStatusTimestamp(status=SessionStatus.COMPLETED, recorded_at=created_at, note="fixture completed"),
        ),
        outcome=RunOutcomeSummary(
            started_at=created_at,
            ended_at=created_at,
            final_event_id="saved-session-event-complete",
        ),
        notes=(
            "Saved session fixture for Results reopen scaffolding.",
            "sample_id:polymer-film-a12",
            "operator_notes:Fixed MIRcat baseline with continuous HF2LI acquisition.",
            "runtime_mode:simulator:nominal",
            "runtime_description:Supported-v1 nominal saved-session fixture.",
        ),
    )
