"""UI-facing typed query and command surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ircp_contracts import DeviceConfiguration, DeviceStatus, PreflightReport, RunState, SessionManifest

from .models import (
    AnalyzePageModel,
    AdvancedPageModel,
    HeaderStatus,
    OperatePageModel,
    ResultsPageModel,
    RunPageModel,
    ServicePageModel,
    SetupPageModel,
)


@dataclass(frozen=True)
class ResultsDownload:
    filename: str
    content_type: str
    body: bytes


@runtime_checkable
class UiQueryService(Protocol):
    async def get_header_status(self, active_route: str) -> HeaderStatus:
        """Return the shell header, route navigation, and global status badges."""
        ...

    async def get_operate_page(self) -> OperatePageModel:
        """Return the default Experiment mission-control page model."""
        ...

    async def get_setup_page(self) -> SetupPageModel:
        """Return the focused Setup page model for experiment preparation."""
        ...

    async def get_run_page(self) -> RunPageModel:
        """Return the focused Run page model for live execution review."""
        ...

    async def get_results_page(
        self,
        selected_session_id: str | None = None,
        *,
        search: str = "",
        status_filter: str = "all",
        sort_order: str = "updated_desc",
    ) -> ResultsPageModel:
        """Return the saved-session review page model."""
        ...

    async def get_results_download(
        self,
        session_id: str,
        *,
        asset: str | None = None,
        artifact_id: str | None = None,
    ) -> ResultsDownload:
        """Return one Results-owned file or serialized session artifact for download."""
        ...

    async def get_advanced_page(self) -> AdvancedPageModel:
        """Return the expert-only advanced page model."""
        ...

    async def get_analyze_page(self, selected_session_id: str | None = None) -> AnalyzePageModel:
        """Return the secondary analyze page model."""
        ...

    async def get_service_page(self) -> ServicePageModel:
        """Return the service and maintenance page model."""
        ...


@runtime_checkable
class UiCommandService(Protocol):
    async def set_experiment_type(self, experiment_type: str) -> str:
        """Select the operator-facing experiment type for the current Experiment page."""
        ...

    async def configure_operating_mode(
        self,
        *,
        experiment_type: str,
        emission_mode: str,
        tune_target_cm1: float | None = None,
        scan_start_cm1: float | None = None,
        scan_stop_cm1: float | None = None,
        scan_step_size_cm1: float | None = None,
        scan_dwell_time_ms: float | None = None,
        pulse_repetition_rate_hz: float | None = None,
        pulse_width_ns: float | None = None,
        pulse_duty_cycle_percent: float | None = None,
    ) -> None:
        """Persist the current MIRcat operating-mode draft fields from the Experiment page."""
        ...

    async def configure_hf2(
        self,
        *,
        sample_rate_hz: float | None = None,
        harmonic: int | None = None,
        time_constant_seconds: float | None = None,
        extref: str | None = None,
        trigger: str | None = None,
    ) -> None:
        """Persist the current HF2LI draft fields from the Experiment page."""
        ...

    async def configure_ndyag(
        self,
        *,
        repetition_rate_hz: float | None = None,
        shot_count: int | None = None,
        continuous: bool,
    ) -> None:
        """Persist the current Nd:YAG draft fields from the Experiment page."""
        ...

    async def set_ndyag_enabled(self, enabled: bool) -> None:
        """Turn the Nd:YAG draft control on or off."""
        ...

    async def save_session(
        self,
        session_id: str,
        session_label: str,
        sample_id: str,
        operator_notes: str,
    ) -> SessionManifest:
        """Persist a planned session using the current draft recipe."""
        ...

    async def delete_saved_session(self, session_id: str) -> None:
        """Delete one saved session and remove it from reopen workflows."""
        ...

    async def open_saved_session(self, session_id: str) -> SessionManifest:
        """Reopen a saved session through the defined session boundary."""
        ...

    async def connect_laser(self) -> DeviceStatus:
        """Connect the MIRcat device."""
        ...

    async def disconnect_laser(self) -> DeviceStatus:
        """Disconnect the MIRcat device."""
        ...

    async def arm_laser(self) -> DeviceStatus:
        """Arm the MIRcat for coordinated control."""
        ...

    async def disarm_laser(self) -> DeviceStatus:
        """Disarm the MIRcat."""
        ...

    async def set_laser_emission(self, enabled: bool) -> DeviceStatus:
        """Set the MIRcat emission state explicitly."""
        ...

    async def tune_laser(self, target_wavenumber_cm1: float) -> DeviceConfiguration:
        """Apply a single-wavelength tune target for operator review."""
        ...

    async def cancel_laser_tune(self) -> DeviceStatus:
        """Cancel the current single-wavelength tune and return MIRcat to idle."""
        ...

    async def start_scan(
        self,
        *,
        start_wavenumber_cm1: float,
        end_wavenumber_cm1: float,
        step_size_cm1: float,
        dwell_time_ms: float | None = None,
    ) -> DeviceStatus:
        """Start the current MIRcat scan recipe using the reviewed operator-facing scan fields."""
        ...

    async def stop_scan(self) -> DeviceStatus:
        """Stop the active MIRcat scan recipe."""
        ...

    async def connect_hf2(self) -> DeviceStatus:
        """Connect the HF2LI device."""
        ...

    async def disconnect_hf2(self) -> DeviceStatus:
        """Disconnect the HF2LI device."""
        ...

    async def run_preflight(self) -> PreflightReport:
        """Trigger the canonical preflight path."""
        ...

    async def start_run(self) -> RunState:
        """Create or reuse the current planned session and run the canonical path."""
        ...

    async def abort_active_run(self) -> RunState | None:
        """Abort the current run when a run is still active."""
        ...


@runtime_checkable
class UiRuntimeGateway(UiQueryService, UiCommandService, Protocol):
    """Combined UI runtime surface for the operator-first simulator shell."""
