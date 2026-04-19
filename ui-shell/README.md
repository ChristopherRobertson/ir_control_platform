# ui-shell

Presentation-facing shell, typed page models, and WSGI app scaffolding for the finished simulator-backed UI shell.

- Owns: shell navigation, page-state wrappers, shared server-rendered UI primitives, focused route rendering, and typed UI-facing service protocols.
- Depends on: `contracts` plus presentation-facing boundaries.
- Must not own drivers, persistence, processing, analysis, or export truth.

## Route Map

- `/experiment`: default mission-control surface for the canonical workflow
- `/setup`: focused preparation and preflight workspace
- `/run`: focused authoritative run-state and live-data workspace
- `/results`: persisted-session review, artifacts, trace previews, and export handoff
- `/analyze`: persisted-session scientific evaluation surface with explicit disabled actions where backend owners are not wired
- `/advanced`: expert timing, routing, and guarded-default review
- `/service`: diagnostics, calibration visibility, and controlled recovery surface
- `/operate`: compatibility redirect to `/experiment`

## Page-State Responsibilities

- `models.py` defines typed page models for `Experiment`, `Setup`, `Run`, `Results`, `Analyze`, `Advanced`, and `Service`.
- `page_state.py` defines explicit `loading`, `blocked`, `warning`, `fault`, `success`, `empty`, `unavailable`, and `recovery` states.
- `components.py` renders all shared shell/header primitives, shared panels, and route-local layouts from typed page-state models.
- `app.py` owns route dispatch, POST/redirect flow, and shell-owned navigation/scenario decoration only.

## UI Boundary Methods

`UiQueryService` now exposes:

- `get_header_status()`
- `get_operate_page()`
- `get_setup_page()`
- `get_run_page()`
- `get_results_page()`
- `get_results_download()`
- `get_advanced_page()`
- `get_analyze_page()`
- `get_service_page()`

`UiCommandService` continues to own typed experiment/session/device/run actions only. The shell still does not import device, persistence, processing, analysis, or report implementations directly.

## Major UI Decisions

- `Experiment` remains the default route and canonical workflow surface.
- `Setup` and `Run` are focused route projections of the same canonical workflow, not alternate orchestration paths.
- Hardware visibility, live data, and analysis are first-class in the shell, but each stays in the surface that owns its context.
- Unsupported capabilities remain visible only as explicit disabled actions with reasons.
- The shell remains server-rendered and dependency-light on purpose.

## Local Review

- Run locally: `python3 run_ui.py`
- Unit tests: `python3 -m unittest discover -s tests -p 'test_*.py'`
- Smoke test: `python3 e2e/smoke_experiment_page.py`
