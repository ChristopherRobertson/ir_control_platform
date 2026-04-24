# PLANS.md - Active V1 Development Sequence

## Objective
Deliver one generic, sample-agnostic v1 vertical slice:

`Session -> Setup -> Results` for `Single-Wavelength Pump-Probe`.

The active product is not a generic platform shell and not a device dashboard. It is one operator workflow that can run against simulators first and required hardware second.

## Fixed Constraints
- one v1 workflow
- three pages only: Session, Setup, Results
- run controls on Setup
- no separate Run page
- no preflight page or preflight section
- no data acquisition section
- no real-time plotting
- no wavelength scanning or scan controls
- no sample-specific product logic
- no advanced scaffolding unless required for basic operation
- session and run persisted separately
- wavelength and timescale belong to run/setup, not session
- timescale means acquisition-window regime

## Milestone 0 - Audit And Salvage Matrix
Audit `Control_System` as read-only reference material.

Exit criteria:
- `docs/refactor/salvage_matrix.md` classifies useful old files as KEEP-ASSET, KEEP-CODE-WITH-BOUNDARY, EXTRACT-AND-REWRITE, REPLACE, or DELETE.
- `docs/refactor/deletion_ledger.md` records old structures intentionally not ported.
- no runtime dependency from `ir_control_platform` to `Control_System`.

## Milestone 1 - Docs, Contracts, Session/Run Model
Establish authoritative contracts and docs for:

- `SessionRecord`
- `RunHeader`
- `RunRecord`
- `TimescaleRegime`
- `SingleWavelengthPumpProbeRecipe`
- `SetupState`
- run lifecycle state
- plot metric family
- plot display mode
- raw and processed run records
- artifact manifest

Exit criteria:
- docs identify v1 as generic single-wavelength pump-probe
- session and run definitions are explicit
- forbidden v1 scope is documented
- canonical recipe spec exists under `contracts/recipes/`

## Milestone 2 - Simulator-Backed Vertical Slice
Implement the first end-to-end path against deterministic simulators:

1. Save session metadata.
2. Create and save draft run header.
3. Configure Setup in the required order.
4. Gate Run until metadata and setup are valid.
5. Freeze settings snapshot at Run.
6. Persist raw X/Y/R/Theta/time for sample and reference.
7. Persist processed result data.
8. Reopen Results without live hardware.

Exit criteria:
- primary navigation is Session / Setup / Results only
- Run button enablement is validation-driven
- Results supports overlay and ratio mode
- nominal and faulted simulator paths are tested

## Milestone 3 - Hardware-Backed Integration
Wire only the hardware needed for the v1 workflow:

- MIRcat single-wavelength control/status with CW and pulsed emission mode
- HF2LI sample/reference acquisition path
- timing path needed for regime-based capture around the YAG pulse
- pump readiness/control path

Rules:
- device integrations stay behind `drivers/*`
- every real path has a deterministic simulator
- SDK/hardware absence fails clearly
- no fake success from real drivers

## Milestone 4 - Export, Replay, Refinement
Harden persisted artifacts and exports:

- raw run data export
- processed result export
- run metadata/settings snapshot export
- replay/reopen validation
- UI refinements after operator review

## Deferred
Defer these until after v1 acceptance:

- wavelength scanning
- spectral maps
- multi-wavelength queues
- multiple experiment types
- generic all-device dashboards
- service pages
- advanced pages
- plot-builder frameworks
- real-time plotting dashboards
