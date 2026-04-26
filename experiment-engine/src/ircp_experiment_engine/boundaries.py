"""Engine-facing orchestration boundaries for the supported v1 slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ircp_contracts import (
    ArtifactSourceRole,
    ConfigurationScalar,
    DeviceFault,
    PreflightReport,
    RunEvent,
    RunFailureReason,
    RunState,
    SessionManifest,
)
from ircp_contracts._deferred_experiment import ExperimentPreset, ExperimentRecipe
from ircp_drivers import (
    ArduinoMuxDriver,
    LabOneHF2Driver,
    MircatDriver,
    PicoScopeDriver,
    T660TimingDriver,
)


@dataclass(frozen=True)
class SupportedV1DriverBundle:
    mircat: MircatDriver
    hf2li: LabOneHF2Driver
    t660_master: T660TimingDriver
    t660_slave: T660TimingDriver
    mux: ArduinoMuxDriver
    picoscope: PicoScopeDriver


@dataclass(frozen=True)
class LiveDataPoint:
    sample_id: str
    captured_at: datetime
    stream_name: str
    axis_label: str
    axis_units: str
    axis_value: float
    value: float
    units: str = "V"
    source_role: ArtifactSourceRole = ArtifactSourceRole.PRIMARY_RAW
    metadata: dict[str, ConfigurationScalar] | None = None


@dataclass(frozen=True)
class RunTimeline:
    run_id: str
    states: tuple[RunState, ...]
    events: tuple[RunEvent, ...]
    live_data_points: tuple[LiveDataPoint, ...]


@runtime_checkable
class PreflightValidator(Protocol):
    async def validate(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        drivers: SupportedV1DriverBundle,
    ) -> PreflightReport:
        """Evaluate the supported-v1 preflight path."""


@runtime_checkable
class RunCoordinator(Protocol):
    async def create_session(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        session_id: str | None = None,
        notes: tuple[str, ...] = (),
    ) -> SessionManifest:
        """Create the authoritative session record before coordinated execution."""

    async def start_run(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        session_id: str,
    ) -> RunState:
        """Start the canonical supported-v1 run path."""

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


@runtime_checkable
class RunMonitor(Protocol):
    async def get_run_timeline(self, run_id: str) -> RunTimeline:
        """Return the explicit run-state progression, events, and live data for one run."""
