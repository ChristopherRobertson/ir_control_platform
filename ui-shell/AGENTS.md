# AGENTS.md — ui-shell

## Purpose
This package is the product surface for operators and expert users.

The current shell is the active Python, server-rendered frontend strategy for the project. Future work should build on this shell rather than assume a frontend-stack replacement.

## Must own
- navigation
- layout
- route scaffolding
- reusable UI components
- rendering of runtime state, results, and faults
- the default `Experiment` workflow
- secondary `Results`, `Analyze`, `Advanced`, and `Service / Maintenance` surfaces

## Rules
- The UI does not import vendor SDKs directly.
- The UI does not orchestrate coordinated hardware behavior.
- The UI does not own raw persistence, processing, analysis, or export logic.
- The UI does not become the owner of authoritative run state or session truth.
- Make device status, blocking issues, vendor errors, and recovery states explicit.
- Keep the default workflow simple and task-oriented.
- Put expert controls in dedicated secondary surfaces instead of polluting the primary flow.
- Treat calibrated values as guarded bench-owned truth, not routine operator settings.
- Show status beside controls.
- Hide complexity by default and use progressive disclosure for expert detail.
- Do not add bypass buttons for invalid states.
- Do not assume React or any other replacement frontend stack without an explicit source-of-truth change.

## Success criteria
The UI can present a usable operator-first starting workflow against simulators and persisted sessions while remaining a thin client of backend contracts.
