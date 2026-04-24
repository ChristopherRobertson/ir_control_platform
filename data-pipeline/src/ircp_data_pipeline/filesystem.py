"""Filesystem-backed session persistence for restart-safe Phase 4 workflows."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import fields, is_dataclass, replace
from datetime import datetime
from enum import Enum
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints

from ircp_contracts import RawDataArtifact, RunEvent, SessionManifest

from .in_memory import InMemorySessionStore, _next_session_counter


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
    if isinstance(value, MappingABC):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    return value


def _deserialize_dataclass(cls: type[Any], payload: Mapping[str, object]) -> Any:
    type_hints = get_type_hints(cls)
    return cls(
        **{
            field.name: _deserialize_value(payload[field.name], type_hints[field.name])
            for field in fields(cls)
            if field.name in payload
        }
    )


def _deserialize_value(value: object, annotation: object) -> object:
    if annotation is Any:
        return value

    origin = get_origin(annotation)
    if origin in {Union, types.UnionType}:
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
        raise TypeError(f"Unable to deserialize value {value!r} as {annotation!r}.")

    if origin in {tuple, list}:
        if not isinstance(value, list):
            raise TypeError(f"Expected list-like JSON payload for {annotation!r}.")
        args = get_args(annotation)
        if not args:
            return tuple(value) if origin is tuple else list(value)
        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                return tuple(_deserialize_value(item, args[0]) for item in value)
            return tuple(_deserialize_value(item, item_type) for item, item_type in zip(value, args, strict=True))
        return [_deserialize_value(item, args[0]) for item in value]

    if origin in {dict, Mapping, MappingABC}:
        if not isinstance(value, dict):
            raise TypeError(f"Expected object-like JSON payload for {annotation!r}.")
        key_type, value_type = get_args(annotation) or (str, Any)
        return {
            _deserialize_value(key, key_type): _deserialize_value(item, value_type)
            for key, item in value.items()
        }

    if isinstance(annotation, type):
        if issubclass(annotation, Enum):
            return annotation(value)
        if annotation is datetime:
            if not isinstance(value, str):
                raise TypeError("Datetimes must be stored as ISO 8601 strings.")
            return datetime.fromisoformat(value)
        if is_dataclass(annotation):
            if not isinstance(value, dict):
                raise TypeError(f"Expected object-like JSON payload for {annotation.__name__}.")
            return _deserialize_dataclass(annotation, value)
        if annotation in {str, int, float, bool}:
            if annotation is float and isinstance(value, int):
                return float(value)
            if not isinstance(value, annotation):
                raise TypeError(f"Expected {annotation.__name__}, got {type(value).__name__}.")
            return value

    return value


def _write_text_atomic(path: Path, payload_text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(payload_text)
        temp_name = handle.name
    os.replace(temp_name, path)


def _require_pyarrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except (ModuleNotFoundError, AttributeError) as exc:
        repo_root = Path(__file__).resolve().parents[3]
        for site_packages in (
            repo_root / "ircpenv" / "Lib" / "site-packages",
            repo_root / "ircpenv" / "lib" / "site-packages",
        ):
            if site_packages.is_dir() and str(site_packages) not in sys.path:
                sys.path.insert(0, str(site_packages))
                try:
                    import pyarrow as pa
                    import pyarrow.parquet as pq
                except (ModuleNotFoundError, AttributeError):
                    continue
                return pa, pq
        raise ModuleNotFoundError(
            "pyarrow is required for Parquet-backed raw artifact persistence."
        ) from exc
    return pa, pq


def _write_parquet_atomic(path: Path, rows: tuple[dict[str, object], ...]) -> None:
    if not rows:
        raise ValueError("Parquet-backed raw artifacts must contain at least one row.")
    pa, pq = _require_pyarrow()
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(list(rows))
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_name = handle.name
    try:
        pq.write_table(table, temp_name, compression="zstd")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class FilesystemSessionStore(InMemorySessionStore):
    """Durable local session store backed by per-session files and Parquet raw payloads."""

    def __init__(
        self,
        root: Path,
        *,
        initial_manifests: tuple[SessionManifest, ...] = (),
        initial_raw_artifact_payloads: Mapping[str, tuple[dict[str, object], ...]] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._sessions_root = self._root / "sessions"
        self._sessions_root.mkdir(parents=True, exist_ok=True)
        _require_pyarrow()
        super().__init__(initial_manifests=())
        self._reload_from_disk()
        self._seed_initial_state(
            initial_manifests=initial_manifests,
            initial_raw_artifact_payloads=initial_raw_artifact_payloads or {},
        )

    async def create_session_manifest(self, *args, **kwargs) -> SessionManifest:
        self._reload_from_disk()
        return await super().create_session_manifest(*args, **kwargs)

    async def delete_session(self, session_id: str) -> None:
        self._reload_from_disk()
        await super().delete_session(session_id)
        session_dir = self._session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
        self._reload_from_disk()

    async def load_session(self, session_id: str) -> SessionManifest:
        self._reload_from_disk()
        return await super().load_session(session_id)

    async def list_sessions(self) -> tuple:
        self._reload_from_disk()
        return await super().list_sessions()

    async def query_artifacts(self, query) -> tuple:
        self._reload_from_disk()
        return await super().query_artifacts(query)

    async def get_session_detail(self, session_id: str):
        self._reload_from_disk()
        return await super().get_session_detail(session_id)

    async def open_session(self, request):
        self._reload_from_disk()
        return await super().open_session(request)

    async def build_replay_plan(self, session_id: str):
        self._reload_from_disk()
        return await super().build_replay_plan(session_id)

    async def register_raw_artifact(self, session_id: str, artifact: RawDataArtifact) -> SessionManifest:
        self._validate_raw_artifact_path(artifact)
        self._require_persisted_payload(artifact)
        return await super().register_raw_artifact(session_id, artifact)

    async def persist_raw_artifact(
        self,
        session_id: str,
        artifact: RawDataArtifact,
        payload_rows: tuple[dict[str, object], ...],
    ) -> SessionManifest:
        self._validate_raw_artifact_path(artifact)
        payload_path = self._resolve_relative_path(artifact.relative_path)
        _write_parquet_atomic(payload_path, payload_rows)
        return await super().register_raw_artifact(session_id, artifact)

    def _store_manifest(self, manifest: SessionManifest) -> SessionManifest:
        self._write_events_file(manifest.session_id, manifest.event_timeline)
        self._write_manifest_file(manifest)
        self._manifests[manifest.session_id] = manifest
        self._counter = max(self._counter, _next_session_counter(self._manifests))
        self._rebuild_indexes()
        return manifest

    def _payload_exists(self, relative_path: str) -> bool:
        return self._resolve_relative_path(relative_path).is_file()

    def _seed_initial_state(
        self,
        *,
        initial_manifests: tuple[SessionManifest, ...],
        initial_raw_artifact_payloads: Mapping[str, tuple[dict[str, object], ...]],
    ) -> None:
        changed = False
        for manifest in initial_manifests:
            manifest_path = self._manifest_file(manifest.session_id)
            events_path = self._events_file(manifest.session_id)
            if not manifest_path.exists():
                self._write_manifest_file(manifest)
                changed = True
            if not events_path.exists():
                self._write_events_file(manifest.session_id, manifest.event_timeline)
                changed = True
            for artifact in manifest.raw_artifacts:
                payload_rows = initial_raw_artifact_payloads.get(artifact.relative_path)
                if payload_rows is None:
                    continue
                self._validate_raw_artifact_path(artifact)
                payload_path = self._resolve_relative_path(artifact.relative_path)
                if not payload_path.exists():
                    _write_parquet_atomic(payload_path, payload_rows)
                    changed = True
        if changed:
            self._reload_from_disk()

    def _reload_from_disk(self) -> None:
        manifests = tuple(
            self._load_session_bundle(manifest_path)
            for manifest_path in sorted(self._sessions_root.glob("*/manifest.json"))
        )
        self._manifests = {manifest.session_id: manifest for manifest in manifests}
        self._counter = _next_session_counter(self._manifests)
        self._rebuild_indexes()

    def _load_session_bundle(self, manifest_path: Path) -> SessionManifest:
        manifest = self._load_manifest_file(manifest_path)
        events = self._load_events_file(manifest.session_id)
        if events:
            manifest = replace(manifest, event_timeline=events)
        return manifest

    def _write_manifest_file(self, manifest: SessionManifest) -> None:
        manifest_text = json.dumps(_serialize_value(manifest), indent=2) + "\n"
        _write_text_atomic(self._manifest_file(manifest.session_id), manifest_text)

    def _write_events_file(self, session_id: str, events: tuple[RunEvent, ...]) -> None:
        payload_text = "".join(json.dumps(_serialize_value(event)) + "\n" for event in events)
        _write_text_atomic(self._events_file(session_id), payload_text)

    def _load_manifest_file(self, manifest_path: Path) -> SessionManifest:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError(f"Manifest payload must be a JSON object: {manifest_path}")
        return _deserialize_dataclass(SessionManifest, payload)

    def _load_events_file(self, session_id: str) -> tuple[RunEvent, ...]:
        events_path = self._events_file(session_id)
        if not events_path.exists():
            return ()
        events: list[RunEvent] = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise TypeError(f"Event payload must be a JSON object: {events_path}")
            events.append(_deserialize_dataclass(RunEvent, payload))
        return tuple(events)

    def _session_dir(self, session_id: str) -> Path:
        return self._sessions_root / session_id

    def _manifest_file(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "manifest.json"

    def _events_file(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "events.jsonl"

    def _require_persisted_payload(self, artifact: RawDataArtifact) -> None:
        payload_path = self._resolve_relative_path(artifact.relative_path)
        if not payload_path.exists():
            raise FileNotFoundError(
                f"Missing persisted raw payload for artifact {artifact.artifact_id}: {artifact.relative_path}"
            )

    def _validate_raw_artifact_path(self, artifact: RawDataArtifact) -> None:
        payload_path = Path(artifact.relative_path)
        expected_prefix = ("sessions", artifact.session_id, "artifacts", "raw")
        if payload_path.parts[:4] != expected_prefix:
            raise ValueError(
                "Raw artifact paths must stay inside the session-centric raw artifact tree: "
                f"{artifact.relative_path}"
            )
        if payload_path.suffix != ".parquet":
            raise ValueError(f"Raw artifact payloads must use Parquet files: {artifact.relative_path}")

    def _resolve_relative_path(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ValueError(f"Artifact paths must stay relative to the store root: {relative_path}")
        resolved = (self._root / candidate).resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise ValueError(f"Artifact path escapes the store root: {relative_path}") from exc
        return resolved
