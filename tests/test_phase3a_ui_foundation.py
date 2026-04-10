"""Phase 3B UI foundation and supported-v1 simulator runtime tests."""

from __future__ import annotations

import asyncio
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from _path_setup import ROOT  # noqa: F401
from ircp_contracts import RunPhase
from ircp_platform import create_phase3b_runtime_map, create_phase3b_simulator_app
from ircp_ui_shell.page_state import PageStateKind


def _call_wsgi(
    app,
    *,
    method: str,
    path: str,
    body: dict[str, str] | None = None,
) -> tuple[str, dict[str, str], str]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method.upper()
    if "?" in path:
        route_path, query = path.split("?", 1)
    else:
        route_path, query = path, ""
    environ["PATH_INFO"] = route_path
    environ["QUERY_STRING"] = query
    encoded_body = urlencode(body or {}).encode("utf-8")
    environ["CONTENT_LENGTH"] = str(len(encoded_body))
    environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    environ["wsgi.input"] = BytesIO(encoded_body)
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    payload = b"".join(app(environ, start_response))
    return (
        str(captured["status"]),
        captured["headers"],  # type: ignore[return-value]
        payload.decode("utf-8"),
    )


class Phase3BUiFoundationTests(unittest.TestCase):
    def _create_runtime_map(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return create_phase3b_runtime_map(storage_root=Path(tempdir.name))

    def _create_app(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return create_phase3b_simulator_app(storage_root=Path(tempdir.name))

    def test_root_redirects_to_setup(self) -> None:
        app = self._create_app()
        status, headers, _body = _call_wsgi(app, method="GET", path="/")

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/setup?scenario=nominal")

    def test_setup_route_renders_supported_v1_summary(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/setup?scenario=nominal")

        self.assertEqual(status, "200 OK")
        self.assertIn("Supported v1 pump-probe scan", body)
        self.assertIn("Session and Sample Identity", body)
        self.assertIn("Default Experiment Path", body)
        self.assertIn("Calibration and Monitoring Context", body)

    def test_advanced_and_calibrated_routes_render_reviewable_controls(self) -> None:
        app = self._create_app()

        advanced_status, _headers, advanced_body = _call_wsgi(
            app,
            method="GET",
            path="/setup/advanced?scenario=nominal",
        )
        calibrated_status, _headers, calibrated_body = _call_wsgi(
            app,
            method="GET",
            path="/setup/calibrated?scenario=nominal",
        )

        self.assertEqual(advanced_status, "200 OK")
        self.assertIn("Timing Program", advanced_body)
        self.assertIn("Capture and Routing", advanced_body)
        self.assertIn("Expert only", advanced_body)

        self.assertEqual(calibrated_status, "200 OK")
        self.assertIn("Calibration References", calibrated_body)
        self.assertIn("Fixed Installation Assumptions", calibrated_body)
        self.assertIn("Guarded defaults", calibrated_body)

    def test_blocked_timing_scenario_shows_explicit_blocked_state(self) -> None:
        runtimes = self._create_runtime_map()
        blocked_page = asyncio.run(runtimes["blocked_timing"].get_setup_page())

        self.assertIsNotNone(blocked_page.state)
        self.assertEqual(blocked_page.state.kind, PageStateKind.BLOCKED)
        self.assertIn("blocking", blocked_page.state.message.lower())

    def test_optional_pico_unavailability_surfaces_warning_not_block(self) -> None:
        runtimes = self._create_runtime_map()
        setup_page = asyncio.run(runtimes["pico_optional"].get_setup_page())

        self.assertIsNotNone(setup_page.state)
        self.assertEqual(setup_page.state.kind, PageStateKind.WARNING)
        self.assertIn("optional", setup_page.state.message.lower())

    def test_nominal_start_run_materializes_primary_and_secondary_artifacts(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]

        run_state = asyncio.run(runtime.start_run())
        run_page = asyncio.run(runtime.get_run_page())
        results_page = asyncio.run(runtime.get_results_page())

        self.assertEqual(run_state.phase, RunPhase.COMPLETED)
        self.assertIsNotNone(run_state.session_id)
        self.assertGreaterEqual(len(run_page.run_steps), 3)
        self.assertGreater(len(run_page.event_log), 0)
        self.assertGreater(len(run_page.primary_live_data), 0)
        self.assertGreater(len(run_page.secondary_live_data), 0)
        self.assertTrue(any(card.session_id == run_state.session_id for card in results_page.sessions))
        selected = next(card for card in results_page.sessions if card.session_id == run_state.session_id)
        self.assertGreaterEqual(selected.primary_raw_artifact_count, 1)
        self.assertGreaterEqual(selected.secondary_monitor_artifact_count, 1)
        self.assertGreater(len(results_page.artifact_panels), 0)
        self.assertGreater(len(results_page.event_log), 0)

    def test_faulted_scenario_surfaces_fault_page_state(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["faulted_hf2"]

        run_state = asyncio.run(runtime.start_run())
        run_page = asyncio.run(runtime.get_run_page())

        self.assertEqual(run_state.phase, RunPhase.FAULTED)
        self.assertIsNotNone(run_page.state)
        self.assertEqual(run_page.state.kind, PageStateKind.FAULT)
        self.assertIn("fault", run_page.state.message.lower())

    def test_results_reopen_uses_saved_supported_v1_session_fixture(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]

        manifest = asyncio.run(runtime.reopen_session("saved-session-001"))
        results_page = asyncio.run(runtime.get_results_page("saved-session-001"))

        self.assertEqual(manifest.session_id, "saved-session-001")
        self.assertEqual(manifest.status.value, "completed")
        self.assertGreaterEqual(len(manifest.primary_raw_artifacts()), 1)
        self.assertGreaterEqual(len(manifest.secondary_monitor_artifacts()), 1)
        self.assertIsNotNone(results_page.selected_session)
        self.assertEqual(results_page.selected_session.session_id, "saved-session-001")
        self.assertGreater(len(results_page.detail_panels), 0)
        self.assertGreater(len(results_page.artifact_panels), 0)
        self.assertGreater(len(results_page.event_log), 0)

    def test_analyze_route_renders_visible_scaffold_from_persisted_session(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(
            app,
            method="GET",
            path="/analyze?scenario=nominal&session_id=saved-session-001",
        )

        self.assertEqual(status, "200 OK")
        self.assertIn("Persisted-session scientific review", body)
        self.assertIn("Processing Controls", body)
        self.assertIn("Analysis Controls", body)
        self.assertIn("Visible Next Backend Steps", body)

    def test_wsgi_start_flow_updates_run_route(self) -> None:
        app = self._create_app()
        status, headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/run/start",
            body={"scenario": "nominal"},
        )
        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/run?scenario=nominal")

        status, _headers, body = _call_wsgi(app, method="GET", path="/run?scenario=nominal")
        self.assertEqual(status, "200 OK")
        self.assertIn("Primary HF2 Live Data", body)
        self.assertIn("Pico Monitor Context", body)

    def test_active_docs_point_to_operator_ui_mvp(self) -> None:
        repo_root = Path(ROOT)
        ui_foundation = (repo_root / "docs" / "ui_foundation.md").read_text(encoding="utf-8")
        operator_ui_mvp = (repo_root / "docs" / "operator_ui_mvp.md").read_text(encoding="utf-8")

        self.assertIn("default operator experience centers on one `Operate` workflow", ui_foundation)
        self.assertIn("This is enough for a valid starting interface.", operator_ui_mvp)
        self.assertFalse((repo_root / "docs" / "phase3a_ui_foundation.md").exists())

    def test_ui_shell_avoids_direct_driver_and_persistence_imports(self) -> None:
        ui_root = Path(ROOT) / "ui-shell" / "src" / "ircp_ui_shell"
        banned_fragments = ("ircp_drivers", "ircp_data_pipeline", "ircp_processing", "ircp_analysis")

        for path in ui_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for fragment in banned_fragments:
                self.assertNotIn(fragment, source, f"{path.name} should not import {fragment}")


if __name__ == "__main__":
    unittest.main()
