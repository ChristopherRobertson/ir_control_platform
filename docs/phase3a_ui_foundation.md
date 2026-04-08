# Phase 3A UI Foundation

## Scope

Phase 3A establishes the smallest useful UI/runtime foundation for the MIRcat + HF2LI golden path only.

This phase intentionally does **not**:

- add real vendor SDK calls
- broaden the recipe beyond MIRcat sweep mode
- add alternate experiment paths
- turn Service into a manual passthrough surface
- move orchestration, persistence, processing, or analysis truth into `ui-shell`

## Chosen stack

The Phase 3A shell uses:

- Python 3.12
- standard-library WSGI for the runtime entry point
- server-rendered HTML and CSS inside `ui-shell`
- `unittest` for stack-level coverage

### Why this fits the repo state

- The repository already had Python contracts and package boundaries, but no UI runtime baseline.
- Adding a JS toolchain in Phase 3A would have created parallel infrastructure before the package boundaries were proven.
- The standard-library stack keeps the slice dependency-light, easy to run, and easy to test while the simulator-backed control path is still being shaped.
- The rendering layer is intentionally replaceable because the page shell consumes a typed UI adapter boundary rather than driver or persistence implementations directly.

This is a Phase 3A delivery choice, not a permanent visual-platform commitment.

## App shell structure

Runtime bootstrap lives in `platform/src/ircp_platform/phase3a.py`.

The shell itself lives in `ui-shell/src/ircp_ui_shell/`:

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

Routes in Phase 3A:

- `/setup`
  - recipe summary, readiness rows, preflight summary
- `/run`
  - run-state timeline, event log, live-data shell
- `/results`
  - saved-session list, reopen entry point, manifest summary
- `/service`
  - expert-only scaffold with read-only device summaries

## Shared component ownership

Shared UI primitives are centralized in `ui-shell/src/ircp_ui_shell/components.py` and `ui-shell/src/ircp_ui_shell/models.py`.

Phase 3A includes reusable shells for:

- top status header with scenario switcher and workflow navigation
- status badges / pills
- readiness rows
- device summary cards
- preflight summary panel
- run progression timeline
- event timeline shell
- live data panel shell
- session summary cards
- fault / blocked / empty / unavailable wrappers
- section headers and panel layout

## Adapter boundary ownership

`ui-shell` consumes only typed UI-facing services.

The concrete simulator-backed adapter lives in `platform/src/ircp_platform/phase3a.py` and composes:

- `simulators`
  - deterministic MIRcat and HF2LI driver implementations plus scenario catalog
- `experiment-engine`
  - preflight validation, session creation, canonical run progression, run monitoring
- `data-pipeline`
  - authoritative in-memory session manifests, artifact registration, reopen flow

Boundary rules enforced by structure:

- `ui-shell` does not import `drivers`
- `ui-shell` does not import `data-pipeline`
- `ui-shell` does not import `processing`
- `ui-shell` does not import `analysis`
- session reopen goes through `SessionReplayer`
- run progression comes from `RunMonitor`

## Simulator-backed scenarios

Phase 3A seeds three deterministic scenarios:

- `nominal`
  - preflight passes, session is created, HF2 capture starts, MIRcat sweep runs, session completes
- `blocked`
  - preflight blocks because MIRcat is offline
- `faulted`
  - preflight passes, nominal start sequence begins, HF2 reports an explicit vendor fault during the run

The nominal scenario also seeds one saved completed session so Results and reopen flows can be exercised before later persistence work lands.

## Tests

Phase 3A test coverage lives in:

- `tests/test_phase3a_ui_foundation.py`

Coverage includes:

- root redirect and route sanity
- nominal Setup rendering
- blocked Setup state
- nominal start-run progression
- faulted run presentation
- saved-session reopen flow
- a static guard against direct `ui-shell` imports of drivers or persistence packages

## Remaining gaps for Phase 3B

Phase 3A intentionally leaves these as later work:

- richer recipe editing and validation affordances
- interactive polling or push updates instead of immediate deterministic progression
- real processing, analysis, and export generation from persisted artifacts
- real hardware adapters and vendor SDK integration
- expert Service actions beyond read-only scaffolding
- deeper Results visualization beyond session and artifact summaries

## Parallel work now unblocked

Because the shell, simulator scenarios, and adapter boundaries now exist, later work can split more safely across:

- Setup form and validation expansion
- Run monitoring detail and control refinement
- Results and replay detail views
- Service expert workflows
- real MIRcat driver implementation
- real HF2LI driver implementation
- session persistence hardening

Each of those can target a bounded package or page area without changing the Phase 3A app shell or runtime ownership model.
