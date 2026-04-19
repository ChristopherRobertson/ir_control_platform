"""Finished UI shell regression tests."""

from __future__ import annotations

import re
import unittest
from html import unescape
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

try:
    from _path_setup import ROOT  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - depends on unittest invocation style
    from tests._path_setup import ROOT
from ircp_platform import create_simulator_app


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


def _visible_text(markup: str) -> str:
    markup = re.sub(r"<style\b[^>]*>.*?</style>", " ", markup, flags=re.IGNORECASE | re.DOTALL)
    markup = re.sub(r"<script\b[^>]*>.*?</script>", " ", markup, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", markup)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip().lower()


class FinishedUiShellTests(unittest.TestCase):
    def _create_app(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return create_simulator_app(storage_root=Path(tempdir.name))

    def test_root_redirects_to_experiment(self) -> None:
        app = self._create_app()

        status, headers, _body = _call_wsgi(app, method="GET", path="/")

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/experiment")

    def test_header_navigation_and_scenario_switcher_render_on_primary_routes(self) -> None:
        app = self._create_app()

        status, _headers, body = _call_wsgi(app, method="GET", path="/setup?scenario=blocked_timing")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        for label in ("experiment", "setup", "run", "results", "analyze", "advanced", "service"):
            self.assertIn(label, text)
        for scenario_label in ("nominal", "blocked timing", "faulted hf2", "pico optional"):
            self.assertIn(scenario_label, text)
        self.assertIn("route setup", text)
        self.assertIn("scenario blocked timing", text)

    def test_experiment_route_renders_finished_mission_control(self) -> None:
        app = self._create_app()

        _call_wsgi(
            app,
            method="POST",
            path="/run/start",
            body={"scenario": "nominal"},
        )
        status, _headers, body = _call_wsgi(app, method="GET", path="/experiment")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        for marker in (
            "experiment",
            "current configuration",
            "hardware visibility",
            "recent activity",
            "live data",
            "open setup workspace",
            "open run workspace",
            "results handoff",
            "start run",
        ):
            self.assertIn(marker, text)

    def test_setup_route_renders_preparation_workspace(self) -> None:
        app = self._create_app()

        status, _headers, body = _call_wsgi(app, method="GET", path="/setup")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        for marker in (
            "setup",
            "preflight / validation",
            "readiness and defaults",
            "hardware readiness",
            "timing and synchronization detail",
            "acquisition and routing detail",
            "run preflight",
            "open run workspace",
        ):
            self.assertIn(marker, text)

    def test_run_route_renders_live_workspace_after_start(self) -> None:
        app = self._create_app()

        start_status, start_headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/run/start",
            body={"scenario": "nominal"},
        )
        run_status, _headers, run_body = _call_wsgi(app, method="GET", path="/run")
        text = _visible_text(run_body)

        self.assertEqual(start_status, "303 See Other")
        self.assertEqual(start_headers["Location"], "/run")
        self.assertEqual(run_status, "200 OK")
        for marker in (
            "run completed",
            "run metadata",
            "hardware health",
            "run timeline",
            "live data review",
            "open results",
            "latest run timeline",
            "lifecycle coverage",
        ):
            self.assertIn(marker, text)

    def test_results_route_renders_persisted_review_workspace(self) -> None:
        app = self._create_app()

        status, _headers, body = _call_wsgi(app, method="GET", path="/results?scenario=nominal")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        for marker in (
            "recent sessions",
            "overview and provenance",
            "visualization and trace review",
            "artifacts and provenance",
            "download and export",
            "download manifest",
            "compare to baseline",
            "reopen in setup",
        ):
            self.assertIn(marker, text)

    def test_service_route_renders_expert_workspace(self) -> None:
        app = self._create_app()

        status, _headers, body = _call_wsgi(app, method="GET", path="/service?scenario=nominal")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        for marker in (
            "device diagnostics",
            "service context",
            "calibration visibility",
            "recovery and maintenance",
            "capture config snapshot",
            "reapply guarded calibration",
            "attempt recovery",
        ):
            self.assertIn(marker, text)

    def test_analyze_route_renders_explicit_disabled_analysis_actions(self) -> None:
        app = self._create_app()

        status, _headers, body = _call_wsgi(
            app,
            method="GET",
            path="/analyze?scenario=nominal&session_id=saved-session-001",
        )
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        for marker in (
            "reprocessing and comparison",
            "saved-session inputs",
            "reprocess session",
            "compare against baseline",
            "generate metrics",
            "explicit disabled analysis actions",
        ):
            self.assertIn(marker, text)

    def test_setup_preflight_post_redirects_to_setup(self) -> None:
        app = self._create_app()

        status, headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/setup/preflight",
            body={"scenario": "nominal"},
        )

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/setup")

    def test_run_start_and_abort_posts_redirect_to_run(self) -> None:
        app = self._create_app()

        start_status, start_headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/run/start",
            body={"scenario": "nominal"},
        )
        abort_status, abort_headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/run/abort",
            body={"scenario": "nominal"},
        )

        self.assertEqual(start_status, "303 See Other")
        self.assertEqual(start_headers["Location"], "/run")
        self.assertEqual(abort_status, "303 See Other")
        self.assertEqual(abort_headers["Location"], "/run")

    def test_results_reopen_redirects_to_setup_and_stages_new_session_id(self) -> None:
        app = self._create_app()

        reopen_status, reopen_headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/results/reopen",
            body={"scenario": "nominal", "recent_session_id": "saved-session-001"},
        )
        setup_status, _headers, setup_body = _call_wsgi(app, method="GET", path="/setup")

        self.assertEqual(reopen_status, "303 See Other")
        self.assertEqual(reopen_headers["Location"], "/setup")
        self.assertEqual(setup_status, "200 OK")
        self.assertIn('value="saved-session-001-rerun"', setup_body)

    def test_results_download_routes_work(self) -> None:
        app = self._create_app()

        manifest_status, manifest_headers, manifest_body = _call_wsgi(
            app,
            method="GET",
            path="/results/download?scenario=nominal&session_id=saved-session-001&asset=manifest",
        )
        events_status, events_headers, events_body = _call_wsgi(
            app,
            method="GET",
            path="/results/download?scenario=nominal&session_id=saved-session-001&asset=events",
        )

        self.assertEqual(manifest_status, "200 OK")
        self.assertEqual(manifest_headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn('"session_id": "saved-session-001"', manifest_body)

        self.assertEqual(events_status, "200 OK")
        self.assertEqual(events_headers["Content-Type"], "application/x-ndjson; charset=utf-8")
        self.assertIn('"event_id": "saved-session-event-created"', events_body)

    def test_results_empty_invalid_and_no_selection_states_render(self) -> None:
        app = self._create_app()

        filtered_status, _headers, filtered_body = _call_wsgi(
            app,
            method="GET",
            path="/results?scenario=nominal&search=no-match",
        )
        invalid_status, _headers, invalid_body = _call_wsgi(
            app,
            method="GET",
            path="/results?scenario=nominal&session_id=missing-session-999",
        )
        cleared_status, _headers, cleared_body = _call_wsgi(
            app,
            method="GET",
            path="/results?scenario=nominal&session_id=__none__",
        )

        self.assertEqual(filtered_status, "200 OK")
        self.assertIn("No sessions match the current filter", filtered_body)
        self.assertEqual(invalid_status, "200 OK")
        self.assertIn("Saved session not found", invalid_body)
        self.assertEqual(cleared_status, "200 OK")
        self.assertIn("No session selected", cleared_body)

    def test_blocked_setup_and_faulted_run_states_are_explicit(self) -> None:
        app = self._create_app()

        blocked_status, _headers, blocked_body = _call_wsgi(
            app,
            method="GET",
            path="/setup?scenario=blocked_timing",
        )
        start_status, start_headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/run/start",
            body={"scenario": "faulted_hf2"},
        )
        faulted_status, _headers, faulted_body = _call_wsgi(
            app,
            method="GET",
            path="/run?scenario=faulted_hf2",
        )

        self.assertEqual(blocked_status, "200 OK")
        self.assertIn("Setup blocked", blocked_body)
        self.assertIn("A hidden timing dependency is unavailable for this experiment.", blocked_body)
        self.assertEqual(start_status, "303 See Other")
        self.assertEqual(start_headers["Location"], "/run?scenario=faulted_hf2")
        self.assertEqual(faulted_status, "200 OK")
        self.assertIn("Run faulted", faulted_body)
        self.assertIn("HF2 reported a simulated overload fault on the canonical path.", faulted_body)

    def test_delete_session_route_removes_saved_session_and_files(self) -> None:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        storage_root = Path(tempdir.name)
        app = create_simulator_app(storage_root=storage_root)
        sessions_root = storage_root / "sessions"
        seeded_session_id = "saved-session-001"
        seeded_session_dir = sessions_root / seeded_session_id
        seeded_dir_exists = seeded_session_dir.is_dir()

        delete_status, delete_headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/experiment/session/delete",
            body={"scenario": "nominal", "recent_session_id": seeded_session_id},
        )
        page_status, _headers, page_body = _call_wsgi(app, method="GET", path="/setup")

        self.assertEqual(delete_status, "303 See Other")
        self.assertEqual(delete_headers["Location"], "/experiment")
        if seeded_dir_exists:
            self.assertFalse(seeded_session_dir.exists())
        self.assertEqual(page_status, "200 OK")
        self.assertNotIn(f'<option value="{seeded_session_id}"', page_body)

    def test_ui_shell_boundaries_stay_thin_and_expose_setup_and_run_queries(self) -> None:
        ui_root = Path(ROOT) / "ui-shell" / "src" / "ircp_ui_shell"
        boundary_source = (ui_root / "boundaries.py").read_text(encoding="utf-8")
        banned_fragments = (
            "ircp_drivers",
            "ircp_data_pipeline",
            "ircp_processing",
            "ircp_analysis",
            "Control_System",
        )

        self.assertIn("async def get_setup_page", boundary_source)
        self.assertIn("async def get_run_page", boundary_source)

        for path in ui_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for fragment in banned_fragments:
                self.assertNotIn(fragment, source, f"{path.name} should not import {fragment}")


if __name__ == "__main__":
    unittest.main()
