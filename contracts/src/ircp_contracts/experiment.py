"""Experiment recipe and preset contracts for the supported v1 slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .common import (
    AcquisitionTimingMode,
    AnalogMonitorRoute,
    CONTRACT_VERSION,
    DeviceKind,
    MuxOutputTarget,
    MuxSignalDomain,
    PicoMonitoringMode,
    ProbeTimingMode,
    TimingControllerIdentity,
    TimingControllerRole,
    TimingMarker,
)


class MircatEmissionMode(str, Enum):
    PULSED = "pulsed"
    CW = "cw"


class MircatSpectralMode(str, Enum):
    SINGLE_WAVELENGTH = "single_wavelength"
    SWEEP_SCAN = "sweep_scan"
    STEP_MEASURE_SCAN = "step_measure_scan"
    MULTISPECTRAL_SCAN = "multispectral_scan"


class HF2SampleComponent(str, Enum):
    X = "x"
    Y = "y"
    R = "r"
    PHASE = "phase"
    FREQUENCY = "frequency"
    TIMESTAMP = "timestamp"


@dataclass(frozen=True)
class CalibrationReference:
    calibration_id: str
    version: str
    kind: str
    location: str
    checksum_sha256: str | None = None


@dataclass(frozen=True)
class MircatSweepScan:
    start_wavenumber_cm1: float
    end_wavenumber_cm1: float
    scan_speed_cm1_per_s: float
    scan_count: int = 1
    bidirectional: bool = False

    def __post_init__(self) -> None:
        if self.start_wavenumber_cm1 <= 0:
            raise ValueError("Sweep start wavenumber must be positive.")
        if self.end_wavenumber_cm1 <= self.start_wavenumber_cm1:
            raise ValueError("Sweep end wavenumber must be greater than the start.")
        if self.scan_speed_cm1_per_s <= 0:
            raise ValueError("Sweep speed must be positive.")
        if self.scan_count < 1:
            raise ValueError("Sweep count must be at least one.")


@dataclass(frozen=True)
class MircatStepMeasureScan:
    start_wavenumber_cm1: float
    end_wavenumber_cm1: float
    step_size_cm1: float
    dwell_time_ms: float
    scan_count: int = 1

    def __post_init__(self) -> None:
        if self.end_wavenumber_cm1 <= self.start_wavenumber_cm1:
            raise ValueError("Step-measure scan end must be greater than the start.")
        if self.step_size_cm1 <= 0:
            raise ValueError("Step-measure scan step size must be positive.")
        if self.dwell_time_ms <= 0:
            raise ValueError("Step-measure scan dwell time must be positive.")
        if self.scan_count < 1:
            raise ValueError("Step-measure scan count must be at least one.")


@dataclass(frozen=True)
class MultispectralElement:
    target_wavenumber_cm1: float
    dwell_time_ms: float
    preferred_qcl: int | None = None

    def __post_init__(self) -> None:
        if self.target_wavenumber_cm1 <= 0:
            raise ValueError("Multispectral element wavenumber must be positive.")
        if self.dwell_time_ms <= 0:
            raise ValueError("Multispectral element dwell time must be positive.")


@dataclass(frozen=True)
class MircatMultispectralScan:
    elements: tuple[MultispectralElement, ...]
    sequence_count: int = 1

    def __post_init__(self) -> None:
        if not self.elements:
            raise ValueError("A multispectral scan requires at least one element.")
        if self.sequence_count < 1:
            raise ValueError("Multispectral sequence count must be at least one.")


@dataclass(frozen=True)
class MircatExperimentConfiguration:
    emission_mode: MircatEmissionMode
    spectral_mode: MircatSpectralMode
    preferred_qcl: int | None = None
    pulse_rate_hz: float | None = None
    pulse_width_ns: float | None = None
    single_wavelength_cm1: float | None = None
    sweep_scan: MircatSweepScan | None = None
    step_measure_scan: MircatStepMeasureScan | None = None
    multispectral_scan: MircatMultispectralScan | None = None

    def __post_init__(self) -> None:
        if self.pulse_rate_hz is not None and self.pulse_rate_hz <= 0:
            raise ValueError("Pulse rate must be positive when provided.")
        if self.pulse_width_ns is not None and self.pulse_width_ns <= 0:
            raise ValueError("Pulse width must be positive when provided.")
        if self.emission_mode == MircatEmissionMode.PULSED and self.pulse_rate_hz is None:
            raise ValueError("Pulsed MIRcat recipes require an explicit pulse rate.")
        if self.spectral_mode == MircatSpectralMode.SINGLE_WAVELENGTH:
            if self.single_wavelength_cm1 is None or self.single_wavelength_cm1 <= 0:
                raise ValueError("Single-wavelength recipes require a positive target wavenumber.")
        elif self.spectral_mode == MircatSpectralMode.SWEEP_SCAN:
            if self.sweep_scan is None:
                raise ValueError("Sweep-scan recipes require sweep settings.")
        elif self.spectral_mode == MircatSpectralMode.STEP_MEASURE_SCAN:
            if self.step_measure_scan is None:
                raise ValueError("Step-measure recipes require step-measure settings.")
        elif self.spectral_mode == MircatSpectralMode.MULTISPECTRAL_SCAN:
            if self.multispectral_scan is None:
                raise ValueError("Multispectral recipes require a multispectral sequence.")


@dataclass(frozen=True)
class HF2StreamSelection:
    demod_index: int
    component: HF2SampleComponent

    def __post_init__(self) -> None:
        if self.demod_index < 0:
            raise ValueError("HF2 demodulator index must be non-negative.")


@dataclass(frozen=True)
class HF2DemodulatorConfiguration:
    demod_index: int
    sample_rate_hz: float
    harmonic: int = 1
    phase_deg: float = 0.0
    enable_transfer: bool = True

    def __post_init__(self) -> None:
        if self.demod_index < 0:
            raise ValueError("HF2 demodulator index must be non-negative.")
        if self.sample_rate_hz <= 0:
            raise ValueError("HF2 sample rate must be positive.")
        if self.harmonic < 1:
            raise ValueError("HF2 harmonic must be at least one.")


@dataclass(frozen=True)
class HF2PrimaryAcquisition:
    profile_name: str
    stream_selections: tuple[HF2StreamSelection, ...]
    demodulators: tuple[HF2DemodulatorConfiguration, ...]
    capture_interval_seconds: float = 0.05
    preferred_device_id: str | None = None

    def __post_init__(self) -> None:
        if not self.stream_selections:
            raise ValueError("HF2 acquisition requires at least one stream selection.")
        if self.capture_interval_seconds <= 0:
            raise ValueError("HF2 capture interval must be positive.")
        selected_demods = {item.demod_index for item in self.stream_selections}
        configured_demods = {item.demod_index for item in self.demodulators}
        if not selected_demods.issubset(configured_demods):
            raise ValueError("Each selected HF2 demodulator must have a configuration entry.")


@dataclass(frozen=True)
class TimingEvent:
    marker: TimingMarker
    offset_ns: float
    width_ns: float | None = None

    def __post_init__(self) -> None:
        if self.width_ns is not None and self.width_ns <= 0:
            raise ValueError("Timing-event width must be positive when provided.")


@dataclass(frozen=True)
class TimingWindow:
    marker: TimingMarker
    start_offset_ns: float
    duration_ns: float

    def __post_init__(self) -> None:
        if self.duration_ns <= 0:
            raise ValueError("Timing-window duration must be positive.")


@dataclass(frozen=True)
class T660MasterTimingConfiguration:
    device_identity: TimingControllerIdentity
    role: TimingControllerRole
    master_clock_hz: float
    cycle_period_ns: float
    pump_fire_command: TimingEvent
    pump_qswitch_command: TimingEvent
    master_to_slave_trigger: TimingEvent

    def __post_init__(self) -> None:
        if self.device_identity != TimingControllerIdentity.T660_2_MASTER:
            raise ValueError("The master timing configuration must target T660-2.")
        if self.role != TimingControllerRole.MASTER:
            raise ValueError("The master timing configuration must use the master role.")
        if self.master_clock_hz <= 0:
            raise ValueError("The T660-2 master clock must be positive.")
        if self.cycle_period_ns <= 0:
            raise ValueError("The master cycle period must be positive.")


@dataclass(frozen=True)
class T660SlaveTimingConfiguration:
    device_identity: TimingControllerIdentity
    role: TimingControllerRole
    trigger_source: TimingMarker
    probe_trigger: TimingEvent
    probe_process_trigger: TimingEvent
    probe_enable_window: TimingWindow
    slave_timing_marker: TimingEvent

    def __post_init__(self) -> None:
        if self.device_identity != TimingControllerIdentity.T660_1_SLAVE:
            raise ValueError("The slave timing configuration must target T660-1.")
        if self.role != TimingControllerRole.SLAVE:
            raise ValueError("The slave timing configuration must use the slave role.")
        if self.trigger_source != TimingMarker.MASTER_TO_SLAVE_TRIGGER:
            raise ValueError("The supported v1 slave trigger source is the master-to-slave trigger.")


@dataclass(frozen=True)
class CanonicalTimingBlock:
    t0_label: str
    master: T660MasterTimingConfiguration
    slave: T660SlaveTimingConfiguration
    acquisition_timing_mode: AcquisitionTimingMode
    acquisition_reference_marker: TimingMarker | None = None
    acquisition_delay_ns: float | None = None
    selected_digital_markers: tuple[TimingMarker, ...] = ()

    def __post_init__(self) -> None:
        if not self.t0_label:
            raise ValueError("The timing block requires a non-empty T0 label.")
        if (
            self.acquisition_timing_mode == AcquisitionTimingMode.DELAYED
            and self.acquisition_delay_ns is None
        ):
            raise ValueError("Delayed acquisition mode requires an explicit delay from T0.")
        if (
            self.acquisition_timing_mode == AcquisitionTimingMode.AROUND_SELECTED_SIGNAL
            and self.acquisition_reference_marker is None
        ):
            raise ValueError(
                "Around-selected-signal acquisition mode requires an acquisition reference marker."
            )


@dataclass(frozen=True)
class MuxRoute:
    target: MuxOutputTarget
    signal_domain: MuxSignalDomain
    analog_source: AnalogMonitorRoute | None = None
    digital_marker: TimingMarker | None = None

    def __post_init__(self) -> None:
        if self.signal_domain == MuxSignalDomain.ANALOG_MONITOR and self.analog_source is None:
            raise ValueError("Analog MUX routes require an analog source.")
        if self.signal_domain == MuxSignalDomain.DIGITAL_MARKER and self.digital_marker is None:
            raise ValueError("Digital MUX routes require a digital marker source.")
        if (
            self.target == MuxOutputTarget.PICO_EXTERNAL_TRIGGER
            and self.signal_domain != MuxSignalDomain.DIGITAL_MARKER
        ):
            raise ValueError("The Pico external trigger path must be driven by a digital marker.")


@dataclass(frozen=True)
class MuxRouteSelection:
    route_set_id: str
    route_set_name: str
    channel_a: MuxRoute
    channel_b: MuxRoute
    external_trigger: MuxRoute


@dataclass(frozen=True)
class PicoSecondaryCapture:
    mode: PicoMonitoringMode
    trigger_marker: TimingMarker | None = None
    trigger_input: MuxOutputTarget = MuxOutputTarget.PICO_EXTERNAL_TRIGGER
    capture_window_ns: float | None = None
    sample_interval_ns: float | None = None
    record_inputs: tuple[MuxOutputTarget, ...] = ()

    def __post_init__(self) -> None:
        if self.mode != PicoMonitoringMode.DISABLED and not self.record_inputs:
            raise ValueError("Enabled Pico capture requires at least one routed input.")
        if self.mode == PicoMonitoringMode.DISABLED and self.record_inputs:
            raise ValueError("Disabled Pico capture cannot declare recorded inputs.")
        if self.capture_window_ns is not None and self.capture_window_ns <= 0:
            raise ValueError("Pico capture windows must be positive when provided.")
        if self.sample_interval_ns is not None and self.sample_interval_ns <= 0:
            raise ValueError("Pico sample intervals must be positive when provided.")


@dataclass(frozen=True)
class TimeToWavenumberMapping:
    mapping_id: str
    calibration_reference_id: str
    applicable_spectral_modes: tuple[MircatSpectralMode, ...]
    start_wavenumber_cm1: float
    end_wavenumber_cm1: float
    scan_speed_cm1_per_s: float
    time_origin_offset_ns: float = 0.0

    def __post_init__(self) -> None:
        if self.end_wavenumber_cm1 <= self.start_wavenumber_cm1:
            raise ValueError("The mapping end wavenumber must exceed the start wavenumber.")
        if self.scan_speed_cm1_per_s <= 0:
            raise ValueError("The mapping scan speed must be positive.")


@dataclass(frozen=True)
class RequiredDevice:
    device_id: str
    device_kind: DeviceKind
    required: bool
    role_label: str


@dataclass(frozen=True)
class ExperimentRecipe:
    recipe_id: str
    title: str
    mircat: MircatExperimentConfiguration
    hf2_primary_acquisition: HF2PrimaryAcquisition
    pump_shots_before_probe: int
    probe_timing_mode: ProbeTimingMode
    timing: CanonicalTimingBlock
    mux_route_selection: MuxRouteSelection
    pico_secondary_capture: PicoSecondaryCapture
    time_to_wavenumber_mapping: TimeToWavenumberMapping | None
    version: str = CONTRACT_VERSION
    session_label: str | None = None
    calibration_references: tuple[CalibrationReference, ...] = ()
    required_devices: tuple[RequiredDevice, ...] = field(
        default_factory=lambda: (
            RequiredDevice(
                device_id="mircat-qcl",
                device_kind=DeviceKind.MIRCAT,
                required=True,
                role_label="probe_source",
            ),
            RequiredDevice(
                device_id="hf2li-primary",
                device_kind=DeviceKind.LABONE_HF2LI,
                required=True,
                role_label="primary_acquisition",
            ),
            RequiredDevice(
                device_id=TimingControllerIdentity.T660_2_MASTER.value,
                device_kind=DeviceKind.T660_TIMING,
                required=True,
                role_label="master_timing",
            ),
            RequiredDevice(
                device_id=TimingControllerIdentity.T660_1_SLAVE.value,
                device_kind=DeviceKind.T660_TIMING,
                required=True,
                role_label="slave_timing",
            ),
            RequiredDevice(
                device_id="arduino-mux",
                device_kind=DeviceKind.ARDUINO_MUX,
                required=True,
                role_label="scope_route_selector",
            ),
            RequiredDevice(
                device_id="picoscope-5244d",
                device_kind=DeviceKind.PICOSCOPE_5244D,
                required=False,
                role_label="secondary_monitor",
            ),
        )
    )
    created_at: datetime | None = None
    operator_notes: str = ""

    def __post_init__(self) -> None:
        if self.pump_shots_before_probe < 0:
            raise ValueError("pump_shots_before_probe cannot be negative.")
        required_kinds = {device.device_kind for device in self.required_devices if device.required}
        expected = {
            DeviceKind.MIRCAT,
            DeviceKind.LABONE_HF2LI,
            DeviceKind.T660_TIMING,
            DeviceKind.ARDUINO_MUX,
        }
        if not expected.issubset(required_kinds):
            raise ValueError("The supported v1 recipe is missing one or more required devices.")
        if (
            self.pico_secondary_capture.mode == PicoMonitoringMode.DISABLED
            and any(
                device.device_kind == DeviceKind.PICOSCOPE_5244D and device.required
                for device in self.required_devices
            )
        ):
            raise ValueError("Pico cannot be marked required when secondary capture is disabled.")
        if (
            self.time_to_wavenumber_mapping is None
            and self.mircat.spectral_mode
            in {
                MircatSpectralMode.SWEEP_SCAN,
                MircatSpectralMode.STEP_MEASURE_SCAN,
            }
        ):
            raise ValueError("Scan-based recipes require time-to-wavenumber mapping context.")


@dataclass(frozen=True)
class ExperimentPreset:
    preset_id: str
    name: str
    recipe: ExperimentRecipe
    version: str = CONTRACT_VERSION
    description: str = ""
    advanced_controls_required: bool = False
    tags: tuple[str, ...] = ()
