"""MIRcat driver contract for the supported v1 experiment slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ircp_contracts import (
    DeviceCapability,
    DeviceFault,
    DeviceKind,
    DeviceStatus,
    FaultCategory,
    FaultSeverity,
    ProbeEmissionMode,
    ProbeSettings,
)

from ..base import DeviceDriver


UNSUPPORTED_SCAN_REQUESTS_V1 = (
    "wavelength_sweep",
    "step_measure_scan",
    "multispectral_scan",
    "wavelength_list",
    "queued_spectral_acquisition",
)


def unsupported_scan_request_fault(
    requested_operation: str,
    *,
    device_id: str,
    detected_at: datetime,
) -> DeviceFault:
    normalized = requested_operation.strip() or "unknown_scan_request"
    return DeviceFault(
        fault_id=f"{device_id}-unsupported-v1-scan-request",
        device_id=device_id,
        device_kind=DeviceKind.MIRCAT,
        category=FaultCategory.VALIDATION,
        severity=FaultSeverity.ERROR,
        code="unsupported_v1_scan_request",
        message=(
            "Unsupported MIRcat scan request for v1. "
            "The supported v1 probe path is single-wavelength only."
        ),
        detected_at=detected_at,
        blocking=True,
        context={
            "requested_operation": normalized,
            "supported_operation": "single_wavelength",
        },
    )


@dataclass(frozen=True)
class MircatCapabilityProfile:
    capability: DeviceCapability
    supported_emission_modes: tuple[ProbeEmissionMode, ...] = (
        ProbeEmissionMode.CW,
        ProbeEmissionMode.PULSED,
    )
    single_wavelength_only: bool = True
    supports_emission_control: bool = True


@runtime_checkable
class MircatDriver(DeviceDriver[MircatCapabilityProfile, ProbeSettings], Protocol):
    device_kind: DeviceKind

    async def arm(self) -> DeviceStatus:
        """Arm MIRcat for a coordinated experiment start."""

    async def disarm(self) -> DeviceStatus:
        """Disarm MIRcat after an explicit stop or fault."""

    async def set_emission_enabled(self, enabled: bool) -> DeviceStatus:
        """Turn MIRcat emission on or off explicitly."""

    async def start_single_wavelength(self, settings: ProbeSettings) -> DeviceStatus:
        """Start MIRcat for the supported-v1 single-wavelength probe path."""

    async def stop_single_wavelength(self) -> DeviceStatus:
        """Stop the active supported-v1 single-wavelength probe path explicitly."""
