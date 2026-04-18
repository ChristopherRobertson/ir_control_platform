"""Minimal baseline simulator and fixture support tests."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    from _path_setup import ROOT  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - depends on unittest invocation style
    from tests._path_setup import ROOT
from ircp_platform import create_simulator_runtime_map
from ircp_simulators import SupportedV1SimulatorCatalog


class MinimalBaselineSupportTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return Path(tempdir.name)

    def test_nominal_runtime_seeds_session_defaults_and_minimal_session_surface(self) -> None:
        runtimes = create_simulator_runtime_map(storage_root=self._temp_root())
        operate_page = asyncio.run(runtimes["nominal"].get_operate_page())

        field_values = {field.name: field.value for field in operate_page.session_panel.fields}
        self.assertEqual(field_values["session_id_input"], "saved-session-001")
        self.assertEqual(field_values["session_label"], "MIRcat 1850 cm^-1 baseline")
        self.assertEqual(field_values["sample_id"], "polymer-film-a12")
        self.assertEqual(
            field_values["operator_notes"],
            "Fixed MIRcat baseline with continuous HF2LI acquisition.",
        )
        self.assertIn("recent_session_id", field_values)
        self.assertEqual(operate_page.session_panel.status_items, ())
        self.assertFalse(hasattr(operate_page, "recent_activity"))
        self.assertFalse(hasattr(operate_page, "live_status"))

    def test_mircat_simulator_supports_baseline_transitions(self) -> None:
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        driver = context.bundle.mircat

        disconnected = asyncio.run(driver.disconnect())
        connected = asyncio.run(driver.connect())
        tuning_snapshot = asyncio.run(driver.apply_configuration(context.recipe.mircat))
        tuning_status = asyncio.run(driver.get_status())
        armed = asyncio.run(driver.arm())
        emission_on = asyncio.run(driver.set_emission_enabled(True))
        disarmed = asyncio.run(driver.disarm())

        self.assertFalse(disconnected.connected)
        self.assertEqual(disconnected.lifecycle_state.value, "disconnected")
        self.assertTrue(connected.connected)
        self.assertEqual(connected.vendor_status["tune_state"], "idle")
        self.assertEqual(tuning_snapshot.device_id, "mircat-qcl")
        self.assertEqual(tuning_status.vendor_status["tune_state"], "tuning")
        self.assertTrue(tuning_status.ready)
        self.assertIn("tuning", tuning_status.status_summary.lower())
        self.assertTrue(armed.vendor_status["armed"])
        self.assertEqual(armed.vendor_status["tune_state"], "tuned")
        self.assertTrue(emission_on.vendor_status["emission_enabled"])
        self.assertEqual(emission_on.vendor_status["tune_state"], "tuned")
        self.assertFalse(disarmed.vendor_status["armed"])
        self.assertEqual(disarmed.vendor_status["tune_state"], "idle")

    def test_hf2_simulator_supports_connect_run_stop_transitions(self) -> None:
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        driver = context.bundle.hf2li
        acquisition = context.recipe.hf2_primary_acquisition

        disconnected = asyncio.run(driver.disconnect())
        connected = asyncio.run(driver.connect())
        configured = asyncio.run(driver.apply_configuration(acquisition))
        capture = asyncio.run(driver.start_capture(acquisition, "session-test-001"))
        running = asyncio.run(driver.get_status())
        stopped = asyncio.run(driver.stop_capture(capture.capture_id))

        self.assertFalse(disconnected.connected)
        self.assertTrue(connected.connected)
        self.assertEqual(connected.vendor_status["acquisition_state"], "idle")
        self.assertEqual(configured.device_id, "hf2li-primary")
        self.assertEqual(running.vendor_status["acquisition_state"], "running")
        self.assertTrue(running.vendor_status["capture_active"])
        self.assertIn("running", running.status_summary.lower())
        self.assertEqual(stopped.vendor_status["acquisition_state"], "stopped")
        self.assertFalse(stopped.vendor_status["capture_active"])
        self.assertIn("stopped", stopped.status_summary.lower())

    def test_run_panel_exposes_preflight_and_stop_labels_for_baseline(self) -> None:
        runtimes = create_simulator_runtime_map(storage_root=self._temp_root())

        nominal_page = asyncio.run(runtimes["nominal"].get_operate_page())
        blocked_page = asyncio.run(runtimes["blocked_timing"].get_operate_page())

        nominal_state = next(
            item.value for item in nominal_page.run_panel.status_items if item.label == "Current run state"
        )
        blocked_state = next(
            item.value for item in blocked_page.run_panel.status_items if item.label == "Current run state"
        )

        self.assertEqual(nominal_state, "Preflight ok")
        self.assertEqual(blocked_state, "Preflight blocked")


if __name__ == "__main__":
    unittest.main()
