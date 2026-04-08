"""Session persistence and replay boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ircp_contracts import (
    AnalysisArtifact,
    CalibrationReference,
    DeviceConfiguration,
    DeviceStatus,
    ExperimentPreset,
    ExperimentRecipe,
    ExportArtifact,
    ProcessedArtifact,
    RawDataArtifact,
    RunEvent,
    SessionManifest,
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
    raw_artifact_ids: tuple[str, ...]
    processed_artifact_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReplayPlan:
    session_id: str
    raw_artifact_ids: tuple[str, ...]
    processed_artifact_ids: tuple[str, ...]
    analysis_artifact_ids: tuple[str, ...]


@runtime_checkable
class SessionStore(Protocol):
    async def create_session_manifest(
        self,
        recipe: ExperimentRecipe,
        preset: ExperimentPreset | None,
        calibration_references: tuple[CalibrationReference, ...],
        device_config_snapshot: tuple[DeviceConfiguration, ...],
        device_status_snapshot: tuple[DeviceStatus, ...],
    ) -> SessionManifest:
        """Create the authoritative session record before run completion."""

    async def append_event(self, session_id: str, event: RunEvent) -> SessionManifest:
        """Persist one run event onto the session timeline."""

    async def register_raw_artifact(self, session_id: str, artifact: RawDataArtifact) -> SessionManifest:
        """Register a raw artifact without letting the UI own the write path."""

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
        """Build the replay or session-reopen inputs from persisted artifacts only."""
