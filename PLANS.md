# PLANS.md — Active Development Sequence for the IR Control Platform

## 1. Objective
Build the IR control platform as one operator-usable application while preserving the architecture already established in `ir_control_platform`.

The active target is not “finish every subsystem.” The active target is to make the current implementation direction unambiguous:
- iteratively refine the operator-first `Experiment` workflow
- preserve control-plane and data-plane ownership
- let supporting backend work and secondary surfaces follow reviewed `Experiment` needs

## 2. Active Source Of Truth
Before implementation begins, use:
- `AGENTS.md` for product and fixed architecture
- `EXPERIMENT.md` for supported v1 control semantics
- `docs/operator_ui_mvp.md` for the current `Experiment` acceptance target
- `docs/ui_foundation.md` for active UI-shell rules
- `docs/package_boundaries.md` for package ownership and dependency direction
- `REFACTOR.md` for rewrite constraints
- package-level `AGENTS.md` files for local rules

`PLANS.md` is the only document that defines the active development sequence.
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

## 4. Experiment-First Development Loop
Use this loop for active work:

1. Refine the default `Experiment` workflow.
2. Review the operator flow in the rendered UI.
3. Add the minimum honest support needed in the owning backend package.
4. Re-review the `Experiment` workflow with the new support in place.
5. Promote stable detail outward only when it no longer belongs on the default `Experiment` path.

This loop is the sequencing authority for the current direction.
It does not change package ownership.

Partial `Results`, `Advanced`, `Service / Maintenance`, and `Analyze` scaffolds may exist during this loop, but they remain subordinate.
They must not pull priority away from the `Experiment` workflow.

## 5. Phase 0 — Documentation Reset
This pass aligns the repository around one active direction.

Exit criteria:
- one active UI-first strategy
- one active development sequence
- one explicit description of the current implementation direction
- obsolete phase-specific UI guidance removed or neutralized

## 6. Phase 1 — Operator-First UI MVP
This is the active implementation phase.

### Desired outcome
Deliver a usable, reviewable, intuitive starting interface that makes the default operator path obvious.

The UI must become a task UI, not an architecture UI.
The default experience must center on one `Experiment` page for the minimal baseline workflow.

Phase 1 is not a one-pass handoff.
It remains active until the `Experiment` workflow has been iterated enough that supporting detail can be promoted outward without re-litigating the primary operator path.

### Working loop
Within Phase 1, use this loop repeatedly:
1. refine the `Experiment` surface
2. review the operator flow in the rendered UI
3. add the minimum honest support needed in the owning backend package
4. re-review the `Experiment` workflow
5. move stable detail into secondary surfaces only after the default path stays clear

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
- current laser status

#### Lock-in / Acquisition
- connect and disconnect HF2LI
- a small set of key acquisition parameters only
- one operator-facing filter control
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

When the `Experiment` workflow reveals a missing capability, add only the minimum honest support in the owning backend package.
Do not use this phase to justify backend expansion that the operator-facing UI does not immediately need.

Partial secondary-surface scaffolds are allowed during Phase 1 when they help review the operator flow.
They remain subordinate and must not set priorities ahead of `Experiment`.

## 7. Phase 2 — Results And Review Pass
After the `Experiment` workflow is stable enough to stop carrying review detail on the default page, promote the smallest useful persisted-session review path into `Results`.

Scope:
- recent sessions
- selected session summary
- artifact and provenance visibility
- result summaries that help review the operator workflow
- iteration based on operator feedback from the MVP

`Analyze` may remain thin or secondary in this phase.
Do not let analysis-first work overtake the operator path.
Work that already exists on secondary surfaces still follows validated `Experiment` needs instead of advancing independently.

## 8. Phase 3 — Advanced And Service Surfaces
Extract expert detail out of the default path once repeated `Experiment` review makes it clear that the detail does not belong in routine operation.

Scope:
- advanced timing and routing controls
- guarded calibrated assumptions
- diagnostics and service actions
- maintenance and recovery tools

Exit condition:
- advanced users can reach needed detail without contaminating the primary `Experiment` workflow

## 9. Phase 4 — Incremental Backend Wiring
Consolidate and harden backend support only for interactions that the reviewed UI has already proven necessary.

Priority:
1. actions needed by the default `Experiment` workflow
2. data needed by Results and recent-session review
3. actions needed by Advanced and Service surfaces

Rules:
- keep the UI thin
- keep one canonical path per workflow
- use simulators and typed boundaries by default
- do not wire speculative capabilities “just in case”
- do not advance backend work independently of the reviewed `Experiment` workflow

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
- the `Experiment` iteration loop is clearly the sequencing authority for new work
- the default UI answers “what do I do now?”
- advanced detail is moved out of the starting flow
- backend work follows UI need instead of speculative architecture expansion
- control-plane, data-plane, and package boundaries stay intact
