#!/usr/bin/env python3
"""Smoke-check the finished simulator-backed UI shell through the local runner."""

from __future__ import annotations

import argparse
import http.client
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "run_ui.py"
HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 12.0

EXPERIMENT_MARKERS = (
    "Experiment",
    "Current Configuration",
    "Hardware Visibility",
    "Live Data",
    "Open Setup Workspace",
    "Open Run Workspace",
)

SETUP_MARKERS = (
    "Setup",
    "Preflight / Validation",
    "Readiness and Defaults",
    "Hardware Readiness",
    "Timing and synchronization detail",
)

RUN_MARKERS = (
    "Run completed",
    "Run Metadata",
    "Run Timeline",
    "Live Data Review",
    "Open Results",
)

RESULTS_MARKERS = (
    "Recent Sessions",
    "Visualization and Trace Review",
    "Artifacts and Provenance",
    "Download Manifest",
    "Compare to Baseline",
)

SERVICE_MARKERS = (
    "Device Diagnostics",
    "Calibration Visibility",
    "Recovery and Maintenance",
    "Attempt Recovery",
)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind((HOST, 0))
        return int(candidate.getsockname()[1])


def _request(
    host: str,
    port: int,
    method: str,
    path: str,
    body: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], str]:
    payload = urlencode(body or {})
    headers = {"Content-Type": "application/x-www-form-urlencoded"} if body is not None else {}
    connection = http.client.HTTPConnection(host, port, timeout=3)
    try:
        connection.request(method, path, body=payload if body is not None else None, headers=headers)
        response = connection.getresponse()
        content = response.read().decode("utf-8", errors="replace")
        return response.status, {name: value for name, value in response.getheaders()}, content
    finally:
        connection.close()


def _wait_for_server(process: subprocess.Popen[str], host: str, port: int, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout is not None else ""
            raise RuntimeError(f"UI runner exited before becoming ready.\n{output}")
        try:
            status, _headers, _body = _request(host, port, "GET", "/experiment")
            if status == 200:
                return
        except Exception as exc:  # pragma: no cover - exercised in manual smoke use
            last_error = exc
        time.sleep(0.2)

    output = process.stdout.read() if process.stdout is not None else ""
    raise TimeoutError(f"UI runner did not become ready within {timeout_seconds:.1f}s.\n{last_error}\n{output}")


def _require_contains(body: str, markers: tuple[str, ...], context: str) -> None:
    missing = [marker for marker in markers if marker not in body]
    if missing:
        raise AssertionError(f"{context} missing markers: {', '.join(missing)}")


def _print_ok(message: str) -> None:
    print(f"PASS {message}")


def _run_smoke_check(host: str, port: int) -> None:
    with tempfile.TemporaryDirectory(prefix="ircp-ui-smoke-") as storage_root:
        process = subprocess.Popen(
            [sys.executable, str(RUNNER), "--host", host, "--port", str(port), "--storage-root", storage_root],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            _wait_for_server(process, host, port, STARTUP_TIMEOUT_SECONDS)
            _print_ok(f"local UI runner launched on http://{host}:{port}")

            root_status, root_headers, _root_body = _request(host, port, "GET", "/")
            if root_status != 303 or root_headers.get("Location") != "/experiment":
                raise AssertionError(f"Expected / to redirect to /experiment, got {root_status} {root_headers!r}")
            _print_ok("default route redirects to /experiment")

            experiment_status, _headers, experiment_body = _request(host, port, "GET", "/experiment")
            if experiment_status != 200:
                raise AssertionError(f"Expected /experiment to return 200, got {experiment_status}")
            _require_contains(experiment_body, EXPERIMENT_MARKERS, "Experiment route")
            _print_ok("Experiment mission-control markers are visible")

            setup_status, _headers, setup_body = _request(host, port, "GET", "/setup")
            if setup_status != 200:
                raise AssertionError(f"Expected /setup to return 200, got {setup_status}")
            _require_contains(setup_body, SETUP_MARKERS, "Setup route")
            _print_ok("Setup workspace markers are visible")

            start_status, start_headers, _body = _request(
                host,
                port,
                "POST",
                "/run/start",
                body={"scenario": "nominal"},
            )
            if start_status != 303 or start_headers.get("Location") != "/run":
                raise AssertionError(f"Expected /run/start to redirect to /run, got {start_status} {start_headers!r}")
            _print_ok("Run start action redirects to the Run workspace")

            run_status, _headers, run_body = _request(host, port, "GET", "/run")
            if run_status != 200:
                raise AssertionError(f"Expected /run to return 200, got {run_status}")
            _require_contains(run_body, RUN_MARKERS, "Run route")
            _print_ok("Run workspace markers are visible after start")

            results_status, _headers, results_body = _request(host, port, "GET", "/results")
            if results_status != 200:
                raise AssertionError(f"Expected /results to return 200, got {results_status}")
            _require_contains(results_body, RESULTS_MARKERS, "Results route")
            _print_ok("Results workspace markers are visible")

            service_status, _headers, service_body = _request(host, port, "GET", "/service")
            if service_status != 200:
                raise AssertionError(f"Expected /service to return 200, got {service_status}")
            _require_contains(service_body, SERVICE_MARKERS, "Service route")
            _print_ok("Service workspace markers are visible")
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check the finished UI shell through the local runner.")
    parser.add_argument("--host", default=HOST, help="Bind address used for the temporary local runner.")
    parser.add_argument("--port", type=int, default=0, help="Port used for the temporary local runner. Defaults to an open port.")
    args = parser.parse_args()

    port = args.port or _pick_free_port()
    try:
        _run_smoke_check(args.host, port)
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    print("PASS Finished UI shell smoke check complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
