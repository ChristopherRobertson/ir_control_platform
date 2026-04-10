# Phase 3A UI Foundation

## Historical record only

Phase 3A is complete.

This file remains only as a historical record of what Phase 3A delivered for the initial MIRcat + HF2LI simulator-backed slice. It is not the active guide for current or future UI work.

Active UI guidance now lives in `docs/ui_foundation.md`.

## What Phase 3A delivered

Phase 3A established the initial UI/runtime foundation by proving:

- the Python, server-rendered shell choice
- the WSGI runtime bootstrap and typed UI boundary pattern
- the initial Setup, Run, Results, and Service scaffolds
- shared page-state wrappers and reusable UI shells
- simulator-backed nominal, blocked, and faulted scenarios
- boundary enforcement that kept orchestration, persistence, processing, and analysis truth out of `ui-shell`

## Historical scope note

Phase 3A covered the smallest useful MIRcat + HF2LI golden path only. It did not define the full supported v1 system.

Current and future work must follow:

- `AGENTS.md`
- `EXPERIMENT.md`
- `docs/ui_foundation.md`
- `PLANS.md`

Do not use this phase-tied file as the active development guide for later phases.
