"""Phase 3A UI foundation and simulator-backed runtime tests."""

from __future__ import annotations

import asyncio
import unittest
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from _path_setup import ROOT  # noqa: F401
from ircp_contracts import RunPhase
from ircp_platform import create_phase3a_runtime_map, create_phase3a_simulator_app
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


class Phase3AUiFoundationTests(unittest.TestCase):
    def test_root_redirects_to_setup(self) -> None:
        app = create_phase3a_simulator_app()
        status, headers, _body = _call_wsgi(app, method="GET", path="/")

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/setup?scenario=nominal")

    def test_setup_route_renders_nominal_preflight_shell(self) -> None:
        app = create_phase3a_simulator_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/setup?scenario=nominal")

        self.assertEqual(status, "200 OK")
        self.assertIn("Preflight Summary", body)
        self.assertIn("MIRcat sweep with HF2LI capture", body)
        self.assertIn("Overall: ready", body)

    def test_blocked_scenario_shows_explicit_blocked_state(self) -> None:
        runtimes = create_phase3a_runtime_map()
        blocked_page = asyncio.run(runtimes["blocked"].get_setup_page())

        self.assertIsNotNone(blocked_page.state)
        self.assertEqual(blocked_page.state.kind, PageStateKind.BLOCKED)
        self.assertIn("blocking", blocked_page.state.message.lower())

    def test_nominal_start_run_materializes_timeline_and_live_data(self) -> None:
        runtimes = create_phase3a_runtime_map()
        runtime = runtimes["nominal"]

        run_state = asyncio.run(runtime.start_run())
        run_page = asyncio.run(runtime.get_run_page())
        results_page = asyncio.run(runtime.get_results_page())

        self.assertEqual(run_state.phase, RunPhase.COMPLETED)
        self.assertIsNotNone(run_state.session_id)
        self.assertIsNotNone(run_page.run_id)
        self.assertGreaterEqual(len(run_page.run_steps), 3)
        self.assertGreater(len(run_page.event_log), 0)
        self.assertGreater(len(run_page.live_data), 0)
        self.assertTrue(any(card.session_id == run_state.session_id for card in results_page.sessions))

    def test_faulted_scenario_surfaces_fault_page_state(self) -> None:
        runtimes = create_phase3a_runtime_map()
        runtime = runtimes["faulted"]

        run_state = asyncio.run(runtime.start_run())
        run_page = asyncio.run(runtime.get_run_page())

        self.assertEqual(run_state.phase, RunPhase.FAULTED)
        self.assertIsNotNone(run_page.state)
        self.assertEqual(run_page.state.kind, PageStateKind.FAULT)
        self.assertIn("fault", run_page.state.message.lower())

    def test_results_reopen_uses_saved_session_fixture(self) -> None:
        runtimes = create_phase3a_runtime_map()
        runtime = runtimes["nominal"]

        manifest = asyncio.run(runtime.reopen_session("saved-session-001"))
        results_page = asyncio.run(runtime.get_results_page("saved-session-001"))

        self.assertEqual(manifest.session_id, "saved-session-001")
        self.assertEqual(manifest.status.value, "completed")
        self.assertIsNotNone(results_page.selected_session)
        self.assertEqual(results_page.selected_session.session_id, "saved-session-001")
        self.assertGreater(len(results_page.manifest_details), 0)

    def test_wsgi_start_flow_updates_run_route(self) -> None:
        app = create_phase3a_simulator_app()
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
        self.assertIn("Run Progression", body)
        self.assertIn("Event Timeline", body)

    def test_ui_shell_avoids_direct_driver_and_persistence_imports(self) -> None:
        ui_root = Path(ROOT) / "ui-shell" / "src" / "ircp_ui_shell"
        banned_fragments = ("ircp_drivers", "ircp_data_pipeline", "ircp_processing", "ircp_analysis")

        for path in ui_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for fragment in banned_fragments:
                self.assertNotIn(fragment, source, f"{path.name} should not import {fragment}")


if __name__ == "__main__":
    unittest.main()
