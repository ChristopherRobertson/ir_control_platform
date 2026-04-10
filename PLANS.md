# PLANS.md — Active Development Sequence for the IR Control Platform

## 1. Objective
Build the IR control platform as one operator-usable application while preserving the architecture already established in `ir_control_platform`.

The active target is not “finish every subsystem.” The active target is to make the next implementation pass unambiguous:
- build a usable operator-first UI MVP
- preserve control-plane and data-plane ownership
- wire only the minimum honest behavior needed to support the reviewed UI

## 2. Active Source Of Truth
Before implementation begins, use:
- `AGENTS.md` for product and fixed architecture
- `EXPERIMENT.md` for supported v1 control semantics
- `docs/operator_ui_mvp.md` for the next-pass UI target
- `docs/ui_foundation.md` for active UI-shell rules
- `docs/package_boundaries.md` for package ownership and dependency direction
- `REFACTOR.md` for rewrite constraints
- package-level `AGENTS.md` files for local rules

Historical audit and migration docs are reference only. They do not define the current sequence.

## 3. Fixed Constraints
The following do not change during the next pass:
- the control plane owns orchestration, validation, commands, and authoritative run state
- the data plane owns sessions, artifacts, replay, and provenance
- processing, analysis, and reports remain outside the UI layer
- the current Python, server-rendered shell remains the active frontend strategy
- React is not the active plan
- package boundaries remain explicit
- backend work follows validated UI needs instead of leading them speculatively

## 4. Layered Development Approach
Use this order for remaining work:

### Layer 1 — Operator MVP
Build a small, intuitive primary interface for normal operation.

### Layer 2 — Advanced Surfaces
Move timing, routing, calibration, hardware detail, and service functions out of the default path.

### Layer 3 — Incremental Backend Wiring
Wire real actions in priority order only after the operator-facing controls are in place and reviewed.

This is a sequencing rule, not an ownership change.

## 5. Phase 0 — Documentation Reset
This pass aligns the repository around one active direction.

Exit criteria:
- one active UI-first strategy
- one active development sequence
- one explicit description of the next implementation pass
- obsolete phase-specific UI guidance removed or neutralized

## 6. Phase 1 — Operator-First UI MVP
This is the next implementation pass.

### Desired outcome
Deliver a usable, reviewable, intuitive starting interface that makes the default operator path obvious.

The UI must become a task UI, not an architecture UI.
The default experience must center on one `Operate` workflow, even if the implementation still uses separate `setup` and `run` routes internally.

### Required contents
The MVP must cover these sections:

#### Session
- session name
- sample ID
- notes
- save and open recent session

#### Laser
- connect and disconnect
- arm and disarm
- emission on and off
- tune to wavelength or wavenumber
- start scan
- stop scan
- current laser status

#### Lock-in / Acquisition
- connect and disconnect HF2LI
- a small set of key acquisition parameters only
- start acquisition
- stop acquisition
- current acquisition status

#### Run control
- preflight
- start run
- abort run
- run state
- errors and warnings

#### Live status
- laser tuned state
- emission state
- scan state
- HF2LI connected state
- timing system ready state
- recent events or warnings

This is enough for a valid starting interface.
Everything else should be hidden from the default view initially.

### In scope
- default landing experience for normal operation
- obvious navigation
- minimal visible controls
- clear status beside controls
- progressive disclosure of advanced detail
- explicit blocked, warning, fault, loading, and recovery states
- short review loops against the rendered UI

### Out of scope
- completing the full product UI
- building every expert or service feature
- deep analysis workflows
- implementing every backend action
- exposing every architecture detail in the main UI

### Minimal backend allowance
Only add the minimum honest support needed for the MVP to render and behave credibly:
- typed view-model adapters
- read-only helpers for session or storage inspection
- fixture-backed or simulator-backed summaries where authoritative data is not wired yet

Do not use this phase to justify backend expansion that the operator-facing UI does not immediately need.

## 7. Phase 2 — Results And Review Pass
After the operator MVP is reviewable, build the smallest useful persisted-session review path.

Scope:
- recent sessions
- selected session summary
- artifact and provenance visibility
- result summaries that help review the operator workflow
- iteration based on operator feedback from the MVP

`Analyze` may remain thin or secondary in this phase. Do not let analysis-first work overtake the operator path.

## 8. Phase 3 — Advanced And Service Surfaces
Move expert detail out of the default path.

Scope:
- advanced timing and routing controls
- guarded calibrated assumptions
- diagnostics and service actions
- maintenance and recovery tools

Exit condition:
- advanced users can reach needed detail without contaminating the primary `Operate` workflow

## 9. Phase 4 — Incremental Backend Wiring
Wire real actions in UI priority order, not architecture-diagram order.

Priority:
1. actions needed by the default `Operate` workflow
2. data needed by Results and recent-session review
3. actions needed by Advanced and Service surfaces

Rules:
- keep the UI thin
- keep one canonical path per workflow
- use simulators and typed boundaries by default
- do not wire speculative capabilities “just in case”

## 10. Phase 5 — Real-Device Hardening
After the reviewed UI and priority wiring are in place:
- validate the minimum supported hardware flows
- validate explicit fault handling
- validate disconnects, write failures, and partial-session behavior
- preserve vendor-reported errors and status

## 11. Phase 6 — Deeper Processing And Analysis
Deeper processing, analysis, comparison, and report work happens only after the operator-facing UI has been validated and the results path is useful.

That work must continue to operate on persisted artifacts and session truth, not transient UI state.

## 12. Codex Execution Rules
1. Plan against the active docs before coding.
2. Do not widen scope past the current phase.
3. Do not do speculative backend-first work ahead of the reviewed UI.
4. Keep `ui-shell` thin and presentation-only.
5. Preserve strong package boundaries and typed contracts.
6. Prefer simulator-backed work unless a phase explicitly requires hardware.
7. Surface blocked, warning, fault, loading, and recovery states explicitly.
8. Preserve session truth and reproducibility from the first wired run onward.
9. Do not add compatibility layers, hidden fallbacks, or duplicate workflow paths.
10. When the system cannot proceed, fail explicitly and record the reason.

## 13. What “Done” Means For The Current Direction
The current direction is successful only when:
- the next implementation pass is clearly operator-first UI MVP work
- the default UI answers “what do I do now?”
- advanced detail is moved out of the starting flow
- backend work follows UI need instead of speculative architecture expansion
- control-plane, data-plane, and package boundaries stay intact
