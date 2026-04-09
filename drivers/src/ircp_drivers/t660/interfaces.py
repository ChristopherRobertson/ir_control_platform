"""T660 family driver contract for supported-v1 master/slave timing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ircp_contracts import (
    DeviceCapability,
    DeviceConfiguration,
    DeviceKind,
    DeviceStatus,
    T660MasterTimingConfiguration,
    T660SlaveTimingConfiguration,
    TimingControllerIdentity,
    TimingControllerRole,
)

from ..base import DeviceDriver

T660TimingConfiguration = T660MasterTimingConfiguration | T660SlaveTimingConfiguration


@dataclass(frozen=True)
class T660CapabilityProfile:
    capability: DeviceCapability
    supported_identities: tuple[TimingControllerIdentity, ...]
    supported_roles: tuple[TimingControllerRole, ...]
    supports_master_clock_output: bool = True
    supports_slave_triggering: bool = True


@runtime_checkable
class T660TimingDriver(DeviceDriver[T660CapabilityProfile, T660TimingConfiguration], Protocol):
    device_kind: DeviceKind

    async def arm_outputs(self) -> DeviceStatus:
        """Arm the programmed timing outputs for the next coordinated run."""

    async def stop_outputs(self) -> DeviceStatus:
        """Stop timing outputs explicitly after completion, abort, or fault."""
