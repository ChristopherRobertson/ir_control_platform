"""Deterministic simulator contexts for the single-wavelength pump-probe v1 slice."""

from __future__ import annotations

from dataclasses import dataclass

from ircp_contracts import (
    LockInSettings,
    ProbeEmissionMode,
    ProbeSettings,
    PumpSettings,
    TimescaleRegime,
)


@dataclass(frozen=True)
class SimulatorScenarioContext:
    scenario_id: str
    label: str
    description: str
    default_pump: PumpSettings
    default_timescale: TimescaleRegime
    default_probe: ProbeSettings
    default_lockin: LockInSettings
    fault_on_start: bool = False


class SupportedV1SimulatorCatalog:
    """Small deterministic scenario catalog for UI and engine tests."""

    def list_contexts(self) -> tuple[SimulatorScenarioContext, ...]:
        return (
            self.get_context("nominal"),
            self.get_context("faulted_hf2"),
        )

    def get_context(self, scenario_id: str) -> SimulatorScenarioContext:
        if scenario_id == "faulted_hf2":
            return SimulatorScenarioContext(
                scenario_id="faulted_hf2",
                label="Faulted HF2",
                description="Deterministic run path that faults after the settings snapshot and partial raw write.",
                default_pump=PumpSettings(enabled=True, shot_count=10),
                default_timescale=TimescaleRegime.MICROSECONDS,
                default_probe=ProbeSettings(
                    wavelength_cm1=1850.0,
                    emission_mode=ProbeEmissionMode.PULSED,
                    pulse_rate_hz=10000.0,
                    pulse_width_ns=180.0,
                ),
                default_lockin=LockInSettings(order=2, time_constant_seconds=1.002, transfer_rate_hz=224.9),
                fault_on_start=True,
            )
        return SimulatorScenarioContext(
            scenario_id="nominal",
            label="Nominal",
            description="Deterministic simulator-backed single-wavelength pump-probe run.",
            default_pump=PumpSettings(enabled=True, shot_count=10),
            default_timescale=TimescaleRegime.MICROSECONDS,
            default_probe=ProbeSettings(
                wavelength_cm1=1850.0,
                emission_mode=ProbeEmissionMode.CW,
            ),
            default_lockin=LockInSettings(order=2, time_constant_seconds=1.002, transfer_rate_hz=224.9),
        )
