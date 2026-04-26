# AGENTS.md - contracts

## Purpose
This package owns the canonical shared schemas for the supported v1
`Single-Wavelength Pump-Probe` workflow.

## Must own
- `SessionRecord`
- `RunHeader`
- `RunRecord`
- `RunSettingsSnapshot`
- `SetupState`
- `SingleWavelengthPumpProbeRecipe`
- `ArtifactManifest`
- `DeviceCapability`
- `DeviceConfiguration`
- `DeviceStatus`
- `DeviceFault`
- `ValidationIssue`
- `RunCommand`
- `RunState`
- `RunEvent`
- `SessionManifest`
- `ArtifactManifest`
- `ProcessingRecipe`
- `AnalysisRecipe`
- `ExportRequest`
- shared enums, units, and error taxonomy

## Rules
- Define one canonical schema per concept.
- Version breaking changes explicitly.
- Keep units and semantics explicit.
- Do not embed UI-only language or vendor-SDK details unless they are part of the normalized public contract.
- Do not add compatibility aliases for old schemas.
- Do not implement business logic, device I/O, or UI behavior here.
- The `ircp_contracts` package root is the supported v1 public surface.
- Do not export MIRcat sweep, step-measure, multispectral, wavelength-list, queued scan, broad experiment-preset, or advanced-control contracts from the package root.
- Deferred broad experiment definitions must stay out of the v1 package root and must not be used as the hardware integration target.

## Success criteria
Downstream packages can compile against stable single-wavelength v1 types without inventing duplicate schemas or depending on deferred scan/advanced surfaces.
