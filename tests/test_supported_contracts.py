"""Contract tests for the single-wavelength pump-probe v1 slice."""

from __future__ import annotations

import importlib
import unittest

try:
    from _path_setup import ROOT  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from tests._path_setup import ROOT
import ircp_contracts
from ircp_contracts import (
    DeviceCapability,
    DeviceKind,
    EXPERIMENT_ID,
    EXPERIMENT_NAME,
    FaultCategory,
    FaultSeverity,
    LockInSettings,
    PlotDisplayMode,
    PlotMetricFamily,
    ProbeEmissionMode,
    ProbeSettings,
    PumpSettings,
    RawRunRecord,
    RawSignalRecord,
    SessionRecord,
    SetupState,
    SingleWavelengthPumpProbeRecipe,
    TimescaleRegime,
    derive_acquisition_window_plan,
    utc_now,
    validate_setup_state,
)


class SingleWavelengthContractTests(unittest.TestCase):
    def test_recipe_identity_and_v1_options_are_fixed(self) -> None:
        recipe = SingleWavelengthPumpProbeRecipe()

        self.assertEqual(recipe.experiment_id, EXPERIMENT_ID)
        self.assertEqual(recipe.display_name, EXPERIMENT_NAME)
        self.assertEqual(
            recipe.timescale_regimes,
            (
                TimescaleRegime.NANOSECONDS,
                TimescaleRegime.MICROSECONDS,
                TimescaleRegime.MILLISECONDS,
            ),
        )
        self.assertEqual(recipe.plot_metric_families, tuple(PlotMetricFamily))
        self.assertEqual(recipe.plot_display_modes, tuple(PlotDisplayMode))
        self.assertIn("wavelength_scanning", recipe.forbidden_features_v1)
        self.assertIn("step_size_controls", recipe.forbidden_features_v1)
        self.assertIn("number_of_points_controls", recipe.forbidden_features_v1)

    def test_session_contract_excludes_wavelength_and_timescale(self) -> None:
        now = utc_now()
        session = SessionRecord(
            session_id="session-001",
            experiment_type=EXPERIMENT_ID,
            session_name="Generic pump-probe session",
            operator="operator",
            sample_id="sample-001",
            sample_notes="sample notes",
            experiment_notes="experiment notes",
            created_at=now,
            updated_at=now,
        )

        self.assertFalse(hasattr(session, "wavelength_cm1"))
        self.assertFalse(hasattr(session, "timescale"))
        self.assertEqual(session.experiment_type, EXPERIMENT_ID)

    def test_setup_validation_gates_run_until_session_run_and_fields_are_ready(self) -> None:
        incomplete = validate_setup_state(SetupState(session_saved=False, run_header_saved=False))

        self.assertFalse(incomplete.can_run)
        self.assertTrue(any(issue.code == "session_not_saved" for issue in incomplete.validation_issues))
        self.assertTrue(any(issue.code == "run_header_not_saved" for issue in incomplete.validation_issues))

        lockin = LockInSettings(order=2, time_constant_seconds=0.1, transfer_rate_hz=224.9)
        complete = validate_setup_state(
            SetupState(
                session_saved=True,
                run_header_saved=True,
                pump=PumpSettings(enabled=True, shot_count=10),
                timescale=TimescaleRegime.MICROSECONDS,
                probe=ProbeSettings(wavelength_cm1=1850.0, emission_mode=ProbeEmissionMode.CW),
                lockin=lockin,
                acquisition_plan=derive_acquisition_window_plan(TimescaleRegime.MICROSECONDS, lockin.transfer_rate_hz),
            )
        )

        self.assertTrue(complete.required_fields_complete)
        self.assertTrue(complete.internally_valid)
        self.assertTrue(complete.can_run)

    def test_acquisition_plan_is_window_based_not_grid_based(self) -> None:
        plan = derive_acquisition_window_plan(TimescaleRegime.MILLISECONDS, 224.9)

        self.assertEqual(plan.timescale, TimescaleRegime.MILLISECONDS)
        self.assertGreater(plan.capture_window_seconds, 0)
        self.assertGreater(plan.estimated_sample_count, 0)
        self.assertTrue(plan.valid)
        self.assertFalse(hasattr(plan, "step_size"))
        self.assertFalse(hasattr(plan, "number_of_points"))
        self.assertFalse(hasattr(plan, "spacing"))

    def test_raw_record_requires_sample_reference_metrics_and_time(self) -> None:
        now = utc_now()
        signal = RawSignalRecord(
            time_seconds=0.0,
            sample_X=1.0,
            sample_Y=0.1,
            sample_R=1.004987562,
            sample_Theta=5.71,
            reference_X=1.2,
            reference_Y=0.2,
            reference_R=1.216552506,
            reference_Theta=9.46,
        )
        raw = RawRunRecord(
            raw_record_id="run-001-raw",
            session_id="session-001",
            run_id="run-001",
            settings_snapshot_id="run-001-settings",
            signals=(signal,),
            created_at=now,
        )

        sample, reference = signal.metric_pair(PlotMetricFamily.R)
        self.assertEqual(raw.signals[0].time_seconds, 0.0)
        self.assertGreater(sample, 0)
        self.assertGreater(reference, 0)

    def test_public_v1_root_excludes_deferred_scan_and_advanced_contracts(self) -> None:
        forbidden_public_names = (
            "ExperimentRecipe",
            "ExperimentPreset",
            "MircatEmissionMode",
            "MircatExperimentConfiguration",
            "MircatSpectralMode",
            "MircatSweepScan",
            "MircatStepMeasureScan",
            "MircatMultispectralScan",
            "MultispectralElement",
            "TimeToWavenumberMapping",
        )

        for name in forbidden_public_names:
            with self.subTest(name=name):
                self.assertFalse(hasattr(ircp_contracts, name))
                self.assertNotIn(name, ircp_contracts.__all__)

        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("ircp_contracts.experiment")

    def test_mircat_driver_contract_is_single_wavelength_only(self) -> None:
        from ircp_drivers.mircat import MircatCapabilityProfile, MircatDriver

        profile = MircatCapabilityProfile(DeviceCapability(DeviceKind.MIRCAT, "MIRcat"))

        self.assertEqual(profile.supported_emission_modes, (ProbeEmissionMode.CW, ProbeEmissionMode.PULSED))
        self.assertTrue(profile.single_wavelength_only)
        self.assertFalse(hasattr(profile, "supported_spectral_modes"))
        self.assertTrue(hasattr(MircatDriver, "start_single_wavelength"))
        self.assertTrue(hasattr(MircatDriver, "stop_single_wavelength"))
        self.assertFalse(hasattr(MircatDriver, "start_recipe"))
        self.assertFalse(hasattr(MircatDriver, "stop_recipe"))

    def test_unsupported_mircat_scan_requests_normalize_to_blocking_faults(self) -> None:
        from ircp_drivers.mircat import (
            UNSUPPORTED_SCAN_REQUESTS_V1,
            unsupported_scan_request_fault,
        )

        self.assertIn("wavelength_sweep", UNSUPPORTED_SCAN_REQUESTS_V1)
        self.assertIn("step_measure_scan", UNSUPPORTED_SCAN_REQUESTS_V1)
        self.assertIn("multispectral_scan", UNSUPPORTED_SCAN_REQUESTS_V1)

        fault = unsupported_scan_request_fault(
            "wavelength_sweep",
            device_id="mircat-001",
            detected_at=utc_now(),
        )

        self.assertEqual(fault.device_kind, DeviceKind.MIRCAT)
        self.assertEqual(fault.category, FaultCategory.VALIDATION)
        self.assertEqual(fault.severity, FaultSeverity.ERROR)
        self.assertEqual(fault.code, "unsupported_v1_scan_request")
        self.assertTrue(fault.blocking)
        self.assertEqual(fault.context["requested_operation"], "wavelength_sweep")
        self.assertEqual(fault.context["supported_operation"], "single_wavelength")
        self.assertIn("single-wavelength only", fault.message)


if __name__ == "__main__":
    unittest.main()
