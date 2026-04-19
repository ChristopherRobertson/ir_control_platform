"""Model-level regression tests for the finished Experiment/Setup/Run shell."""

from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from _path_setup import ROOT  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - depends on unittest invocation style
    from tests._path_setup import ROOT
from ircp_platform import create_simulator_runtime_map


class FinishedExperimentShellModelTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return Path(tempdir.name)

    def test_header_status_exposes_richer_global_badges(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        header = asyncio.run(runtime.get_header_status("experiment"))

        badge_labels = tuple(badge.label for badge in header.badges)
        self.assertGreaterEqual(len(badge_labels), 4)
        self.assertIn("Experiment", badge_labels)
        self.assertTrue(any(label.startswith("Devices ") for label in badge_labels))
        self.assertTrue(any(label.startswith("Issues ") for label in badge_labels))

    def test_experiment_page_model_exposes_finished_sections(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        page = asyncio.run(runtime.get_operate_page())

        self.assertEqual(page.title, "Experiment")
        self.assertGreaterEqual(len(page.surface_badges), 2)
        self.assertGreaterEqual(len(page.summary_metrics), 4)
        self.assertGreaterEqual(len(page.configuration_panels), 2)
        self.assertGreaterEqual(len(page.hardware_cards), 6)
        self.assertTrue(any(action.label == "Open Setup Workspace" for action in page.workflow_actions))
        self.assertEqual(page.run_panel.actions[0].label, "Run Preflight")
        self.assertEqual(page.run_panel.actions[1].label, "Start Run")

    def test_setup_page_model_exposes_readiness_hardware_and_advanced_sections(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        page = asyncio.run(runtime.get_setup_page())

        self.assertEqual(page.title, "Setup")
        self.assertGreaterEqual(len(page.summary_metrics), 4)
        self.assertGreaterEqual(len(page.readiness_panels), 3)
        self.assertGreaterEqual(len(page.hardware_cards), 6)
        self.assertGreaterEqual(len(page.advanced_sections), 2)
        self.assertEqual(page.run_panel.title, "Preflight / Validation")
        self.assertEqual(page.run_panel.actions[0].action, "/setup/preflight")

    def test_run_page_model_exposes_live_timeline_data_after_start(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        run_state = asyncio.run(runtime.start_run())
        page = asyncio.run(runtime.get_run_page())

        self.assertEqual(page.title, "Run")
        self.assertEqual(run_state.phase.value, "completed")
        self.assertIsNotNone(page.state)
        assert page.state is not None
        self.assertEqual(page.state.title, "Run completed")
        self.assertGreaterEqual(len(page.summary_metrics), 4)
        self.assertGreaterEqual(len(page.metadata_panels), 3)
        self.assertGreaterEqual(len(page.live_data_previews), 1)
        self.assertGreaterEqual(len(page.event_log), 1)
        self.assertGreaterEqual(len(page.tables), 2)
        self.assertTrue(any(action.label == "Open Results" for action in page.post_run_actions))

    def test_faulted_run_page_model_projects_fault_state_and_trace_preview(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["faulted_hf2"]

        asyncio.run(runtime.start_run())
        page = asyncio.run(runtime.get_run_page())

        self.assertIsNotNone(page.state)
        assert page.state is not None
        self.assertEqual(page.state.title, "Run faulted")
        self.assertTrue(any("HF2 reported a simulated overload fault" in item.message for item in page.event_log))
        self.assertGreaterEqual(len(page.live_data_previews), 1)

    def test_open_saved_session_stages_unique_session_id_for_rerun(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        asyncio.run(runtime.open_saved_session("saved-session-001"))
        page = asyncio.run(runtime.get_setup_page())
        field_values = {field.name: field.value for field in page.session_panel.fields}

        self.assertEqual(field_values["session_id_input"], "saved-session-001-rerun")

    def test_default_seeded_runtime_suggests_new_session_id_before_start(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        page = asyncio.run(runtime.get_setup_page())
        field_values = {field.name: field.value for field in page.session_panel.fields}
        run_state = asyncio.run(runtime.start_run())

        self.assertEqual(field_values["session_id_input"], "saved-session-001-rerun")
        self.assertEqual(run_state.session_id, "saved-session-001-rerun")

    def test_ui_shell_source_exposes_finished_page_models(self) -> None:
        ui_root = Path(ROOT) / "ui-shell" / "src" / "ircp_ui_shell"
        models_source = (ui_root / "models.py").read_text(encoding="utf-8")

        self.assertIn("class SetupPageModel", models_source)
        self.assertIn("class RunPageModel", models_source)
        self.assertIn("class TracePreviewModel", models_source)


if __name__ == "__main__":
    unittest.main()
