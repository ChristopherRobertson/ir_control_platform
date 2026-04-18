# Operator UI MVP

## Purpose And Document Role
This document defines the living operator-facing acceptance target for the current `Experiment` iteration loop.

Use it with:
- `AGENTS.md` for product and architecture
- `PLANS.md` for development order
- `docs/ui_foundation.md` for active UI-shell rules
- `docs/package_boundaries.md` for ownership and dependency rules
- `EXPERIMENT.md` for supported v1 control semantics

This is the active acceptance target for the default `Experiment` workflow.

## Desired Outcome
The next real deliverable is a usable, reviewable, intuitive starting interface.

The UI must become a task UI, not an architecture UI.
The default operator experience centers on one `Experiment` page for the minimal baseline workflow.
That page remains the design driver for the current development loop.

The default page should answer:
1. What do I do now?
2. Is the system ready?
3. What can I safely control here?
4. What is the current state of the run?
5. What needs my attention?

## Default Experiment Workflow
The normal operator path is:
1. Identify the session and sample.
2. Connect and verify the laser and HF2LI.
3. Review readiness and preflight.
4. Start or abort the run.
5. Watch live status and recent warnings.
6. Reopen a recent session from a secondary surface when needed.

This default path should feel like one job, not a tour of architecture surfaces.

## Current Iteration Loop
Use this document as the acceptance target for repeated `Experiment`-first review:
1. refine the `Experiment` workflow
2. review the rendered operator flow
3. add the minimum honest support needed in the owning backend package
4. re-review the `Experiment` workflow
5. move stable detail outward only after it no longer belongs on the default page

## Minimum MVP Surface
The current `Experiment` loop should build and verify a starting operator interface with these sections.

### Session
- session name
- sample ID
- notes
- save session
- open recent session

### Laser
- connect and disconnect
- arm and disarm
- emission on and off
- tune to wavelength or wavenumber
- current laser status

### Lock-in / Acquisition
- connect and disconnect HF2LI
- a small set of key acquisition parameters only
- one operator-facing filter control
- start acquisition
- stop acquisition
- current acquisition status

### Run Control
- preflight
- start run
- abort run
- run state
- errors and warnings

### Live Status
- laser tuned state
- emission state
- scan state
- HF2LI connected state
- timing system ready state
- recent events or warnings

This is enough for a valid starting interface.
Everything else should be hidden from the default view initially.
Additional functionality should be added only after review.

## Secondary Surfaces
Complexity moves out of the default path and into secondary surfaces:

### Results
- recent sessions
- persisted summaries
- artifact and provenance visibility

### Advanced
- timing detail
- routing detail
- calibration-adjacent expert controls
- hardware detail that is not routine-use

### Service / Maintenance
- diagnostics
- recovery actions
- installation-owned workflows

### Analyze
- persisted-session scientific review
- comparison and reprocessing work

`Analyze` remains secondary until the default `Experiment` flow and basic results review are useful.
These surfaces may exist as early scaffolds, but they remain subordinate to `Experiment` while the default workflow is still being iterated.

## Layered Development Approach

### Layer 1 — Operator MVP
Build the small, intuitive primary interface for routine use first.

### Layer 2 — Advanced Surfaces
Move timing, routing, calibration, and service detail out of the default path.

### Layer 3 — Incremental Backend Wiring
Wire real actions in priority order only after the operator-facing controls are in place and reviewed.

The backend must follow the UI's needs. It must not lead them speculatively.

## Promotion Rules

### What Must Stay On `Experiment`
- routine session identity and save or reopen actions
- routine laser and HF2LI controls needed for normal operation
- preflight, start, abort, run state, faults, warnings, and live operator context
- the minimum status needed to answer “what do I do now?” and “what needs my attention?”

### What Moves To Secondary Surfaces Once Stable
- persisted-session review that no longer needs to stay on the default page
- timing, routing, calibration, and service detail that is not part of routine operation
- deeper artifact review, provenance inspection, and later scientific interpretation

### What Is Explicitly Deferred Until `Experiment` Stabilizes
- backend expansion added only for future pages
- deeper processing, analysis, comparison, and report work
- expert or service detail that would crowd the default operator flow

## UI Quality Rules
- one screen = one job
- the default page must answer “what do I do now?”
- labels should be action-based, not architecture-based
- show status beside controls
- hide read-only detail behind collapsible sections or secondary pages
- avoid giant tables unless the user is reviewing something specific
- the default UI should optimize for the first five minutes of use
- advanced detail must not dominate the primary operator interface

## Scope And Non-goals
The next pass is not trying to:
- complete the whole product UI
- build every expert or service feature
- build deep analysis workflows
- implement every backend action
- expose every architecture detail in the main UI

The immediate goal is:
- a usable, intuitive, minimal operator-facing starting interface
- easy to navigate
- incrementally expandable
- suitable for review and iteration

## Review Standard
The next pass succeeds when the rendered UI makes these points obvious without extra explanation:
- where routine operation starts
- what controls are available now
- what state the system is in
- what is blocked, warning, faulted, or ready
- where deeper detail lives without dominating the default path
