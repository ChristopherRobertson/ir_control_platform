"""Focused operator-first Experiment page regression tests."""

from __future__ import annotations

import asyncio
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
from ircp_platform import create_simulator_app, create_simulator_runtime_map


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


class ExperimentPageMvpTests(unittest.TestCase):
    def _create_runtime_map(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return create_simulator_runtime_map(storage_root=Path(tempdir.name))

    def _create_app(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return create_simulator_app(storage_root=Path(tempdir.name))

    def _get_experiment_mode_field(self, page):
        for field in page.laser_panel.fields:
            if field.name == "experiment_type":
                return field
        self.skipTest("Experiment type selector is not present in the current Experiment page.")

    @staticmethod
    def _visible_action_labels(page) -> tuple[str, ...]:
        return tuple(button.label for button in page.laser_panel.actions if not button.hidden)

    def test_root_lands_on_the_experiment_page(self) -> None:
        app = self._create_app()

        root_status, root_headers, _ = _call_wsgi(app, method="GET", path="/")
        experiment_status, _headers, body = _call_wsgi(app, method="GET", path="/experiment")

        self.assertEqual(root_status, "303 See Other")
        self.assertEqual(root_headers["Location"], "/experiment")
        self.assertEqual(experiment_status, "200 OK")
        self.assertIn("experiment", _visible_text(body))

    def test_experiment_page_keeps_the_operator_first_core_sections(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/experiment")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        for label in (
            "mircat",
            "session",
            "nd:yag settings",
            "hf2li",
            "run control",
        ):
            self.assertIn(label, text)

    def test_experiment_page_excludes_advanced_and_legacy_device_clutter(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/experiment")
        text = _visible_text(body)

        self.assertEqual(status, "200 OK")
        for forbidden in (
            "opo",
            "pico",
            "t660",
            "mux route",
            "readiness matrix",
            "workflow review map",
            "pump shots before probe",
            "current mircat status",
            "readout component",
            "start acquisition",
            "stop acquisition",
            "acquisition status",
            "live status",
            "recent activity",
            "probe settings",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_fixed_mode_keeps_single_wavelength_controls_when_mode_switch_exists(self) -> None:
        runtimes = self._create_runtime_map()
        operate_page = asyncio.run(runtimes["nominal"].get_operate_page())
        mode_field = self._get_experiment_mode_field(operate_page)

        option_labels = {option.label for option in mode_field.options}
        action_labels = self._visible_action_labels(operate_page)
        field_labels = tuple(field.label for field in operate_page.laser_panel.fields)

        self.assertIn("Fixed Wavelength", option_labels)
        self.assertIn("Wavelength Scan", option_labels)
        self.assertIn("Emission Mode", field_labels)
        self.assertIn("Tune", action_labels)
        self.assertNotIn("Start Scan", action_labels)
        self.assertNotIn("Stop Scan", action_labels)
        self.assertIn("Wavenumber (cm^-1)", field_labels)
        self.assertNotIn("Start wavenumber (cm^-1)", field_labels)
        self.assertNotIn("Stop wavenumber (cm^-1)", field_labels)

    def test_scan_mode_swaps_in_scan_controls_when_mode_switch_exists(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]
        initial_page = asyncio.run(runtime.get_operate_page())
        self._get_experiment_mode_field(initial_page)

        asyncio.run(runtime.set_experiment_type("wavelength_scan"))
        operate_page = asyncio.run(runtime.get_operate_page())

        action_labels = self._visible_action_labels(operate_page)
        field_labels = tuple(field.label for field in operate_page.laser_panel.fields)

        self.assertIn("Start Scan", action_labels)
        self.assertIn("Stop Scan", action_labels)
        self.assertNotIn("Tune", action_labels)
        self.assertIn("Emission Mode", field_labels)
        self.assertIn("Start wavenumber (cm^-1)", field_labels)
        self.assertIn("Stop wavenumber (cm^-1)", field_labels)
        self.assertIn("Scan Speed", field_labels)
        self.assertNotIn("Dwell time per point (ms)", field_labels)
        self.assertNotIn("Wavenumber (cm^-1)", field_labels)

    def test_pulsed_mode_exposes_pulse_fields(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]
        asyncio.run(
            runtime.configure_operating_mode(
                experiment_type="fixed_wavelength",
                emission_mode="pulsed",
            )
        )
        operate_page = asyncio.run(runtime.get_operate_page())
        field_labels = {field.label for field in operate_page.laser_panel.fields}

        self.assertIn("Pulse repetition rate (Hz)", field_labels)
        self.assertIn("Pulse width (ns)", field_labels)
        self.assertIn("Duty cycle (%)", field_labels)

    def test_ui_shell_stays_on_typed_presentation_boundaries(self) -> None:
        ui_root = Path(ROOT) / "ui-shell" / "src" / "ircp_ui_shell"
        boundary_source = (ui_root / "boundaries.py").read_text(encoding="utf-8")
        banned_fragments = (
            "ircp_drivers",
            "ircp_data_pipeline",
            "ircp_processing",
            "ircp_analysis",
            "Control_System",
        )

        self.assertIn("class UiQueryService(Protocol)", boundary_source)
        self.assertIn("class UiCommandService(Protocol)", boundary_source)
        self.assertIn("class UiRuntimeGateway(UiQueryService, UiCommandService, Protocol)", boundary_source)

        for path in ui_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for fragment in banned_fragments:
                self.assertNotIn(fragment, source, f"{path.name} should not import {fragment}")


if __name__ == "__main__":
    unittest.main()
