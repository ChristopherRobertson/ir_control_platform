"""UI-facing command and query surfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ircp_contracts import ExperimentPreset, ExperimentRecipe, PreflightReport, RunState, SessionManifest


@runtime_checkable
class ControlPlaneClient(Protocol):
    async def run_preflight(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None = None,
    ) -> PreflightReport:
        """Request the authoritative preflight evaluation from the engine boundary."""

    async def start_run(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None = None,
    ) -> RunState:
        """Request the canonical run-start path from the engine boundary."""

    async def abort_run(self, run_id: str) -> RunState:
        """Request explicit abort through the engine boundary."""

    async def get_run_state(self, run_id: str) -> RunState:
        """Read the current run state without orchestrating devices locally."""


@runtime_checkable
class ResultsQueryService(Protocol):
    async def open_session(self, session_id: str) -> SessionManifest:
        """Open a saved session for results, replay, or comparison views."""
