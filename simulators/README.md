# simulators

Deterministic simulator bundles and scenario fixtures for the supported v1 control slice.

- Owns: simulator scenario catalogs, nominal and failure fixtures, and simulated device adapters.
- Depends on: `contracts`, `drivers`.
- Must not leak simulator-only shortcuts into production contracts.

Typical scenario classes:
- nominal
- blocked or preflight-failure scenarios
- warning or degraded scenarios
- faulted scenarios
