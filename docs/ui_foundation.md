# UI Foundation

## Purpose and document role

This document is the active UI foundation for `ir_control_platform`.

Use it for current and future UI work that builds on the existing shell. It is normative for:

- the active frontend strategy
- the runtime shell structure
- the route and page model
- shared component and page-state structure
- presentation-plane boundary rules
- how the remaining user-facing workflow should be completed

Historical Phase 3A delivery notes belong in `docs/phase3a_ui_foundation.md`. That file is a historical record only. It is not the active guide for current or future work.

Document relationship:

- `AGENTS.md` defines the finished product and steady-state architecture.
- `EXPERIMENT.md` defines the canonical experiment-control model and operator-facing control semantics.
- `docs/ui_foundation.md` defines the active presentation foundation and workflow surface model.
- `REFACTOR.md` defines rewrite and salvage constraints.
- `PLANS.md` defines milestone order and remaining execution sequencing.

## Active frontend strategy

The current UI strategy remains the existing Python, server-rendered shell.

The active stack is:

- Python 3.12
- standard-library WSGI for the runtime entry point
- server-rendered HTML and CSS inside `ui-shell`
- typed UI command, query, and subscription boundaries between `ui-shell` and backend packages

This remains the active frontend strategy for the remaining work.

UI-first execution does not imply:

- replacing the current Python/server-rendered shell
- introducing React as the default assumption
- moving orchestration, persistence, processing, or analysis into the presentation layer

The rendering layer may be replaceable in principle later, but no source-of-truth document currently authorizes a frontend-stack replacement. Future work should therefore extend the existing shell.

## Runtime shell structure

The current runtime bootstrap lives in `platform/src/ircp_platform/phase3a.py`.

The active shell structure in `ui-shell/src/ircp_ui_shell/` is:

- `app.py`
  - WSGI router and POST/redirect flow
- `boundaries.py`
  - typed UI query, command, and subscription interfaces
- `models.py`
  - page and component view models
- `page_state.py`
  - loading, blocked, fault, empty, and unavailable wrappers
- `components.py`
  - shared server-rendered layout and component shells

Future work should extend this structure instead of replacing it with a second UI runtime or a parallel shell.

## Workflow surface model

The remaining work should be organized around the actual user-facing surfaces:

- Setup
- Advanced
- Calibrated
- Run
- Results
- Analyze
- Service / Maintenance

Surface definitions:

### Setup
- Normal operator entry surface
- Recipe selection, validated defaults, readiness, and saved-settings review
- The place where the operator understands whether the system is ready to run

### Advanced
- Expert experiment-to-experiment tuning surface
- Detailed timing, acquisition, synchronization, and scan controls
- Part of the same workflow as Setup, not a separate device-first console

### Calibrated
- Bench-owned and installation-owned truth
- Calibration references, mapping defaults, and fixed scientific wiring assumptions
- Explicitly guarded and not treated as routine operator tuning

### Run
- Current-state execution surface
- Progress, warnings, faults, live status, live plots, and event visibility
- The place where active hardware state is monitored, not authored

### Results
- Persisted-session browser and run-summary surface
- Saved settings metadata, raw outputs, artifacts, provenance summary, and export entry points

### Analyze
- Persisted-session scientific review surface
- Reprocessing, comparison, overlays, derived metrics, and analysis affordances driven from persisted session truth

### Service / Maintenance
- Expert-oriented diagnostics, calibration tools, recovery actions, and configuration snapshots
- Not the normal operator workflow

Supporting views such as hardware detail and expanded live-data inspection belong within these surfaces, mainly inside Run and Service / Maintenance. They do not become separate authorities or a device-first navigation model.

## Route and page model

The current shell already proves the basic route structure with Setup, Run, Results, and Service scaffolds.

Future work should extend that shell with a phase-neutral page model:

- `/setup`
  - operator-facing setup and readiness flow
- `/setup/advanced`
  - expert tuning within the experiment workflow
- `/setup/calibrated`
  - guarded calibrated and installation-owned assumptions
- `/run`
  - active execution, live status, faults, and live data
- `/results`
  - persisted-session browser and result summaries
- `/analyze`
  - persisted-session scientific review and reprocessing
- `/service`
  - expert diagnostics and maintenance workflows

Exact URL spelling may change if needed, but the surface model and ownership rules must remain intact.

## Shared component and page-state model

Shared UI primitives remain centralized in `ui-shell/src/ircp_ui_shell/components.py` and `ui-shell/src/ircp_ui_shell/models.py`.

The active foundation includes reusable shells for:

- top status header and workflow navigation
- status badges and readiness indicators
- configuration and summary panels
- shared blocked, fault, loading, empty, and unavailable wrappers
- run progression and event timeline views
- live data panel shells
- session summary and artifact summary cards
- section headers and panel layout primitives

These shared pieces should be extended deliberately so the workflow stays coherent across Setup, Advanced, Calibrated, Run, Results, Analyze, and Service / Maintenance.

## Boundary rules

The presentation plane remains a consumer of typed boundaries.

`ui-shell` must:

- request queries, commands, and subscriptions through typed presentation-facing boundaries
- render authoritative control-plane and data-plane state clearly
- surface saved settings metadata, raw outputs, provenance, faults, and recovery entry points through the workflow

`ui-shell` must not:

- import `drivers`
- import `data-pipeline`
- import `processing`
- import `analysis`
- become the authoritative writer of run state, persistence, processing truth, analysis truth, or export truth
- introduce compatibility layers, hidden fallback branches, or alternate workflow paths

Authority stays with the existing architecture:

- the control plane owns orchestration, validation, command handling, and authoritative run state
- the data plane owns sessions, artifacts, replay, and provenance
- processing owns deterministic transforms
- analysis owns deterministic interpretation and derived outputs
- reports own export bundles and generated outputs

## Remaining execution guidance

The remaining work should now be completed in a UI-first / workflow-first order.

That means:

- finish the user-facing workflow surfaces first
- use real interaction with the product to decide which controls, metadata, visualizations, and analysis affordances are truly necessary
- make saved settings metadata and raw outputs visible through Results and Analyze early enough to guide later refinement
- use canonical sessions and artifacts created through those surfaces to shape later processing and analysis detail

This is a sequencing rule, not an architectural exception.

It does not authorize:

- moving orchestration into the UI
- moving persistence into the UI
- moving processing or analysis truth into the UI
- introducing a second frontend stack
- bypassing the control plane or data plane for convenience

## How future work should build on this foundation

Future work should:

- extend the existing Python/server-rendered shell
- keep the workflow surfaces legible to operators and expert users
- add backend detail only where the user-facing workflow actually needs it
- keep one canonical execution path per workflow
- preserve explicit blocked, fault, loading, and recovery states

Completed phase documents remain historical records. Active UI guidance for current and future work lives here.
