"""Simulator bundle boundaries for the supported-v1 slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ircp_drivers import (
    ArduinoMuxDriver,
    LabOneHF2Driver,
    MircatDriver,
    PicoScopeDriver,
    T660TimingDriver,
)


@dataclass(frozen=True)
class SupportedV1SimulatorBundle:
    scenario_id: str
    mircat: MircatDriver
    hf2li: LabOneHF2Driver
    t660_master: T660TimingDriver
    t660_slave: T660TimingDriver
    mux: ArduinoMuxDriver
    picoscope: PicoScopeDriver
    description: str = ""


@runtime_checkable
class SimulatorCatalog(Protocol):
    async def create_bundle(self, scenario_id: str) -> SupportedV1SimulatorBundle:
        """Create a deterministic supported-v1 simulator bundle for one named scenario."""
