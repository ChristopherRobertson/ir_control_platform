"""Bootstrap helpers for the simulator-backed platform app."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from wsgiref.types import WSGIApplication

from ircp_data_pipeline import FilesystemSessionStore, InMemorySessionStore
from ircp_experiment_engine import SupportedV1DriverBundle
from ircp_experiment_engine.runtime import InMemoryRunCoordinator, SupportedV1PreflightValidator
from ircp_simulators import SupportedV1SimulatorCatalog
from ircp_ui_shell import IRCPUiApp, create_ui_app

from .runtime_helpers import storage_base_root
from .simulator_runtime import SimulatorUiRuntime


def create_simulator_runtime_map(storage_root: Path | None = None) -> dict[str, SimulatorUiRuntime]:
    catalog = SupportedV1SimulatorCatalog()
    contexts = catalog.list_contexts()
    base_root = storage_base_root(storage_root)
    runtimes: dict[str, SimulatorUiRuntime] = {}
    for context in contexts:
        try:
            session_store = FilesystemSessionStore(
                root=base_root,
                initial_manifests=context.initial_manifests,
                initial_raw_artifact_payloads=context.initial_raw_artifact_payloads,
            )
        except (ModuleNotFoundError, AttributeError):
            session_store = InMemorySessionStore(
                initial_manifests=context.initial_manifests,
                initial_raw_artifact_payloads=context.initial_raw_artifact_payloads,
            )
        coordinator = InMemoryRunCoordinator(
            drivers=SupportedV1DriverBundle(
                mircat=context.bundle.mircat,
                hf2li=context.bundle.hf2li,
                t660_master=context.bundle.t660_master,
                t660_slave=context.bundle.t660_slave,
                mux=context.bundle.mux,
                picoscope=context.bundle.picoscope,
            ),
            session_store=session_store,
            session_replayer=session_store,
            preflight_validator=SupportedV1PreflightValidator(),
            run_plan_factory=context.run_plan_factory,
        )
        runtimes[context.scenario_id] = SimulatorUiRuntime(
            scenario=context,
            coordinator=coordinator,
            session_store=session_store,
            session_catalog=session_store,
            session_replayer=session_store,
            storage_root=base_root,
        )
    return runtimes


def create_simulator_app(storage_root: Path | None = None) -> IRCPUiApp:
    return create_ui_app(create_simulator_runtime_map(storage_root=storage_root), default_scenario="nominal")


def run_simulator_demo(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the dependency-light simulator shell locally."""

    from wsgiref.simple_server import make_server

    app = cast(WSGIApplication, create_simulator_app())
    with make_server(host, port, app) as server:
        server.serve_forever()


if __name__ == "__main__":
    run_simulator_demo()
