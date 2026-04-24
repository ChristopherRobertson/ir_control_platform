"""Model-level tests for the three-page single-wavelength workflow."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    from _path_setup import ROOT  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from tests._path_setup import ROOT
from ircp_platform import create_simulator_runtime_map
from ircp_ui_shell.components import render_session_page


class ThreePageWorkflowModelTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return Path(tempdir.name)

    def test_header_navigation_is_exactly_session_setup_results(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        header = asyncio.run(runtime.get_header_status("session"))

        self.assertEqual(tuple(item.label for item in header.navigation), ("Session", "Setup", "Results"))

    def test_session_page_has_session_and_run_information_sections(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        page = asyncio.run(runtime.get_session_page())
        experiment_type = next(field for field in page.session_panel.fields if field.name == "experiment_type")

        self.assertEqual(page.title, "Session")
        self.assertEqual(page.session_panel.title, "Session Information")
        self.assertEqual(page.run_header_panel.title, "Run Information")
        self.assertEqual(experiment_type.field_type, "select")
        self.assertEqual(tuple(option.label for option in experiment_type.options), ("Single-Wavelength",))
        self.assertEqual(tuple(action.label for action in page.session_panel.actions), ("Save",))
        self.assertEqual(tuple(action.label for action in page.run_header_panel.actions), ("Save",))
        self.assertEqual(tuple(field.label for field in page.session_panel.fields), ("Experiment type", "Name / ID", "Operator", "Sample ID or sample name", "Sample notes", "Notes"))
        self.assertEqual(tuple(field.label for field in page.run_header_panel.fields), ("Name / ID", "Notes"))

    def test_session_page_does_not_render_redundant_top_session_section(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        page = asyncio.run(runtime.get_session_page())
        html = render_session_page(page)

        self.assertNotIn('class="hero"', html)
        self.assertIn("Session Information", html)

    def test_setup_page_has_exact_required_sections_and_no_extra_section(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        page = asyncio.run(runtime.get_setup_page())

        self.assertEqual(
            [
                page.pump_panel.title,
                page.timescale_panel.title,
                page.probe_panel.title,
                page.lockin_panel.title,
                page.run_controls_panel.title,
            ],
            [
                "Pump Settings",
                "Timescale",
                "Probe Settings",
                "Lock-In Amplifier Settings",
                "Run Controls",
            ],
        )

    def test_results_page_supports_metric_family_and_display_mode(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]
        asyncio.run(
            runtime.save_session(
                session_name="Session",
                operator="Operator",
                sample_id="Sample",
                sample_notes="",
                experiment_notes="",
            )
        )
        asyncio.run(runtime.save_run_header(run_name="Run 1", run_notes=""))
        asyncio.run(runtime.start_run())

        overlay = asyncio.run(runtime.get_results_page(metric_family="X", display_mode="overlay"))
        ratio = asyncio.run(runtime.get_results_page(metric_family="Theta", display_mode="ratio"))

        self.assertIsNotNone(overlay.plot)
        self.assertIsNotNone(ratio.plot)
        assert overlay.plot is not None
        assert ratio.plot is not None
        self.assertEqual(overlay.plot.metric_family, "X")
        self.assertEqual(overlay.plot.display_mode, "overlay")
        self.assertEqual(ratio.plot.metric_family, "Theta")
        self.assertEqual(ratio.plot.display_mode, "ratio")

    def test_user_entered_name_becomes_session_and_run_id(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        session_id = asyncio.run(
            runtime.save_session(
                session_name="Session 001",
                operator="Operator",
                sample_id="Sample",
                sample_notes="",
                experiment_notes="",
            )
        )
        run_id = asyncio.run(runtime.save_run_header(run_name="Run 001", run_notes=""))

        self.assertEqual(session_id, "Session 001")
        self.assertEqual(run_id, "Run 001")

    def test_duplicate_run_id_is_rejected_for_same_session(self) -> None:
        runtime = create_simulator_runtime_map(storage_root=self._temp_root())["nominal"]

        asyncio.run(
            runtime.save_session(
                session_name="Session 001",
                operator="Operator",
                sample_id="Sample",
                sample_notes="",
                experiment_notes="",
            )
        )
        asyncio.run(runtime.save_run_header(run_name="Run 001", run_notes=""))

        with self.assertRaisesRegex(ValueError, "Run ID already exists in session Session 001: Run 001"):
            asyncio.run(runtime.create_run(run_name="Run 001", run_notes=""))

    def test_existing_run_requires_opened_session_before_opening(self) -> None:
        root = self._temp_root()
        runtime = create_simulator_runtime_map(storage_root=root)["nominal"]

        asyncio.run(
            runtime.save_session(
                session_name="Session 001",
                operator="Operator",
                sample_id="Sample",
                sample_notes="",
                experiment_notes="",
            )
        )
        asyncio.run(runtime.save_run_header(run_name="Run 001", run_notes=""))

        fresh_runtime = create_simulator_runtime_map(storage_root=root)["nominal"]
        with self.assertRaisesRegex(ValueError, "Open the session before opening one of its runs."):
            asyncio.run(fresh_runtime.open_run(session_id="Session 001", run_id="Run 001"))

        opened_session_id = asyncio.run(fresh_runtime.open_session(session_id="Session 001"))
        opened_run_id = asyncio.run(fresh_runtime.open_run(session_id="Session 001", run_id="Run 001"))

        self.assertEqual(opened_session_id, "Session 001")
        self.assertEqual(opened_run_id, "Run 001")


if __name__ == "__main__":
    unittest.main()
