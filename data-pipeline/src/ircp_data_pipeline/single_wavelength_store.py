"""Session/run-centered persistence for the single-wavelength v1 workflow."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from datetime import datetime
from enum import Enum
import csv
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints

from ircp_contracts import (
    ArtifactManifest,
    ConfigurationScalar,
    PlotMetricFamily,
    ProcessedRunRecord,
    RawRunRecord,
    RawSignalRecord,
    RunHeader,
    RunLifecycleState,
    RunRecord,
    RunSettingsSnapshot,
    SessionRecord,
    utc_now,
)


class PersistedRunLoadError(ValueError):
    """Raised when a persisted single-wavelength record cannot be reloaded."""


def _serialize_value(value: object) -> object:
    if is_dataclass(value):
        return {
            field.name: _serialize_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [_serialize_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    return value


def _deserialize_dataclass(cls: type[Any], payload: Mapping[str, object]) -> Any:
    hints = get_type_hints(cls)
    return cls(
        **{
            field.name: _deserialize_value(payload[field.name], hints[field.name])
            for field in fields(cls)
            if field.name in payload
        }
    )


def _deserialize_value(value: object, annotation: object) -> object:
    if annotation is Any:
        return value
    origin = get_origin(annotation)
    if origin in {Union, getattr(__import__("types"), "UnionType")}:
        args = get_args(annotation)
        if value is None and type(None) in args:
            return None
        for candidate in args:
            if candidate is type(None):
                continue
            try:
                return _deserialize_value(value, candidate)
            except (TypeError, ValueError, KeyError):
                continue
        raise TypeError(f"Cannot deserialize {value!r} as {annotation!r}.")
    if origin in {tuple, list}:
        if not isinstance(value, list):
            raise TypeError(f"Expected list payload for {annotation!r}.")
        args = get_args(annotation)
        if not args:
            return tuple(value) if origin is tuple else list(value)
        item_type = args[0]
        return tuple(_deserialize_value(item, item_type) for item in value)
    if origin in {dict, Mapping}:
        return dict(value) if isinstance(value, Mapping) else value
    if isinstance(annotation, type):
        if issubclass(annotation, Enum):
            return annotation(value)
        if annotation is datetime:
            if not isinstance(value, str):
                raise TypeError("Datetime payloads must be ISO strings.")
            return datetime.fromisoformat(value)
        if is_dataclass(annotation):
            if not isinstance(value, Mapping):
                raise TypeError(f"Expected object payload for {annotation.__name__}.")
            return _deserialize_dataclass(annotation, value)
        if annotation in {str, int, float, bool}:
            if annotation is float and isinstance(value, int):
                return float(value)
            if not isinstance(value, annotation):
                raise TypeError(f"Expected {annotation.__name__}, got {type(value).__name__}.")
    return value


def _write_text_atomic(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(payload)
        temp_name = handle.name
    os.replace(temp_name, path)


class SingleWavelengthRunStore:
    """Durable local store for session/run metadata, snapshots, raw records, and results."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.sessions_root = self.root / "sessions"
        self.sessions_root.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        *,
        session_id: str,
        experiment_type: str,
        session_name: str,
        operator: str,
        sample_id: str,
        sample_notes: str,
        experiment_notes: str,
    ) -> SessionRecord:
        if self._session_path(session_id).exists():
            raise ValueError(f"Session ID already exists: {session_id}")
        now = utc_now()
        record = SessionRecord(
            session_id=session_id,
            experiment_type=experiment_type,
            session_name=session_name,
            operator=operator,
            sample_id=sample_id,
            sample_notes=sample_notes,
            experiment_notes=experiment_notes,
            created_at=now,
            updated_at=now,
        )
        self.save_session(record)
        return record

    def save_session(self, record: SessionRecord) -> SessionRecord:
        updated = replace(record, updated_at=max(utc_now(), record.updated_at))
        self._write_json(self._session_path(updated.session_id), updated)
        return updated

    def load_session(self, session_id: str) -> SessionRecord:
        return self._load_json(self._session_path(session_id), SessionRecord)

    def session_exists(self, session_id: str) -> bool:
        return self._session_path(session_id).exists()

    def list_sessions(self) -> tuple[SessionRecord, ...]:
        records: list[SessionRecord] = []
        for path in sorted(self.sessions_root.glob("*/session.json")):
            records.append(self._load_json(path, SessionRecord))
        return tuple(sorted(records, key=lambda item: item.updated_at, reverse=True))

    def create_run_header(
        self,
        *,
        session_id: str,
        run_id: str,
        run_name: str,
        run_notes: str,
    ) -> RunHeader:
        self.load_session(session_id)
        if self._run_header_path(session_id, run_id).exists():
            raise ValueError(f"Run ID already exists in session {session_id}: {run_id}")
        now = utc_now()
        header = RunHeader(
            run_id=run_id,
            session_id=session_id,
            run_name=run_name,
            run_notes=run_notes,
            created_at=now,
            updated_at=now,
            saved=False,
        )
        self._write_json(self._run_header_path(session_id, run_id), header)
        return header

    def save_run_header(self, header: RunHeader) -> RunHeader:
        self.load_session(header.session_id)
        saved = replace(header, saved=True, updated_at=max(utc_now(), header.updated_at))
        self._write_json(self._run_header_path(saved.session_id, saved.run_id), saved)
        initial_record = RunRecord(
            run_id=saved.run_id,
            session_id=saved.session_id,
            run_name=saved.run_name,
            run_notes=saved.run_notes,
            settings_snapshot=None,
            raw_record_id=None,
            processed_record_id=None,
            started_at=None,
            ended_at=None,
            completion_status=RunLifecycleState.DRAFT,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )
        if not self._run_record_path(saved.session_id, saved.run_id).exists():
            self.save_run_record(initial_record)
        return saved

    def load_run_header(self, session_id: str, run_id: str) -> RunHeader:
        return self._load_json(self._run_header_path(session_id, run_id), RunHeader)

    def list_run_headers(self, session_id: str) -> tuple[RunHeader, ...]:
        headers: list[RunHeader] = []
        for path in sorted((self._session_dir(session_id) / "runs").glob("*/run_header.json")):
            headers.append(self._load_json(path, RunHeader))
        return tuple(sorted(headers, key=lambda item: item.updated_at, reverse=True))

    def save_run_record(self, record: RunRecord) -> RunRecord:
        updated = replace(record, updated_at=max(utc_now(), record.updated_at))
        self._write_json(self._run_record_path(updated.session_id, updated.run_id), updated)
        return updated

    def load_run_record(self, session_id: str, run_id: str) -> RunRecord:
        return self._load_json(self._run_record_path(session_id, run_id), RunRecord)

    def save_settings_snapshot(self, snapshot: RunSettingsSnapshot) -> RunSettingsSnapshot:
        self._write_json(self._settings_snapshot_path(snapshot.session_id, snapshot.run_id), snapshot)
        return snapshot

    def load_settings_snapshot(self, session_id: str, run_id: str) -> RunSettingsSnapshot:
        return self._load_json(self._settings_snapshot_path(session_id, run_id), RunSettingsSnapshot)

    def save_raw_run_record(self, raw_record: RawRunRecord) -> RawRunRecord:
        self._write_json(self._raw_json_path(raw_record.session_id, raw_record.run_id), raw_record)
        self._write_raw_csv(self._raw_csv_path(raw_record.session_id, raw_record.run_id), raw_record.signals)
        return raw_record

    def load_raw_run_record(self, session_id: str, run_id: str) -> RawRunRecord:
        return self._load_json(self._raw_json_path(session_id, run_id), RawRunRecord)

    def save_processed_run_record(self, processed_record: ProcessedRunRecord) -> ProcessedRunRecord:
        self._write_json(self._processed_path(processed_record.session_id, processed_record.run_id), processed_record)
        return processed_record

    def load_processed_run_record(self, session_id: str, run_id: str) -> ProcessedRunRecord:
        return self._load_json(self._processed_path(session_id, run_id), ProcessedRunRecord)

    def save_artifact_manifest(self, manifest: ArtifactManifest) -> ArtifactManifest:
        self._write_json(self._artifact_manifest_path(manifest.session_id, manifest.run_id), manifest)
        return manifest

    def load_artifact_manifest(self, session_id: str, run_id: str) -> ArtifactManifest:
        return self._load_json(self._artifact_manifest_path(session_id, run_id), ArtifactManifest)

    def latest_completed_run(self) -> tuple[SessionRecord, RunRecord] | None:
        candidates: list[tuple[SessionRecord, RunRecord]] = []
        for session in self.list_sessions():
            runs_dir = self._session_dir(session.session_id) / "runs"
            for path in sorted(runs_dir.glob("*/run.json")):
                run = self._load_json(path, RunRecord)
                if run.completion_status == RunLifecycleState.COMPLETED:
                    candidates.append((session, run))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[1].updated_at)

    def relative_path(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.root))

    def _session_dir(self, session_id: str) -> Path:
        return self.sessions_root / session_id

    def _run_dir(self, session_id: str, run_id: str) -> Path:
        return self._session_dir(session_id) / "runs" / run_id

    def _session_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "session.json"

    def _run_header_path(self, session_id: str, run_id: str) -> Path:
        return self._run_dir(session_id, run_id) / "run_header.json"

    def _run_record_path(self, session_id: str, run_id: str) -> Path:
        return self._run_dir(session_id, run_id) / "run.json"

    def _settings_snapshot_path(self, session_id: str, run_id: str) -> Path:
        return self._run_dir(session_id, run_id) / "settings_snapshot.json"

    def _raw_json_path(self, session_id: str, run_id: str) -> Path:
        return self._run_dir(session_id, run_id) / "raw" / "raw_record.json"

    def _raw_csv_path(self, session_id: str, run_id: str) -> Path:
        return self._run_dir(session_id, run_id) / "raw" / "raw_signals.csv"

    def _processed_path(self, session_id: str, run_id: str) -> Path:
        return self._run_dir(session_id, run_id) / "processed" / "processed_record.json"

    def _artifact_manifest_path(self, session_id: str, run_id: str) -> Path:
        return self._run_dir(session_id, run_id) / "artifact_manifest.json"

    def _write_json(self, path: Path, payload: object) -> None:
        _write_text_atomic(path, json.dumps(_serialize_value(payload), indent=2) + "\n")

    def _load_json(self, path: Path, cls: type[Any]) -> Any:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except json.JSONDecodeError as exc:
            raise self._malformed_error(path, cls, str(exc)) from exc
        if not isinstance(payload, Mapping):
            raise self._malformed_error(path, cls, "expected a JSON object")
        try:
            return _deserialize_dataclass(cls, payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise self._malformed_error(path, cls, str(exc)) from exc

    def _malformed_error(self, path: Path, cls: type[Any], detail: str) -> PersistedRunLoadError:
        try:
            location = self.relative_path(path)
        except ValueError:
            location = str(path)
        return PersistedRunLoadError(f"Malformed persisted {cls.__name__} at {location}: {detail}")

    def _write_raw_csv(self, path: Path, signals: tuple[RawSignalRecord, ...]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        field_names = (
            "time",
            "sample_X",
            "sample_Y",
            "sample_R",
            "sample_Theta",
            "reference_X",
            "reference_Y",
            "reference_R",
            "reference_Theta",
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=field_names)
            writer.writeheader()
            for signal in signals:
                writer.writerow(
                    {
                        "time": signal.time_seconds,
                        "sample_X": signal.sample_X,
                        "sample_Y": signal.sample_Y,
                        "sample_R": signal.sample_R,
                        "sample_Theta": signal.sample_Theta,
                        "reference_X": signal.reference_X,
                        "reference_Y": signal.reference_Y,
                        "reference_R": signal.reference_R,
                        "reference_Theta": signal.reference_Theta,
                    }
                )
            temp_name = handle.name
        os.replace(temp_name, path)


def processed_metric_records(
    processed: ProcessedRunRecord,
    metric_family: PlotMetricFamily,
) -> tuple[dict[str, ConfigurationScalar], ...]:
    return tuple(
        {
            "time_seconds": signal.time_seconds,
            "metric_family": metric_family.value,
            "sample": signal.sample,
            "reference": signal.reference,
            "ratio": signal.ratio,
        }
        for signal in processed.signals
        if signal.metric_family == metric_family
    )
