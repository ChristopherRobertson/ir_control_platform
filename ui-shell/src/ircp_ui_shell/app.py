"""Minimal WSGI application for the operator-first UI shell."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Callable, Mapping, cast
from urllib.parse import parse_qs

from .boundaries import UiRuntimeGateway
from .components import (
    render_advanced_page,
    render_analyze_page,
    render_layout,
    render_operate_page,
    render_results_page,
    render_service_page,
)


StartResponse = Callable[[str, list[tuple[str, str]]], None]


class IRCPUiApp:
    """Dependency-light server-rendered UI shell for simulator-backed development."""

    def __init__(self, runtimes: Mapping[str, UiRuntimeGateway], default_scenario: str = "nominal") -> None:
        if default_scenario not in runtimes:
            raise ValueError(f"Unknown default scenario {default_scenario!r}.")
        self._runtimes = dict(runtimes)
        self._default_scenario = default_scenario

    def __call__(self, environ: dict[str, object], start_response: StartResponse) -> list[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        query = parse_qs(str(environ.get("QUERY_STRING", "")))
        form = self._read_form(environ) if method == "POST" else {}
        scenario_id = _extract_value(form, "scenario") or _extract_value(query, "scenario") or self._default_scenario

        try:
            runtime = self._runtimes[scenario_id]
        except KeyError:
            return self._respond(start_response, "404 Not Found", f"Unknown scenario: {scenario_id}")

        if path == "/":
            return self._redirect(start_response, self._surface_location("experiment", scenario_id))

        if method == "POST":
            return self._handle_post(start_response, runtime, path, scenario_id, form)

        return self._handle_get(start_response, runtime, path, scenario_id, query)

    def _handle_get(
        self,
        start_response: StartResponse,
        runtime: UiRuntimeGateway,
        path: str,
        scenario_id: str,
        query: dict[str, list[str]],
    ) -> list[bytes]:
        if path in {"/operate", "/setup", "/run"}:
            return self._redirect(start_response, self._surface_location("experiment", scenario_id))
        if path in {"/setup/advanced", "/setup/calibrated"}:
            return self._redirect(start_response, self._surface_location("advanced", scenario_id))
        if path == "/experiment":
            header = asyncio.run(runtime.get_header_status("experiment"))
            page = asyncio.run(runtime.get_operate_page())
            return self._html(start_response, render_layout(header, render_operate_page(page, scenario_id)))
        if path == "/results":
            selected_session_id = _extract_value(query, "session_id")
            header = asyncio.run(runtime.get_header_status("results"))
            page = asyncio.run(runtime.get_results_page(selected_session_id=selected_session_id))
            return self._html(start_response, render_layout(header, render_results_page(page, scenario_id)))
        if path == "/advanced":
            header = asyncio.run(runtime.get_header_status("advanced"))
            page = asyncio.run(runtime.get_advanced_page())
            return self._html(start_response, render_layout(header, render_advanced_page(page)))
        if path == "/service":
            header = asyncio.run(runtime.get_header_status("service"))
            page = asyncio.run(runtime.get_service_page())
            return self._html(start_response, render_layout(header, render_service_page(page)))
        if path == "/analyze":
            selected_session_id = _extract_value(query, "session_id")
            header = asyncio.run(runtime.get_header_status("analyze"))
            page = asyncio.run(runtime.get_analyze_page(selected_session_id=selected_session_id))
            return self._html(start_response, render_layout(header, render_analyze_page(page, scenario_id)))
        return self._respond(start_response, "404 Not Found", f"No route for {path}")

    def _handle_post(
        self,
        start_response: StartResponse,
        runtime: UiRuntimeGateway,
        path: str,
        scenario_id: str,
        form: dict[str, list[str]],
    ) -> list[bytes]:
        if path.startswith("/operate/"):
            path = "/experiment/" + path.removeprefix("/operate/")
        try:
            if path == "/experiment/laser/configure":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/hf2/configure":
                asyncio.run(
                    runtime.configure_hf2(
                        sample_rate_hz=_optional_float(form, "hf2_sample_rate_hz"),
                        harmonic=_optional_int(form, "hf2_harmonic"),
                        time_constant_seconds=_optional_float(form, "hf2_time_constant_seconds"),
                        extref=_extract_value(form, "hf2_extref"),
                        trigger=_extract_value(form, "hf2_trigger"),
                    )
                )
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/ndyag/configure":
                asyncio.run(
                    runtime.configure_ndyag(
                        repetition_rate_hz=_optional_float(form, "ndyag_repetition_rate_hz"),
                        shot_count=_optional_int(form, "ndyag_shot_count"),
                        continuous=_checkbox_checked(form, "ndyag_continuous"),
                    )
                )
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/ndyag/on":
                asyncio.run(
                    runtime.configure_ndyag(
                        repetition_rate_hz=_optional_float(form, "ndyag_repetition_rate_hz"),
                        shot_count=_optional_int(form, "ndyag_shot_count"),
                        continuous=_checkbox_checked(form, "ndyag_continuous"),
                    )
                )
                asyncio.run(runtime.set_ndyag_enabled(True))
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/ndyag/off":
                asyncio.run(
                    runtime.configure_ndyag(
                        repetition_rate_hz=_optional_float(form, "ndyag_repetition_rate_hz"),
                        shot_count=_optional_int(form, "ndyag_shot_count"),
                        continuous=_checkbox_checked(form, "ndyag_continuous"),
                    )
                )
                asyncio.run(runtime.set_ndyag_enabled(False))
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/session/save":
                asyncio.run(
                    runtime.save_session(
                        session_label=_extract_value(form, "session_label") or "",
                        sample_id=_extract_value(form, "sample_id") or "",
                        operator_notes=_extract_value(form, "operator_notes") or "",
                    )
                )
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/session/open":
                session_id = _require_value(form, "session_id")
                asyncio.run(runtime.open_saved_session(session_id))
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/laser/connect":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                asyncio.run(runtime.connect_laser())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/laser/disconnect":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                asyncio.run(runtime.disconnect_laser())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/laser/arm":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                asyncio.run(runtime.arm_laser())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/laser/disarm":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                asyncio.run(runtime.disarm_laser())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/laser/emission/on":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                asyncio.run(runtime.set_laser_emission(True))
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/laser/emission/off":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                asyncio.run(runtime.set_laser_emission(False))
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/laser/tune":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                asyncio.run(runtime.tune_laser(_require_float(form, "tune_target_cm1")))
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/laser/scan/start":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                asyncio.run(
                    runtime.start_scan(
                        start_wavenumber_cm1=_require_float(form, "scan_start_cm1"),
                        end_wavenumber_cm1=_require_float(form, "scan_stop_cm1"),
                        step_size_cm1=_require_float(form, "scan_step_size_cm1"),
                        dwell_time_ms=_require_float(form, "scan_dwell_time_ms"),
                    )
                )
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/laser/scan/stop":
                asyncio.run(
                    runtime.configure_operating_mode(
                        experiment_type=_require_value(form, "experiment_type"),
                        emission_mode=_require_value(form, "emission_mode"),
                        tune_target_cm1=_optional_float(form, "tune_target_cm1"),
                        scan_start_cm1=_optional_float(form, "scan_start_cm1"),
                        scan_stop_cm1=_optional_float(form, "scan_stop_cm1"),
                        scan_step_size_cm1=_optional_float(form, "scan_step_size_cm1"),
                        scan_dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
                        pulse_repetition_rate_hz=_optional_float(form, "pulse_repetition_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        pulse_duty_cycle_percent=_optional_float(form, "pulse_duty_cycle_percent"),
                    )
                )
                asyncio.run(runtime.stop_scan())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/hf2/connect":
                asyncio.run(
                    runtime.configure_hf2(
                        sample_rate_hz=_optional_float(form, "hf2_sample_rate_hz"),
                        harmonic=_optional_int(form, "hf2_harmonic"),
                        time_constant_seconds=_optional_float(form, "hf2_time_constant_seconds"),
                        extref=_extract_value(form, "hf2_extref"),
                        trigger=_extract_value(form, "hf2_trigger"),
                    )
                )
                asyncio.run(runtime.connect_hf2())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/hf2/disconnect":
                asyncio.run(
                    runtime.configure_hf2(
                        sample_rate_hz=_optional_float(form, "hf2_sample_rate_hz"),
                        harmonic=_optional_int(form, "hf2_harmonic"),
                        time_constant_seconds=_optional_float(form, "hf2_time_constant_seconds"),
                        extref=_extract_value(form, "hf2_extref"),
                        trigger=_extract_value(form, "hf2_trigger"),
                    )
                )
                asyncio.run(runtime.disconnect_hf2())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/run/preflight":
                asyncio.run(runtime.run_preflight())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/run/start":
                asyncio.run(runtime.start_run())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/run/abort":
                asyncio.run(runtime.abort_active_run())
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
        except Exception as exc:  # pragma: no cover - exercised through page-state projections instead
            return self._respond(start_response, "500 Internal Server Error", str(exc))
        return self._respond(start_response, "404 Not Found", f"No action for {path}")

    def _html(self, start_response: StartResponse, body: str) -> list[bytes]:
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [body.encode("utf-8")]

    def _respond(self, start_response: StartResponse, status: str, body: str) -> list[bytes]:
        start_response(status, [("Content-Type", "text/plain; charset=utf-8")])
        return [body.encode("utf-8")]

    def _redirect(self, start_response: StartResponse, location: str) -> list[bytes]:
        start_response("303 See Other", [("Location", location)])
        return [b""]

    def _surface_location(self, surface: str, scenario_id: str) -> str:
        if scenario_id == self._default_scenario:
            return f"/{surface}"
        return f"/{surface}?scenario={scenario_id}"

    def _read_form(self, environ: dict[str, object]) -> dict[str, list[str]]:
        try:
            content_length = int(str(environ.get("CONTENT_LENGTH", "0")) or "0")
        except ValueError:
            content_length = 0
        if content_length <= 0:
            return {}
        body_stream = environ.get("wsgi.input", BytesIO())
        if not hasattr(body_stream, "read"):
            return {}
        read = cast(Callable[[int], bytes], getattr(body_stream, "read"))
        body = read(content_length).decode("utf-8")
        return parse_qs(body)


def _extract_value(values: Mapping[str, list[str]], key: str) -> str | None:
    items = values.get(key)
    if not items:
        return None
    return items[0]


def _require_value(values: Mapping[str, list[str]], key: str) -> str:
    value = _extract_value(values, key)
    if value is None:
        raise ValueError(f"Missing required field: {key}")
    return value


def _require_float(values: Mapping[str, list[str]], key: str) -> float:
    return float(_require_value(values, key))


def _optional_float(values: Mapping[str, list[str]], key: str) -> float | None:
    value = _extract_value(values, key)
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(values: Mapping[str, list[str]], key: str) -> int | None:
    value = _extract_value(values, key)
    if value is None or value == "":
        return None
    return int(value)


def _checkbox_checked(values: Mapping[str, list[str]], key: str) -> bool:
    value = _extract_value(values, key)
    return value not in {None, "", "0", "false", "False", "off"}


def create_ui_app(runtimes: Mapping[str, UiRuntimeGateway], default_scenario: str = "nominal") -> IRCPUiApp:
    return IRCPUiApp(runtimes=runtimes, default_scenario=default_scenario)
