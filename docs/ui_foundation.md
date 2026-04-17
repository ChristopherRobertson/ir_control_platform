# UI Foundation

## Purpose And Document Role
This document defines the active UI-shell rules for `ir_control_platform`.

Use it for:
- the active frontend strategy
- the runtime shell structure
- the route and page model
- shared component and page-state expectations
- presentation-plane boundary rules
- the current UI development order

Pair it with:
- `AGENTS.md` for product and architecture
- `docs/operator_ui_mvp.md` for the next-pass UI target
- `docs/package_boundaries.md` for ownership and dependency direction
- `EXPERIMENT.md` for supported v1 control semantics
- `PLANS.md` for phase order

## Active Frontend Strategy
The active UI strategy remains the existing Python, server-rendered shell.

The active stack is:
- Python 3.12
- standard-library WSGI for the runtime entry point
- server-rendered HTML and CSS inside `ui-shell`
- typed UI command, query, and subscription boundaries between `ui-shell` and backend packages

UI-first execution does not imply:
- replacing the current Python or server-rendered shell
- introducing React as the default assumption
- moving orchestration, persistence, processing, or analysis into the presentation layer

Future work should extend the existing shell, not replace it.

## Active UI Framing
This UI must read as a task UI, not an architecture UI.
The landing experience should make the default path obvious and keep advanced detail out of the way.

The default operator experience centers on one `Experiment` page.
That workflow should emphasize:
- session and sample identity
- laser controls
- HF2LI acquisition controls
- run control
- live status
- recent events and warnings

Secondary surfaces carry the complexity that should not dominate the starting interface:
- `Results`
- `Analyze`
- `Advanced`
- `Service / Maintenance`

Guarded calibrated assumptions belong in advanced or service-oriented expert surfaces, not in the default operator flow.

## Runtime Shell Structure
The active shell structure in `ui-shell/src/ircp_ui_shell/` remains:
- `app.py` for WSGI routing and POST/redirect flow
- `boundaries.py` for typed UI query, command, and subscription interfaces
- `models.py` for page and component view models
- `page_state.py` for loading, blocked, warning, fault, empty, and unavailable wrappers
- `components.py` for shared server-rendered layout and component shells

Future work should extend this structure instead of replacing it with a second UI runtime or a parallel shell.

## Route And Page Model
The operator-facing product should lead with `Experiment`.

The current route model should use:
- `/experiment` for the minimal baseline workflow
- `/results` for persisted-session review
- `/analyze` for persisted-session scientific review
- `/advanced` for expert tuning
- `/service` for diagnostics and maintenance

Internal route spelling may change later. What may not change is the operator-facing framing:
- `Experiment` is the default starting job
- advanced detail is progressive
- service work is clearly separate
- results and later analysis do not dominate the landing experience

## Shared Component And Page-state Model
Shared UI primitives remain centralized in `ui-shell/src/ircp_ui_shell/components.py` and `ui-shell/src/ircp_ui_shell/models.py`.

The active foundation should support:
- top status and workflow navigation
- status badges and readiness indicators
- section panels for routine controls
- explicit blocked, warning, fault, loading, recovery, empty, and unavailable states
- run progression and event views
- live status and live-data shells
- session and artifact summary cards

Extend these pieces deliberately so the UI stays coherent as `Experiment`, `Results`, `Advanced`, and `Service / Maintenance` deepen.

## UI Quality Rules
- one screen = one job
- the default page must answer “what do I do now?”
- labels should be action-based, not architecture-based
- show status beside controls
- hide read-only detail behind collapsible sections or secondary pages
- avoid giant tables unless the user is reviewing something specific
- optimize the default UI for the first five minutes of use
- advanced detail must not dominate the primary operator interface

## Boundary Rules
The presentation plane remains a consumer of typed boundaries.

`ui-shell` must:
- request queries, commands, and subscriptions through typed presentation-facing boundaries
- render authoritative control-plane and data-plane state clearly
- surface status, faults, warnings, saved-session context, and recovery entry points through the workflow

`ui-shell` must not:
- import `drivers`
- import `data-pipeline`
- import `processing`
- import `analysis`
- become the authoritative writer of run state, persistence, processing truth, analysis truth, or export truth
- introduce compatibility layers, hidden fallback branches, or alternate workflow paths

Authority stays where it already belongs:
- the control plane owns orchestration, validation, command handling, and authoritative run state
- the data plane owns sessions, artifacts, replay, and provenance
- processing owns deterministic transforms
- analysis owns deterministic interpretation and derived outputs
- reports own export bundles and generated outputs

## Current Development Order
The next UI work should proceed in this order:
1. build the operator-first `Experiment` MVP
2. deepen `Results` and recent-session review
3. move expert detail into `Advanced` and `Service / Maintenance`
4. wire backend actions in UI priority order

During the MVP pass, add only the minimum support required for honest rendering:
- typed view-model adapters over authoritative state
- minimal read-only helpers for session and storage inspection
- fixture-backed or simulator-backed summaries when clearly labeled

Do not treat the UI pass as approval for:
- speculative backend-first expansion
- processing or analysis work that exists only to populate screens
- UI-owned orchestration or persistence
- a second frontend stack
