"""UI-facing query and command boundary for the three-page v1 workflow."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import HeaderStatus, ResultsDownload, ResultsPageModel, SessionPageModel, SetupPageModel


@runtime_checkable
class UiQueryService(Protocol):
    async def get_header_status(self, active_route: str) -> HeaderStatus:
        """Return navigation and global workflow badges."""

    async def get_session_page(self) -> SessionPageModel:
        """Return Page 1 - Session."""

    async def get_setup_page(self) -> SetupPageModel:
        """Return Page 2 - Setup."""

    async def get_results_page(
        self,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
        metric_family: str = "R",
        display_mode: str = "overlay",
    ) -> ResultsPageModel:
        """Return Page 3 - Results from saved run data."""

    async def get_results_download(
        self,
        *,
        session_id: str,
        run_id: str,
        asset: str,
    ) -> ResultsDownload:
        """Return raw, processed, or metadata export bytes for a saved run."""


@runtime_checkable
class UiCommandService(Protocol):
    async def save_session(
        self,
        *,
        session_name: str,
        operator: str,
        sample_id: str,
        sample_notes: str,
        experiment_notes: str,
    ) -> str:
        """Create or save editable session metadata."""

    async def confirm_session_overwrite(self) -> str:
        """Overwrite the conflicting saved session using the pending form values."""

    async def cancel_session_overwrite(self) -> None:
        """Cancel the pending overwrite and keep the conflicting field highlighted."""

    async def open_session(self, *, session_id: str) -> str:
        """Load an existing session into the Session page."""

    async def open_run(self, *, session_id: str, run_id: str) -> str:
        """Load an existing run for the currently opened session."""

    async def create_run(self, *, run_name: str, run_notes: str) -> str:
        """Create a draft run header inside the saved session."""

    async def save_run_header(self, *, run_name: str, run_notes: str) -> str:
        """Persist the draft run header before setup begins."""

    async def configure_pump(self, *, enabled: bool, shot_count: int) -> None:
        """Persist pump setup draft values."""

    async def configure_timescale(self, *, timescale: str) -> None:
        """Persist the acquisition-window regime."""

    async def configure_probe(
        self,
        *,
        wavelength_cm1: float,
        emission_mode: str,
        pulse_rate_hz: float | None,
        pulse_width_ns: float | None,
    ) -> None:
        """Persist single-wavelength MIRcat probe settings."""

    async def configure_lockin(
        self,
        *,
        order: int,
        time_constant_seconds: float,
        transfer_rate_hz: float,
    ) -> None:
        """Persist the only operator-editable lock-in overrides for v1."""

    async def save_setup(
        self,
        *,
        pump_enabled: bool,
        shot_count: int,
        timescale: str,
        wavelength_cm1: float,
        emission_mode: str,
        pulse_rate_hz: float | None,
        pulse_width_ns: float | None,
        order: int,
        time_constant_seconds: float,
        transfer_rate_hz: float,
    ) -> None:
        """Persist the current setup draft as the saved run configuration."""

    async def toggle_probe_connection(self) -> None:
        """Toggle simulated MIRcat connection state."""

    async def clear_probe_fault(self) -> None:
        """Clear the current simulated MIRcat fault state."""

    async def toggle_lockin_connection(self) -> None:
        """Toggle simulated lock-in connection state."""

    async def start_run(self) -> str:
        """Start the canonical run from the saved session, saved run header, and valid setup."""

    async def stop_run(self) -> str | None:
        """Stop the active run when the backend has a distinct stoppable state."""


@runtime_checkable
class UiRuntimeGateway(UiQueryService, UiCommandService, Protocol):
    """Combined UI runtime surface."""
