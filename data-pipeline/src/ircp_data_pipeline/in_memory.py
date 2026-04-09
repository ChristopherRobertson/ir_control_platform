"""In-memory session persistence for the Phase 3B simulator workflows."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from ircp_contracts import (
    AnalysisArtifact,
    CONTRACT_VERSION,
    CalibrationReference,
    DeviceConfiguration,
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
    SessionManifest,
    SessionStatus,
    TimeToWavenumberMapping,
    TimingMarker,
    TimingSummary,
)

from .boundaries import (
    ReplayPlan,
    SessionCatalog,
    SessionOpenRequest,
    SessionOpenResult,
    SessionReplayer,
    SessionStore,
    SessionSummary,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InMemorySessionStore(SessionStore, SessionReplayer, SessionCatalog):
    """Authoritative session store for the Phase 3B simulator slice."""

    def __init__(self, initial_manifests: tuple[SessionManifest, ...] = ()) -> None:
        self._manifests = {manifest.session_id: manifest for manifest in initial_manifests}
        self._counter = len(self._manifests)

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
    ) -> SessionManifest:
        self._counter += 1
        now = _utc_now()
        session_id = f"session-{self._counter:03d}"
        manifest = SessionManifest(
            session_id=session_id,
            version=CONTRACT_VERSION,
            created_at=now,
            updated_at=now,
            status=SessionStatus.PLANNED,
            recipe_snapshot=recipe,
            device_config_snapshot=device_config_snapshot,
            calibration_references=calibration_references,
            raw_artifacts=(),
            event_timeline=(),
            processing_outputs=(),
            analysis_outputs=(),
            export_artifacts=(),
            timing_summary=timing_summary,
            pump_probe_summary=pump_probe_summary,
            selected_markers=tuple(marker.value for marker in selected_markers),
            mux_route_snapshot=mux_route_snapshot,
            mux_summary=mux_summary,
            pico_capture_snapshot=pico_capture_snapshot,
            pico_summary=pico_summary,
            time_to_wavenumber_mapping=time_to_wavenumber_mapping,
            preset_snapshot=preset,
            device_status_snapshot=device_status_snapshot,
        )
        self._manifests[session_id] = manifest
        return manifest

    async def update_device_snapshots(
        self,
        session_id: str,
        *,
        device_config_snapshot: tuple[DeviceConfiguration, ...] | None = None,
        device_status_snapshot: tuple[DeviceStatus, ...] | None = None,
    ) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            device_config_snapshot=device_config_snapshot or manifest.device_config_snapshot,
            device_status_snapshot=device_status_snapshot or manifest.device_status_snapshot,
        )
        self._manifests[session_id] = updated
        return updated

    async def append_event(self, session_id: str, event: RunEvent) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            event_timeline=(*manifest.event_timeline, event),
        )
        self._manifests[session_id] = updated
        return updated

    async def update_session_status(self, session_id: str, status: SessionStatus) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            status=status,
        )
        self._manifests[session_id] = updated
        return updated

    async def register_raw_artifact(self, session_id: str, artifact: RawDataArtifact) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            raw_artifacts=(*manifest.raw_artifacts, artifact),
        )
        self._manifests[session_id] = updated
        return updated

    async def register_processed_artifact(
        self,
        session_id: str,
        artifact: ProcessedArtifact,
    ) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            processing_outputs=(*manifest.processing_outputs, artifact),
        )
        self._manifests[session_id] = updated
        return updated

    async def register_analysis_artifact(
        self,
        session_id: str,
        artifact: AnalysisArtifact,
    ) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            analysis_outputs=(*manifest.analysis_outputs, artifact),
        )
        self._manifests[session_id] = updated
        return updated

    async def register_export_artifact(self, session_id: str, artifact: ExportArtifact) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            export_artifacts=(*manifest.export_artifacts, artifact),
        )
        self._manifests[session_id] = updated
        return updated

    async def open_session(self, request: SessionOpenRequest) -> SessionOpenResult:
        manifest = self._require_manifest(request.session_id)
        primary = manifest.primary_raw_artifacts()
        secondary = manifest.secondary_monitor_artifacts()
        return SessionOpenResult(
            manifest=manifest,
            replay_ready=bool(primary),
            primary_raw_artifact_ids=tuple(artifact.artifact_id for artifact in primary),
            secondary_monitor_artifact_ids=tuple(artifact.artifact_id for artifact in secondary),
            processed_artifact_ids=tuple(
                artifact.artifact_id for artifact in manifest.processing_outputs
            ),
        )

    async def build_replay_plan(self, session_id: str) -> ReplayPlan:
        manifest = self._require_manifest(session_id)
        return ReplayPlan(
            session_id=session_id,
            primary_raw_artifact_ids=tuple(
                artifact.artifact_id for artifact in manifest.primary_raw_artifacts()
            ),
            secondary_monitor_artifact_ids=tuple(
                artifact.artifact_id for artifact in manifest.secondary_monitor_artifacts()
            ),
            processed_artifact_ids=tuple(
                artifact.artifact_id for artifact in manifest.processing_outputs
            ),
            analysis_artifact_ids=tuple(
                artifact.artifact_id for artifact in manifest.analysis_outputs
            ),
        )

    async def list_sessions(self) -> tuple[SessionSummary, ...]:
        ordered = sorted(
            self._manifests.values(),
            key=lambda manifest: (manifest.updated_at, manifest.created_at, manifest.session_id),
            reverse=True,
        )
        return tuple(
            SessionSummary(
                session_id=manifest.session_id,
                recipe_id=manifest.recipe_snapshot.recipe_id,
                recipe_title=manifest.recipe_snapshot.title,
                created_at=manifest.created_at,
                updated_at=manifest.updated_at,
                status=manifest.status,
                primary_raw_artifact_count=len(manifest.primary_raw_artifacts()),
                secondary_monitor_artifact_count=len(manifest.secondary_monitor_artifacts()),
                processed_artifact_count=len(manifest.processing_outputs),
                analysis_artifact_count=len(manifest.analysis_outputs),
                export_artifact_count=len(manifest.export_artifacts),
            )
            for manifest in ordered
        )

    def _require_manifest(self, session_id: str) -> SessionManifest:
        try:
            return self._manifests[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session id: {session_id}") from exc
