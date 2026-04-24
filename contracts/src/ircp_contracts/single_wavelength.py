"""Canonical contracts for the generic single-wavelength pump-probe v1 slice."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import math

from .common import CONTRACT_VERSION, ConfigurationScalar, DeviceKind


EXPERIMENT_ID = "single_wavelength_pump_probe_v1"
EXPERIMENT_NAME = "Single-Wavelength Pump-Probe"
HF2LI_EFFECTIVE_FILE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimescaleRegime(str, Enum):
    NANOSECONDS = "nanoseconds"
    MICROSECONDS = "microseconds"
    MILLISECONDS = "milliseconds"


class ProbeEmissionMode(str, Enum):
    CW = "cw"
    PULSED = "pulsed"


class RunLifecycleState(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ABORTED = "aborted"
    FAULTED = "faulted"


class PlotMetricFamily(str, Enum):
    X = "X"
    Y = "Y"
    R = "R"
    THETA = "Theta"


class PlotDisplayMode(str, Enum):
    OVERLAY = "overlay"
    RATIO = "ratio"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    field_path: str
    blocking: bool = True


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    experiment_type: str
    session_name: str
    operator: str
    sample_id: str
    sample_notes: str
    experiment_notes: str
    created_at: datetime
    updated_at: datetime
    version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.experiment_type != EXPERIMENT_ID:
            raise ValueError(f"v1 sessions must use experiment type {EXPERIMENT_ID}.")
        if not self.session_id.strip():
            raise ValueError("Session ID is required.")
        if not self.session_name.strip():
            raise ValueError("Session name is required.")
        if not self.operator.strip():
            raise ValueError("Operator is required.")
        if not self.sample_id.strip():
            raise ValueError("Sample ID or sample name is required.")
        if self.updated_at < self.created_at:
            raise ValueError("Session updated_at cannot precede created_at.")


@dataclass(frozen=True)
class RunHeader:
    run_id: str
    session_id: str
    run_name: str
    run_notes: str
    created_at: datetime
    updated_at: datetime
    saved: bool = False
    version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("Run ID is required.")
        if not self.session_id.strip():
            raise ValueError("Run header must reference a session.")
        if not self.run_name.strip():
            raise ValueError("Run name or run number is required.")
        if self.updated_at < self.created_at:
            raise ValueError("Run header updated_at cannot precede created_at.")


@dataclass(frozen=True)
class PumpSettings:
    enabled: bool
    shot_count: int
    ready: bool = True
    interlock_ok: bool = True
    fault: str | None = None

    def __post_init__(self) -> None:
        if self.shot_count < 1:
            raise ValueError("Pump shot count must be at least one.")


@dataclass(frozen=True)
class ProbeSettings:
    wavelength_cm1: float
    emission_mode: ProbeEmissionMode
    pulse_rate_hz: float | None = None
    pulse_width_ns: float | None = None
    ready: bool = True
    fault: str | None = None

    def __post_init__(self) -> None:
        if self.wavelength_cm1 <= 0:
            raise ValueError("Probe wavelength must be a positive wavenumber in cm^-1.")
        if self.emission_mode == ProbeEmissionMode.PULSED:
            if self.pulse_rate_hz is None or self.pulse_rate_hz <= 0:
                raise ValueError("Pulsed probe mode requires a positive pulse rate.")
            if self.pulse_width_ns is None or self.pulse_width_ns <= 0:
                raise ValueError("Pulsed probe mode requires a positive pulse width.")


@dataclass(frozen=True)
class LockInSettings:
    order: int
    time_constant_seconds: float
    transfer_rate_hz: float
    ready: bool = True
    fault: str | None = None

    def __post_init__(self) -> None:
        if self.order < 1:
            raise ValueError("Lock-in order must be at least one.")
        if self.time_constant_seconds <= 0:
            raise ValueError("Lock-in time constant must be positive.")
        if self.transfer_rate_hz <= 0:
            raise ValueError("Lock-in transfer rate must be positive.")


@dataclass(frozen=True)
class AcquisitionWindowPlan:
    timescale: TimescaleRegime
    pre_trigger_seconds: float
    post_trigger_seconds: float
    transfer_rate_hz: float
    estimated_sample_count: int
    recorded_signal_count: int
    estimated_file_size_bytes: int
    hf2_file_limit_bytes: int = HF2LI_EFFECTIVE_FILE_LIMIT_BYTES

    @property
    def capture_window_seconds(self) -> float:
        return self.pre_trigger_seconds + self.post_trigger_seconds

    @property
    def valid(self) -> bool:
        return self.estimated_file_size_bytes <= self.hf2_file_limit_bytes


@dataclass(frozen=True)
class SetupState:
    session_saved: bool
    run_header_saved: bool
    pump: PumpSettings | None = None
    timescale: TimescaleRegime | None = None
    probe: ProbeSettings | None = None
    lockin: LockInSettings | None = None
    acquisition_plan: AcquisitionWindowPlan | None = None
    validation_issues: tuple[ValidationIssue, ...] = ()

    @property
    def required_fields_complete(self) -> bool:
        return all((self.pump, self.timescale, self.probe, self.lockin, self.acquisition_plan))

    @property
    def internally_valid(self) -> bool:
        return not any(issue.blocking for issue in self.validation_issues) and (
            self.acquisition_plan.valid if self.acquisition_plan is not None else False
        )

    @property
    def can_run(self) -> bool:
        return (
            self.session_saved
            and self.run_header_saved
            and self.required_fields_complete
            and self.internally_valid
        )


@dataclass(frozen=True)
class RunSettingsSnapshot:
    snapshot_id: str
    session_id: str
    run_id: str
    experiment_type: str
    frozen_at: datetime
    timescale: TimescaleRegime
    pump: PumpSettings
    probe: ProbeSettings
    lockin: LockInSettings
    acquisition_plan: AcquisitionWindowPlan
    recipe_id: str = EXPERIMENT_ID
    version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.experiment_type != EXPERIMENT_ID:
            raise ValueError("Run snapshots must use the fixed v1 experiment type.")


@dataclass(frozen=True)
class RawSignalRecord:
    time_seconds: float
    sample_X: float
    sample_Y: float
    sample_R: float
    sample_Theta: float
    reference_X: float
    reference_Y: float
    reference_R: float
    reference_Theta: float

    def metric_pair(self, family: PlotMetricFamily) -> tuple[float, float]:
        if family == PlotMetricFamily.X:
            return self.sample_X, self.reference_X
        if family == PlotMetricFamily.Y:
            return self.sample_Y, self.reference_Y
        if family == PlotMetricFamily.R:
            return self.sample_R, self.reference_R
        if family == PlotMetricFamily.THETA:
            return self.sample_Theta, self.reference_Theta
        raise ValueError(f"Unsupported metric family: {family}")


@dataclass(frozen=True)
class RawRunRecord:
    raw_record_id: str
    session_id: str
    run_id: str
    settings_snapshot_id: str
    signals: tuple[RawSignalRecord, ...]
    created_at: datetime
    version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.signals:
            raise ValueError("Raw run records require at least one signal row.")


@dataclass(frozen=True)
class ProcessedSignalRecord:
    time_seconds: float
    metric_family: PlotMetricFamily
    sample: float
    reference: float
    ratio: float


@dataclass(frozen=True)
class ProcessedRunRecord:
    processed_record_id: str
    session_id: str
    run_id: str
    raw_record_id: str
    settings_snapshot_id: str
    signals: tuple[ProcessedSignalRecord, ...]
    created_at: datetime
    processing_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.signals:
            raise ValueError("Processed run records require at least one signal row.")


@dataclass(frozen=True)
class ArtifactManifest:
    manifest_id: str
    session_id: str
    run_id: str
    settings_snapshot_id: str
    raw_record_id: str
    processed_record_id: str | None
    session_metadata_path: str
    run_metadata_path: str
    settings_snapshot_path: str
    raw_data_path: str
    processed_data_path: str | None
    export_paths: tuple[str, ...]
    created_at: datetime
    version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        required_paths = (
            self.session_metadata_path,
            self.run_metadata_path,
            self.settings_snapshot_path,
            self.raw_data_path,
        )
        if any(not item for item in required_paths):
            raise ValueError("Artifact manifests require session, run, settings, and raw paths.")


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    session_id: str
    run_name: str
    run_notes: str
    settings_snapshot: RunSettingsSnapshot | None
    raw_record_id: str | None
    processed_record_id: str | None
    started_at: datetime | None
    ended_at: datetime | None
    completion_status: RunLifecycleState
    fault_error_state: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.ended_at is not None and self.started_at is not None and self.ended_at < self.started_at:
            raise ValueError("Run end timestamp cannot precede start timestamp.")
        if self.completion_status == RunLifecycleState.COMPLETED and self.settings_snapshot is None:
            raise ValueError("Completed runs must retain the exact settings snapshot.")
        if self.completion_status == RunLifecycleState.COMPLETED and self.raw_record_id is None:
            raise ValueError("Completed runs must reference raw data.")
        if self.completion_status == RunLifecycleState.FAULTED and not self.fault_error_state:
            raise ValueError("Faulted runs must carry an explicit fault/error state.")


@dataclass(frozen=True)
class SingleWavelengthPumpProbeRecipe:
    experiment_id: str = EXPERIMENT_ID
    display_name: str = EXPERIMENT_NAME
    hardware_families: tuple[DeviceKind, ...] = (
        DeviceKind.MIRCAT,
        DeviceKind.LABONE_HF2LI,
        DeviceKind.T660_TIMING,
    )
    required_session_metadata: tuple[str, ...] = (
        "experiment_type",
        "session_name_or_id",
        "operator",
        "sample_id_or_name",
        "sample_notes",
        "experiment_notes",
        "created_timestamp",
        "updated_timestamp",
    )
    required_run_metadata: tuple[str, ...] = (
        "run_name_or_number",
        "run_notes",
        "session_reference",
        "settings_snapshot",
        "timescale_regime",
        "probe_settings",
        "pump_settings",
        "lockin_settings",
        "raw_data",
        "processed_data",
        "start_timestamp",
        "end_timestamp",
        "completion_status",
        "fault_error_state",
    )
    timescale_regimes: tuple[TimescaleRegime, ...] = (
        TimescaleRegime.NANOSECONDS,
        TimescaleRegime.MICROSECONDS,
        TimescaleRegime.MILLISECONDS,
    )
    required_raw_signals: tuple[str, ...] = (
        "sample_X",
        "sample_Y",
        "sample_R",
        "sample_Theta",
        "reference_X",
        "reference_Y",
        "reference_R",
        "reference_Theta",
        "time",
    )
    plot_metric_families: tuple[PlotMetricFamily, ...] = (
        PlotMetricFamily.X,
        PlotMetricFamily.Y,
        PlotMetricFamily.R,
        PlotMetricFamily.THETA,
    )
    plot_display_modes: tuple[PlotDisplayMode, ...] = (
        PlotDisplayMode.OVERLAY,
        PlotDisplayMode.RATIO,
    )
    forbidden_features_v1: tuple[str, ...] = (
        "wavelength_scanning",
        "multi_wavelength_queues",
        "delay_scan_grids",
        "step_size_controls",
        "number_of_points_controls",
        "linear_log_adaptive_grid_controls",
        "real_time_plotting",
        "separate_data_acquisition_section",
        "separate_run_page",
        "preflight_page_or_section",
        "generic_device_dashboard",
        "sample_specific_product_logic",
    )

    def __post_init__(self) -> None:
        if self.experiment_id != EXPERIMENT_ID:
            raise ValueError("The v1 recipe identity is fixed.")
        if len(self.timescale_regimes) != 3:
            raise ValueError("Exactly three v1 timescale regimes are allowed.")


def derive_acquisition_window_plan(
    timescale: TimescaleRegime,
    transfer_rate_hz: float,
    *,
    recorded_signal_count: int = 9,
    bytes_per_value: int = 8,
) -> AcquisitionWindowPlan:
    if transfer_rate_hz <= 0:
        raise ValueError("Transfer rate must be positive.")
    windows = {
        TimescaleRegime.NANOSECONDS: (1.0e-6, 1.0e-6),
        TimescaleRegime.MICROSECONDS: (1.0e-3, 1.0e-3),
        TimescaleRegime.MILLISECONDS: (1.0, 1.0),
    }
    pre, post = windows[timescale]
    sample_count = max(1, math.ceil((pre + post) * transfer_rate_hz))
    estimated_size = sample_count * recorded_signal_count * bytes_per_value
    return AcquisitionWindowPlan(
        timescale=timescale,
        pre_trigger_seconds=pre,
        post_trigger_seconds=post,
        transfer_rate_hz=transfer_rate_hz,
        estimated_sample_count=sample_count,
        recorded_signal_count=recorded_signal_count,
        estimated_file_size_bytes=estimated_size,
    )


def validate_session_fields(
    *,
    session_name: str,
    operator: str,
    sample_id: str,
) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    if not session_name.strip():
        issues.append(ValidationIssue("session_name_required", "Session name or ID is required.", "session.session_name"))
    if not operator.strip():
        issues.append(ValidationIssue("operator_required", "Operator is required.", "session.operator"))
    if not sample_id.strip():
        issues.append(ValidationIssue("sample_required", "Sample ID or sample name is required.", "session.sample_id"))
    return tuple(issues)


def validate_run_header_fields(*, run_name: str) -> tuple[ValidationIssue, ...]:
    if not run_name.strip():
        return (ValidationIssue("run_name_required", "Run name or run number is required.", "run.run_name"),)
    return ()


def validate_setup_state(setup: SetupState) -> SetupState:
    issues: list[ValidationIssue] = []
    if not setup.session_saved:
        issues.append(ValidationIssue("session_not_saved", "Save the session before setup.", "session"))
    if not setup.run_header_saved:
        issues.append(ValidationIssue("run_header_not_saved", "Save the draft run header before setup.", "run"))
    if setup.pump is None:
        issues.append(ValidationIssue("pump_missing", "Pump settings are required.", "setup.pump"))
    elif setup.pump.fault or not setup.pump.ready or not setup.pump.interlock_ok:
        issues.append(ValidationIssue("pump_not_ready", setup.pump.fault or "Pump is not ready.", "setup.pump"))
    if setup.timescale is None:
        issues.append(ValidationIssue("timescale_missing", "Timescale regime is required.", "setup.timescale"))
    if setup.probe is None:
        issues.append(ValidationIssue("probe_missing", "Probe settings are required.", "setup.probe"))
    elif setup.probe.fault or not setup.probe.ready:
        issues.append(ValidationIssue("probe_not_ready", setup.probe.fault or "Probe is not ready.", "setup.probe"))
    if setup.lockin is None:
        issues.append(ValidationIssue("lockin_missing", "Lock-in amplifier settings are required.", "setup.lockin"))
    elif setup.lockin.fault or not setup.lockin.ready:
        issues.append(ValidationIssue("lockin_not_ready", setup.lockin.fault or "Lock-in amplifier is not ready.", "setup.lockin"))
    if setup.acquisition_plan is None:
        issues.append(ValidationIssue("plan_missing", "Acquisition-window plan is required.", "setup.acquisition_plan"))
    elif not setup.acquisition_plan.valid:
        issues.append(
            ValidationIssue(
                "hf2_file_limit_exceeded",
                "The derived HF2LI acquisition-window plan exceeds the practical file-size limit.",
                "setup.timescale",
            )
        )
    return replace(setup, validation_issues=tuple(issues))


def ratio_value(sample: float, reference: float) -> float:
    if sample <= 0 or reference <= 0:
        raise ValueError("Ratio mode requires positive sample and reference values.")
    return -math.log(sample / reference)
