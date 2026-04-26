# EXPERIMENT.md - V1 Experiment-Control Model

## 1. Purpose

This file defines the supported v1 experiment model for
`ir_control_platform`.

The active v1 product is one generic, sample-agnostic workflow:

`Session -> Setup -> Results`

The experiment is `Single-Wavelength Pump-Probe`.

This document is subordinate to `AGENTS.md`, `REFACTOR.md`, and `PLANS.md`
when those files define package boundaries, migration rules, or milestone
order. It narrows the public contracts and operator-facing documentation before
hardware integration starts.

## 2. Supported V1 System

The v1 system models only the subsystems required for one saved
single-wavelength pump-probe run:

- YAG/OPO pump path as the physical pump source, with v1 control centered on
  pump enablement, readiness, and shot count.
- MIRcat probe source at one target wavenumber.
- HF2LI lock-in amplifier as the primary recorded sample/reference signal
  path.
- Timing path needed to acquire a window in the selected timescale regime.
- Deterministic simulators for the nominal and explicit fault paths.

The following remain deferred in v1:

- wavelength scanning
- wavelength lists
- queued spectral acquisition
- sweep, step-measure, and multispectral MIRcat modes
- time-to-wavenumber scan mapping
- generic experiment presets
- advanced pages or advanced controls
- service pages
- direct OPO control
- raw timing-channel editors
- raw MUX route editors
- PicoScope-first or generic device-dashboard workflows

## 3. Operator Workflow

The only primary workflow pages are:

1. `Session`
2. `Setup`
3. `Results`

There is no separate Run page. Run controls live at the bottom of `Setup`.

`Setup` uses this section order:

1. Pump settings
2. Timescale
3. Probe settings
4. Lock-In Amplifier settings
5. Run controls

Timescale is an acquisition-window regime. It is not a delay-scan grid and
must not expose step size, point count, spacing mode, or grid controls in v1.

## 4. Public Contract Surface

The supported v1 public contract root is `ircp_contracts`.

The public v1 surface includes:

- `SessionRecord`
- `RunHeader`
- `RunRecord`
- `RunSettingsSnapshot`
- `SetupState`
- `SingleWavelengthPumpProbeRecipe`
- `PumpSettings`
- `TimescaleRegime`
- `ProbeSettings`
- `ProbeEmissionMode`
- `LockInSettings`
- `RawRunRecord`
- `ProcessedRunRecord`
- `ArtifactManifest`
- result plotting metric and display-mode contracts
- normalized device capability, status, fault, and lifecycle contracts

The public v1 surface must not export broad scan or advanced experiment APIs,
including:

- `ExperimentRecipe`
- `ExperimentPreset`
- `MircatSpectralMode`
- `MircatExperimentConfiguration`
- `MircatSweepScan`
- `MircatStepMeasureScan`
- `MircatMultispectralScan`
- `MultispectralElement`
- `TimeToWavenumberMapping`

Deferred broad definitions may remain as internal migration scaffolding only.
They are not the target API for v1 hardware work and must not be re-exported
from the package root.

## 5. MIRcat V1 Model

MIRcat v1 control is limited to:

- one positive target wavenumber in `cm^-1`
- emission mode `cw` or `pulsed`
- pulse rate and pulse width only when pulsed mode requires them
- explicit ready/fault state

The MIRcat driver public surface must accept `ProbeSettings` for the one
target wavenumber. It must not expose spectral mode selection, sweep bounds,
step spacing, scan count, bidirectional scan behavior, QCL sequence editing, or
multispectral element lists in v1.

## 6. Session And Run Semantics

A session is user-defined experiment context. It includes experiment type,
session name or ID, operator, sample ID or name, sample notes, experiment
notes, created timestamp, and updated timestamp.

Wavelength and timescale are not session fields. They belong to setup and the
immutable run settings snapshot.

A run is one acquisition inside a session. It stores a frozen settings
snapshot, lifecycle state, raw data, processed data, start timestamp, end
timestamp, and explicit fault/error state when aborted or failed.

The settings snapshot is frozen when Run starts.

## 7. Data Semantics

HF2LI demodulated and filtered sample/reference data is the primary scientific
raw data in v1.

Each raw signal record stores time plus sample/reference values for:

- `X`
- `Y`
- `R`
- `Theta`

Processed v1 result data is derived from persisted raw records. The required
v1 processed views are:

- sample/reference overlay
- `-log(sample/reference)` ratio value

Results and exports must read from persisted session/run artifacts. They must
not depend on live hardware state or UI memory.

## 8. Hardware Work Rule

Hardware integration after this point must target the narrow v1 contracts:

- MIRcat: `ProbeSettings` for a single wavenumber.
- HF2LI: sample/reference acquisition for the saved run snapshot.
- Timing path: regime-based acquisition window support.
- Pump path: readiness, explicit faults, and shot count support.

If real hardware or SDKs are unavailable, real drivers fail with explicit
faults. They must not fake success or route around missing dependencies.
