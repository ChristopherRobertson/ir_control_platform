# REFACTOR.md - Migration Rules For V1

## Purpose
This document governs what may be salvaged from `Control_System` and what must be replaced while building the generic `Single-Wavelength Pump-Probe` vertical slice in `ir_control_platform`.

## Salvage Principles
Preserve hardware and scientific knowledge only when it fits the new package boundaries.

Useful material may include:

- MIRcat SDK calls, status interpretation, readiness checks, and vendor error mapping
- MIRcat single-wavelength tuning and CW/pulsed emission semantics
- HF2LI LabOne connection, node, poll, sample, X/Y/R/phase parsing, and file writing lessons
- timing/delay generator command semantics needed for acquisition windows
- pump readiness and fault handling knowledge
- hardware configuration ranges and defaults
- raw data format knowledge and sample/reference ratio formulas
- deterministic fixtures and fault cases

## Delete / Replace Rules
Generic experiment-agnostic UI surfaces are REPLACE or DELETE.

Device-first page layout is REPLACE.

Direct UI-to-device orchestration is DELETE.

UI-owned persistence is DELETE.

UI-owned scientific transforms are DELETE.

Broad future-proof controls not required for v1 are DELETE or DEFER.

Sample-specific product logic is DELETE.

Do not carry forward:

- old React route hierarchy
- device dashboards as the primary product
- MIRcat scan controls
- HF2LI broad dashboard tabs
- raw timing channel editors in operator flow
- raw MUX routing editors in operator flow
- wavelength sweep or spectral map workflows
- multi-path compatibility code
- fallback behavior
- old screen-driven state
- UI-owned analysis or export truth

## Required Re-Homing
Re-home accepted knowledge into the correct destination:

- `contracts/` for session, run, setup, recipe, plotting, raw record, and artifact schemas
- `drivers/*` for normalized device integration and vendor error mapping
- `experiment-engine/` for run lifecycle and coordinated behavior
- `data-pipeline/` for persistence and artifacts
- `processing/` for reusable transforms
- `analysis/` for derived scientific logic beyond reusable transforms
- `reports/` for exports
- `simulators/` for deterministic success and fault paths
- `ui-shell/` for presentation only

## V1 Forbidden Scope
The active product must not implement:

- wavelength scanning
- wavelength lists
- queued spectral acquisition
- spectral maps
- generic all-device dashboards
- separate data acquisition page or section
- separate run page
- preflight page or section
- real-time plotting
- broad service pages
- advanced scaffolding
- free-form delay-generator channel editing
- raw MUX routing editing
- universal spectroscopy interfaces
- sample-specific workflows

## Verification Rules
- New persisted formats are versioned.
- Raw, processed, metadata, and export artifacts remain distinct.
- Processed outputs cite raw inputs.
- Exports cite persisted sources.
- UI-shell remains a thin client of runtime contracts.
- `ir_control_platform` never imports or shells into `Control_System` at runtime.
- Real drivers fail clearly if SDKs or hardware are unavailable.

## Control_System Boundary
The parent workspace rules make `Control_System` read-only. Do not edit it, create files in it, or depend on it. Documentation changes that would be desirable in the old repo are captured in the target repo's salvage matrix and deletion ledger instead.
