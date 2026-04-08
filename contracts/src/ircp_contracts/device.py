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
)


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
class DeviceCapability:
    device_kind: DeviceKind
    model: str
    version: str = CONTRACT_VERSION
    supported_actions: tuple[str, ...] = ()
    configuration_fields: tuple[ConfigurationFieldDefinition, ...] = ()
    stream_components: tuple[str, ...] = ()
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
    reported_faults: tuple[DeviceFault, ...] = ()
    vendor_status: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
    telemetry: Mapping[str, ConfigurationScalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.ready and not self.connected:
            raise ValueError("A device cannot be ready while disconnected.")
