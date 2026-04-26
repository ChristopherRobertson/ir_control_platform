"""Canonical device capability, configuration, status, and fault contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from .common import (
    CONTRACT_VERSION,
    ConfigurationScalar,
    ConfigurationValueKind,
    DeviceKind,
    DeviceLifecycleState,
    FaultCategory,
    FaultSeverity,
    PicoMonitoringMode,
    TimingControllerIdentity,
    TimingControllerRole,
)
from ._deferred_experiment import MuxRouteSelection, PicoSecondaryCapture, TimingEvent, TimingWindow


@dataclass(frozen=True)
class ConfigurationFieldDefinition:
    key: str
    value_kind: ConfigurationValueKind
    required: bool
    description: str
    units: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    allowed_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimingProgramSnapshot:
    device_identity: TimingControllerIdentity
    role: TimingControllerRole
    master_clock_hz: float | None = None
    cycle_period_ns: float | None = None
    trigger_source: str | None = None
    pump_fire_command: TimingEvent | None = None
    pump_qswitch_command: TimingEvent | None = None
    master_to_slave_trigger: TimingEvent | None = None
    probe_trigger: TimingEvent | None = None
    probe_process_trigger: TimingEvent | None = None
    probe_enable_window: TimingWindow | None = None
    slave_timing_marker: TimingEvent | None = None
    pump_shots_before_probe: int | None = None


@dataclass(frozen=True)
class PicoCaptureSnapshot:
    mode: PicoMonitoringMode
    trigger_marker: str | None = None
    capture_window_ns: float | None = None
    sample_interval_ns: float | None = None
    record_inputs: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeviceCapability:
    device_kind: DeviceKind
    model: str
    version: str = CONTRACT_VERSION
    supported_actions: tuple[str, ...] = ()
    configuration_fields: tuple[ConfigurationFieldDefinition, ...] = ()
    stream_components: tuple[str, ...] = ()
    supported_roles: tuple[str, ...] = ()
    supported_route_targets: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeviceConfiguration:
    configuration_id: str
    device_id: str
    device_kind: DeviceKind
    applied_at: datetime
    settings: Mapping[str, ConfigurationScalar]
    version: str = CONTRACT_VERSION
    source_preset_id: str | None = None
    timing_program: TimingProgramSnapshot | None = None
    mux_route_selection: MuxRouteSelection | None = None
    pico_capture: PicoSecondaryCapture | None = None


@dataclass(frozen=True)
class DeviceFault:
    fault_id: str
    device_id: str
    device_kind: DeviceKind
    category: FaultCategory
    severity: FaultSeverity
    code: str
    message: str
    detected_at: datetime
    blocking: bool = True
    vendor_code: str | None = None
    vendor_message: str | None = None
    device_role: str | None = None
    context: Mapping[str, ConfigurationScalar] = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceStatus:
    device_id: str
    device_kind: DeviceKind
    lifecycle_state: DeviceLifecycleState
    connected: bool
    ready: bool
    busy: bool
    updated_at: datetime
    status_summary: str
    active_configuration_id: str | None = None
    device_role: str | None = None
    device_identity: str | None = None
    reported_faults: tuple[DeviceFault, ...] = ()
    vendor_status: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
    telemetry: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
    timing_program: TimingProgramSnapshot | None = None
    mux_route_selection: MuxRouteSelection | None = None
    pico_capture: PicoCaptureSnapshot | None = None

    def __post_init__(self) -> None:
        if self.ready and not self.connected:
            raise ValueError("A device cannot be ready while disconnected.")
