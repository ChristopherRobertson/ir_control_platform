"""Simulator bundle boundaries for the first vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ircp_drivers import LabOneHF2Driver, MircatDriver


@dataclass(frozen=True)
class GoldenPathSimulatorBundle:
    scenario_id: str
    mircat: MircatDriver
    hf2li: LabOneHF2Driver
    description: str = ""


@runtime_checkable
class SimulatorCatalog(Protocol):
    async def create_bundle(self, scenario_id: str) -> GoldenPathSimulatorBundle:
        """Create a deterministic MIRcat + HF2LI simulator bundle for one named scenario."""
