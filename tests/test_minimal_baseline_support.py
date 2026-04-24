"""Simulator-backed vertical-slice tests for Session -> Setup -> Results."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    from _path_setup import ROOT  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from tests._path_setup import ROOT
from ircp_contracts import RunLifecycleState
from ircp_platform import create_simulator_runtime_map


class SingleWavelengthVerticalSliceTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return Path(tempdir.name)

    def _runtime(self, scenario: str = "nominal"):
        return create_simulator_runtime_map(storage_root=self._temp_root())[scenario]

    def _save_session_and_run(self, runtime) -> None:
        asyncio.run(
            runtime.save_session(
                session_name="Session A",
                operator="Operator A",
                sample_id="Sample A",
                sample_notes="Any sample.",
                experiment_notes="Generic pump-probe test.",
            )
        )
        asyncio.run(runtime.save_run_header(run_name="Run 1", run_notes="Saved run."))
        asyncio.run(
            runtime.save_setup(
                pump_enabled=True,
                shot_count=10,
                timescale="microseconds",
                wavelength_cm1=1850.0,
                emission_mode="cw",
                pulse_rate_hz=None,
                pulse_width_ns=None,
                order=2,
                time_constant_seconds=0.1,
                transfer_rate_hz=224.9,
            )
        )

    def test_session_and_run_header_gating_blocks_setup_until_saved(self) -> None:
        runtime = self._runtime()

        session_page = asyncio.run(runtime.get_session_page())
        setup_page = asyncio.run(runtime.get_setup_page())

        self.assertEqual(session_page.title, "Session")
        self.assertIsNotNone(session_page.state)
        self.assertIn("metadata", session_page.state.title.lower())
        self.assertIsNone(setup_page.state)
        self.assertTrue(setup_page.run_controls_panel.actions[0].disabled)

    def test_saved_metadata_and_default_setup_enable_run(self) -> None:
        runtime = self._runtime()
        self._save_session_and_run(runtime)

        setup_page = asyncio.run(runtime.get_setup_page())

        self.assertEqual(setup_page.title, "Setup")
        self.assertEqual(
            (
                setup_page.pump_panel.title,
                setup_page.timescale_panel.title,
                setup_page.probe_panel.title,
                setup_page.lockin_panel.title,
                setup_page.run_controls_panel.title,
            ),
            (
                "Pump Settings",
                "Timescale",
                "Probe Settings",
                "Lock-In Amplifier Settings",
                "Run Controls",
            ),
        )
        self.assertFalse(setup_page.run_controls_panel.actions[0].disabled)

    def test_happy_path_persists_run_snapshot_raw_processed_and_results_reopen(self) -> None:
        root = self._temp_root()
        runtime = create_simulator_runtime_map(storage_root=root)["nominal"]
        self._save_session_and_run(runtime)

        run_id = asyncio.run(runtime.start_run())
        results = asyncio.run(runtime.get_results_page(metric_family="R", display_mode="overlay"))

        self.assertEqual(results.selected_run_id, run_id)
        self.assertIsNotNone(results.plot)
        assert results.plot is not None
        self.assertEqual(results.plot.metric_family, "R")
        self.assertEqual(results.plot.display_mode, "overlay")
        self.assertGreater(len(results.plot.points), 0)
        self.assertIsNotNone(results.plot.points[0].sample)
        self.assertIsNotNone(results.plot.points[0].reference)
        self.assertTrue((root / "nominal" / "sessions").is_dir())

        recreated = create_simulator_runtime_map(storage_root=root)["nominal"]
        reopened = asyncio.run(recreated.get_results_page(metric_family="R", display_mode="ratio"))
        self.assertEqual(reopened.selected_run_id, run_id)
        self.assertIsNotNone(reopened.plot)
        assert reopened.plot is not None
        self.assertEqual(reopened.plot.display_mode, "ratio")
        self.assertIsNotNone(reopened.plot.points[0].ratio)

    def test_faulted_path_persists_partial_raw_and_explicit_fault(self) -> None:
        runtime = self._runtime("faulted_hf2")
        self._save_session_and_run(runtime)

        run_id = asyncio.run(runtime.start_run())
        results = asyncio.run(runtime.get_results_page(run_id=run_id))

        self.assertIsNotNone(results.state)
        assert results.state is not None
        self.assertEqual(results.state.title, "Run faulted")
        self.assertIn("HF2LI", results.state.message)

    def test_exports_are_available_from_saved_run(self) -> None:
        runtime = self._runtime()
        self._save_session_and_run(runtime)
        run_id = asyncio.run(runtime.start_run())
        results = asyncio.run(runtime.get_results_page())
        assert results.selected_session_id is not None

        raw = asyncio.run(
            runtime.get_results_download(
                session_id=results.selected_session_id,
                run_id=run_id,
                asset="raw",
            )
        )
        metadata = asyncio.run(
            runtime.get_results_download(
                session_id=results.selected_session_id,
                run_id=run_id,
                asset="metadata",
            )
        )

        self.assertEqual(raw.content_type, "text/csv; charset=utf-8")
        self.assertIn(b"sample_X", raw.body)
        self.assertIn(b"settings_snapshot", metadata.body)

    def test_save_setup_overwrites_previous_saved_settings_completely(self) -> None:
        runtime = self._runtime()
        asyncio.run(
            runtime.save_session(
                session_name="Session A",
                operator="Operator A",
                sample_id="Sample A",
                sample_notes="Any sample.",
                experiment_notes="Generic pump-probe test.",
            )
        )
        asyncio.run(runtime.save_run_header(run_name="Run 1", run_notes="Saved run."))

        asyncio.run(
            runtime.save_setup(
                pump_enabled=True,
                shot_count=25,
                timescale="milliseconds",
                wavelength_cm1=1725.5,
                emission_mode="pulsed",
                pulse_rate_hz=5000.0,
                pulse_width_ns=150.0,
                order=4,
                time_constant_seconds=0.25,
                transfer_rate_hz=100.0,
            )
        )
        asyncio.run(
            runtime.save_setup(
                pump_enabled=False,
                shot_count=3,
                timescale="nanoseconds",
                wavelength_cm1=1850.0,
                emission_mode="cw",
                pulse_rate_hz=9999.0,
                pulse_width_ns=999.0,
                order=2,
                time_constant_seconds=0.1,
                transfer_rate_hz=224.9,
            )
        )

        run_id = asyncio.run(runtime.start_run())
        results = asyncio.run(runtime.get_results_page(run_id=run_id))
        assert results.selected_session_id is not None
        metadata = asyncio.run(
            runtime.get_results_download(
                session_id=results.selected_session_id,
                run_id=run_id,
                asset="metadata",
            )
        )

        self.assertIn(b'"enabled": false', metadata.body)
        self.assertIn(b'"shot_count": 3', metadata.body)
        self.assertIn(b'"timescale": "nanoseconds"', metadata.body)
        self.assertIn(b'"wavelength_cm1": 1850.0', metadata.body)
        self.assertIn(b'"emission_mode": "cw"', metadata.body)
        self.assertNotIn(b'"pulse_rate_hz": 5000.0', metadata.body)
        self.assertNotIn(b'"pulse_width_ns": 150.0', metadata.body)
        self.assertIn(b'"pulse_rate_hz": null', metadata.body)
        self.assertIn(b'"pulse_width_ns": null', metadata.body)
        self.assertIn(b'"order": 2', metadata.body)
        self.assertIn(b'"time_constant_seconds": 0.1', metadata.body)
        self.assertIn(b'"transfer_rate_hz": 224.9', metadata.body)


if __name__ == "__main__":
    unittest.main()
