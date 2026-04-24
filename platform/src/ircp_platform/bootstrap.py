"""Bootstrap helpers for the simulator-backed v1 application."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from wsgiref.types import WSGIApplication

from ircp_simulators import SupportedV1SimulatorCatalog
from ircp_ui_shell import IRCPUiApp, create_ui_app

from .runtime_helpers import storage_base_root
from .simulator_runtime import SimulatorUiRuntime


def create_simulator_runtime_map(storage_root: Path | None = None) -> dict[str, SimulatorUiRuntime]:
    catalog = SupportedV1SimulatorCatalog()
    base_root = storage_base_root(storage_root)
    return {
        context.scenario_id: SimulatorUiRuntime(
            scenario=context,
            storage_root=base_root / context.scenario_id,
        )
        for context in catalog.list_contexts()
    }


def create_simulator_app(storage_root: Path | None = None) -> IRCPUiApp:
    return create_ui_app(create_simulator_runtime_map(storage_root=storage_root), default_scenario="nominal")


def run_simulator_demo(host: str = "127.0.0.1", port: int = 8000) -> None:
    from wsgiref.simple_server import make_server

    app = cast(WSGIApplication, create_simulator_app())
    with make_server(host, port, app) as server:
        server.serve_forever()


if __name__ == "__main__":
    run_simulator_demo()
