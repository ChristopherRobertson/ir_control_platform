# processing

Deterministic processing job boundaries that consume persisted raw artifacts.

- Owns: processing request and runner contracts.
- Depends on: `contracts`.
- Must not depend on UI state or live device ownership.
