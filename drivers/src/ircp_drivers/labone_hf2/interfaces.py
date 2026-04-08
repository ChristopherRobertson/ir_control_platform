"""HF2LI golden-path driver contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ircp_contracts import (
    DeviceCapability,
    DeviceConfiguration,
    DeviceKind,
    DeviceStatus,
    HF2AcquisitionRecipe,
    HF2SampleComponent,
)

from ..base import DeviceDriver


@dataclass(frozen=True)
class HF2CapabilityProfile:
    capability: DeviceCapability
    demodulator_count: int = 8
    supports_phase_zero: bool = True
    supported_components: tuple[HF2SampleComponent, ...] = (
        HF2SampleComponent.X,
        HF2SampleComponent.Y,
        HF2SampleComponent.R,
        HF2SampleComponent.PHASE,
        HF2SampleComponent.FREQUENCY,
        HF2SampleComponent.TIMESTAMP,
    )


@dataclass(frozen=True)
class HF2CaptureHandle:
    capture_id: str
    session_id: str
    selected_streams: tuple[str, ...]
    started_at: datetime


@runtime_checkable
class LabOneHF2Driver(DeviceDriver[HF2CapabilityProfile, HF2AcquisitionRecipe], Protocol):
    device_kind: DeviceKind

    async def start_capture(self, recipe: HF2AcquisitionRecipe, session_id: str) -> HF2CaptureHandle:
        """Start raw acquisition for the approved HF2LI stream selection surface."""

    async def stop_capture(self, capture_id: str) -> DeviceStatus:
        """Stop an active raw acquisition and return normalized status."""

    async def zero_demod_phase(self, demod_index: int) -> DeviceStatus:
        """Run the explicit phase-zero expert action for one demodulator."""
