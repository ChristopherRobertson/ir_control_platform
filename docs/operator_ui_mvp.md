# Operator UI MVP

## Purpose And Document Role
This document defines the operator-facing outcome for the next implementation pass.

Use it with:
- `AGENTS.md` for product and architecture
- `PLANS.md` for development order
- `docs/ui_foundation.md` for active UI-shell rules
- `docs/package_boundaries.md` for ownership and dependency rules
- `EXPERIMENT.md` for supported v1 control semantics

This is the active next-pass UI target.

## Desired Outcome
The next real deliverable is a usable, reviewable, intuitive starting interface.

The UI must become a task UI, not an architecture UI.
The default operator experience centers on one `Operate` workflow, even if the implementation still uses separate `setup` and `run` routes internally.

The default page should answer:
1. What do I do now?
2. Is the system ready?
3. What can I safely control here?
4. What is the current state of the run?
5. What needs my attention?

## Default Operate Workflow
The normal operator path is:
1. Identify the session and sample.
2. Connect and verify the laser and HF2LI.
3. Review readiness and preflight.
4. Start or abort the run.
5. Watch live status and recent warnings.
6. Reopen a recent session from a secondary surface when needed.

This default path should feel like one job, not a tour of architecture surfaces.

## Minimum MVP Surface
The next implementation pass should build a starting operator interface with these sections.

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
- start scan
- stop scan
- current laser status

### Lock-in / Acquisition
- connect and disconnect HF2LI
- a small set of key acquisition parameters only
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

`Analyze` remains secondary until the default `Operate` flow and basic results review are useful.

## Layered Development Approach

### Layer 1 — Operator MVP
Build the small, intuitive primary interface for routine use first.

### Layer 2 — Advanced Surfaces
Move timing, routing, calibration, and service detail out of the default path.

### Layer 3 — Incremental Backend Wiring
Wire real actions in priority order only after the operator-facing controls are in place and reviewed.

The backend must follow the UI's needs. It must not lead them speculatively.

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
