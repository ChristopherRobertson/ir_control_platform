"""MIRcat driver contract for the supported v1 experiment slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ircp_contracts import (
    DeviceCapability,
    DeviceConfiguration,
    DeviceKind,
    DeviceStatus,
    MircatEmissionMode,
    MircatExperimentConfiguration,
    MircatSpectralMode,
    ProbeTimingMode,
)

from ..base import DeviceDriver


@dataclass(frozen=True)
class MircatCapabilityProfile:
    capability: DeviceCapability
    supported_emission_modes: tuple[MircatEmissionMode, ...] = (
        MircatEmissionMode.PULSED,
        MircatEmissionMode.CW,
    )
    supported_spectral_modes: tuple[MircatSpectralMode, ...] = (
        MircatSpectralMode.SINGLE_WAVELENGTH,
        MircatSpectralMode.SWEEP_SCAN,
        MircatSpectralMode.STEP_MEASURE_SCAN,
        MircatSpectralMode.MULTISPECTRAL_SCAN,
    )
    supported_probe_timing_modes: tuple[ProbeTimingMode, ...] = (
        ProbeTimingMode.CONTINUOUS_PROBE,
        ProbeTimingMode.SYNCHRONIZED_PROBE,
    )
    supports_emission_control: bool = True


@runtime_checkable
class MircatDriver(DeviceDriver[MircatCapabilityProfile, MircatExperimentConfiguration], Protocol):
    device_kind: DeviceKind

    async def arm(self) -> DeviceStatus:
        """Arm MIRcat for a coordinated experiment start."""

    async def disarm(self) -> DeviceStatus:
        """Disarm MIRcat after an explicit stop or fault."""

    async def set_emission_enabled(self, enabled: bool) -> DeviceStatus:
        """Turn MIRcat emission on or off explicitly."""

    async def start_recipe(
        self,
        configuration: MircatExperimentConfiguration,
        probe_timing_mode: ProbeTimingMode,
    ) -> DeviceStatus:
        """Start the one supported-v1 MIRcat path for the configured experiment recipe."""

    async def stop_recipe(self) -> DeviceStatus:
        """Stop the active supported-v1 MIRcat path explicitly."""
