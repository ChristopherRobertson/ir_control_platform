"""Simulator catalog boundary for the single-wavelength v1 workflow."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .golden_path import SimulatorScenarioContext


@runtime_checkable
class SimulatorCatalog(Protocol):
    def list_contexts(self) -> tuple[SimulatorScenarioContext, ...]:
        """Return deterministic simulator contexts."""

    def get_context(self, scenario_id: str) -> SimulatorScenarioContext:
        """Return one deterministic simulator context."""


SupportedV1SimulatorBundle = SimulatorScenarioContext
