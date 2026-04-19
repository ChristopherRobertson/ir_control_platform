"""Minimal WSGI application for the operator-first UI shell."""

from __future__ import annotations

import asyncio
from dataclasses import replace
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
    render_run_page,
    render_service_page,
    render_setup_page,
)
from .models import HeaderStatus, NavigationItem, ScenarioOption


StartResponse = Callable[[str, list[tuple[str, str]]], None]


class IRCPUiApp:
    """Dependency-light server-rendered UI shell for simulator-backed development."""

    def __init__(
        self,
        runtimes: Mapping[str, UiRuntimeGateway],
        default_scenario: str = "nominal",
        scenario_catalog: Mapping[str, tuple[str, str]] | None = None,
    ) -> None:
        if default_scenario not in runtimes:
            raise ValueError(f"Unknown default scenario {default_scenario!r}.")
        self._runtimes = dict(runtimes)
        self._default_scenario = default_scenario
        self._scenario_catalog = dict(scenario_catalog or {})

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
        if path == "/operate":
            return self._redirect(start_response, self._surface_location("experiment", scenario_id))
        if path in {"/setup/advanced", "/setup/calibrated"}:
            return self._redirect(start_response, self._surface_location("advanced", scenario_id))
        if path == "/experiment":
            header = self._decorate_header(asyncio.run(runtime.get_header_status("experiment")), scenario_id)
            page = asyncio.run(runtime.get_operate_page())
            return self._html(start_response, render_layout(header, render_operate_page(page, scenario_id)))
        if path == "/setup":
            header = self._decorate_header(asyncio.run(runtime.get_header_status("setup")), scenario_id)
            page = asyncio.run(runtime.get_setup_page())
            return self._html(start_response, render_layout(header, render_setup_page(page, scenario_id)))
        if path == "/run":
            header = self._decorate_header(asyncio.run(runtime.get_header_status("run")), scenario_id)
            page = asyncio.run(runtime.get_run_page())
            return self._html(start_response, render_layout(header, render_run_page(page, scenario_id)))
        if path == "/results":
            selected_session_id = _extract_value(query, "session_id")
            search = _extract_value(query, "search") or ""
            status_filter = _extract_value(query, "status") or "all"
            sort_order = _extract_value(query, "sort") or "updated_desc"
            header = self._decorate_header(asyncio.run(runtime.get_header_status("results")), scenario_id)
            page = asyncio.run(
                runtime.get_results_page(
                    selected_session_id=selected_session_id,
                    search=search,
                    status_filter=status_filter,
                    sort_order=sort_order,
                )
            )
            return self._html(start_response, render_layout(header, render_results_page(page, scenario_id)))
        if path == "/results/download":
            session_id = _require_value(query, "session_id")
            asset = _extract_value(query, "asset")
            artifact_id = _extract_value(query, "artifact_id")
            download = asyncio.run(
                runtime.get_results_download(session_id, asset=asset, artifact_id=artifact_id)
            )
            return self._download(start_response, download.filename, download.content_type, download.body)
        if path == "/advanced":
            header = self._decorate_header(asyncio.run(runtime.get_header_status("advanced")), scenario_id)
            page = asyncio.run(runtime.get_advanced_page())
            return self._html(start_response, render_layout(header, render_advanced_page(page)))
        if path == "/service":
            header = self._decorate_header(asyncio.run(runtime.get_header_status("service")), scenario_id)
            page = asyncio.run(runtime.get_service_page())
            return self._html(start_response, render_layout(header, render_service_page(page, scenario_id)))
        if path == "/analyze":
            selected_session_id = _extract_value(query, "session_id")
            header = self._decorate_header(asyncio.run(runtime.get_header_status("analyze")), scenario_id)
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
                        session_id=_extract_value(form, "session_id_input") or "",
                        session_label=_extract_value(form, "session_label") or "",
                        sample_id=_extract_value(form, "sample_id") or "",
                        operator_notes=_extract_value(form, "operator_notes") or "",
                    )
                )
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/experiment/session/open":
                session_id = _require_value(form, "recent_session_id")
                asyncio.run(runtime.open_saved_session(session_id))
                return self._redirect(start_response, self._surface_location("experiment", scenario_id))
            if path == "/results/reopen":
                session_id = _require_value(form, "recent_session_id")
                asyncio.run(runtime.open_saved_session(session_id))
                return self._redirect(start_response, self._surface_location("setup", scenario_id))
            if path == "/experiment/session/delete":
                session_id = _require_value(form, "recent_session_id")
                asyncio.run(runtime.delete_saved_session(session_id))
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
                if _extract_value(form, "laser_tune_intent") == "cancel":
                    asyncio.run(runtime.cancel_laser_tune())
                else:
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
                        dwell_time_ms=_optional_float(form, "scan_dwell_time_ms"),
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
            if path in {"/experiment/run/preflight", "/setup/preflight"}:
                asyncio.run(runtime.run_preflight())
                target = "setup" if path == "/setup/preflight" else "experiment"
                return self._redirect(start_response, self._surface_location(target, scenario_id))
            if path in {"/experiment/run/start", "/run/start"}:
                asyncio.run(runtime.start_run())
                target = "run" if path == "/run/start" else "experiment"
                return self._redirect(start_response, self._surface_location(target, scenario_id))
            if path in {"/experiment/run/abort", "/run/abort"}:
                asyncio.run(runtime.abort_active_run())
                target = "run" if path == "/run/abort" else "experiment"
                return self._redirect(start_response, self._surface_location(target, scenario_id))
        except Exception as exc:  # pragma: no cover - exercised through page-state projections instead
            return self._respond(start_response, "500 Internal Server Error", str(exc))
        return self._respond(start_response, "404 Not Found", f"No action for {path}")

    def _html(self, start_response: StartResponse, body: str) -> list[bytes]:
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [body.encode("utf-8")]

    def _respond(self, start_response: StartResponse, status: str, body: str) -> list[bytes]:
        start_response(status, [("Content-Type", "text/plain; charset=utf-8")])
        return [body.encode("utf-8")]

    def _download(self, start_response: StartResponse, filename: str, content_type: str, body: bytes) -> list[bytes]:
        start_response(
            "200 OK",
            [
                ("Content-Type", content_type),
                ("Content-Disposition", f'attachment; filename="{filename}"'),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    def _redirect(self, start_response: StartResponse, location: str) -> list[bytes]:
        start_response("303 See Other", [("Location", location)])
        return [b""]

    def _surface_location(self, surface: str, scenario_id: str) -> str:
        if scenario_id == self._default_scenario:
            return f"/{surface}"
        return f"/{surface}?scenario={scenario_id}"

    def _decorate_header(self, header: HeaderStatus, scenario_id: str) -> HeaderStatus:
        scenario_options = tuple(
            ScenarioOption(
                scenario_id=known_scenario_id,
                label=self._scenario_catalog.get(known_scenario_id, (known_scenario_id.replace("_", " ").title(), ""))[0],
                description=self._scenario_catalog.get(known_scenario_id, ("", ""))[1],
                active=known_scenario_id == scenario_id,
            )
            for known_scenario_id in self._runtimes
        )
        navigation = tuple(
            NavigationItem(
                label=label,
                href=self._surface_location(route, scenario_id),
                active=header.active_route == route,
            )
            for route, label in (
                ("experiment", "Experiment"),
                ("setup", "Setup"),
                ("run", "Run"),
                ("results", "Results"),
                ("analyze", "Analyze"),
                ("advanced", "Advanced"),
                ("service", "Service"),
            )
        )
        return replace(header, scenario_options=scenario_options, navigation=navigation)

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


def create_ui_app(
    runtimes: Mapping[str, UiRuntimeGateway],
    default_scenario: str = "nominal",
    scenario_catalog: Mapping[str, tuple[str, str]] | None = None,
) -> IRCPUiApp:
    return IRCPUiApp(runtimes=runtimes, default_scenario=default_scenario, scenario_catalog=scenario_catalog)
