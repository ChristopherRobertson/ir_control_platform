#!/usr/bin/env python3
"""Smoke-check the baseline Experiment page through the local UI runner."""

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

VISIBLE_MARKERS = (
    "Experiment",
    "Fixed Wavelength",
    "Session",
    "Operating Mode",
    "Nd:YAG Settings",
    "HF2LI",
    "Run Control",
    "Save Session",
    "Run Preflight",
    "Start Experiment",
)

HIDDEN_MARKERS = (
    "Pump Shots Before Probe",
    "Pico Secondary Capture",
    "Pico Monitoring Mode",
    "MUX Route Set",
    "T660-2",
    "T660-1",
    "Timing Program",
    "Trigger Marker",
)

FIXED_MODE_MARKERS = (
    'name="tune_target_cm1"',
    ">Tune<",
)

SCAN_MODE_MARKERS = (
    'name="scan_start_cm1"',
    'name="scan_stop_cm1"',
    'name="scan_step_size_cm1"',
    'name="scan_dwell_time_ms"',
    ">Start Scan<",
    ">Stop Scan<",
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


def _require_absent(body: str, markers: tuple[str, ...], context: str) -> None:
    present = [marker for marker in markers if marker in body]
    if present:
        raise AssertionError(f"{context} unexpectedly included: {', '.join(present)}")


def _print_ok(message: str) -> None:
    print(f"PASS {message}")


def _print_skip(message: str) -> None:
    print(f"SKIP {message}")


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

            experiment_status, _experiment_headers, experiment_body = _request(host, port, "GET", "/experiment")
            if experiment_status != 200:
                raise AssertionError(f"Expected /experiment to return 200, got {experiment_status}")
            _print_ok("Experiment page loads")

            _require_contains(experiment_body, VISIBLE_MARKERS, "baseline Experiment page")
            _print_ok("baseline sections and scope markers are visible")

            _require_absent(experiment_body, HIDDEN_MARKERS, "baseline Experiment page")
            _print_ok("timing, Pico, and MUX clutter stay off the main page")

            _require_contains(experiment_body, FIXED_MODE_MARKERS, "fixed-wavelength mode")
            _require_absent(experiment_body, ('name="scan_start_cm1"',), "fixed-wavelength mode")
            _print_ok("default mode stays on fixed-wavelength MIRcat controls")

            mode_switch_present = (
                'action="/experiment/laser/configure"' in experiment_body
                and 'name="experiment_type"' in experiment_body
                and "Fixed Wavelength" in experiment_body
                and "Wavelength Scan" in experiment_body
            )
            if not mode_switch_present:
                _print_skip("experiment-type switch is not rendered")
                return

            switch_status, switch_headers, _switch_body = _request(
                host,
                port,
                "POST",
                "/experiment/laser/configure",
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
            if switch_status != 303 or switch_headers.get("Location") != "/experiment":
                raise AssertionError(
                    f"Expected wavelength-scan POST to redirect to /experiment, got {switch_status} {switch_headers!r}"
                )

            scan_status, _scan_headers, scan_body = _request(host, port, "GET", "/experiment")
            if scan_status != 200:
                raise AssertionError(f"Expected scan-mode /experiment to return 200, got {scan_status}")

            _require_contains(scan_body, SCAN_MODE_MARKERS, "wavelength-scan mode")
            _require_absent(scan_body, ('name="tune_target_cm1"', ">Tune<"), "wavelength-scan mode")
            _print_ok("mode switch swaps fixed controls for scan controls")
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check the minimal Experiment page through the local UI runner.")
    parser.add_argument("--host", default=HOST, help="Bind address used for the temporary local runner.")
    parser.add_argument("--port", type=int, default=0, help="Port used for the temporary local runner. Defaults to an open port.")
    args = parser.parse_args()

    port = args.port or _pick_free_port()
    try:
        _run_smoke_check(args.host, port)
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    print("PASS Experiment page smoke check complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
