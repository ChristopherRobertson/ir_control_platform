# REFACTOR.md — Transition Rules for the IR Control Platform

## Active Documents
Use the repository documents this way:

- `AGENTS.md` defines the required product outcome and fixed architecture.
- `docs/operator_ui_mvp.md` defines the active next-pass UI target.
- `docs/ui_foundation.md` defines the active UI-shell rules.
- `docs/package_boundaries.md` defines package ownership and dependency direction.
- `REFACTOR.md` defines what may be salvaged, rewritten, deleted, or retired during the migration.
- `PLANS.md` defines the active development sequence.

## Purpose
This document governs how the current codebase is replaced while preserving the architecture already established in `ir_control_platform`.

Use it to decide:
- what must be preserved
- what knowledge should be extracted and rewritten
- what structure must be replaced
- what documentation or code should be removed because it no longer helps

This is not an in-place cleanup. It is a controlled replacement.

## Core Direction
Treat the current implementation as a source of:
- hardware integration knowledge
- vendor API usage patterns
- scientific logic
- data-format knowledge
- error-code handling knowledge
- useful datasets and fixtures
- practical lessons from bench use

Do not treat it as the structural template for the new product.

Active rewrite decisions:
- Preserve valuable low-level logic and scientific knowledge.
- Do not preserve the current UI architecture.
- Do not preserve UI ownership of orchestration, persistence, processing, or analysis.
- Preserve the control-plane and data-plane split already established in `ir_control_platform`.
- Build the next implementation pass around the operator-first UI MVP in `docs/operator_ui_mvp.md`.
- Let backend work follow validated UI needs instead of speculative expansion.
- Remove obsolete phase-tied and workflow-map guidance once active guidance replaces it.

## Non-negotiable Rewrite Rules
1. **One implementation path per workflow.**
   Do not keep alternate legacy paths, compatibility modes, or fallback branches for the same behavior.
2. **No legacy UI structure in the new product.**
   Do not port old screens, callback trees, or device-first route hierarchies into `ui-shell`.
3. **No direct UI-to-device orchestration.**
   Coordinated device control belongs in `experiment-engine` and `drivers`, never in pages or widgets.
4. **No UI-owned persistence, processing, analysis, or export truth.**
   Those responsibilities belong in `data-pipeline`, `processing`, `analysis`, and `reports`.
5. **Fail explicitly instead of bypassing.**
   If a device faults or a required dependency is missing, surface the reason and stop cleanly.
6. **Prefer vendor-reported status over duplicated protection logic.**
   Preserve vendor error mappings. Do not re-implement external protections in the UI.
7. **No silent retries, hidden correction, or workaround branches.**
8. **Delete aggressively after extraction.**
   Once useful content has been re-homed cleanly, remove the obsolete structure from the active path.
9. **Keep historical reference material out of the active execution path.**
   Historical docs may exist as reference, but they must not compete with active guidance.
10. **Record destructive removals.**
    Keep a clear note of what was removed, what replaced it, and why.

## What May Be Salvaged
Salvage only material that supports the new architecture:
- low-level device communication logic
- vendor API wrapping knowledge
- error and fault mappings
- validated parameter translations and unit handling
- file readers, writers, and metadata interpretation
- calibration loaders and calibration application knowledge
- reusable scientific transforms
- useful tests, diagnostics, replay fixtures, and setup notes

Re-home salvaged material into the correct destination package such as:
- `contracts`
- `platform`
- `drivers`
- `experiment-engine`
- `data-pipeline`
- `processing`
- `analysis`
- `reports`
- `simulators`
- `e2e`

## What Must Not Be Carried Forward
Do not carry these patterns or structures into the active product path:
- old UI architecture
- device-first navigation
- per-screen business logic
- UI-owned orchestration
- UI-owned persistence
- UI-owned processing or analysis truth
- compatibility layers
- fallback logic
- duplicated execution paths
- giant architecture-led shells that expose internal surfaces before the operator workflow is usable

## Active Transition Sequence
Use `PLANS.md` for the authoritative phase order. The rewrite sequence is:

1. Documentation reset
   Remove conflicting guidance and establish one active operator-first path.
2. Operator-first UI MVP
   Build the default `Operate` experience first.
3. Results and review
   Make recent sessions and persisted summaries reviewable.
4. Advanced and service surfaces
   Move timing, routing, calibration, and recovery detail out of the default path.
5. Incremental backend wiring
   Wire real actions in UI priority order only where the reviewed UI proves they are needed.
6. Real-device hardening
   Validate the minimum supported hardware flows and explicit failure behavior.
7. Deeper processing and analysis
   Expand processing and analysis only after the operator-facing UI has been validated.

## Deletion Rules
Delete or retire these when active replacements exist:
- obsolete phase-specific UI docs
- stale workflow-map plans that are no longer the current execution guide
- direct vendor API calls from presentation code
- screen controllers or view-models that embed orchestration
- UI-triggered persistence code
- UI-local processing and analysis pipelines
- duplicated validation logic across screens
- compatibility code that keeps legacy behavior alive

Do not keep obsolete docs “for history” when they compete with the active plan. If the content still matters, merge the useful part into an active document and remove the obsolete file.

## Data And Verification Rules
- Do not strand historical data. Existing runs, calibrations, and reference datasets must stay readable, importable, or explicitly retired with documentation.
- Version all new persisted formats.
- Preserve provenance from raw artifacts through processed, analysis, and export outputs.
- Prefer importers over manual conversion when historical formats matter.
- Keep simulator-backed validation as the default path until a phase explicitly requires hardware.

## Final Instruction
Assume the old UI is not the blueprint.
Assume the old knowledge base is valuable.
Assume the correct outcome is a clean new architecture with selectively preserved assets and decisively removed obsolete structure and guidance.
