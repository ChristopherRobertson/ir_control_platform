"""Rendered UI tests for the v1 Session / Setup / Results shell."""

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
except ModuleNotFoundError:  # pragma: no cover
    from tests._path_setup import ROOT
from ircp_platform import create_simulator_app


def _call_wsgi(app, *, method: str, path: str, body: dict[str, str] | None = None):
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method.upper()
    if "?" in path:
        route_path, query = path.split("?", 1)
    else:
        route_path, query = path, ""
    environ["PATH_INFO"] = route_path
    environ["QUERY_STRING"] = query
    encoded = urlencode(body or {}).encode("utf-8")
    environ["CONTENT_LENGTH"] = str(len(encoded))
    environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    environ["wsgi.input"] = BytesIO(encoded)
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    payload = b"".join(app(environ, start_response))
    return str(captured["status"]), captured["headers"], payload.decode("utf-8")


def _visible_text(markup: str) -> str:
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", markup, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip().lower()


class V1UiShellTests(unittest.TestCase):
    def _app(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return create_simulator_app(storage_root=Path(tempdir.name))

    def _app_at(self, root: Path):
        return create_simulator_app(storage_root=root)

    def test_root_redirects_to_session(self) -> None:
        app = self._app()

        status, headers, _ = _call_wsgi(app, method="GET", path="/")

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/session")

    def test_header_navigation_has_no_fourth_page(self) -> None:
        app = self._app()

        status, _headers, body = _call_wsgi(app, method="GET", path="/session")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        self.assertIn("session", text)
        self.assertIn("setup", text)
        self.assertIn("results", text)
        for forbidden in ("run page", "advanced", "service", "analyze", "dashboard"):
            self.assertNotIn(forbidden, text)

    def test_setup_renders_required_order_and_no_forbidden_controls(self) -> None:
        app = self._app()

        status, _headers, body = _call_wsgi(app, method="GET", path="/setup")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        ordered_markers = [
            "pump settings",
            "timescale",
            "probe settings",
            "lock-in amplifier settings",
            "run controls",
        ]
        positions = [text.index(marker) for marker in ordered_markers]
        self.assertEqual(positions, sorted(positions))
        for forbidden in (
            "step size",
            "number of points",
            "linear spacing",
            "logarithmic spacing",
            "adaptive",
            "data acquisition section",
            "preflight",
            "start scan",
            "wavelength sweep",
            "real-time",
        ):
            self.assertNotIn(forbidden, text)

    def test_setup_includes_client_side_pump_toggle_script(self) -> None:
        app = self._app()

        status, _headers, body = _call_wsgi(app, method="GET", path="/setup")

        self.assertEqual(status, "200 OK")
        self.assertIn('input[name="pump_enabled"]', body)
        self.assertIn('input[name="shot_count"]', body)
        self.assertIn('shotCount.disabled = !pumpEnabled.checked;', body)

    def test_setup_includes_client_side_draft_persistence_script(self) -> None:
        app = self._app()

        status, _headers, body = _call_wsgi(app, method="GET", path="/setup")

        self.assertEqual(status, "200 OK")
        self.assertIn('form[action="/setup/save"]', body)
        self.assertIn('ircp.setupDraft', body)
        self.assertIn('window.sessionStorage.setItem(setupDraftKey, JSON.stringify(draft));', body)
        self.assertIn('window.sessionStorage.removeItem(setupDraftKey);', body)

    def test_setup_includes_client_side_probe_toggle_script(self) -> None:
        app = self._app()

        status, _headers, body = _call_wsgi(app, method="GET", path="/setup")

        self.assertEqual(status, "200 OK")
        self.assertIn('select[name="emission_mode"]', body)
        self.assertIn('input[name="pulse_rate_hz"]', body)
        self.assertIn('input[name="pulse_width_ns"]', body)
        self.assertIn('pulseRate.disabled = !pulsed;', body)
        self.assertIn('pulseWidth.disabled = !pulsed;', body)

    def test_post_workflow_runs_and_results_render_saved_data(self) -> None:
        app = self._app()

        _call_wsgi(
            app,
            method="POST",
            path="/session/save",
            body={
                "session_name": "Session A",
                "operator": "Operator",
                "sample_id": "Sample",
                "sample_notes": "",
                "experiment_notes": "",
            },
        )
        _call_wsgi(app, method="POST", path="/session/run/save", body={"run_name": "Run 1", "run_notes": ""})
        _call_wsgi(
            app,
            method="POST",
            path="/setup/save",
            body={
                "pump_enabled": "1",
                "shot_count": "10",
                "timescale": "microseconds",
                "wavelength_cm1": "1850",
                "emission_mode": "cw",
                "pulse_rate_hz": "",
                "pulse_width_ns": "",
                "order": "2",
                "time_constant_seconds": "0.1",
                "transfer_rate_hz": "224.9",
            },
        )
        status, headers, _ = _call_wsgi(app, method="POST", path="/setup/run/start")
        results_status, _headers, results_body = _call_wsgi(app, method="GET", path="/results?metric=R&display=ratio")
        text = _visible_text(results_body)

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/results")
        self.assertEqual(results_status, "200 OK")
        self.assertIn("result plot", text)
        self.assertIn("-log(sample/reference)", text)
        self.assertIn("export", text)

    def test_session_page_renders_open_buttons_and_disables_run_open_until_session_opened(self) -> None:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        app = self._app_at(root)

        _call_wsgi(
            app,
            method="POST",
            path="/session/save",
            body={
                "session_name": "Session A",
                "operator": "Operator",
                "sample_id": "Sample",
                "sample_notes": "",
                "experiment_notes": "",
            },
        )
        _call_wsgi(app, method="POST", path="/session/run/save", body={"run_name": "Run 1", "run_notes": ""})
        second_app = self._app_at(root)
        status, _headers, body = _call_wsgi(second_app, method="GET", path="/session")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        self.assertIn("open existing session", text)
        self.assertIn("open existing run for review", text)
        self.assertIn("open the session first.", text)
        self.assertIn('action="/session/open"', body)
        self.assertIn('action="/session/run/open"', body)
        self.assertIn('disabled', body)

    def test_opening_run_without_opening_session_is_rejected(self) -> None:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        original = self._app_at(root)
        reopened = self._app_at(root)

        _call_wsgi(
            original,
            method="POST",
            path="/session/save",
            body={
                "session_name": "Session A",
                "operator": "Operator",
                "sample_id": "Sample",
                "sample_notes": "",
                "experiment_notes": "",
            },
        )
        _call_wsgi(original, method="POST", path="/session/run/save", body={"run_name": "Run 1", "run_notes": ""})

        status, _headers, response = _call_wsgi(
            reopened,
            method="POST",
            path="/session/run/open",
            body={"session_id": "Session A", "run_id": "Run 1"},
        )

        self.assertEqual(status, "400 Bad Request")
        self.assertIn("Open the session before opening one of its runs.", response)

    def test_open_session_then_open_run_populates_session_page(self) -> None:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        original = self._app_at(root)
        reopened = self._app_at(root)

        _call_wsgi(
            original,
            method="POST",
            path="/session/save",
            body={
                "session_name": "Session A",
                "operator": "Operator",
                "sample_id": "Sample",
                "sample_notes": "",
                "experiment_notes": "",
            },
        )
        _call_wsgi(original, method="POST", path="/session/run/save", body={"run_name": "Run 1", "run_notes": "Run notes"})

        open_session_status, open_session_headers, _ = _call_wsgi(
            reopened,
            method="POST",
            path="/session/open",
            body={"session_id": "Session A"},
        )
        open_run_status, open_run_headers, _ = _call_wsgi(
            reopened,
            method="POST",
            path="/session/run/open",
            body={"session_id": "Session A", "run_id": "Run 1"},
        )
        status, _headers, body = _call_wsgi(reopened, method="GET", path="/session")

        self.assertEqual(open_session_status, "303 See Other")
        self.assertEqual(open_session_headers["Location"], "/session")
        self.assertEqual(open_run_status, "303 See Other")
        self.assertEqual(open_run_headers["Location"], "/session")
        self.assertEqual(status, "200 OK")
        self.assertIn('value="Session A"', body)
        self.assertIn('value="Run 1"', body)
        self.assertIn("Run notes", body)

    def test_duplicate_session_id_redirects_to_overwrite_prompt(self) -> None:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        app = self._app_at(root)
        body = {
            "session_name": "Session A",
            "operator": "Operator",
            "sample_id": "Sample",
            "sample_notes": "",
            "experiment_notes": "",
        }

        _call_wsgi(app, method="POST", path="/session/save", body=body)
        duplicate_app = self._app_at(root)
        status, _headers, response = _call_wsgi(duplicate_app, method="POST", path="/session/save", body=body)

        self.assertEqual(status, "303 See Other")
        self.assertEqual(_headers["Location"], "/session")
        self.assertEqual(response, "")

    def test_duplicate_session_prompts_for_overwrite(self) -> None:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        app = self._app_at(root)
        body = {
            "session_name": "Session A",
            "operator": "Operator",
            "sample_id": "Sample",
            "sample_notes": "",
            "experiment_notes": "",
        }

        _call_wsgi(app, method="POST", path="/session/save", body=body)
        duplicate_app = self._app_at(root)
        status, headers, _ = _call_wsgi(duplicate_app, method="POST", path="/session/save", body=body)
        session_status, _headers, markup = _call_wsgi(duplicate_app, method="GET", path=headers["Location"])
        text = _visible_text(markup)

        self.assertEqual(status, "303 See Other")
        self.assertEqual(session_status, "200 OK")
        self.assertIn("a saved session already uses this name / id.", text)
        self.assertIn("overwrite", text)
        self.assertIn("cancel", text)

    def test_cancel_overwrite_keeps_conflict_highlight_visible(self) -> None:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        original = self._app_at(root)
        body = {
            "session_name": "Session A",
            "operator": "Operator",
            "sample_id": "Sample",
            "sample_notes": "",
            "experiment_notes": "",
        }

        _call_wsgi(original, method="POST", path="/session/save", body=body)
        duplicate_app = self._app_at(root)
        _call_wsgi(duplicate_app, method="POST", path="/session/save", body=body)
        _call_wsgi(duplicate_app, method="POST", path="/session/overwrite/cancel")
        status, _headers, markup = _call_wsgi(duplicate_app, method="GET", path="/session")
        text = _visible_text(markup)

        self.assertEqual(status, "200 OK")
        self.assertIn("a saved session already uses this name / id.", text)
        self.assertIn('class="field invalid"', markup)

    def test_confirm_overwrite_replaces_saved_session_metadata(self) -> None:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        root = Path(tempdir.name)
        original = self._app_at(root)
        duplicate = self._app_at(root)

        _call_wsgi(
            original,
            method="POST",
            path="/session/save",
            body={
                "session_name": "Session A",
                "operator": "Original Operator",
                "sample_id": "Sample",
                "sample_notes": "",
                "experiment_notes": "Original",
            },
        )
        _call_wsgi(
            duplicate,
            method="POST",
            path="/session/save",
            body={
                "session_name": "Session A",
                "operator": "Updated Operator",
                "sample_id": "Sample B",
                "sample_notes": "Updated sample",
                "experiment_notes": "Updated",
            },
        )
        _call_wsgi(duplicate, method="POST", path="/session/overwrite")
        status, _headers, markup = _call_wsgi(duplicate, method="GET", path="/session")
        text = _visible_text(markup)

        self.assertEqual(status, "200 OK")
        self.assertIn('value="Updated Operator"', markup)
        self.assertIn('Updated sample', markup)

    def test_ui_shell_does_not_import_device_or_data_packages(self) -> None:
        ui_root = Path(ROOT) / "ui-shell" / "src" / "ircp_ui_shell"
        old_repo_name = "Control" + "_" + "System"
        banned = ("ircp_drivers", "ircp_data_pipeline", "ircp_processing", "ircp_analysis", old_repo_name)
        for path in ui_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for fragment in banned:
                self.assertNotIn(fragment, source, f"{path.name} imports {fragment}")


if __name__ == "__main__":
    unittest.main()
