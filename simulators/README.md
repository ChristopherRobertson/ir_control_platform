# simulators

Deterministic simulator bundle contracts and Phase 3A scenario fixtures for the first MIRcat + HF2LI slice.

- Owns: simulator scenario catalogs, nominal and failure fixtures, and simulated MIRcat/HF2LI adapters.
- Depends on: `contracts`, `drivers`.
- Must not leak simulator-only shortcuts into production contracts.

Phase 3A scenarios:

- `nominal`
- `blocked`
- `faulted`
