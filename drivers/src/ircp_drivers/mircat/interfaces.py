"""MIRcat golden-path driver contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ircp_contracts import DeviceCapability, DeviceConfiguration, DeviceKind, DeviceStatus, MircatLaserMode, MircatSweepRecipe

from ..base import DeviceDriver


@dataclass(frozen=True)
class MircatCapabilityProfile:
    capability: DeviceCapability
    supported_laser_modes: tuple[MircatLaserMode, ...] = (
        MircatLaserMode.PULSED,
        MircatLaserMode.CW,
        MircatLaserMode.CW_MODULATION,
    )
    supported_scan_modes: tuple[str, ...] = ("sweep",)
    supports_tune: bool = True
    supports_emission_control: bool = True
    supports_bidirectional_sweep: bool = True


@runtime_checkable
class MircatDriver(DeviceDriver[MircatCapabilityProfile, MircatSweepRecipe], Protocol):
    device_kind: DeviceKind

    async def arm(self) -> DeviceStatus:
        """Arm MIRcat for later tune or sweep operations."""

    async def disarm(self) -> DeviceStatus:
        """Disarm MIRcat after an explicit stop or fault."""

    async def tune_to_wavenumber(self, wavenumber_cm1: float) -> DeviceStatus:
        """Tune MIRcat to a single wavenumber without starting a scan."""

    async def set_emission_enabled(self, enabled: bool) -> DeviceStatus:
        """Turn emission on or off explicitly."""

    async def start_sweep(self, recipe: MircatSweepRecipe) -> DeviceStatus:
        """Start the one approved sweep-scan path for the Phase 3 slice."""

    async def stop_sweep(self) -> DeviceStatus:
        """Stop the active sweep scan explicitly."""
