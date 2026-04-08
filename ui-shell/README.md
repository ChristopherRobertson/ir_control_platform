# ui-shell

Presentation-facing command and query boundaries for Setup, Run, and Results workflows.

- Owns: thin UI-facing service protocols only at this phase.
- Depends on: `contracts`.
- Must not own drivers, persistence, processing, or analysis truth.
