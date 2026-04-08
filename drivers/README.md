# drivers

Typed device boundaries for real and simulated hardware adapters.

- Owns: base driver contracts plus MIRcat and HF2LI interfaces for the first vertical slice.
- Depends on: `contracts`, `platform`.
- Must not own cross-device orchestration or persistence.
