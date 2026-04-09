"""Shared enums and scalar aliases for Phase 3B contracts."""

from __future__ import annotations

from enum import Enum
from typing import Union

CONTRACT_VERSION = "phase3b.v1"
ConfigurationScalar = Union[bool, int, float, str]


class DeviceKind(str, Enum):
    MIRCAT = "mircat"
    LABONE_HF2LI = "labone_hf2li"
    T660_TIMING = "t660_timing"
    PICOSCOPE_5244D = "picoscope_5244d"
    ARDUINO_MUX = "arduino_mux"
    PICOVNA = "picovna"


class TimingControllerRole(str, Enum):
    MASTER = "master"
    SLAVE = "slave"


class TimingControllerIdentity(str, Enum):
    T660_2_MASTER = "t660-2-master"
    T660_1_SLAVE = "t660-1-slave"


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
    DEVICE_CONFIGURATION_APPLIED = "device_configuration_applied"
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


class ArtifactSourceRole(str, Enum):
    PRIMARY_RAW = "primary_raw"
    SECONDARY_MONITOR = "secondary_monitor"


class SessionStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAULTED = "faulted"
    ABORTED = "aborted"
    REPLAY = "replay"


class ProbeTimingMode(str, Enum):
    CONTINUOUS_PROBE = "continuous_probe"
    SYNCHRONIZED_PROBE = "synchronized_probe"


class AcquisitionTimingMode(str, Enum):
    CONTINUOUS = "continuous"
    DELAYED = "delayed"
    AROUND_SELECTED_SIGNAL = "around_selected_signal"


class TimingMarker(str, Enum):
    PUMP_FIRE_COMMAND = "pump_fire_command"
    PUMP_QSWITCH_COMMAND = "pump_qswitch_command"
    MASTER_TO_SLAVE_TRIGGER = "master_to_slave_trigger"
    PROBE_TRIGGER = "probe_trigger"
    PROBE_PROCESS_TRIGGER = "probe_process_trigger"
    PROBE_ENABLE_WINDOW = "probe_enable_window"
    SLAVE_TIMING_MARKER = "slave_timing_marker"
    NDYAG_FIXED_SYNC = "ndyag_fixed_sync"
    NDYAG_VARIABLE_SYNC = "ndyag_variable_sync"
    NDYAG_FLASHLAMP_SYNC = "ndyag_flashlamp_sync"
    MIRCAT_TRIGGER_OUT = "mircat_trigger_out"
    MIRCAT_SCAN_DIRECTION = "mircat_scan_direction"
    MIRCAT_TUNED_OR_SCAN_FIRING = "mircat_tuned_or_scan_firing"
    MIRCAT_WAVELENGTH_TRIGGER = "mircat_wavelength_trigger"


class MuxSignalDomain(str, Enum):
    ANALOG_MONITOR = "analog_monitor"
    DIGITAL_MARKER = "digital_marker"


class MuxOutputTarget(str, Enum):
    PICO_CHANNEL_A = "pico_channel_a"
    PICO_CHANNEL_B = "pico_channel_b"
    PICO_EXTERNAL_TRIGGER = "pico_external_trigger"


class AnalogMonitorRoute(str, Enum):
    HF2_AUX_X = "hf2_aux_x"
    HF2_AUX_Y = "hf2_aux_y"
    HF2_AUX_R = "hf2_aux_r"
    HF2_AUX_THETA = "hf2_aux_theta"


class PicoMonitoringMode(str, Enum):
    DISABLED = "disabled"
    MONITOR_ONLY = "monitor_only"
    RECORD_ONLY = "record_only"
    MONITOR_AND_RECORD = "monitor_and_record"
