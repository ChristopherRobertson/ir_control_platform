# Package Boundaries

## Direction
V1 implements one generic single-wavelength pump-probe workflow. Package authority follows the workflow, not devices or pages.

## Ownership
- `contracts/`: authoritative session, run, setup, recipe, plot, raw record, and artifact schemas.
- `experiment-engine/`: setup validation, run lifecycle, settings snapshot freeze, coordinated device actions, explicit stop/abort/fault behavior.
- `data-pipeline/`: session/run persistence, raw records, processed records, artifact manifests, reopen/replay inputs.
- `processing/`: reusable transforms, including overlay and `-log(sample/reference)`.
- `analysis/`: derived scientific logic when needed beyond reusable transforms.
- `reports/`: exports from persisted artifacts.
- `drivers/*`: normalized device integrations and vendor errors.
- `simulators/`: deterministic success and fault paths.
- `ui-shell/`: Session / Setup / Results presentation only.

## Dependency Rules
- `ui-shell` does not import `drivers`, `data-pipeline`, `processing`, `analysis`, or `reports`.
- `ui-shell` does not call vendor SDKs.
- `ui-shell` does not write raw data or settings snapshots.
- `experiment-engine` owns coordinated run state.
- `data-pipeline` owns persisted truth.
- `ir_control_platform` has no runtime dependency on `Control_System`.
