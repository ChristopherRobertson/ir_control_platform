"""Minimal WSGI application for the Phase 3A UI shell."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Callable, Mapping
from urllib.parse import parse_qs

from .boundaries import UiRuntimeGateway
from .components import render_layout, render_results_page, render_run_page, render_service_page, render_setup_page


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
            return self._redirect(start_response, f"/setup?scenario={scenario_id}")

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
        if path == "/setup":
            header = asyncio.run(runtime.get_header_status("setup"))
            page = asyncio.run(runtime.get_setup_page())
            return self._html(start_response, render_layout(header, render_setup_page(page, scenario_id)))
        if path == "/run":
            header = asyncio.run(runtime.get_header_status("run"))
            page = asyncio.run(runtime.get_run_page())
            return self._html(start_response, render_layout(header, render_run_page(page, scenario_id)))
        if path == "/results":
            selected_session_id = _extract_value(query, "session_id")
            header = asyncio.run(runtime.get_header_status("results"))
            page = asyncio.run(runtime.get_results_page(selected_session_id=selected_session_id))
            return self._html(
                start_response,
                render_layout(header, render_results_page(page, scenario_id)),
            )
        if path == "/service":
            header = asyncio.run(runtime.get_header_status("service"))
            page = asyncio.run(runtime.get_service_page())
            return self._html(start_response, render_layout(header, render_service_page(page)))
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
            if path == "/setup/preflight":
                asyncio.run(runtime.run_preflight())
                return self._redirect(start_response, f"/setup?scenario={scenario_id}")
            if path == "/run/start":
                asyncio.run(runtime.start_run())
                return self._redirect(start_response, f"/run?scenario={scenario_id}")
            if path == "/run/abort":
                asyncio.run(runtime.abort_active_run())
                return self._redirect(start_response, f"/run?scenario={scenario_id}")
            if path == "/results/reopen":
                session_id = _extract_value(form, "session_id")
                if session_id is None:
                    return self._respond(start_response, "400 Bad Request", "Missing session_id.")
                asyncio.run(runtime.reopen_session(session_id))
                return self._redirect(
                    start_response,
                    f"/results?scenario={scenario_id}&session_id={session_id}",
                )
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


def create_ui_app(runtimes: Mapping[str, UiRuntimeGateway], default_scenario: str = "nominal") -> IRCPUiApp:
    return IRCPUiApp(runtimes=runtimes, default_scenario=default_scenario)
