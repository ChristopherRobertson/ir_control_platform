"""Operator draft state and recipe-shaping helpers for the simulator runtime."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from ircp_contracts import (
    ExperimentRecipe,
    HF2DemodulatorConfiguration,
    HF2PrimaryAcquisition,
    HF2SampleComponent,
    HF2StreamSelection,
    MircatEmissionMode,
    MircatExperimentConfiguration,
    MircatSpectralMode,
    MircatStepMeasureScan,
    SessionManifest,
)
from ircp_simulators import SimulatorScenarioContext


FIXED_WAVELENGTH_EXPERIMENT_TYPE = "fixed_wavelength"
WAVELENGTH_SCAN_EXPERIMENT_TYPE = "wavelength_scan"
ExperimentType = Literal["fixed_wavelength", "wavelength_scan"]
PULSE_REPETITION_RATE_MIN_HZ = 10.0
PULSE_REPETITION_RATE_MAX_HZ = 3_000_000.0
PULSE_WIDTH_MIN_NS = 20.0
PULSE_WIDTH_MAX_NS = 1005.0
PULSE_DUTY_CYCLE_MAX_PERCENT = 30.0
MIRCAT_WAVENUMBER_MIN_CM1 = 1638.8
MIRCAT_WAVENUMBER_MAX_CM1 = 2077.3
SCAN_SPEED_MIN = 0.1
SCAN_SPEED_MAX = 10_000.0
NDYAG_REPETITION_RATE_MIN_HZ = 10.0
NDYAG_SHOT_COUNT_MAX = 100
HF2_DIO_0 = "dio_0"
HF2_DIO_1 = "dio_1"
HF2_DIO_0_1 = "dio_0_1"
HF2_DIO_SELECTIONS = (HF2_DIO_0, HF2_DIO_1, HF2_DIO_0_1)


@dataclass
class OperatorDraftState:
    session_id_input: str
    session_label: str
    sample_id: str
    operator_notes: str
    experiment_type: ExperimentType
    emission_mode: MircatEmissionMode
    tune_target_cm1: float
    scan_start_cm1: float
    scan_stop_cm1: float
    scan_step_size_cm1: float
    scan_dwell_time_ms: float
    pulse_repetition_rate_hz: float
    pulse_width_ns: float
    pulse_duty_cycle_percent: float
    ndyag_enabled: bool
    ndyag_repetition_rate_hz: float
    ndyag_shot_count: int
    ndyag_continuous: bool
    hf2_demod_index: int
    hf2_component: HF2SampleComponent
    hf2_sample_rate_hz: float
    hf2_harmonic: int
    hf2_time_constant_seconds: float
    hf2_extref: str
    hf2_trigger: str
    hf2_capture_interval_seconds: float


def create_operator_draft(scenario: SimulatorScenarioContext) -> OperatorDraftState:
    initial_hf2 = scenario.recipe.hf2_primary_acquisition
    initial_component = initial_hf2.stream_selections[0].component
    initial_demod = initial_hf2.demodulators[0]
    initial_emission_mode = scenario.recipe.mircat.emission_mode
    initial_pulse_rate_hz = scenario.recipe.mircat.pulse_rate_hz or 10_000.0
    initial_pulse_width_ns = scenario.recipe.mircat.pulse_width_ns or 180.0
    initial_pulse_rate_hz, initial_pulse_width_ns, initial_duty_cycle_percent = normalize_pulse_parameters(
        initial_pulse_rate_hz,
        initial_pulse_width_ns,
    )
    return OperatorDraftState(
        session_id_input="session-001",
        session_label=scenario.recipe.session_label or "MIRcat 1850 cm^-1 baseline",
        sample_id="polymer-film-a12",
        operator_notes="Fixed MIRcat baseline with continuous HF2LI acquisition.",
        experiment_type=default_experiment_type(scenario),
        emission_mode=initial_emission_mode,
        tune_target_cm1=normalize_wavenumber_cm1(default_tune_target(scenario)),
        scan_start_cm1=normalize_wavenumber_cm1(default_scan_start(scenario)),
        scan_stop_cm1=normalize_wavenumber_cm1(default_scan_stop(scenario)),
        scan_step_size_cm1=normalize_scan_speed(1.0),
        scan_dwell_time_ms=250.0,
        pulse_repetition_rate_hz=initial_pulse_rate_hz,
        pulse_width_ns=initial_pulse_width_ns,
        pulse_duty_cycle_percent=initial_duty_cycle_percent,
        ndyag_enabled=False,
        ndyag_repetition_rate_hz=10.0,
        ndyag_shot_count=1,
        ndyag_continuous=False,
        hf2_demod_index=initial_demod.demod_index,
        hf2_component=initial_component,
        hf2_sample_rate_hz=initial_demod.sample_rate_hz,
        hf2_harmonic=initial_demod.harmonic,
        hf2_time_constant_seconds=initial_demod.time_constant_seconds or 0.1,
        hf2_extref=HF2_DIO_0,
        hf2_trigger=HF2_DIO_0,
        hf2_capture_interval_seconds=initial_hf2.capture_interval_seconds,
    )


def normalize_experiment_type(experiment_type: str) -> ExperimentType:
    if experiment_type == WAVELENGTH_SCAN_EXPERIMENT_TYPE:
        return WAVELENGTH_SCAN_EXPERIMENT_TYPE
    return FIXED_WAVELENGTH_EXPERIMENT_TYPE


def experiment_type_label(experiment_type: ExperimentType) -> str:
    if experiment_type == WAVELENGTH_SCAN_EXPERIMENT_TYPE:
        return "Wavelength Scan"
    return "Fixed Wavelength"


def build_hf2_acquisition(
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
) -> HF2PrimaryAcquisition:
    return HF2PrimaryAcquisition(
        profile_name=scenario.recipe.hf2_primary_acquisition.profile_name,
        stream_selections=(
            HF2StreamSelection(
                demod_index=draft.hf2_demod_index,
                component=draft.hf2_component,
            ),
        ),
        demodulators=(
            HF2DemodulatorConfiguration(
                demod_index=draft.hf2_demod_index,
                sample_rate_hz=draft.hf2_sample_rate_hz,
                harmonic=draft.hf2_harmonic,
                time_constant_seconds=draft.hf2_time_constant_seconds,
            ),
        ),
        capture_interval_seconds=draft.hf2_capture_interval_seconds,
        preferred_device_id=scenario.recipe.hf2_primary_acquisition.preferred_device_id,
    )


def build_mircat_configuration(
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
) -> MircatExperimentConfiguration:
    pulse_rate_hz = draft.pulse_repetition_rate_hz if draft.emission_mode == MircatEmissionMode.PULSED else None
    pulse_width_ns = draft.pulse_width_ns if draft.emission_mode == MircatEmissionMode.PULSED else None
    if draft.experiment_type == WAVELENGTH_SCAN_EXPERIMENT_TYPE:
        return replace(
            scenario.recipe.mircat,
            emission_mode=draft.emission_mode,
            spectral_mode=MircatSpectralMode.STEP_MEASURE_SCAN,
            single_wavelength_cm1=None,
            sweep_scan=None,
            step_measure_scan=MircatStepMeasureScan(
                start_wavenumber_cm1=draft.scan_start_cm1,
                end_wavenumber_cm1=draft.scan_stop_cm1,
                step_size_cm1=draft.scan_step_size_cm1,
                dwell_time_ms=draft.scan_dwell_time_ms,
            ),
            multispectral_scan=None,
            pulse_rate_hz=pulse_rate_hz,
            pulse_width_ns=pulse_width_ns,
        )
    return replace(
        scenario.recipe.mircat,
        emission_mode=draft.emission_mode,
        spectral_mode=MircatSpectralMode.SINGLE_WAVELENGTH,
        single_wavelength_cm1=draft.tune_target_cm1,
        sweep_scan=None,
        step_measure_scan=None,
        multispectral_scan=None,
        pulse_rate_hz=pulse_rate_hz,
        pulse_width_ns=pulse_width_ns,
    )


def build_recipe(
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
) -> ExperimentRecipe:
    return replace(
        scenario.recipe,
        session_label=draft.session_label or None,
        mircat=build_mircat_configuration(draft, scenario),
        hf2_primary_acquisition=build_hf2_acquisition(draft, scenario),
    )


def build_session_notes(
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
) -> tuple[str, ...]:
    return (
        f"session_id_input:{draft.session_id_input}",
        f"sample_id:{draft.sample_id}",
        f"operator_notes:{draft.operator_notes}",
        f"experiment_type:{draft.experiment_type}",
        f"emission_mode:{draft.emission_mode.value}",
        f"pulse_duty_cycle_percent:{draft.pulse_duty_cycle_percent}",
        f"ndyag_enabled:{int(draft.ndyag_enabled)}",
        f"ndyag_repetition_rate_hz:{draft.ndyag_repetition_rate_hz}",
        f"ndyag_shot_count:{draft.ndyag_shot_count}",
        f"ndyag_continuous:{int(draft.ndyag_continuous)}",
        f"hf2_extref:{draft.hf2_extref}",
        f"hf2_trigger:{draft.hf2_trigger}",
        f"runtime_mode:simulator:{scenario.scenario_id}",
        f"runtime_description:{scenario.description}",
    )


def apply_manifest_to_draft(
    draft: OperatorDraftState,
    manifest: SessionManifest,
    scenario: SimulatorScenarioContext,
) -> None:
    draft.session_id_input = manifest.session_id
    draft.session_label = manifest.recipe_snapshot.session_label or draft.session_label
    draft.sample_id = note_value(manifest.notes, "sample_id") or draft.sample_id
    draft.operator_notes = note_value(manifest.notes, "operator_notes") or draft.operator_notes
    draft.emission_mode = manifest.recipe_snapshot.mircat.emission_mode
    acquisition = manifest.recipe_snapshot.hf2_primary_acquisition
    draft.hf2_capture_interval_seconds = acquisition.capture_interval_seconds
    draft.hf2_demod_index = acquisition.demodulators[0].demod_index
    draft.hf2_component = acquisition.stream_selections[0].component
    draft.hf2_sample_rate_hz = acquisition.demodulators[0].sample_rate_hz
    draft.hf2_harmonic = acquisition.demodulators[0].harmonic
    draft.hf2_time_constant_seconds = (
        acquisition.demodulators[0].time_constant_seconds or draft.hf2_time_constant_seconds
    )
    draft.hf2_extref = normalize_hf2_dio_selection(note_value(manifest.notes, "hf2_extref") or draft.hf2_extref)
    draft.hf2_trigger = normalize_hf2_dio_selection(note_value(manifest.notes, "hf2_trigger") or draft.hf2_trigger)
    draft.experiment_type = experiment_type_from_recipe(manifest.recipe_snapshot)
    pulse_repetition_rate_hz, pulse_width_ns, pulse_duty_cycle_percent = normalize_pulse_parameters(
        manifest.recipe_snapshot.mircat.pulse_rate_hz or draft.pulse_repetition_rate_hz,
        manifest.recipe_snapshot.mircat.pulse_width_ns or draft.pulse_width_ns,
    )
    draft.pulse_repetition_rate_hz = pulse_repetition_rate_hz
    draft.pulse_width_ns = pulse_width_ns
    draft.pulse_duty_cycle_percent = pulse_duty_cycle_percent
    draft.ndyag_enabled = note_bool_value(manifest.notes, "ndyag_enabled") or False
    draft.ndyag_repetition_rate_hz = normalize_ndyag_repetition_rate_hz(
        note_float_value(manifest.notes, "ndyag_repetition_rate_hz") or draft.ndyag_repetition_rate_hz
    )
    draft.ndyag_shot_count = normalize_ndyag_shot_count(
        note_int_value(manifest.notes, "ndyag_shot_count") or draft.ndyag_shot_count
    )
    draft.ndyag_continuous = note_bool_value(manifest.notes, "ndyag_continuous") or False
    draft.tune_target_cm1 = normalize_wavenumber_cm1(
        default_tune_target(scenario)
        if manifest.recipe_snapshot.mircat.single_wavelength_cm1 is None
        else manifest.recipe_snapshot.mircat.single_wavelength_cm1
    )
    if manifest.recipe_snapshot.mircat.step_measure_scan is not None:
        draft.scan_start_cm1 = normalize_wavenumber_cm1(
            manifest.recipe_snapshot.mircat.step_measure_scan.start_wavenumber_cm1
        )
        draft.scan_stop_cm1 = normalize_wavenumber_cm1(
            manifest.recipe_snapshot.mircat.step_measure_scan.end_wavenumber_cm1
        )
        draft.scan_step_size_cm1 = normalize_scan_speed(
            manifest.recipe_snapshot.mircat.step_measure_scan.step_size_cm1
        )
        draft.scan_dwell_time_ms = manifest.recipe_snapshot.mircat.step_measure_scan.dwell_time_ms


def experiment_type_from_recipe(recipe: ExperimentRecipe) -> ExperimentType:
    return experiment_type_from_spectral_mode(recipe.mircat.spectral_mode)


def note_value(notes: tuple[str, ...], prefix: str) -> str | None:
    target = f"{prefix}:"
    for note in notes:
        if note.startswith(target):
            return note[len(target) :]
    return None


def note_float_value(notes: tuple[str, ...], prefix: str) -> float | None:
    value = note_value(notes, prefix)
    if value is None or value == "":
        return None
    return float(value)


def note_int_value(notes: tuple[str, ...], prefix: str) -> int | None:
    value = note_value(notes, prefix)
    if value is None or value == "":
        return None
    return int(value)


def note_bool_value(notes: tuple[str, ...], prefix: str) -> bool | None:
    value = note_value(notes, prefix)
    if value in {None, ""}:
        return None
    return value == "1"


def default_experiment_type(scenario: SimulatorScenarioContext) -> ExperimentType:
    return experiment_type_from_spectral_mode(scenario.recipe.mircat.spectral_mode)


def default_tune_target(scenario: SimulatorScenarioContext) -> float:
    mircat = scenario.recipe.mircat
    if mircat.single_wavelength_cm1 is not None:
        return mircat.single_wavelength_cm1
    if mircat.sweep_scan is not None:
        return (mircat.sweep_scan.start_wavenumber_cm1 + mircat.sweep_scan.end_wavenumber_cm1) / 2.0
    if mircat.step_measure_scan is not None:
        return (mircat.step_measure_scan.start_wavenumber_cm1 + mircat.step_measure_scan.end_wavenumber_cm1) / 2.0
    if mircat.multispectral_scan is not None:
        return mircat.multispectral_scan.elements[0].target_wavenumber_cm1
    return 1750.0


def default_scan_start(scenario: SimulatorScenarioContext) -> float:
    mircat = scenario.recipe.mircat
    if mircat.step_measure_scan is not None:
        return mircat.step_measure_scan.start_wavenumber_cm1
    if mircat.sweep_scan is not None:
        return mircat.sweep_scan.start_wavenumber_cm1
    return max(default_tune_target(scenario) - 5.0, 1.0)


def default_scan_stop(scenario: SimulatorScenarioContext) -> float:
    mircat = scenario.recipe.mircat
    if mircat.step_measure_scan is not None:
        return mircat.step_measure_scan.end_wavenumber_cm1
    if mircat.sweep_scan is not None:
        return mircat.sweep_scan.end_wavenumber_cm1
    return default_tune_target(scenario) + 5.0


def experiment_type_from_spectral_mode(spectral_mode: MircatSpectralMode) -> ExperimentType:
    if spectral_mode in {MircatSpectralMode.SWEEP_SCAN, MircatSpectralMode.STEP_MEASURE_SCAN}:
        return WAVELENGTH_SCAN_EXPERIMENT_TYPE
    return FIXED_WAVELENGTH_EXPERIMENT_TYPE


def normalize_wavenumber_cm1(wavenumber_cm1: float) -> float:
    return min(max(wavenumber_cm1, MIRCAT_WAVENUMBER_MIN_CM1), MIRCAT_WAVENUMBER_MAX_CM1)


def normalize_scan_speed(scan_speed: float) -> float:
    return min(max(scan_speed, SCAN_SPEED_MIN), SCAN_SPEED_MAX)


def calculate_duty_cycle_percent(pulse_repetition_rate_hz: float, pulse_width_ns: float) -> float:
    if pulse_repetition_rate_hz <= 0 or pulse_width_ns <= 0:
        return 0.0
    return (pulse_repetition_rate_hz * pulse_width_ns * 1e-9) * 100.0


def normalize_hf2_dio_selection(selection: str) -> str:
    if selection in HF2_DIO_SELECTIONS:
        return selection
    return HF2_DIO_0


def normalize_ndyag_repetition_rate_hz(repetition_rate_hz: float) -> float:
    return max(repetition_rate_hz, NDYAG_REPETITION_RATE_MIN_HZ)


def normalize_ndyag_shot_count(shot_count: int) -> int:
    return min(max(shot_count, 1), NDYAG_SHOT_COUNT_MAX)


def max_pulse_width_ns_for_repetition_rate(pulse_repetition_rate_hz: float) -> float:
    if pulse_repetition_rate_hz <= 0:
        return PULSE_WIDTH_MAX_NS
    return (PULSE_DUTY_CYCLE_MAX_PERCENT / 100.0) / (pulse_repetition_rate_hz * 1e-9)


def normalize_pulse_parameters(
    pulse_repetition_rate_hz: float,
    pulse_width_ns: float,
) -> tuple[float, float, float]:
    normalized_rate_hz = min(max(pulse_repetition_rate_hz, PULSE_REPETITION_RATE_MIN_HZ), PULSE_REPETITION_RATE_MAX_HZ)
    normalized_width_ns = min(max(pulse_width_ns, PULSE_WIDTH_MIN_NS), PULSE_WIDTH_MAX_NS)
    normalized_width_ns = min(
        normalized_width_ns,
        max_pulse_width_ns_for_repetition_rate(normalized_rate_hz),
    )
    normalized_width_ns = max(normalized_width_ns, PULSE_WIDTH_MIN_NS)
    duty_cycle_percent = calculate_duty_cycle_percent(normalized_rate_hz, normalized_width_ns)
    return normalized_rate_hz, normalized_width_ns, min(duty_cycle_percent, PULSE_DUTY_CYCLE_MAX_PERCENT)
