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
- Setup, Advanced, Calibrated, Run, Results, Analyze, and Service / Maintenance surfaces

## Rules
- The UI does not import vendor SDKs directly.
- The UI does not orchestrate coordinated hardware behavior.
- The UI does not own raw persistence, processing, or analysis logic.
- The UI does not become the owner of authoritative run state or session truth.
- Make device status, blocking issues, and vendor errors explicit.
- Keep the default workflow simple.
- Put expert controls in dedicated surfaces instead of polluting the primary flow.
- Treat calibrated values as guarded bench-owned truth, not routine operator settings.
- Do not add bypass buttons for invalid states.
- Do not assume React or any other replacement frontend stack without an explicit source-of-truth change.

## Success criteria
The UI can drive the operator workflow cleanly against simulators and persisted sessions while remaining a thin client of backend contracts and exposing the real workflow surfaces that users need to operate the product.
