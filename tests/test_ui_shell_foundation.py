"""Operator-first UI shell regression tests."""

from __future__ import annotations

import asyncio
import re
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

try:
    from _path_setup import ROOT  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - depends on unittest invocation style
    from tests._path_setup import ROOT
from ircp_contracts import DeviceKind, RunPhase
from ircp_experiment_engine.runtime import build_fault, device_status_from_fault
from ircp_platform import create_simulator_app, create_simulator_runtime_map
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
        return create_simulator_runtime_map(storage_root=Path(tempdir.name))

    def _create_app(self):
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return create_simulator_app(storage_root=Path(tempdir.name))

    @staticmethod
    def _visible_action_buttons(panel):
        return tuple(button for button in panel.actions if not button.hidden)

    def test_root_redirects_to_experiment(self) -> None:
        app = self._create_app()
        status, headers, _body = _call_wsgi(app, method="GET", path="/")

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/experiment")

    def test_compatibility_routes_redirect_to_experiment(self) -> None:
        app = self._create_app()

        operate_status, operate_headers, _ = _call_wsgi(app, method="GET", path="/operate?scenario=nominal")
        setup_status, setup_headers, _ = _call_wsgi(app, method="GET", path="/setup?scenario=nominal")
        run_status, run_headers, _ = _call_wsgi(app, method="GET", path="/run?scenario=nominal")
        advanced_status, advanced_headers, _ = _call_wsgi(app, method="GET", path="/setup/advanced?scenario=nominal")

        self.assertEqual(operate_status, "303 See Other")
        self.assertEqual(operate_headers["Location"], "/experiment")
        self.assertEqual(setup_status, "303 See Other")
        self.assertEqual(setup_headers["Location"], "/experiment")
        self.assertEqual(run_status, "303 See Other")
        self.assertEqual(run_headers["Location"], "/experiment")
        self.assertEqual(advanced_status, "303 See Other")
        self.assertEqual(advanced_headers["Location"], "/advanced")

    def test_experiment_route_renders_minimal_sections(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/experiment")

        self.assertEqual(status, "200 OK")
        for label in (
            "MIRcat",
            "Fixed Wavelength",
            "Wavelength Scan",
            "Session",
            "Nd:YAG Settings",
            "HF2LI",
            "Run Control",
            "Save Session",
            "Run Preflight",
            "Start Experiment",
        ):
            self.assertIn(label, body)
        self.assertNotIn("Workflow Review Map", body)
        self.assertNotIn("Readiness Matrix", body)
        self.assertNotIn("Continue to Run", body)
        self.assertNotIn("Pump Shots Before Probe", body)
        self.assertNotIn("MUX Route Set", body)
        self.assertNotIn("Pico Secondary Capture", body)
        self.assertNotIn("T660-2", body)
        self.assertNotIn("Trigger layout only for now", body)
        self.assertNotIn("Current MIRcat status", body)
        self.assertNotIn("Readout component", body)
        self.assertNotIn("Start Acquisition", body)
        self.assertNotIn("Stop Acquisition", body)
        self.assertNotIn("Acquisition status", body)
        self.assertNotIn("Live Status", body)
        self.assertNotIn("Recent Activity / Messages", body)
        self.assertNotIn("Probe Settings", body)

    def test_default_experiment_shell_hides_multi_page_navigation(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/experiment")

        self.assertEqual(status, "200 OK")
        self.assertNotIn(">Operate<", body)
        self.assertNotIn(">Results<", body)
        self.assertNotIn(">Advanced<", body)
        self.assertNotIn(">Service<", body)
        self.assertNotIn('class="scenario-chip', body)
        self.assertNotIn('class="nav-link', body)

    def test_blocked_timing_scenario_shows_blocked_experiment_state(self) -> None:
        runtimes = self._create_runtime_map()
        operate_page = asyncio.run(runtimes["blocked_timing"].get_operate_page())
        state = operate_page.state

        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state.kind, PageStateKind.BLOCKED)
        self.assertIn("blocking", state.message.lower())

    def test_mircat_panel_uses_toggle_controls(self) -> None:
        runtimes = self._create_runtime_map()
        operate_page = asyncio.run(runtimes["nominal"].get_operate_page())
        visible_actions = self._visible_action_buttons(operate_page.laser_panel)

        self.assertEqual(tuple(button.label for button in operate_page.laser_panel.header_actions), ("Disconnect",))
        self.assertEqual(operate_page.laser_panel.header_actions[0].tone, "danger")
        self.assertEqual(tuple(button.label for button in visible_actions), ("Arm", "Tune", "Emission On"))
        self.assertEqual(operate_page.laser_panel.title, "MIRcat")
        self.assertIn("Operating Mode", tuple(field.label for field in operate_page.laser_panel.fields))
        self.assertIn("Emission Mode", tuple(field.label for field in operate_page.laser_panel.fields))
        self.assertIn("Wavenumber (cm^-1)", tuple(field.label for field in operate_page.laser_panel.fields))
        self.assertEqual(operate_page.laser_panel.status_items, ())
        self.assertEqual(operate_page.laser_panel.disclosures, ())

    def test_mircat_panel_updates_toggle_labels_after_state_changes(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]
        target = next(
            float(field.value)
            for field in asyncio.run(runtime.get_operate_page()).laser_panel.fields
            if field.name == "tune_target_cm1"
        )

        asyncio.run(runtime.tune_laser(target))
        asyncio.run(runtime.arm_laser())
        asyncio.run(runtime.set_laser_emission(True))
        operate_page = asyncio.run(runtime.get_operate_page())
        visible_actions = self._visible_action_buttons(operate_page.laser_panel)

        self.assertEqual(tuple(button.label for button in visible_actions), ("Disarm", "Tune", "Emission Off"))
        self.assertEqual(visible_actions[0].tone, "danger")
        self.assertEqual(visible_actions[2].tone, "danger")

    def test_mircat_panel_shows_reported_faults_in_footer_callout(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]
        fault = build_fault(
            fault_id="mircat-fault-1",
            device_id="mircat-qcl",
            device_kind=DeviceKind.MIRCAT,
            code="mircat_vendor_fault",
            message="MIRcat reported a vendor fault.",
            vendor_code="E201",
            vendor_message="Interlock open.",
        )
        cast(Any, runtime._scenario.bundle.mircat)._status = device_status_from_fault(
            "mircat-qcl",
            DeviceKind.MIRCAT,
            fault,
        )

        operate_page = asyncio.run(runtime.get_operate_page())

        self.assertEqual(len(operate_page.laser_panel.footer_callouts), 1)
        self.assertEqual(operate_page.laser_panel.footer_callouts[0].title, "MIRcat Errors")
        self.assertIn("E201", operate_page.laser_panel.footer_callouts[0].items[0])

    def test_hf2_panel_uses_simple_operator_controls(self) -> None:
        runtimes = self._create_runtime_map()
        operate_page = asyncio.run(runtimes["nominal"].get_operate_page())

        self.assertEqual(tuple(button.label for button in operate_page.acquisition_panel.header_actions), ("Disconnect",))
        self.assertEqual(operate_page.acquisition_panel.header_actions[0].tone, "danger")
        self.assertEqual(operate_page.acquisition_panel.actions, ())
        self.assertEqual(operate_page.acquisition_panel.status_items, ())
        self.assertEqual(operate_page.acquisition_panel.title, "HF2LI")
        field_labels = tuple(field.label for field in operate_page.acquisition_panel.fields)
        self.assertEqual(field_labels[:2], ("Order", "Time constant (s)"))
        self.assertIn("Transfer Rate", field_labels)
        self.assertIn("ExtRef", field_labels)
        self.assertIn("Trigger", field_labels)
        self.assertNotIn("Readout component", tuple(field.label for field in operate_page.acquisition_panel.fields))
        self.assertNotIn("Capture interval (s)", tuple(field.label for field in operate_page.acquisition_panel.fields))
        self.assertNotIn("Source", tuple(field.label for field in operate_page.acquisition_panel.fields))
        self.assertNotIn("Mode", tuple(field.label for field in operate_page.acquisition_panel.fields))
        self.assertEqual(operate_page.acquisition_panel.field_columns, 2)
        extref_field = next(field for field in operate_page.acquisition_panel.fields if field.name == "hf2_extref")
        trigger_field = next(field for field in operate_page.acquisition_panel.fields if field.name == "hf2_trigger")
        self.assertEqual(tuple(option.label for option in extref_field.options), ("DIO 0", "DIO 1", "DIO 0|1"))
        self.assertEqual(tuple(option.label for option in trigger_field.options), ("DIO 0", "DIO 1", "DIO 0|1"))

    def test_session_panel_keeps_name_sample_id_notes_and_open_recent_fields(self) -> None:
        runtimes = self._create_runtime_map()
        operate_page = asyncio.run(runtimes["nominal"].get_operate_page())

        field_labels = tuple(field.label for field in operate_page.session_panel.fields)
        action_labels = tuple(button.label for button in operate_page.session_panel.actions)

        self.assertEqual(field_labels, ("Name", "Sample", "ID", "Notes", "Open Recent"))
        self.assertEqual(operate_page.session_panel.field_columns, 3)
        self.assertEqual(action_labels, ("Save Session", "Open Recent", "Delete Session"))

    def test_experiment_type_control_exists_and_posts_back_to_experiment(self) -> None:
        app = self._create_app()
        status, headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/experiment/laser/configure",
            body={
                "scenario": "nominal",
                "experiment_type": "wavelength_scan",
                "emission_mode": "cw",
                "scan_start_cm1": "1845",
                "scan_stop_cm1": "1855",
                "scan_step_size_cm1": "1",
                "scan_dwell_time_ms": "250",
            },
        )

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/experiment")

    def test_fixed_wavelength_mode_shows_single_tune_controls_only(self) -> None:
        runtimes = self._create_runtime_map()
        operate_page = asyncio.run(runtimes["nominal"].get_operate_page())
        visible_action_labels = tuple(button.label for button in self._visible_action_buttons(operate_page.laser_panel))
        action_map = {button.label: button for button in operate_page.laser_panel.actions}

        self.assertEqual(
            tuple(field.label for field in operate_page.laser_panel.fields),
            ("Operating Mode", "Emission Mode", "Wavenumber (cm^-1)"),
        )
        tune_field = next(field for field in operate_page.laser_panel.fields if field.name == "tune_target_cm1")
        self.assertEqual(tune_field.min_value, "1638.8")
        self.assertEqual(tune_field.max_value, "2077.3")
        self.assertIn("Tune", visible_action_labels)
        self.assertNotIn("Start Scan", visible_action_labels)
        self.assertNotIn("Stop Scan", visible_action_labels)
        self.assertTrue(action_map["Start Scan"].hidden)
        self.assertTrue(action_map["Stop Scan"].hidden)
        self.assertFalse(action_map["Tune"].hidden)

    def test_wavelength_scan_mode_shows_scan_controls_and_hides_single_tune(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]

        asyncio.run(runtime.set_experiment_type("wavelength_scan"))
        operate_page = asyncio.run(runtime.get_operate_page())
        visible_action_labels = tuple(button.label for button in self._visible_action_buttons(operate_page.laser_panel))
        action_map = {button.label: button for button in operate_page.laser_panel.actions}

        field_labels = tuple(field.label for field in operate_page.laser_panel.fields)
        self.assertIn("Operating Mode", field_labels)
        self.assertIn("Emission Mode", field_labels)
        self.assertIn("Start wavenumber (cm^-1)", field_labels)
        self.assertIn("Stop wavenumber (cm^-1)", field_labels)
        scan_start_field = next(field for field in operate_page.laser_panel.fields if field.name == "scan_start_cm1")
        scan_stop_field = next(field for field in operate_page.laser_panel.fields if field.name == "scan_stop_cm1")
        self.assertEqual(scan_start_field.min_value, "1638.8")
        self.assertEqual(scan_start_field.max_value, "2077.3")
        self.assertEqual(scan_stop_field.min_value, "1638.8")
        self.assertEqual(scan_stop_field.max_value, "2077.3")
        self.assertIn("Scan Speed", field_labels)
        scan_speed_field = next(field for field in operate_page.laser_panel.fields if field.name == "scan_step_size_cm1")
        self.assertEqual(scan_speed_field.help_text, "0.1 to 10000")
        self.assertEqual(scan_speed_field.min_value, "0.1")
        self.assertEqual(scan_speed_field.max_value, "10000")
        self.assertNotIn("Dwell time per point (ms)", field_labels)
        self.assertIn("Start Scan", visible_action_labels)
        self.assertIn("Stop Scan", visible_action_labels)
        self.assertNotIn("Tune", visible_action_labels)
        self.assertTrue(action_map["Tune"].hidden)
        self.assertFalse(action_map["Start Scan"].hidden)
        self.assertFalse(action_map["Stop Scan"].hidden)
        self.assertIsNotNone(operate_page.state)
        assert operate_page.state is not None
        self.assertIn("partially wired", operate_page.state.title.lower())

    def test_operating_mode_clamps_wavenumber_fields_to_mircat_limits(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]

        asyncio.run(
            runtime.configure_operating_mode(
                experiment_type="wavelength_scan",
                emission_mode="cw",
                tune_target_cm1=1500.0,
                scan_start_cm1=1500.0,
                scan_stop_cm1=2200.0,
            )
        )
        operate_page = asyncio.run(runtime.get_operate_page())
        fields = {field.name: field for field in operate_page.laser_panel.fields}

        self.assertEqual(fields["scan_start_cm1"].value, "1638.80")
        self.assertEqual(fields["scan_stop_cm1"].value, "2077.30")
        self.assertEqual(fields["scan_step_size_cm1"].value, "1.00")

    def test_operating_mode_clamps_scan_speed_to_supported_limits(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]

        asyncio.run(
            runtime.configure_operating_mode(
                experiment_type="wavelength_scan",
                emission_mode="cw",
                scan_step_size_cm1=50_000.0,
            )
        )
        operate_page = asyncio.run(runtime.get_operate_page())
        fields = {field.name: field for field in operate_page.laser_panel.fields}

        self.assertEqual(fields["scan_step_size_cm1"].value, "10000.00")

    def test_pulsed_mode_derives_duty_cycle_and_applies_pulse_limits(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]

        asyncio.run(
            runtime.configure_operating_mode(
                experiment_type="fixed_wavelength",
                emission_mode="pulsed",
                pulse_repetition_rate_hz=3_000_000,
                pulse_width_ns=1005,
            )
        )
        operate_page = asyncio.run(runtime.get_operate_page())
        fields = {field.name: field for field in operate_page.laser_panel.fields}

        self.assertEqual(fields["pulse_repetition_rate_hz"].value, "3000000")
        self.assertEqual(fields["pulse_repetition_rate_hz"].min_value, "10")
        self.assertEqual(fields["pulse_repetition_rate_hz"].max_value, "3000000")
        self.assertEqual(fields["pulse_width_ns"].value, "100")
        self.assertEqual(fields["pulse_width_ns"].min_value, "20")
        self.assertEqual(fields["pulse_width_ns"].max_value, "1005")
        self.assertEqual(fields["pulse_duty_cycle_percent"].value, "30.000")
        self.assertTrue(fields["pulse_duty_cycle_percent"].read_only)

    def test_experiment_page_excludes_routing_timing_and_removed_sections(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/experiment")

        self.assertEqual(status, "200 OK")
        self.assertNotIn("MUX Route Set", body)
        self.assertNotIn("Pump Shots Before Probe", body)
        self.assertNotIn("Pico Secondary Capture", body)
        self.assertNotIn("Timing Program", body)
        self.assertNotIn("Readiness Matrix", body)
        self.assertNotIn("Probe Settings", body)
        self.assertNotIn("Current MIRcat status", body)
        self.assertNotIn("Readout component", body)
        self.assertNotIn("Start Acquisition", body)
        self.assertNotIn("Stop Acquisition", body)
        self.assertNotIn("Acquisition status", body)
        self.assertNotIn("Live Status", body)
        self.assertNotIn("Recent Activity / Messages", body)

    def test_save_session_and_start_experiment_flow_updates_experiment_and_results(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]

        manifest = asyncio.run(
            runtime.save_session(
                session_id="bench-mvp-001",
                session_label="Bench MVP",
                sample_id="sample-42",
                operator_notes="operator review",
            )
        )
        run_state = asyncio.run(runtime.start_run())
        operate_page = asyncio.run(runtime.get_operate_page())
        results_page = asyncio.run(runtime.get_results_page(run_state.session_id))

        self.assertEqual(manifest.session_id, "bench-mvp-001")
        self.assertEqual(manifest.session_id, run_state.session_id)
        self.assertEqual(run_state.phase, RunPhase.COMPLETED)
        self.assertEqual(operate_page.session_panel.status_items, ())
        self.assertIsNotNone(operate_page.results_handoff)
        assert operate_page.results_handoff is not None
        self.assertEqual(operate_page.results_handoff.label, "Open Latest Session in Results")
        self.assertEqual(operate_page.results_handoff.session_id, run_state.session_id)
        self.assertFalse(hasattr(operate_page, "recent_activity"))
        self.assertFalse(hasattr(operate_page, "live_status"))
        self.assertIsNotNone(results_page.selected_session)
        assert results_page.selected_session is not None
        self.assertEqual(results_page.selected_session.session_id, run_state.session_id)
        self.assertGreaterEqual(len(results_page.artifact_panels), 1)
        self.assertGreaterEqual(len(results_page.visualization_panels), 1)
        self.assertGreaterEqual(len(results_page.export_panels), 1)
        self.assertGreaterEqual(len(results_page.export_actions), 1)
        self.assertGreaterEqual(len(results_page.event_log), 1)

    def test_session_id_must_be_unique_across_saved_sessions(self) -> None:
        runtimes = self._create_runtime_map()
        runtime = runtimes["nominal"]

        asyncio.run(
            runtime.save_session(
                session_id="bench-mvp-unique",
                session_label="Bench MVP",
                sample_id="sample-42",
                operator_notes="operator review",
            )
        )

        with self.assertRaises(ValueError):
            asyncio.run(
                runtime.save_session(
                    session_id="bench-mvp-unique",
                    session_label="Bench MVP 2",
                    sample_id="sample-43",
                    operator_notes="duplicate id",
                )
            )

    def test_ndyag_panel_is_off_by_default_and_disables_inputs(self) -> None:
        runtimes = self._create_runtime_map()
        operate_page = asyncio.run(runtimes["nominal"].get_operate_page())

        self.assertEqual(operate_page.ndyag_panel.title, "Nd:YAG Settings")
        self.assertEqual(tuple(button.label for button in operate_page.ndyag_panel.header_actions), ("On",))
        self.assertEqual(operate_page.ndyag_panel.field_columns, 3)
        fields = {field.name: field for field in operate_page.ndyag_panel.fields}
        self.assertEqual(fields["ndyag_repetition_rate_hz"].label, "Rep. Rate (Hz)")
        self.assertEqual(fields["ndyag_shot_count"].label, "Shot Count")
        self.assertEqual(fields["ndyag_continuous"].label, "Cont.")
        self.assertEqual(fields["ndyag_repetition_rate_hz"].min_value, "10")
        self.assertEqual(fields["ndyag_shot_count"].max_value, "100")
        self.assertTrue(fields["ndyag_repetition_rate_hz"].disabled)
        self.assertTrue(fields["ndyag_shot_count"].disabled)
        self.assertTrue(fields["ndyag_continuous"].disabled)

    def test_emission_mode_toggle_uses_client_side_visibility_instead_of_auto_submit(self) -> None:
        app = self._create_app()
        status, _headers, body = _call_wsgi(app, method="GET", path="/experiment")

        self.assertEqual(status, "200 OK")
        self.assertRegex(body, r'data-async-form="true"')
        self.assertRegex(body, r'data-field-name="tune_target_cm1"')
        self.assertRegex(body, r'data-field-name="scan_start_cm1"')
        self.assertRegex(body, r'data-field-name="scan_stop_cm1"')
        self.assertRegex(body, r'data-field-name="scan_step_size_cm1"')
        self.assertNotRegex(body, r'data-field-name="scan_dwell_time_ms"')
        self.assertRegex(body, r'data-field-name="pulse_repetition_rate_hz"')
        self.assertRegex(body, r'data-field-name="pulse_width_ns"')
        self.assertRegex(body, r'data-field-name="pulse_duty_cycle_percent"')
        self.assertRegex(body, r'data-action-button="/experiment/laser/tune"')
        self.assertRegex(body, r'data-action-button="/experiment/laser/scan/start"')
        self.assertRegex(body, r'data-action-button="/experiment/laser/scan/stop"')
        self.assertRegex(body, r"syncOperatingModeFields")
        self.assertRegex(body, r"syncFieldVisibility")
        self.assertRegex(body, r"syncActionVisibility")
        self.assertRegex(body, r"syncNdyagFields")
        self.assertRegex(body, r"submitAsyncForm")
        self.assertRegex(body, r"operatingModeFieldNames")
        self.assertRegex(body, r"root instanceof HTMLFormElement")
        self.assertRegex(body, r"collectAsyncFormState")
        self.assertRegex(body, r"restoreAsyncFormState")
        self.assertRegex(body, r"syncOperatingModeActionButtons")
        self.assertRegex(body, r"guardedLaserActions")
        self.assertRegex(body, r"form\.reportValidity\(\)")
        self.assertRegex(body, r'input", \(event\)')
        self.assertRegex(body, r'change", \(event\)')
        self.assertIn('name="pulse_repetition_rate_hz"', body)
        self.assertIn('min="10"', body)
        self.assertIn('max="3000000"', body)
        self.assertIn('name="pulse_width_ns"', body)
        self.assertIn('min="20"', body)
        self.assertIn('max="1005"', body)
        self.assertIn('name="pulse_duty_cycle_percent"', body)
        self.assertIn("readonly", body)
        self.assertNotIn("this.form.submit()", body)
        self.assertNotIn("this.form.requestSubmit()", body)

    def test_experiment_post_routes_redirect_back_to_experiment(self) -> None:
        app = self._create_app()
        status, headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/experiment/session/save",
            body={
                "scenario": "nominal",
                "session_id_input": "bench-mvp-post",
                "session_label": "Bench MVP",
                "sample_id": "sample-42",
                "operator_notes": "operator review",
            },
        )

        self.assertEqual(status, "303 See Other")
        self.assertEqual(headers["Location"], "/experiment")

    def test_delete_session_route_removes_saved_session_and_files(self) -> None:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        storage_root = Path(tempdir.name)
        app = create_simulator_app(storage_root=storage_root)
        sessions_root = storage_root / "sessions"
        seeded_session_id = "saved-session-001"
        seeded_session_dir = sessions_root / seeded_session_id
        self.assertTrue(seeded_session_dir.is_dir())

        delete_status, delete_headers, _body = _call_wsgi(
            app,
            method="POST",
            path="/experiment/session/delete",
            body={
                "scenario": "nominal",
                "recent_session_id": seeded_session_id,
            },
        )

        self.assertEqual(delete_status, "303 See Other")
        self.assertEqual(delete_headers["Location"], "/experiment")
        self.assertFalse(seeded_session_dir.exists())

        page_status, _headers, page_body = _call_wsgi(app, method="GET", path="/experiment")
        self.assertEqual(page_status, "200 OK")
        self.assertNotIn(f'<option value="{seeded_session_id}"', page_body)

    def test_results_and_advanced_routes_render_secondary_surfaces(self) -> None:
        app = self._create_app()

        results_status, _headers, results_body = _call_wsgi(app, method="GET", path="/results?scenario=nominal")
        advanced_status, _headers, advanced_body = _call_wsgi(app, method="GET", path="/advanced?scenario=nominal")

        self.assertEqual(results_status, "200 OK")
        self.assertIn("Recent Sessions", results_body)
        self.assertIn("Artifacts and Provenance", results_body)
        self.assertIn("Visualization and Overlay Review", results_body)
        self.assertIn("Export From Persisted Session", results_body)

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
        self.assertIn("Calibration and recovery scope", service_body)

        self.assertEqual(analyze_status, "200 OK")
        self.assertIn("Saved-session scientific evaluation surface", analyze_body)
        self.assertIn("Reprocessing and Comparison", analyze_body)

    def test_active_docs_point_to_operator_ui_mvp(self) -> None:
        repo_root = Path(ROOT)
        ui_foundation = (repo_root / "docs" / "ui_foundation.md").read_text(encoding="utf-8")
        operator_ui_mvp = (repo_root / "docs" / "operator_ui_mvp.md").read_text(encoding="utf-8")

        self.assertIn("default operator experience centers on one `Experiment` page", ui_foundation)
        self.assertIn("## Default Experiment Workflow", operator_ui_mvp)

    def test_ui_shell_avoids_direct_driver_and_persistence_imports(self) -> None:
        ui_root = Path(ROOT) / "ui-shell" / "src" / "ircp_ui_shell"
        banned_fragments = ("ircp_drivers", "ircp_data_pipeline", "ircp_processing", "ircp_analysis")

        for path in ui_root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for fragment in banned_fragments:
                self.assertNotIn(fragment, source, f"{path.name} should not import {fragment}")


if __name__ == "__main__":
    unittest.main()
