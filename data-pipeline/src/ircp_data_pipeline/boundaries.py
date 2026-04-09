"""Session persistence and replay boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ircp_contracts import (
    AnalysisArtifact,
    ArtifactKind,
    ArtifactSourceRole,
    CalibrationReference,
    DeviceConfiguration,
    DeviceFault,
    DeviceKind,
    DeviceStatus,
    ExperimentPreset,
    ExperimentRecipe,
    ExportArtifact,
    MuxRouteSelection,
    MuxRoutingSummary,
    PicoCaptureSummary,
    PicoSecondaryCapture,
    ProcessedArtifact,
    PumpProbeAcquisitionSummary,
    RawDataArtifact,
    RunEvent,
    RunFailureReason,
    SessionManifest,
    SessionStatus,
    TimeToWavenumberMapping,
    TimingSummary,
    TimingMarker,
)


@dataclass(frozen=True)
class SessionOpenRequest:
    session_id: str
    requested_at: datetime
    reopen_for_replay: bool = False


@dataclass(frozen=True)
class SessionOpenResult:
    manifest: SessionManifest
    replay_ready: bool
    primary_raw_artifact_ids: tuple[str, ...]
    secondary_monitor_artifact_ids: tuple[str, ...]
    processed_artifact_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReplayPlan:
    session_id: str
    primary_raw_artifact_ids: tuple[str, ...]
    secondary_monitor_artifact_ids: tuple[str, ...]
    processed_artifact_ids: tuple[str, ...]
    analysis_artifact_ids: tuple[str, ...]


@dataclass(frozen=True)
class ArtifactSummary:
    artifact_id: str
    session_id: str
    artifact_kind: ArtifactKind
    relative_path: str
    created_at: datetime
    source_role: ArtifactSourceRole | None = None
    device_kind: DeviceKind | None = None
    stream_name: str | None = None
    content_type: str | None = None
    record_count: int | None = None
    mux_output_target: str | None = None
    related_marker: str | None = None
    registered_by_event_id: str | None = None


@dataclass(frozen=True)
class ArtifactQuery:
    session_id: str | None = None
    artifact_kind: ArtifactKind | None = None
    source_role: ArtifactSourceRole | None = None


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    recipe_id: str
    recipe_title: str
    created_at: datetime
    updated_at: datetime
    status: SessionStatus
    event_count: int
    last_event_at: datetime | None
    replay_ready: bool
    primary_raw_artifact_count: int
    secondary_monitor_artifact_count: int
    processed_artifact_count: int
    analysis_artifact_count: int
    export_artifact_count: int
    failure_reason: RunFailureReason | None = None


@dataclass(frozen=True)
class SessionDetail:
    summary: SessionSummary
    manifest: SessionManifest
    event_timeline: tuple[RunEvent, ...]
    primary_raw_artifacts: tuple[ArtifactSummary, ...]
    secondary_monitor_artifacts: tuple[ArtifactSummary, ...]
    processed_artifacts: tuple[ArtifactSummary, ...]
    analysis_artifacts: tuple[ArtifactSummary, ...]
    export_artifacts: tuple[ArtifactSummary, ...]
    replay_plan: ReplayPlan


@runtime_checkable
class SessionStore(Protocol):
    async def create_session_manifest(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        calibration_references: tuple[CalibrationReference, ...],
        device_config_snapshot: tuple[DeviceConfiguration, ...],
        device_status_snapshot: tuple[DeviceStatus, ...],
        timing_summary: TimingSummary,
        pump_probe_summary: PumpProbeAcquisitionSummary,
        selected_markers: tuple[TimingMarker, ...],
        mux_route_snapshot: MuxRouteSelection,
        mux_summary: MuxRoutingSummary,
        pico_capture_snapshot: PicoSecondaryCapture,
        pico_summary: PicoCaptureSummary,
        time_to_wavenumber_mapping: TimeToWavenumberMapping | None,
        notes: tuple[str, ...] = (),
    ) -> SessionManifest:
        """Create the authoritative session record before run completion."""

    async def update_device_snapshots(
        self,
        session_id: str,
        *,
        device_config_snapshot: tuple[DeviceConfiguration, ...] | None = None,
        device_status_snapshot: tuple[DeviceStatus, ...] | None = None,
    ) -> SessionManifest:
        """Replace authoritative device snapshots for a persisted session."""

    async def append_event(self, session_id: str, event: RunEvent) -> SessionManifest:
        """Persist one run event onto the session timeline."""

    async def update_session_status(self, session_id: str, status: SessionStatus) -> SessionManifest:
        """Update the authoritative session lifecycle state."""

    async def finalize_session(
        self,
        session_id: str,
        status: SessionStatus,
        *,
        ended_at: datetime | None = None,
        failure_reason: RunFailureReason | None = None,
        latest_fault: DeviceFault | None = None,
        final_event: RunEvent | None = None,
        note: str | None = None,
    ) -> SessionManifest:
        """Finalize a session explicitly as completed, faulted, or aborted."""

    async def register_raw_artifact(self, session_id: str, artifact: RawDataArtifact) -> SessionManifest:
        """Register a raw artifact without letting the UI own the write path."""

    async def persist_raw_artifact(
        self,
        session_id: str,
        artifact: RawDataArtifact,
        payload_rows: tuple[dict[str, object], ...],
    ) -> SessionManifest:
        """Write one structured raw payload durably, then register the raw artifact in the session manifest."""

    async def register_processed_artifact(
        self, session_id: str, artifact: ProcessedArtifact
    ) -> SessionManifest:
        """Register a processed artifact with provenance back to raw inputs."""

    async def register_analysis_artifact(
        self, session_id: str, artifact: AnalysisArtifact
    ) -> SessionManifest:
        """Register an analysis artifact with provenance back to processed or raw inputs."""

    async def register_export_artifact(self, session_id: str, artifact: ExportArtifact) -> SessionManifest:
        """Register an export artifact with provenance back to persisted sources."""


@runtime_checkable
class SessionReplayer(Protocol):
    async def open_session(self, request: SessionOpenRequest) -> SessionOpenResult:
        """Reopen a persisted session without live hardware dependencies."""

    async def build_replay_plan(self, session_id: str) -> ReplayPlan:
        """Build replay or reopen inputs from persisted artifacts only."""


@runtime_checkable
class SessionCatalog(Protocol):
    async def load_session(self, session_id: str) -> SessionManifest:
        """Load one authoritative session manifest by id."""

    async def list_sessions(self) -> tuple[SessionSummary, ...]:
        """Return saved sessions for Results and reopen workflows."""

    async def query_artifacts(self, query: ArtifactQuery) -> tuple[ArtifactSummary, ...]:
        """Query indexed artifacts without reverse-engineering storage internals."""

    async def get_session_detail(self, session_id: str) -> SessionDetail:
        """Return a stable persisted session detail view for results and reopen flows."""
