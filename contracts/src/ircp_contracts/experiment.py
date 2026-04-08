"""Experiment recipe and preset contracts for the MIRcat + HF2LI golden path."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .common import CONTRACT_VERSION, DeviceKind


class MircatLaserMode(str, Enum):
    PULSED = "pulsed"
    CW = "cw"
    CW_MODULATION = "cw_modulation"


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
class MircatSweepRecipe:
    start_wavenumber_cm1: float
    end_wavenumber_cm1: float
    scan_speed_cm1_per_s: float
    scan_count: int = 1
    bidirectional: bool = False
    preferred_qcl: int | None = None
    laser_mode: MircatLaserMode = MircatLaserMode.PULSED
    pulse_rate_hz: float | None = None
    pulse_width_ns: float | None = None

    def __post_init__(self) -> None:
        if self.start_wavenumber_cm1 <= 0:
            raise ValueError("MIRcat sweep start must be positive.")
        if self.end_wavenumber_cm1 <= self.start_wavenumber_cm1:
            raise ValueError("MIRcat sweep end must be greater than start.")
        if self.scan_speed_cm1_per_s <= 0:
            raise ValueError("MIRcat sweep speed must be positive.")
        if self.scan_count < 1:
            raise ValueError("MIRcat sweep count must be at least 1.")


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
            raise ValueError("HF2 demodulator sample rate must be positive.")
        if self.harmonic < 1:
            raise ValueError("HF2 demodulator harmonic must be at least 1.")


@dataclass(frozen=True)
class HF2AcquisitionRecipe:
    stream_selections: tuple[HF2StreamSelection, ...]
    demodulators: tuple[HF2DemodulatorConfiguration, ...]
    capture_interval_seconds: float = 0.05
    preferred_device_id: str | None = None

    def __post_init__(self) -> None:
        if not self.stream_selections:
            raise ValueError("HF2 acquisition requires at least one stream selection.")
        if self.capture_interval_seconds <= 0:
            raise ValueError("HF2 capture interval must be positive.")

        selection_keys = {
            (selection.demod_index, selection.component.value) for selection in self.stream_selections
        }
        if len(selection_keys) != len(self.stream_selections):
            raise ValueError("HF2 stream selections must be unique.")

        configured_demods = {item.demod_index for item in self.demodulators}
        selected_demods = {item.demod_index for item in self.stream_selections}
        if not selected_demods.issubset(configured_demods):
            raise ValueError("Every selected HF2 demodulator must have a configuration entry.")


@dataclass(frozen=True)
class ExperimentRecipe:
    recipe_id: str
    title: str
    mircat_sweep: MircatSweepRecipe
    hf2_acquisition: HF2AcquisitionRecipe
    version: str = CONTRACT_VERSION
    session_label: str | None = None
    required_devices: tuple[DeviceKind, ...] = field(
        default_factory=lambda: (DeviceKind.MIRCAT, DeviceKind.LABONE_HF2LI)
    )
    calibration_references: tuple[CalibrationReference, ...] = ()
    created_at: datetime | None = None
    operator_notes: str = ""

    def __post_init__(self) -> None:
        if DeviceKind.MIRCAT not in self.required_devices:
            raise ValueError("Experiment recipe must require MIRcat for the Phase 2 golden path.")
        if DeviceKind.LABONE_HF2LI not in self.required_devices:
            raise ValueError("Experiment recipe must require HF2LI for the Phase 2 golden path.")


@dataclass(frozen=True)
class ExperimentPreset:
    preset_id: str
    name: str
    recipe: ExperimentRecipe
    version: str = CONTRACT_VERSION
    description: str = ""
    advanced_controls_required: bool = False
    tags: tuple[str, ...] = ()
