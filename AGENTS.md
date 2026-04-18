# AGENTS.md — IR Control Platform

## Active Source Of Truth
Use the repository documents this way:

- `AGENTS.md` defines the product, fixed architecture, and active guidance set.
- `EXPERIMENT.md` defines the supported v1 experiment model and control semantics.
- `docs/operator_ui_mvp.md` defines the current acceptance target for the `Experiment` workflow.
- `docs/ui_foundation.md` defines the active Python, server-rendered UI shell rules.
- `docs/package_boundaries.md` defines package ownership and dependency direction.
- `REFACTOR.md` defines what may be salvaged, rewritten, or deleted during the migration.
- `PLANS.md` defines the only active development sequence.
- Package-level `AGENTS.md` files refine local implementation rules.
- Historical reference docs such as `docs/repo_audit.md`, `docs/salvage_matrix.md`, `docs/migration_notes.md`, `docs/legacy_to_target_mapping.md`, and `docs/risk_register.md` are reference only. They do not set the current plan.

## Purpose
This repository defines the finished IR control platform and the active direction for completing it.

The product must remain:
- one application
- operator-usable
- single-path and fail-fast
- organized around the real operating workflow instead of device consoles or architecture exposition

## Fixed Architecture
- The control plane owns orchestration, validation, commands, and authoritative run state.
- The data plane owns sessions, artifacts, replay, and provenance.
- Processing, analysis, and reports remain outside the UI layer.
- The active frontend strategy is the current Python, server-rendered UI shell.
- React is not the active plan.
- Package boundaries remain strong and explicit. See `docs/package_boundaries.md`.

## Product Goal
The next visible product milestone is a usable, reviewable, intuitive starting interface for operators.

That interface must center on one default `Experiment` page for the minimal fixed-wavelength baseline workflow.

The default workflow should answer:
1. What session am I working in?
2. Is the system ready?
3. How do I control the laser and acquisition?
4. How do I start or abort a run?
5. What is happening right now?

## Default Operator Experience
The default path is a task UI, not an architecture UI.

It should emphasize:
- session and sample identity
- laser controls
- HF2LI acquisition controls
- run control
- live status
- recent events and warnings

It should hide deeper detail by default and move it into secondary surfaces:
- `Results`
- `Analyze`
- `Advanced`
- `Service / Maintenance`

Guarded calibrated assumptions are expert-only content. They may exist as dedicated advanced or service sub-surfaces, but they are not the starting operator interface.

## Active Development Direction
The active development loop is not:
- deeper processing or analysis work
- architecture expansion for its own sake
- exhaustive hardware or service coverage
- a giant shell full of internal system information

The active development loop is:
- iterative refinement of the default `Experiment` surface
- a simple default landing experience
- minimum controls for normal operation
- progressive disclosure for advanced detail
- short review loops that shape supporting backend work and secondary surfaces

Supporting backend work and secondary surfaces follow reviewed `Experiment` needs.
They do not advance independently of the default operator workflow.

## End-State Product Areas
The finished product should read as:
- `Experiment` for normal operation
- `Results` for persisted session review
- `Analyze` for persisted-session scientific review
- `Advanced` for expert timing, routing, and calibration tuning
- `Service / Maintenance` for diagnostics, recovery, and bench-owned workflows

Supporting views such as detailed hardware state, calibration inspection, and expanded live data stay subordinate to those surfaces. They do not become separate authorities or a device-first navigation model.

## Core Design Principles

### Product-first, not device-first
The user experience is organized around running experiments and understanding results. Device-specific behavior stays behind drivers and expert surfaces.

### One orchestrator, one workflow path
The experiment engine owns coordinated behavior. The UI does not orchestrate hardware. Each workflow has one approved implementation path.

### Explicit faults instead of bypass behavior
The system shows device-reported status and vendor errors clearly and stops cleanly when it cannot proceed.

### Reproducible session truth
Every run must remain traceable through session metadata, device snapshots, artifacts, and provenance.

### Extensibility at boundaries
Variation belongs in contracts, presets, drivers, processing recipes, and analysis recipes. It does not belong as alternate code paths inside the same workflow.

## Non-goals
- a UI that directly drives vendor APIs
- a product organized as per-device control consoles
- compatibility layers that preserve the old UI structure
- hidden retries, fallbacks, or duplicate workflow paths
- processing or analysis logic embedded exclusively in the UI
- speculative backend depth that the operator-facing workflow does not need yet

## Instruction Boundary
Use this file to preserve the required product outcome and fixed architecture.
Use `docs/operator_ui_mvp.md` for the current `Experiment` acceptance target.
Use `docs/ui_foundation.md` for active UI-shell rules.
Use `REFACTOR.md` for migration constraints.
Use `PLANS.md` for development order.
