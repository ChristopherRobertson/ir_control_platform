"""Shared enums and scalar aliases for Phase 2 contracts."""

from __future__ import annotations

from enum import Enum
from typing import Union

CONTRACT_VERSION = "phase2.v1"
ConfigurationScalar = Union[bool, int, float, str]


class DeviceKind(str, Enum):
    MIRCAT = "mircat"
    LABONE_HF2LI = "labone_hf2li"
    PICOSCOPE = "picoscope"
    T660 = "t660"
    T661 = "t661"
    PICOVNA = "picovna"


class ConfigurationValueKind(str, Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    ENUM = "enum"


class DeviceLifecycleState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    CONFIGURED = "configured"
    RUNNING = "running"
    FAULTED = "faulted"


class FaultSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FaultCategory(str, Enum):
    CONNECTION = "connection"
    READINESS = "readiness"
    SAFETY_INTERLOCK = "safety_interlock"
    VENDOR = "vendor"
    VALIDATION = "validation"
    ACQUISITION = "acquisition"
    PERSISTENCE = "persistence"
    PROCESSING = "processing"
    ANALYSIS = "analysis"
    UNKNOWN = "unknown"


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ReadinessState(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


class RunPhase(str, Enum):
    DRAFT = "draft"
    PREFLIGHT = "preflight"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAULTED = "faulted"
    ABORTED = "aborted"
    REOPENING = "reopening"


class RunEventType(str, Enum):
    PREFLIGHT_COMPLETED = "preflight_completed"
    SESSION_CREATED = "session_created"
    RUN_STARTED = "run_started"
    DEVICE_STATUS_CHANGED = "device_status_changed"
    DEVICE_FAULT_REPORTED = "device_fault_reported"
    RAW_ARTIFACT_REGISTERED = "raw_artifact_registered"
    PROCESSED_ARTIFACT_REGISTERED = "processed_artifact_registered"
    ANALYSIS_ARTIFACT_REGISTERED = "analysis_artifact_registered"
    EXPORT_ARTIFACT_REGISTERED = "export_artifact_registered"
    RUN_COMPLETED = "run_completed"
    RUN_ABORTED = "run_aborted"
    SESSION_REOPENED = "session_reopened"


class RunCommandType(str, Enum):
    PREFLIGHT = "preflight"
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    ABORT = "abort"
    REOPEN_SESSION = "reopen_session"


class RunFailureReason(str, Enum):
    VALIDATION_FAILED = "validation_failed"
    DEVICE_FAULT = "device_fault"
    PERSISTENCE_FAILED = "persistence_failed"
    OPERATOR_ABORT = "operator_abort"
    SESSION_REOPEN_FAILED = "session_reopen_failed"
    REPLAY_UNAVAILABLE = "replay_unavailable"


class ArtifactKind(str, Enum):
    RAW = "raw"
    PROCESSED = "processed"
    ANALYSIS = "analysis"
    EXPORT = "export"


class SessionStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAULTED = "faulted"
    ABORTED = "aborted"
    REPLAY = "replay"
