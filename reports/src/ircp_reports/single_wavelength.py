"""Export helpers for persisted single-wavelength pump-probe runs."""

from __future__ import annotations

import json

from ircp_contracts import ArtifactManifest, ProcessedRunRecord, RawRunRecord, RunRecord, RunSettingsSnapshot, SessionRecord


def metadata_export_bytes(
    *,
    session: SessionRecord,
    run: RunRecord,
    settings_snapshot: RunSettingsSnapshot,
    artifact_manifest: ArtifactManifest,
) -> bytes:
    payload = {
        "session": session,
        "run": run,
        "settings_snapshot": settings_snapshot,
        "artifact_manifest": artifact_manifest,
    }
    return json.dumps(payload, default=_json_default, indent=2).encode("utf-8")


def raw_export_bytes(raw_record: RawRunRecord) -> bytes:
    lines = [
        "time,sample_X,sample_Y,sample_R,sample_Theta,reference_X,reference_Y,reference_R,reference_Theta"
    ]
    for signal in raw_record.signals:
        lines.append(
            ",".join(
                str(value)
                for value in (
                    signal.time_seconds,
                    signal.sample_X,
                    signal.sample_Y,
                    signal.sample_R,
                    signal.sample_Theta,
                    signal.reference_X,
                    signal.reference_Y,
                    signal.reference_R,
                    signal.reference_Theta,
                )
            )
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def processed_export_bytes(processed_record: ProcessedRunRecord) -> bytes:
    payload = {
        "processed_record_id": processed_record.processed_record_id,
        "session_id": processed_record.session_id,
        "run_id": processed_record.run_id,
        "raw_record_id": processed_record.raw_record_id,
        "settings_snapshot_id": processed_record.settings_snapshot_id,
        "signals": processed_record.signals,
    }
    return json.dumps(payload, default=_json_default, indent=2).encode("utf-8")


def _json_default(value: object) -> object:
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    if hasattr(value, "value"):
        return value.value  # type: ignore[no-any-return]
    if hasattr(value, "__dataclass_fields__"):
        return {
            field_name: getattr(value, field_name)
            for field_name in value.__dataclass_fields__  # type: ignore[attr-defined]
        }
    raise TypeError(f"Object is not JSON serializable: {value!r}")
