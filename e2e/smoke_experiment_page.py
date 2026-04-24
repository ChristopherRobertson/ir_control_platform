#!/usr/bin/env python3
"""Smoke-check the single-wavelength simulator UI through the local runner."""

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


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind((HOST, 0))
        return int(candidate.getsockname()[1])


def _request(host: str, port: int, method: str, path: str, body: dict[str, str] | None = None):
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


def _wait_for_server(process: subprocess.Popen[str], host: str, port: int) -> None:
    deadline = time.time() + STARTUP_TIMEOUT_SECONDS
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout is not None else ""
            raise RuntimeError(f"UI runner exited before becoming ready.\n{output}")
        try:
            status, _headers, _body = _request(host, port, "GET", "/session")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise TimeoutError("UI runner did not become ready.")


def _require_contains(body: str, markers: tuple[str, ...], context: str) -> None:
    missing = [marker for marker in markers if marker not in body]
    if missing:
        raise AssertionError(f"{context} missing markers: {', '.join(missing)}")


def _run_smoke_check(host: str, port: int) -> None:
    with tempfile.TemporaryDirectory(prefix="ircp-v1-smoke-") as storage_root:
        process = subprocess.Popen(
            [sys.executable, str(RUNNER), "--host", host, "--port", str(port), "--storage-root", storage_root],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            _wait_for_server(process, host, port)
            root_status, root_headers, _root_body = _request(host, port, "GET", "/")
            if root_status != 303 or root_headers.get("Location") != "/session":
                raise AssertionError(f"Expected / to redirect to /session, got {root_status} {root_headers!r}")

            session_status, _headers, session_body = _request(host, port, "GET", "/session")
            if session_status != 200:
                raise AssertionError(f"Expected /session to return 200, got {session_status}")
            _require_contains(session_body, ("Session Information", "Run Information"), "Session page")

            _request(
                host,
                port,
                "POST",
                "/session/save",
                {
                    "session_name": "Smoke Session",
                    "operator": "Operator",
                    "sample_id": "Sample",
                    "sample_notes": "",
                    "experiment_notes": "",
                },
            )
            _request(host, port, "POST", "/session/run/save", {"run_name": "Run 1", "run_notes": ""})
            _request(
                host,
                port,
                "POST",
                "/setup/save",
                {
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

            setup_status, _headers, setup_body = _request(host, port, "GET", "/setup")
            if setup_status != 200:
                raise AssertionError(f"Expected /setup to return 200, got {setup_status}")
            _require_contains(
                setup_body,
                (
                    "Pump Settings",
                    "Timescale",
                    "Probe Settings",
                    "Lock-In Amplifier Settings",
                    "Run Controls",
                ),
                "Setup page",
            )

            start_status, start_headers, _body = _request(host, port, "POST", "/setup/run/start")
            if start_status != 303 or start_headers.get("Location") != "/results":
                raise AssertionError(f"Expected /setup/run/start to redirect to /results, got {start_status} {start_headers!r}")

            results_status, _headers, results_body = _request(host, port, "GET", "/results?metric=R&display=ratio")
            if results_status != 200:
                raise AssertionError(f"Expected /results to return 200, got {results_status}")
            _require_contains(results_body, ("Result plot", "-log(sample/reference)", "Export"), "Results page")
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check the single-wavelength UI shell.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    try:
        _run_smoke_check(args.host, args.port or _pick_free_port())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print("PASS single-wavelength UI smoke check complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
