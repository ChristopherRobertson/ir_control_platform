# platform

Cross-cutting runtime primitives shared by later implementations.

- Owns: event envelopes, normalized driver error wrappers, and the explicit Phase 3A simulator bootstrap entry point.
- Depends on: `contracts`.
- Must stay generic and free of device-specific orchestration.

Phase 3A bootstrap:

- `ircp_platform.phase3a.create_phase3a_simulator_app()`
- `python3 -m ircp_platform.phase3a`
