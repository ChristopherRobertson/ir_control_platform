"""Base driver protocols shared by real and simulated adapters."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from ircp_contracts import DeviceCapability, DeviceConfiguration, DeviceFault, DeviceKind, DeviceStatus

CapabilityT = TypeVar("CapabilityT")
ConfigurationT = TypeVar("ConfigurationT")


@runtime_checkable
class DeviceDriver(Protocol[CapabilityT, ConfigurationT]):
    device_kind: DeviceKind

    async def connect(self) -> DeviceStatus:
        """Establish a device connection and return normalized status."""

    async def disconnect(self) -> DeviceStatus:
        """Close a device connection and return normalized status."""

    async def get_capability(self) -> CapabilityT:
        """Return the device capability profile for this adapter."""

    async def get_status(self) -> DeviceStatus:
        """Return the current normalized device status."""

    async def apply_configuration(self, configuration: ConfigurationT) -> DeviceConfiguration:
        """Apply the supported configuration surface and return a snapshot."""

    async def get_active_faults(self) -> tuple[DeviceFault, ...]:
        """Return currently active normalized device faults."""
