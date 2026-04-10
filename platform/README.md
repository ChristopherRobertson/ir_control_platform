# platform

Cross-cutting runtime primitives shared across control, data, and presentation layers.

- Owns: event envelopes, normalized driver error wrappers, and current simulator or demo bootstrap entry points.
- Depends on: `contracts`.
- Must stay generic and free of device-specific orchestration.

Current bootstrap entry points:
- `ircp_platform.create_phase3b_runtime_map()`
- `ircp_platform.create_phase3b_simulator_app()`
- `python3 -m ircp_platform.phase3a`
