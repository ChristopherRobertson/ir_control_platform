# AGENTS.md — contracts

## Purpose
This package owns the canonical shared schemas for the control platform.

## Must own
- `ExperimentRecipe`
- `ExperimentPreset`
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

## Success criteria
Downstream packages can compile against stable types without inventing their own duplicate schemas.
