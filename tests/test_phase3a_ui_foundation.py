"""Operator-first UI shell regression tests."""

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


class OperatorFirstUiTests(unittest.TestCase):
    def _create_runtime_map(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return create_phase3b_runtime_map(storage_root=Path(tempdir.name))

    def _create_app(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return create_phase3b_simulator_app(storage_root=Path(tempdir.name))

    def test_root_redirects_to_operate(self) -> None:
        app = self._create_app()
        status, headers, _body = _call_wsgi(app, method="GET", path="/")

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/operate?scenario=nominal")

    def test_compatibility_routes_redirect_to_new_surfaces(self) -> None:
        app = self._create_app()

        setup_status, setup_headers, _ = _call_wsgi(app, method="GET", path="/setup?scenario=nominal")
        run_status, run_headers, _ = _call_wsgi(app, method="GET", path="/run?scenario=nominal")
        advanced_status, advanced_headers, _ = _call_wsgi(app, method="GET", path="/setup/advanced?scenario=nominal")

        self.assertEqual(setup_status, "303 See Other")
        self.assertEqual(setup_headers["Location"], "/operate?scenario=nominal")
        self.assertEqual(run_status, "303 See Other")
        self.assertEqual(run_headers["Location"], "/operate?scenario=nominal")
        self.assertEqual(advanced_status, "303 See Other")
        self.assertEqual(advanced_headers["Location"], "/advanced?scenario=nominal")

    def test_operate_route_renders_task_first_sections(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/operate?scenario=nominal")

        self.assertEqual(status, "200 OK")
        for label in (
            "Operate",
            "Session",
            "Laser",
            "HF2LI / Acquisition",
            "Run Control",
            "Live Status",
            "Recent Activity",
            "Save Session",
            "Run Preflight",
        ):
            self.assertIn(label, body)
        self.assertNotIn("Workflow Review Map", body)
        self.assertNotIn("Readiness Matrix", body)
        self.assertNotIn("Continue to Run", body)

    def test_primary_navigation_uses_operator_first_labels(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/operate?scenario=nominal")

        self.assertEqual(status, "200 OK")
        self.assertIn(">Operate<", body)
        self.assertIn(">Results<", body)
        self.assertIn(">Advanced<", body)
        self.assertIn(">Service<", body)
        self.assertNotIn(">Setup<", body)
        self.assertNotIn(">Run<", body)

    def test_blocked_timing_scenario_shows_blocked_operate_state(self) -> None:
        runtimes = self._create_runtime_map()
        operate_page = asyncio.run(runtimes["blocked_timing"].get_operate_page())

        self.assertIsNotNone(operate_page.state)
        self.assertEqual(operate_page.state.kind, PageStateKind.BLOCKED)
        self.assertIn("blocking", operate_page.state.message.lower())

    def test_optional_pico_unavailability_surfaces_warning_not_block(self) -> None:
        runtimes = self._create_runtime_map()
        operate_page = asyncio.run(runtimes["pico_optional"].get_operate_page())

        self.assertIsNotNone(operate_page.state)
        self.assertEqual(operate_page.state.kind, PageStateKind.WARNING)
        self.assertIn("optional", operate_page.state.message.lower())

    def test_save_session_and_start_run_flow_updates_operate_and_results(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]

        manifest = asyncio.run(runtime.save_session("Bench MVP", "sample-42", "operator review"))
        run_state = asyncio.run(runtime.start_run())
        operate_page = asyncio.run(runtime.get_operate_page())
        results_page = asyncio.run(runtime.get_results_page(run_state.session_id))

        self.assertEqual(manifest.session_id, run_state.session_id)
        self.assertEqual(run_state.phase, RunPhase.COMPLETED)
        self.assertTrue(any(item.label == "Current session" and run_state.session_id in item.value for item in operate_page.session_panel.status_items))
        self.assertGreater(len(operate_page.recent_activity), 0)
        self.assertIsNotNone(results_page.selected_session)
        self.assertEqual(results_page.selected_session.session_id, run_state.session_id)
        self.assertGreaterEqual(len(results_page.artifact_panels), 1)
        self.assertGreaterEqual(len(results_page.event_log), 1)

    def test_operate_post_routes_redirect_back_to_operate(self) -> None:
        app = self._create_app()
        status, headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/operate/session/save",
            body={
                "scenario": "nominal",
                "session_label": "Bench MVP",
                "sample_id": "sample-42",
                "operator_notes": "operator review",
            },
        )

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/operate?scenario=nominal")

    def test_results_and_advanced_routes_render_secondary_surfaces(self) -> None:
        app = self._create_app()

        results_status, _headers, results_body = _call_wsgi(app, method="GET", path="/results?scenario=nominal")
        advanced_status, _headers, advanced_body = _call_wsgi(app, method="GET", path="/advanced?scenario=nominal")

        self.assertEqual(results_status, "200 OK")
        self.assertIn("Recent Sessions", results_body)
        self.assertIn("Artifacts and Provenance", results_body)

        self.assertEqual(advanced_status, "200 OK")
        self.assertIn("Timing and marker detail", advanced_body)
        self.assertIn("Readiness Matrix", advanced_body)
        self.assertNotIn("Live Status", advanced_body)

    def test_service_and_analyze_routes_remain_available_but_secondary(self) -> None:
        app = self._create_app()

        service_status, _headers, service_body = _call_wsgi(app, method="GET", path="/service?scenario=nominal")
        analyze_status, _headers, analyze_body = _call_wsgi(
            app,
            method="GET",
            path="/analyze?scenario=nominal&session_id=saved-session-001",
        )

        self.assertEqual(service_status, "200 OK")
        self.assertIn("Device Diagnostics", service_body)

        self.assertEqual(analyze_status, "200 OK")
        self.assertIn("Secondary persisted-session review surface", analyze_body)
        self.assertIn("Analyze Preview", analyze_body)

    def test_active_docs_point_to_operator_ui_mvp(self) -> None:
        repo_root = Path(ROOT)
        ui_foundation = (repo_root / "docs" / "ui_foundation.md").read_text(encoding="utf-8")
        operator_ui_mvp = (repo_root / "docs" / "operator_ui_mvp.md").read_text(encoding="utf-8")

        self.assertIn("default operator experience centers on one `Operate` workflow", ui_foundation)
        self.assertIn("This is the active next-pass UI target.", operator_ui_mvp)

    def test_ui_shell_avoids_direct_driver_and_persistence_imports(self) -> None:
        ui_root = Path(ROOT) / "ui-shell" / "src" / "ircp_ui_shell"
        banned_fragments = ("ircp_drivers", "ircp_data_pipeline", "ircp_processing", "ircp_analysis")

        for path in ui_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for fragment in banned_fragments:
                self.assertNotIn(fragment, source, f"{path.name} should not import {fragment}")


if __name__ == "__main__":
    unittest.main()
