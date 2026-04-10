# ui-shell

Presentation-facing shell, typed UI models, and WSGI app scaffolding for the operator-first UI MVP.

- Owns: navigation, route scaffolds, page-state wrappers, shared server-rendered UI primitives, and typed UI-facing service protocols.
- Depends on: `contracts` plus presentation-facing boundaries.
- Must not own drivers, persistence, processing, analysis, or export truth.

Current UI framing:
- the default landing experience centers on one `Operate` workflow
- internal routes may still split that workflow across `/setup` and `/run`
- `Results`, `Advanced`, and `Service` are secondary surfaces
- `Analyze` remains secondary until persisted-session review is useful

Implementation notes:
- the shell remains server-rendered and dependency-light on purpose
- concrete simulator-backed adapters live outside this package so the UI stays a thin client of typed boundaries
- show status beside controls
- hide advanced detail by default
- use explicit labels when a surface is fixture-backed or not fully wired yet
- local review entrypoint: `python3 run_ui.py`
