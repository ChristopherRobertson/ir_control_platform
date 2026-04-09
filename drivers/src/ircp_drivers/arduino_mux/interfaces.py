"""Arduino-controlled MUX driver contract for supported-v1 routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ircp_contracts import DeviceCapability, DeviceKind, DeviceStatus, MuxRouteSelection

from ..base import DeviceDriver


@dataclass(frozen=True)
class ArduinoMuxCapabilityProfile:
    capability: DeviceCapability
    supports_analog_routes: bool = True
    supports_digital_routes: bool = True
    supports_external_trigger_selection: bool = True


@runtime_checkable
class ArduinoMuxDriver(DeviceDriver[ArduinoMuxCapabilityProfile, MuxRouteSelection], Protocol):
    device_kind: DeviceKind

    async def clear_routes(self) -> DeviceStatus:
        """Return the MUX to an explicit no-route state."""
