# AGENTS.md — ui-shell

## Purpose
This package is the product surface for operators and expert users.

## Must own
- navigation
- layout
- route scaffolding
- reusable UI components
- rendering of runtime state, results, and faults
- simple and advanced interaction surfaces

## Rules
- The UI does not import vendor SDKs directly.
- The UI does not orchestrate coordinated hardware behavior.
- The UI does not own raw persistence, processing, or analysis logic.
- Make device status, blocking issues, and vendor errors explicit.
- Keep the default workflow simple.
- Put expert controls in dedicated surfaces instead of polluting the primary flow.
- Do not add bypass buttons for invalid states.

## Success criteria
The UI can drive the operator workflow cleanly against simulators and persisted sessions while remaining a thin client of backend contracts.
