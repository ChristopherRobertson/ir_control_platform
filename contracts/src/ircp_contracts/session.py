"""Session and artifact provenance contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from .common import (
    ArtifactKind,
    ArtifactSourceRole,
    CONTRACT_VERSION,
    ConfigurationScalar,
    DeviceKind,
    SessionStatus,
)
from .device import DeviceConfiguration, DeviceStatus
from .experiment import (
    CalibrationReference,
    ExperimentPreset,
    ExperimentRecipe,
    MuxRouteSelection,
    PicoSecondaryCapture,
    TimeToWavenumberMapping,
)
from .run import (
    MuxRoutingSummary,
    PicoCaptureSummary,
    PumpProbeAcquisitionSummary,
    RunOutcomeSummary,
    RunEvent,
    TimingSummary,
)


@dataclass(frozen=True)
class SessionStatusTimestamp:
    status: SessionStatus
    recorded_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class RawDataArtifact:
    artifact_id: str
    session_id: str
    device_kind: DeviceKind
    stream_name: str
    relative_path: str
    created_at: datetime
    version: str = CONTRACT_VERSION
    content_type: str = "text/plain"
    record_count: int | None = None
    checksum_sha256: str | None = None
    source_role: ArtifactSourceRole = ArtifactSourceRole.PRIMARY_RAW
    mux_output_target: str | None = None
    related_marker: str | None = None
    registered_by_event_id: str | None = None
    metadata: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
    artifact_kind: ArtifactKind = ArtifactKind.RAW


@dataclass(frozen=True)
class ProcessedArtifact:
    artifact_id: str
    session_id: str
    relative_path: str
    processing_recipe_id: str
    processing_recipe_version: str
    source_raw_artifact_ids: tuple[str, ...]
    created_at: datetime
    version: str = CONTRACT_VERSION
    content_type: str = "text/plain"
    registered_by_event_id: str | None = None
    metadata: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
    artifact_kind: ArtifactKind = ArtifactKind.PROCESSED

    def __post_init__(self) -> None:
        if not self.source_raw_artifact_ids:
            raise ValueError("Processed artifacts must cite raw input artifact ids.")


@dataclass(frozen=True)
class AnalysisArtifact:
    artifact_id: str
    session_id: str
    relative_path: str
    analysis_recipe_id: str
    analysis_recipe_version: str
    created_at: datetime
    source_processed_artifact_ids: tuple[str, ...] = ()
    source_raw_artifact_ids: tuple[str, ...] = ()
    version: str = CONTRACT_VERSION
    content_type: str = "text/plain"
    registered_by_event_id: str | None = None
    metadata: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
    artifact_kind: ArtifactKind = ArtifactKind.ANALYSIS

    def __post_init__(self) -> None:
        if not self.source_processed_artifact_ids and not self.source_raw_artifact_ids:
            raise ValueError("Analysis artifacts must cite processed or raw inputs.")


@dataclass(frozen=True)
class ExportArtifact:
    artifact_id: str
    session_id: str
    relative_path: str
    format_name: str
    export_name: str
    source_artifact_ids: tuple[str, ...]
    created_at: datetime
    version: str = CONTRACT_VERSION
    content_type: str = "application/octet-stream"
    registered_by_event_id: str | None = None
    metadata: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
    artifact_kind: ArtifactKind = ArtifactKind.EXPORT

    def __post_init__(self) -> None:
        if not self.source_artifact_ids:
            raise ValueError("Export artifacts must cite their source artifacts.")


@dataclass(frozen=True)
class SessionManifest:
    session_id: str
    version: str
    created_at: datetime
    updated_at: datetime
    status: SessionStatus
    recipe_snapshot: ExperimentRecipe
    device_config_snapshot: tuple[DeviceConfiguration, ...]
    calibration_references: tuple[CalibrationReference, ...]
    raw_artifacts: tuple[RawDataArtifact, ...]
    event_timeline: tuple[RunEvent, ...]
    processing_outputs: tuple[ProcessedArtifact, ...]
    analysis_outputs: tuple[AnalysisArtifact, ...]
    export_artifacts: tuple[ExportArtifact, ...]
    timing_summary: TimingSummary
    pump_probe_summary: PumpProbeAcquisitionSummary
    selected_markers: tuple[str, ...]
    mux_route_snapshot: MuxRouteSelection
    mux_summary: MuxRoutingSummary
    pico_capture_snapshot: PicoSecondaryCapture
    pico_summary: PicoCaptureSummary
    time_to_wavenumber_mapping: TimeToWavenumberMapping | None
    preset_snapshot: ExperimentPreset | None = None
    device_status_snapshot: tuple[DeviceStatus, ...] = ()
    status_timestamps: tuple[SessionStatusTimestamp, ...] = ()
    outcome: RunOutcomeSummary = field(default_factory=RunOutcomeSummary)
    reopened_from_session_id: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.updated_at < self.created_at:
            raise ValueError("Session manifest update time cannot precede creation time.")
        errors = self.validate_provenance()
        if errors:
            raise ValueError("; ".join(errors))

    def all_artifact_ids(self) -> tuple[str, ...]:
        return (
            *(artifact.artifact_id for artifact in self.raw_artifacts),
            *(artifact.artifact_id for artifact in self.processing_outputs),
            *(artifact.artifact_id for artifact in self.analysis_outputs),
            *(artifact.artifact_id for artifact in self.export_artifacts),
        )

    def primary_raw_artifacts(self) -> tuple[RawDataArtifact, ...]:
        return tuple(
            artifact for artifact in self.raw_artifacts if artifact.source_role == ArtifactSourceRole.PRIMARY_RAW
        )

    def secondary_monitor_artifacts(self) -> tuple[RawDataArtifact, ...]:
        return tuple(
            artifact
            for artifact in self.raw_artifacts
            if artifact.source_role == ArtifactSourceRole.SECONDARY_MONITOR
        )

    def event_ids(self) -> tuple[str, ...]:
        return tuple(event.event_id for event in self.event_timeline)

    def replay_ready(self) -> bool:
        return bool(self.primary_raw_artifacts())

    def validate_provenance(self) -> tuple[str, ...]:
        errors: list[str] = []
        event_ids = set(self.event_ids())
        raw_ids = {artifact.artifact_id for artifact in self.raw_artifacts}
        processed_ids = {artifact.artifact_id for artifact in self.processing_outputs}
        all_source_ids = raw_ids | processed_ids | {
            artifact.artifact_id for artifact in self.analysis_outputs
        }

        primary_raw = self.primary_raw_artifacts()
        secondary_raw = self.secondary_monitor_artifacts()

        for artifact in self.raw_artifacts:
            if artifact.session_id != self.session_id:
                errors.append(f"Raw artifact {artifact.artifact_id} points to a different session.")
            if artifact.source_role == ArtifactSourceRole.PRIMARY_RAW and artifact.device_kind != DeviceKind.LABONE_HF2LI:
                errors.append(
                    f"Primary raw artifact {artifact.artifact_id} must originate from the HF2LI."
                )
            if (
                artifact.source_role == ArtifactSourceRole.SECONDARY_MONITOR
                and artifact.device_kind != DeviceKind.PICOSCOPE_5244D
            ):
                errors.append(
                    f"Secondary monitor artifact {artifact.artifact_id} must originate from the PicoScope."
                )
            if (
                artifact.registered_by_event_id is not None
                and artifact.registered_by_event_id not in event_ids
            ):
                errors.append(
                    f"Raw artifact {artifact.artifact_id} references missing registration event "
                    f"{artifact.registered_by_event_id}."
                )

        if self.status == SessionStatus.COMPLETED and not primary_raw:
            errors.append("Completed sessions must preserve at least one HF2LI primary raw artifact.")
        if secondary_raw and not primary_raw and self.status == SessionStatus.COMPLETED:
            errors.append("Secondary monitor artifacts cannot be the only raw authority in a completed session.")

        for artifact in self.processing_outputs:
            if artifact.session_id != self.session_id:
                errors.append(f"Processed artifact {artifact.artifact_id} points to a different session.")
            missing = [item for item in artifact.source_raw_artifact_ids if item not in raw_ids]
            if missing:
                errors.append(
                    f"Processed artifact {artifact.artifact_id} references missing raw inputs: {missing}."
                )
            if (
                artifact.registered_by_event_id is not None
                and artifact.registered_by_event_id not in event_ids
            ):
                errors.append(
                    f"Processed artifact {artifact.artifact_id} references missing registration event "
                    f"{artifact.registered_by_event_id}."
                )

        for artifact in self.analysis_outputs:
            if artifact.session_id != self.session_id:
                errors.append(f"Analysis artifact {artifact.artifact_id} points to a different session.")
            missing_processed = [
                item for item in artifact.source_processed_artifact_ids if item not in processed_ids
            ]
            missing_raw = [item for item in artifact.source_raw_artifact_ids if item not in raw_ids]
            if missing_processed:
                errors.append(
                    f"Analysis artifact {artifact.artifact_id} references missing processed inputs: {missing_processed}."
                )
            if missing_raw:
                errors.append(
                    f"Analysis artifact {artifact.artifact_id} references missing raw inputs: {missing_raw}."
                )
            if (
                artifact.registered_by_event_id is not None
                and artifact.registered_by_event_id not in event_ids
            ):
                errors.append(
                    f"Analysis artifact {artifact.artifact_id} references missing registration event "
                    f"{artifact.registered_by_event_id}."
                )

        for artifact in self.export_artifacts:
            if artifact.session_id != self.session_id:
                errors.append(f"Export artifact {artifact.artifact_id} points to a different session.")
            missing = [item for item in artifact.source_artifact_ids if item not in all_source_ids]
            if missing:
                errors.append(
                    f"Export artifact {artifact.artifact_id} references missing source artifacts: {missing}."
                )
            if (
                artifact.registered_by_event_id is not None
                and artifact.registered_by_event_id not in event_ids
            ):
                errors.append(
                    f"Export artifact {artifact.artifact_id} references missing registration event "
                    f"{artifact.registered_by_event_id}."
                )

        if not self.status_timestamps:
            errors.append("Session manifests must record status timestamps from creation onward.")
        else:
            previous_time = self.created_at
            for timestamp in self.status_timestamps:
                if timestamp.recorded_at < previous_time:
                    errors.append("Session status timestamps must be chronological.")
                    break
                previous_time = timestamp.recorded_at
            if self.status_timestamps[-1].status != self.status:
                errors.append("The latest recorded session status must match the manifest status.")

        if self.outcome.final_event_id is not None and self.outcome.final_event_id not in event_ids:
            errors.append(
                f"Session outcome references missing final event {self.outcome.final_event_id}."
            )
        if self.reopened_from_session_id == self.session_id:
            errors.append("A session cannot reopen from itself.")
        if self.outcome.started_at is not None and self.outcome.started_at < self.created_at:
            errors.append("Session outcome start time cannot precede session creation.")
        if self.status == SessionStatus.ACTIVE and self.outcome.ended_at is not None:
            errors.append("Active sessions cannot already have an end time.")
        if self.status == SessionStatus.COMPLETED:
            if self.outcome.ended_at is None:
                errors.append("Completed sessions must record when the run ended.")
            if self.outcome.failure_reason is not None:
                errors.append("Completed sessions must not carry a failure reason.")
            if self.outcome.latest_fault is not None:
                errors.append("Completed sessions must not carry a terminal device fault.")
        if self.status == SessionStatus.FAULTED:
            if self.outcome.ended_at is None:
                errors.append("Faulted sessions must record when the run ended.")
            if self.outcome.failure_reason is None:
                errors.append("Faulted sessions must record an explicit failure reason.")
        if self.status == SessionStatus.ABORTED:
            if self.outcome.ended_at is None:
                errors.append("Aborted sessions must record when the run ended.")
            if self.outcome.failure_reason is None:
                errors.append("Aborted sessions must record an explicit abort reason.")

        return tuple(errors)
