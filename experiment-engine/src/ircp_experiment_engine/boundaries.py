"""Engine-facing orchestration boundaries for the first vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ircp_contracts import (
    DeviceFault,
    ExperimentPreset,
    ExperimentRecipe,
    PreflightReport,
    RunEvent,
    RunFailureReason,
    RunState,
    SessionManifest,
)
from ircp_drivers import LabOneHF2Driver, MircatDriver


@dataclass(frozen=True)
class GoldenPathDriverBundle:
    mircat: MircatDriver
    hf2li: LabOneHF2Driver


@runtime_checkable
class PreflightValidator(Protocol):
    async def validate(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        drivers: GoldenPathDriverBundle,
    ) -> PreflightReport:
        """Evaluate the single approved preflight path for MIRcat + HF2LI."""


@runtime_checkable
class RunCoordinator(Protocol):
    async def create_session(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
    ) -> SessionManifest:
        """Create the authoritative session record before coordinated execution."""

    async def start_run(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        session_id: str,
    ) -> RunState:
        """Start the single approved coordinated run path."""

    async def get_run_state(self, run_id: str) -> RunState:
        """Return the current authoritative run state."""

    async def report_device_fault(self, run_id: str, fault: DeviceFault) -> RunEvent:
        """Convert a normalized device fault into an engine-level run event."""

    async def abort_run(
        self,
        run_id: str,
        reason: RunFailureReason = RunFailureReason.OPERATOR_ABORT,
    ) -> RunState:
        """Abort the active run explicitly."""

    async def reopen_session(self, session_id: str) -> SessionManifest:
        """Reopen a saved or partial session for later replay or review."""
