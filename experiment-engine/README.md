# experiment-engine

Single-path orchestration boundaries for validation, session start, run execution, fault handling, and reopen flows.

- Owns: preflight and run-control protocols.
- Depends on: `contracts`, `drivers`.
- Must remain the only coordinator of multi-device run state.
