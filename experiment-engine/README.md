# experiment-engine

Single-path orchestration for the generic single-wavelength pump-probe v1 workflow.

- Owns: setup validation, run settings snapshot freeze, run lifecycle transitions, coordinated device sequencing, and explicit fault handling.
- Depends on: `contracts`, `drivers`, and persistence interfaces supplied by `data-pipeline`.
- Must remain the only coordinator of multi-device run state.
- Setup validation drives run-control gating without a separate readiness page or card.
