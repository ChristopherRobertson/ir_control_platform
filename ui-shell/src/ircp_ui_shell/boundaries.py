"""UI-facing typed query, command, and subscription surfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ircp_contracts import ExperimentPreset, ExperimentRecipe, PreflightReport, RunState, SessionManifest

from .models import (
    AnalyzePageModel,
    EventLogItem,
    HeaderStatus,
    LiveDataSeries,
    ResultsPageModel,
    RunPageModel,
    RunStepSummary,
    ServicePageModel,
    SetupPageModel,
)


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


@runtime_checkable
class UiQueryService(Protocol):
    async def get_header_status(self, active_route: str) -> HeaderStatus:
        """Return the shell header, route navigation, and global status badges."""

    async def get_setup_page(self, surface: str = "setup") -> SetupPageModel:
        """Return the Setup, Advanced, or Calibrated scaffold model."""

    async def get_run_page(self) -> RunPageModel:
        """Return the Run scaffold model."""

    async def get_results_page(self, selected_session_id: str | None = None) -> ResultsPageModel:
        """Return the Results scaffold model."""

    async def get_analyze_page(self, selected_session_id: str | None = None) -> AnalyzePageModel:
        """Return the Analyze scaffold model."""

    async def get_service_page(self) -> ServicePageModel:
        """Return the Service scaffold model."""


@runtime_checkable
class UiCommandService(Protocol):
    async def run_preflight(self) -> PreflightReport:
        """Trigger the canonical preflight path."""

    async def start_run(self) -> RunState:
        """Create a session and execute the canonical run path."""

    async def abort_active_run(self) -> RunState | None:
        """Abort the current run when a run is still active."""

    async def reopen_session(self, session_id: str) -> SessionManifest:
        """Reopen a saved session through the defined session boundary."""


@runtime_checkable
class UiSubscriptionService(Protocol):
    async def get_known_run_id(self) -> str | None:
        """Return the current run id, if one exists."""

    async def get_run_events(self, run_id: str) -> tuple[EventLogItem, ...]:
        """Return the current event log projection for one run."""

    async def get_live_data(
        self,
        run_id: str,
    ) -> tuple[tuple[LiveDataSeries, ...], tuple[LiveDataSeries, ...]]:
        """Return primary and secondary live-data projections for one run."""

    async def get_run_steps(self, run_id: str) -> tuple[RunStepSummary, ...]:
        """Return the explicit run-state progression for one run."""


@runtime_checkable
class UiRuntimeGateway(UiQueryService, UiCommandService, UiSubscriptionService, Protocol):
    """Combined UI runtime surface for the Phase 3B shell."""
