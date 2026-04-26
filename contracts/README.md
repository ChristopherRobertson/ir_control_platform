# contracts

Canonical shared contracts for the generic `Single-Wavelength Pump-Probe`
v1 path.

- Owns: session records, run headers, immutable run settings snapshots, setup state, single-wavelength pump/probe/lock-in settings, result records, artifact manifests, device capability/status/fault types, validation/readiness types, and provenance contracts.
- Depends on: no product packages.
- Used by: every other package.

The package root is intentionally narrow for v1. It does not export MIRcat
sweep, step-measure, multispectral, wavelength-list, queued scan,
time-to-wavenumber scan mapping, broad experiment preset, or advanced-control
contracts. Hardware work should target `ProbeSettings` and
`SingleWavelengthPumpProbeRecipe` for one target wavenumber.
