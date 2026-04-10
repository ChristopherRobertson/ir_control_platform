"""UI-facing typed query and command surfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ircp_contracts import HF2SampleComponent, SessionManifest

from .models import AnalyzePageModel, AdvancedPageModel, HeaderStatus, OperatePageModel, ResultsPageModel, ServicePageModel


@runtime_checkable
class UiQueryService(Protocol):
    async def get_header_status(self, active_route: str) -> HeaderStatus:
        """Return the shell header, route navigation, and global status badges."""

    async def get_operate_page(self) -> OperatePageModel:
        """Return the default operator-first page model."""

    async def get_results_page(self, selected_session_id: str | None = None) -> ResultsPageModel:
        """Return the saved-session review page model."""

    async def get_advanced_page(self) -> AdvancedPageModel:
        """Return the expert-only advanced page model."""

    async def get_analyze_page(self, selected_session_id: str | None = None) -> AnalyzePageModel:
        """Return the secondary analyze page model."""

    async def get_service_page(self) -> ServicePageModel:
        """Return the service and maintenance page model."""


@runtime_checkable
class UiCommandService(Protocol):
    async def save_session(self, session_label: str, sample_id: str, operator_notes: str) -> SessionManifest:
        """Persist a planned session using the current draft recipe."""

    async def open_saved_session(self, session_id: str) -> SessionManifest:
        """Reopen a saved session through the defined session boundary."""

    async def connect_laser(self):
        """Connect the MIRcat device."""

    async def disconnect_laser(self):
        """Disconnect the MIRcat device."""

    async def arm_laser(self):
        """Arm the MIRcat for coordinated control."""

    async def disarm_laser(self):
        """Disarm the MIRcat."""

    async def set_laser_emission(self, enabled: bool):
        """Set the MIRcat emission state explicitly."""

    async def tune_laser(self, target_wavenumber_cm1: float):
        """Apply a single-wavelength tune target for operator review."""

    async def start_scan(self):
        """Start the current MIRcat scan recipe."""

    async def stop_scan(self):
        """Stop the active MIRcat scan recipe."""

    async def connect_hf2(self):
        """Connect the HF2LI device."""

    async def disconnect_hf2(self):
        """Disconnect the HF2LI device."""

    async def start_hf2_acquisition(
        self,
        *,
        demod_index: int,
        component: HF2SampleComponent,
        sample_rate_hz: float,
        harmonic: int,
        capture_interval_seconds: float,
    ):
        """Apply the current HF2 draft and start acquisition when a session exists."""

    async def stop_hf2_acquisition(self):
        """Stop the active HF2 acquisition."""

    async def run_preflight(self):
        """Trigger the canonical preflight path."""

    async def start_run(self):
        """Create or reuse the current planned session and run the canonical path."""

    async def abort_active_run(self):
        """Abort the current run when a run is still active."""


@runtime_checkable
class UiRuntimeGateway(UiQueryService, UiCommandService, Protocol):
    """Combined UI runtime surface for the operator-first simulator shell."""
