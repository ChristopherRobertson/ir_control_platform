"""Minimal WSGI app for the three-page single-wavelength pump-probe workflow."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Callable, Mapping, cast
from urllib.parse import parse_qs

from .boundaries import UiRuntimeGateway
from .components import render_layout, render_results_page, render_session_page, render_setup_page
from .models import HeaderStatus


StartResponse = Callable[[str, list[tuple[str, str]]], None]


class IRCPUiApp:
    def __init__(
        self,
        runtimes: Mapping[str, UiRuntimeGateway],
        default_scenario: str = "nominal",
    ) -> None:
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
        runtime = self._runtimes.get(scenario_id)
        if runtime is None:
            return self._respond(start_response, "404 Not Found", f"Unknown scenario: {scenario_id}")
        if path == "/":
            return self._redirect(start_response, self._location("session", scenario_id))
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
        if path in {"/experiment", "/operate"}:
            return self._redirect(start_response, self._location("session", scenario_id))
        if path == "/session":
            header = self._header(runtime, "session")
            page = asyncio.run(runtime.get_session_page())
            return self._html(start_response, render_layout(header, render_session_page(page)))
        if path == "/setup":
            header = self._header(runtime, "setup")
            page = asyncio.run(runtime.get_setup_page())
            return self._html(start_response, render_layout(header, render_setup_page(page)))
        if path == "/results":
            header = self._header(runtime, "results")
            page = asyncio.run(
                runtime.get_results_page(
                    session_id=_extract_value(query, "session_id"),
                    run_id=_extract_value(query, "run_id"),
                    metric_family=_extract_value(query, "metric") or "R",
                    display_mode=_extract_value(query, "display") or "overlay",
                )
            )
            return self._html(start_response, render_layout(header, render_results_page(page)))
        if path == "/results/download":
            download = asyncio.run(
                runtime.get_results_download(
                    session_id=_require_value(query, "session_id"),
                    run_id=_require_value(query, "run_id"),
                    asset=_extract_value(query, "asset") or "metadata",
                )
            )
            return self._download(start_response, download.filename, download.content_type, download.body)
        return self._respond(start_response, "404 Not Found", f"No route for {path}")

    def _handle_post(
        self,
        start_response: StartResponse,
        runtime: UiRuntimeGateway,
        path: str,
        scenario_id: str,
        form: dict[str, list[str]],
    ) -> list[bytes]:
        try:
            if path == "/session/save":
                result = asyncio.run(
                    runtime.save_session(
                        session_name=_require_value(form, "session_name"),
                        operator=_require_value(form, "operator"),
                        sample_id=_require_value(form, "sample_id"),
                        sample_notes=_extract_value(form, "sample_notes") or "",
                        experiment_notes=_extract_value(form, "experiment_notes") or "",
                    )
                )
                if result == "overwrite_pending":
                    return self._redirect(start_response, self._location("session", scenario_id))
                return self._redirect(start_response, self._location("session", scenario_id))
            if path == "/session/overwrite":
                asyncio.run(runtime.confirm_session_overwrite())
                return self._redirect(start_response, self._location("session", scenario_id))
            if path == "/session/overwrite/cancel":
                asyncio.run(runtime.cancel_session_overwrite())
                return self._redirect(start_response, self._location("session", scenario_id))
            if path == "/session/open":
                asyncio.run(runtime.open_session(session_id=_require_value(form, "session_id")))
                return self._redirect(start_response, self._location("session", scenario_id))
            if path == "/session/run/open":
                asyncio.run(
                    runtime.open_run(
                        session_id=_require_value(form, "session_id"),
                        run_id=_require_value(form, "run_id"),
                    )
                )
                return self._redirect(start_response, self._location("session", scenario_id))
            if path == "/session/run/create":
                asyncio.run(
                    runtime.create_run(
                        run_name=_require_value(form, "run_name"),
                        run_notes=_extract_value(form, "run_notes") or "",
                    )
                )
                return self._redirect(start_response, self._location("session", scenario_id))
            if path == "/session/run/save":
                asyncio.run(
                    runtime.save_run_header(
                        run_name=_require_value(form, "run_name"),
                        run_notes=_extract_value(form, "run_notes") or "",
                    )
                )
                return self._redirect(start_response, self._location("setup", scenario_id))
            if path == "/setup/save":
                asyncio.run(
                    runtime.save_setup(
                        pump_enabled=_checkbox_checked(form, "pump_enabled"),
                        shot_count=_require_int(form, "shot_count"),
                        timescale=_require_value(form, "timescale"),
                        wavelength_cm1=_require_float(form, "wavelength_cm1"),
                        emission_mode=_require_value(form, "emission_mode"),
                        pulse_rate_hz=_optional_float(form, "pulse_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                        order=_require_int(form, "order"),
                        time_constant_seconds=_require_float(form, "time_constant_seconds"),
                        transfer_rate_hz=_require_float(form, "transfer_rate_hz"),
                    )
                )
                return self._redirect(start_response, self._location("setup", scenario_id))
            if path == "/setup/probe/connection":
                asyncio.run(runtime.toggle_probe_connection())
                return self._redirect(start_response, self._location("setup", scenario_id))
            if path == "/setup/probe/fault/clear":
                asyncio.run(runtime.clear_probe_fault())
                return self._redirect(start_response, self._location("setup", scenario_id))
            if path == "/setup/lockin/connection":
                asyncio.run(runtime.toggle_lockin_connection())
                return self._redirect(start_response, self._location("setup", scenario_id))
            if path == "/setup/pump":
                asyncio.run(
                    runtime.configure_pump(
                        enabled=_checkbox_checked(form, "pump_enabled"),
                        shot_count=_require_int(form, "shot_count"),
                    )
                )
                return self._redirect(start_response, self._location("setup", scenario_id))
            if path == "/setup/timescale":
                asyncio.run(runtime.configure_timescale(timescale=_require_value(form, "timescale")))
                return self._redirect(start_response, self._location("setup", scenario_id))
            if path == "/setup/probe":
                asyncio.run(
                    runtime.configure_probe(
                        wavelength_cm1=_require_float(form, "wavelength_cm1"),
                        emission_mode=_require_value(form, "emission_mode"),
                        pulse_rate_hz=_optional_float(form, "pulse_rate_hz"),
                        pulse_width_ns=_optional_float(form, "pulse_width_ns"),
                    )
                )
                return self._redirect(start_response, self._location("setup", scenario_id))
            if path == "/setup/lockin":
                asyncio.run(
                    runtime.configure_lockin(
                        order=_require_int(form, "order"),
                        time_constant_seconds=_require_float(form, "time_constant_seconds"),
                        transfer_rate_hz=_require_float(form, "transfer_rate_hz"),
                    )
                )
                return self._redirect(start_response, self._location("setup", scenario_id))
            if path == "/setup/run/start":
                asyncio.run(runtime.start_run())
                return self._redirect(start_response, self._location("results", scenario_id))
            if path == "/setup/run/stop":
                asyncio.run(runtime.stop_run())
                return self._redirect(start_response, self._location("setup", scenario_id))
        except Exception as exc:
            return self._respond(start_response, "400 Bad Request", str(exc))
        return self._respond(start_response, "404 Not Found", f"No action for {path}")

    def _header(self, runtime: UiRuntimeGateway, active_route: str) -> HeaderStatus:
        return asyncio.run(runtime.get_header_status(active_route))

    def _location(self, route: str, scenario_id: str) -> str:
        path = f"/{route}"
        if scenario_id == self._default_scenario:
            return path
        return f"{path}?scenario={scenario_id}"

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

    def _read_form(self, environ: dict[str, object]) -> dict[str, list[str]]:
        try:
            content_length = int(str(environ.get("CONTENT_LENGTH", "0")) or "0")
        except ValueError:
            content_length = 0
        body_stream = environ.get("wsgi.input", BytesIO())
        if content_length <= 0 or not hasattr(body_stream, "read"):
            return {}
        read = cast(Callable[[int], bytes], getattr(body_stream, "read"))
        return parse_qs(read(content_length).decode("utf-8"))


def _extract_value(values: Mapping[str, list[str]], key: str) -> str | None:
    items = values.get(key)
    if not items:
        return None
    return items[0]


def _require_value(values: Mapping[str, list[str]], key: str) -> str:
    value = _extract_value(values, key)
    if value is None or value == "":
        raise ValueError(f"Missing required field: {key}")
    return value


def _require_float(values: Mapping[str, list[str]], key: str) -> float:
    return float(_require_value(values, key))


def _optional_float(values: Mapping[str, list[str]], key: str) -> float | None:
    value = _extract_value(values, key)
    if value in {None, ""}:
        return None
    return float(value)


def _require_int(values: Mapping[str, list[str]], key: str) -> int:
    return int(_require_value(values, key))


def _checkbox_checked(values: Mapping[str, list[str]], key: str) -> bool:
    return _extract_value(values, key) not in {None, "", "0", "false", "False", "off"}


def create_ui_app(
    runtimes: Mapping[str, UiRuntimeGateway],
    default_scenario: str = "nominal",
) -> IRCPUiApp:
    return IRCPUiApp(runtimes=runtimes, default_scenario=default_scenario)
