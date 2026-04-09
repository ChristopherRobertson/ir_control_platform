"""PicoScope 5244D driver contract for secondary monitoring and recording."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ircp_contracts import DeviceCapability, DeviceKind, DeviceStatus, PicoSecondaryCapture

from ..base import DeviceDriver


@dataclass(frozen=True)
class PicoCapabilityProfile:
    capability: DeviceCapability
    channel_count: int = 2
    supports_external_trigger: bool = True
    supports_secondary_recording: bool = True


@dataclass(frozen=True)
class PicoCaptureHandle:
    capture_id: str
    session_id: str
    started_at: datetime
    monitored_inputs: tuple[str, ...]


@runtime_checkable
class PicoScopeDriver(DeviceDriver[PicoCapabilityProfile, PicoSecondaryCapture], Protocol):
    device_kind: DeviceKind

    async def start_capture(
        self,
        configuration: PicoSecondaryCapture,
        session_id: str,
    ) -> PicoCaptureHandle | None:
        """Start Pico monitoring or recording when the recipe enables it."""

    async def stop_capture(self, capture_id: str) -> DeviceStatus:
        """Stop an active secondary Pico capture explicitly."""
