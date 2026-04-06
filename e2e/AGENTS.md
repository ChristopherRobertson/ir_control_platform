# AGENTS.md — e2e

## Purpose
This package owns cross-package verification of the finished workflows.

## Must own
- golden-path workflow tests
- fault-path tests
- replay and reprocessing tests
- export validation
- hardware smoke checks where required

## Rules
- Cover the operator workflow first.
- Keep simulator-backed tests as the default.
- Add real-device smoke tests only where simulator fidelity is not sufficient.
- Validate explicit failure behavior, not just success cases.

## Success criteria
The repository has repeatable end-to-end evidence that the new architecture works for normal runs, failure cases, and offline analysis.
