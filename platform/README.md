# platform

Cross-cutting runtime primitives shared by later implementations.

- Owns: event envelopes and normalized driver error wrappers.
- Depends on: `contracts`.
- Must stay generic and free of device-specific orchestration.
