# ui-shell

Presentation-facing shell, typed UI models, and WSGI app scaffolding for Setup, Run, Results, and Service.

- Owns: route scaffolds, page-state wrappers, shared UI primitives, and typed UI-facing service protocols.
- Depends on: `contracts`.
- Must not own drivers, persistence, processing, or analysis truth.

Phase 3A notes:

- The shell is server-rendered and dependency-light on purpose.
- Concrete simulator-backed adapters live outside this package so the UI can remain a thin client of typed boundaries.
- The default workflow is Setup -> Run -> Results, with Service intentionally scaffold-only.
