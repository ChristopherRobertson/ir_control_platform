"""Minimal WSGI application for the operator-first UI shell."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Callable, Mapping
from urllib.parse import parse_qs

from ircp_contracts import HF2SampleComponent

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
            return self._redirect(start_response, f"/operate?scenario={scenario_id}")

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
        if path in {"/setup", "/run"}:
            return self._redirect(start_response, f"/operate?scenario={scenario_id}")
        if path in {"/setup/advanced", "/setup/calibrated"}:
            return self._redirect(start_response, f"/advanced?scenario={scenario_id}")
        if path == "/operate":
            header = asyncio.run(runtime.get_header_status("operate"))
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
        try:
            if path == "/operate/session/save":
                asyncio.run(
                    runtime.save_session(
                        session_label=_extract_value(form, "session_label") or "",
                        sample_id=_extract_value(form, "sample_id") or "",
                        operator_notes=_extract_value(form, "operator_notes") or "",
                    )
                )
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/session/open":
                session_id = _require_value(form, "session_id")
                asyncio.run(runtime.open_saved_session(session_id))
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/laser/connect":
                asyncio.run(runtime.connect_laser())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/laser/disconnect":
                asyncio.run(runtime.disconnect_laser())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/laser/arm":
                asyncio.run(runtime.arm_laser())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/laser/disarm":
                asyncio.run(runtime.disarm_laser())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/laser/emission/on":
                asyncio.run(runtime.set_laser_emission(True))
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/laser/emission/off":
                asyncio.run(runtime.set_laser_emission(False))
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/laser/tune":
                asyncio.run(runtime.tune_laser(_require_float(form, "tune_target_cm1")))
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/laser/scan/start":
                asyncio.run(runtime.start_scan())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/laser/scan/stop":
                asyncio.run(runtime.stop_scan())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/hf2/connect":
                asyncio.run(runtime.connect_hf2())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/hf2/disconnect":
                asyncio.run(runtime.disconnect_hf2())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/hf2/start":
                asyncio.run(
                    runtime.start_hf2_acquisition(
                        demod_index=_require_int(form, "hf2_demod_index"),
                        component=HF2SampleComponent(_require_value(form, "hf2_component")),
                        sample_rate_hz=_require_float(form, "hf2_sample_rate_hz"),
                        harmonic=_require_int(form, "hf2_harmonic"),
                        capture_interval_seconds=_require_float(form, "hf2_capture_interval_seconds"),
                    )
                )
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/hf2/stop":
                asyncio.run(runtime.stop_hf2_acquisition())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/run/preflight":
                asyncio.run(runtime.run_preflight())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/run/start":
                asyncio.run(runtime.start_run())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
            if path == "/operate/run/abort":
                asyncio.run(runtime.abort_active_run())
                return self._redirect(start_response, f"/operate?scenario={scenario_id}")
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
        body = body_stream.read(content_length).decode("utf-8")
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


def _require_int(values: Mapping[str, list[str]], key: str) -> int:
    return int(_require_value(values, key))


def _require_float(values: Mapping[str, list[str]], key: str) -> float:
    return float(_require_value(values, key))


def create_ui_app(runtimes: Mapping[str, UiRuntimeGateway], default_scenario: str = "nominal") -> IRCPUiApp:
    return IRCPUiApp(runtimes=runtimes, default_scenario=default_scenario)
