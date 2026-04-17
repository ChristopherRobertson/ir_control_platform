"""In-memory session persistence for the supported-v1 simulator workflows."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import re
from typing import Mapping

from ircp_contracts import (
    AnalysisArtifact,
    ArtifactKind,
    ArtifactSourceRole,
    CONTRACT_VERSION,
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
    RunOutcomeSummary,
    SessionManifest,
    SessionStatus,
    SessionStatusTimestamp,
    TimeToWavenumberMapping,
    TimingMarker,
    TimingSummary,
)

from .boundaries import (
    ArtifactQuery,
    ArtifactSummary,
    ReplayPlan,
    SessionCatalog,
    SessionDetail,
    SessionOpenRequest,
    SessionOpenResult,
    SessionReplayer,
    SessionStore,
    SessionSummary,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _next_session_counter(manifests: Mapping[str, SessionManifest]) -> int:
    highest = 0
    for session_id in manifests:
        match = re.fullmatch(r"session-(\d+)", session_id)
        if match is not None:
            highest = max(highest, int(match.group(1)))
    return highest


class InMemorySessionStore(SessionStore, SessionReplayer, SessionCatalog):
    """Authoritative session store for the supported-v1 simulator slice."""

    def __init__(
        self,
        initial_manifests: tuple[SessionManifest, ...] = (),
        initial_raw_artifact_payloads: Mapping[str, tuple[dict[str, object], ...]] | None = None,
    ) -> None:
        self._manifests = {manifest.session_id: manifest for manifest in initial_manifests}
        self._counter = _next_session_counter(self._manifests)
        self._raw_payloads_by_path = dict(initial_raw_artifact_payloads or {})
        self._artifacts_by_id: dict[str, ArtifactSummary] = {}
        self._artifact_ids_by_session: dict[str, tuple[str, ...]] = {}
        self._artifact_ids_by_kind: dict[ArtifactKind, tuple[str, ...]] = {}
        self._artifact_ids_by_source_role: dict[ArtifactSourceRole, tuple[str, ...]] = {}
        self._rebuild_indexes()

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
            status_timestamps=(
                SessionStatusTimestamp(
                    status=SessionStatus.PLANNED,
                    recorded_at=now,
                    note="Session manifest created before the run became live.",
                ),
            ),
            outcome=RunOutcomeSummary(),
            notes=notes,
        )
        return self._store_manifest(manifest)

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
        return self._store_manifest(updated)

    async def append_event(self, session_id: str, event: RunEvent) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            event_timeline=(*manifest.event_timeline, event),
        )
        return self._store_manifest(updated)

    async def update_session_status(self, session_id: str, status: SessionStatus) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        recorded_at = _utc_now()
        status_timestamps = (*manifest.status_timestamps, SessionStatusTimestamp(status=status, recorded_at=recorded_at))
        outcome = manifest.outcome
        if status == SessionStatus.ACTIVE and outcome.started_at is None:
            outcome = replace(outcome, started_at=recorded_at)
        updated = replace(
            manifest,
            updated_at=max(recorded_at, manifest.updated_at),
            status=status,
            status_timestamps=status_timestamps,
            outcome=outcome,
        )
        return self._store_manifest(updated)

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
        if status not in {SessionStatus.COMPLETED, SessionStatus.FAULTED, SessionStatus.ABORTED}:
            raise ValueError("Only terminal session states may be finalized explicitly.")
        manifest = self._require_manifest(session_id)
        recorded_at = ended_at or _utc_now()
        outcome = replace(
            manifest.outcome,
            ended_at=recorded_at,
            failure_reason=failure_reason,
            latest_fault=latest_fault,
            final_event_id=final_event.event_id if final_event is not None else manifest.outcome.final_event_id,
        )
        updated = replace(
            manifest,
            updated_at=max(recorded_at, manifest.updated_at),
            status=status,
            status_timestamps=(
                *manifest.status_timestamps,
                SessionStatusTimestamp(status=status, recorded_at=recorded_at, note=note),
            ),
            outcome=outcome,
        )
        return self._store_manifest(updated)

    async def register_raw_artifact(self, session_id: str, artifact: RawDataArtifact) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            raw_artifacts=(*manifest.raw_artifacts, artifact),
        )
        return self._store_manifest(updated)

    async def persist_raw_artifact(
        self,
        session_id: str,
        artifact: RawDataArtifact,
        payload_rows: tuple[dict[str, object], ...],
    ) -> SessionManifest:
        self._raw_payloads_by_path[artifact.relative_path] = payload_rows
        return await self.register_raw_artifact(session_id, artifact)

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
        return self._store_manifest(updated)

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
        return self._store_manifest(updated)

    async def register_export_artifact(self, session_id: str, artifact: ExportArtifact) -> SessionManifest:
        manifest = self._require_manifest(session_id)
        updated = replace(
            manifest,
            updated_at=max(_utc_now(), manifest.updated_at),
            export_artifacts=(*manifest.export_artifacts, artifact),
        )
        return self._store_manifest(updated)

    async def open_session(self, request: SessionOpenRequest) -> SessionOpenResult:
        manifest = await self.load_session(request.session_id)
        self._ensure_raw_payloads_available(manifest.raw_artifacts)
        primary = await self.query_artifacts(
            ArtifactQuery(
                session_id=request.session_id,
                artifact_kind=ArtifactKind.RAW,
                source_role=ArtifactSourceRole.PRIMARY_RAW,
            )
        )
        secondary = await self.query_artifacts(
            ArtifactQuery(
                session_id=request.session_id,
                artifact_kind=ArtifactKind.RAW,
                source_role=ArtifactSourceRole.SECONDARY_MONITOR,
            )
        )
        return SessionOpenResult(
            manifest=manifest,
            replay_ready=self._manifest_replay_ready(manifest),
            primary_raw_artifact_ids=tuple(artifact.artifact_id for artifact in primary),
            secondary_monitor_artifact_ids=tuple(artifact.artifact_id for artifact in secondary),
            processed_artifact_ids=tuple(
                artifact.artifact_id for artifact in manifest.processing_outputs
            ),
        )

    async def build_replay_plan(self, session_id: str) -> ReplayPlan:
        manifest = await self.load_session(session_id)
        self._ensure_raw_payloads_available(manifest.raw_artifacts)
        primary = await self.query_artifacts(
            ArtifactQuery(
                session_id=session_id,
                artifact_kind=ArtifactKind.RAW,
                source_role=ArtifactSourceRole.PRIMARY_RAW,
            )
        )
        secondary = await self.query_artifacts(
            ArtifactQuery(
                session_id=session_id,
                artifact_kind=ArtifactKind.RAW,
                source_role=ArtifactSourceRole.SECONDARY_MONITOR,
            )
        )
        processed = await self.query_artifacts(
            ArtifactQuery(session_id=session_id, artifact_kind=ArtifactKind.PROCESSED)
        )
        analysis = await self.query_artifacts(
            ArtifactQuery(session_id=session_id, artifact_kind=ArtifactKind.ANALYSIS)
        )
        return ReplayPlan(
            session_id=session_id,
            primary_raw_artifact_ids=tuple(artifact.artifact_id for artifact in primary),
            secondary_monitor_artifact_ids=tuple(artifact.artifact_id for artifact in secondary),
            processed_artifact_ids=tuple(artifact.artifact_id for artifact in processed),
            analysis_artifact_ids=tuple(artifact.artifact_id for artifact in analysis),
        )

    async def load_session(self, session_id: str) -> SessionManifest:
        return self._require_manifest(session_id)

    async def list_sessions(self) -> tuple[SessionSummary, ...]:
        ordered = sorted(
            self._manifests.values(),
            key=lambda manifest: (manifest.updated_at, manifest.created_at, manifest.session_id),
            reverse=True,
        )
        return tuple(self._build_session_summary(manifest) for manifest in ordered)

    async def query_artifacts(self, query: ArtifactQuery) -> tuple[ArtifactSummary, ...]:
        candidate_ids: set[str] | None = None
        if query.session_id is not None:
            candidate_ids = set(self._artifact_ids_by_session.get(query.session_id, ()))
        if query.artifact_kind is not None:
            kind_ids = set(self._artifact_ids_by_kind.get(query.artifact_kind, ()))
            candidate_ids = kind_ids if candidate_ids is None else candidate_ids & kind_ids
        if query.source_role is not None:
            role_ids = set(self._artifact_ids_by_source_role.get(query.source_role, ()))
            candidate_ids = role_ids if candidate_ids is None else candidate_ids & role_ids
        selected_ids = candidate_ids if candidate_ids is not None else set(self._artifacts_by_id)
        artifacts = [self._artifacts_by_id[artifact_id] for artifact_id in selected_ids]
        artifacts.sort(key=lambda artifact: (artifact.created_at, artifact.artifact_kind.value, artifact.artifact_id))
        return tuple(artifacts)

    async def get_session_detail(self, session_id: str) -> SessionDetail:
        manifest = await self.load_session(session_id)
        all_artifacts = await self.query_artifacts(ArtifactQuery(session_id=session_id))
        summary = self._build_session_summary(manifest)
        return SessionDetail(
            summary=summary,
            manifest=manifest,
            event_timeline=manifest.event_timeline,
            primary_raw_artifacts=tuple(
                artifact
                for artifact in all_artifacts
                if artifact.artifact_kind == ArtifactKind.RAW
                and artifact.source_role == ArtifactSourceRole.PRIMARY_RAW
            ),
            secondary_monitor_artifacts=tuple(
                artifact
                for artifact in all_artifacts
                if artifact.artifact_kind == ArtifactKind.RAW
                and artifact.source_role == ArtifactSourceRole.SECONDARY_MONITOR
            ),
            processed_artifacts=tuple(
                artifact for artifact in all_artifacts if artifact.artifact_kind == ArtifactKind.PROCESSED
            ),
            analysis_artifacts=tuple(
                artifact for artifact in all_artifacts if artifact.artifact_kind == ArtifactKind.ANALYSIS
            ),
            export_artifacts=tuple(
                artifact for artifact in all_artifacts if artifact.artifact_kind == ArtifactKind.EXPORT
            ),
            replay_plan=self._build_replay_plan_from_artifacts(session_id, all_artifacts),
        )

    def _require_manifest(self, session_id: str) -> SessionManifest:
        try:
            return self._manifests[session_id]
        except KeyError as exc:
            raise KeyError(f"Unknown session id: {session_id}") from exc

    def _store_manifest(self, manifest: SessionManifest) -> SessionManifest:
        self._manifests[manifest.session_id] = manifest
        self._rebuild_indexes()
        return manifest

    def _rebuild_indexes(self) -> None:
        artifacts_by_id: dict[str, ArtifactSummary] = {}
        artifact_ids_by_session: dict[str, list[str]] = {}
        artifact_ids_by_kind: dict[ArtifactKind, list[str]] = {}
        artifact_ids_by_source_role: dict[ArtifactSourceRole, list[str]] = {}
        for manifest in self._manifests.values():
            session_ids: list[str] = []
            for artifact in self._artifact_summaries_from_manifest(manifest):
                artifacts_by_id[artifact.artifact_id] = artifact
                session_ids.append(artifact.artifact_id)
                artifact_ids_by_kind.setdefault(artifact.artifact_kind, []).append(artifact.artifact_id)
                if artifact.source_role is not None:
                    artifact_ids_by_source_role.setdefault(artifact.source_role, []).append(artifact.artifact_id)
            artifact_ids_by_session[manifest.session_id] = session_ids
        self._artifacts_by_id = artifacts_by_id
        self._artifact_ids_by_session = {
            session_id: tuple(artifact_ids) for session_id, artifact_ids in artifact_ids_by_session.items()
        }
        self._artifact_ids_by_kind = {
            kind: tuple(artifact_ids) for kind, artifact_ids in artifact_ids_by_kind.items()
        }
        self._artifact_ids_by_source_role = {
            role: tuple(artifact_ids) for role, artifact_ids in artifact_ids_by_source_role.items()
        }

    def _artifact_summaries_from_manifest(self, manifest: SessionManifest) -> tuple[ArtifactSummary, ...]:
        summaries: list[ArtifactSummary] = []
        for artifact in manifest.raw_artifacts:
            summaries.append(
                ArtifactSummary(
                    artifact_id=artifact.artifact_id,
                    session_id=artifact.session_id,
                    artifact_kind=artifact.artifact_kind,
                    relative_path=artifact.relative_path,
                    created_at=artifact.created_at,
                    source_role=artifact.source_role,
                    device_kind=artifact.device_kind,
                    stream_name=artifact.stream_name,
                    content_type=artifact.content_type,
                    record_count=artifact.record_count,
                    mux_output_target=artifact.mux_output_target,
                    related_marker=artifact.related_marker,
                    registered_by_event_id=artifact.registered_by_event_id,
                )
            )
        for artifact in manifest.processing_outputs:
            summaries.append(
                ArtifactSummary(
                    artifact_id=artifact.artifact_id,
                    session_id=artifact.session_id,
                    artifact_kind=artifact.artifact_kind,
                    relative_path=artifact.relative_path,
                    created_at=artifact.created_at,
                    content_type=artifact.content_type,
                    registered_by_event_id=artifact.registered_by_event_id,
                )
            )
        for artifact in manifest.analysis_outputs:
            summaries.append(
                ArtifactSummary(
                    artifact_id=artifact.artifact_id,
                    session_id=artifact.session_id,
                    artifact_kind=artifact.artifact_kind,
                    relative_path=artifact.relative_path,
                    created_at=artifact.created_at,
                    content_type=artifact.content_type,
                    registered_by_event_id=artifact.registered_by_event_id,
                )
            )
        for artifact in manifest.export_artifacts:
            summaries.append(
                ArtifactSummary(
                    artifact_id=artifact.artifact_id,
                    session_id=artifact.session_id,
                    artifact_kind=artifact.artifact_kind,
                    relative_path=artifact.relative_path,
                    created_at=artifact.created_at,
                    content_type=artifact.content_type,
                    registered_by_event_id=artifact.registered_by_event_id,
                )
            )
        return tuple(summaries)

    def _build_replay_plan_from_artifacts(
        self,
        session_id: str,
        artifacts: tuple[ArtifactSummary, ...],
    ) -> ReplayPlan:
        return ReplayPlan(
            session_id=session_id,
            primary_raw_artifact_ids=tuple(
                artifact.artifact_id
                for artifact in artifacts
                if artifact.artifact_kind == ArtifactKind.RAW
                and artifact.source_role == ArtifactSourceRole.PRIMARY_RAW
            ),
            secondary_monitor_artifact_ids=tuple(
                artifact.artifact_id
                for artifact in artifacts
                if artifact.artifact_kind == ArtifactKind.RAW
                and artifact.source_role == ArtifactSourceRole.SECONDARY_MONITOR
            ),
            processed_artifact_ids=tuple(
                artifact.artifact_id for artifact in artifacts if artifact.artifact_kind == ArtifactKind.PROCESSED
            ),
            analysis_artifact_ids=tuple(
                artifact.artifact_id for artifact in artifacts if artifact.artifact_kind == ArtifactKind.ANALYSIS
            ),
        )

    def _manifest_replay_ready(self, manifest: SessionManifest) -> bool:
        return manifest.replay_ready() and all(
            self._payload_exists(artifact.relative_path) for artifact in manifest.raw_artifacts
        )

    def _payload_exists(self, relative_path: str) -> bool:
        return relative_path in self._raw_payloads_by_path

    def _ensure_raw_payloads_available(self, artifacts: tuple[RawDataArtifact, ...]) -> None:
        for artifact in artifacts:
            if not self._payload_exists(artifact.relative_path):
                raise FileNotFoundError(
                    f"Missing persisted raw payload for artifact {artifact.artifact_id}: {artifact.relative_path}"
                )

    def _build_session_summary(self, manifest: SessionManifest) -> SessionSummary:
        last_event_at = manifest.event_timeline[-1].emitted_at if manifest.event_timeline else None
        return SessionSummary(
            session_id=manifest.session_id,
            recipe_id=manifest.recipe_snapshot.recipe_id,
            recipe_title=manifest.recipe_snapshot.title,
            created_at=manifest.created_at,
            updated_at=manifest.updated_at,
            status=manifest.status,
            event_count=len(manifest.event_timeline),
            last_event_at=last_event_at,
            replay_ready=self._manifest_replay_ready(manifest),
            primary_raw_artifact_count=len(manifest.primary_raw_artifacts()),
            secondary_monitor_artifact_count=len(manifest.secondary_monitor_artifacts()),
            processed_artifact_count=len(manifest.processing_outputs),
            analysis_artifact_count=len(manifest.analysis_outputs),
            export_artifact_count=len(manifest.export_artifacts),
            failure_reason=manifest.outcome.failure_reason,
        )
