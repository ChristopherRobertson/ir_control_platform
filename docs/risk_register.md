# Risk Register

This register is scoped to the generic single-wavelength pump-probe v1 vertical slice.
Use `PLANS.md` for milestone order and `docs/refactor/salvage_matrix.md` for old-repository salvage decisions.

`Control_System` remains reference-only. Risks should be resolved by rewriting useful hardware and scientific knowledge into the correct `ir_control_platform` package, not by preserving old UI structure or compatibility paths.

| ID | Risk | Impact if ignored | Required mitigation | Validation needed | Priority |
|---|---|---|---|---|---|
| `R1` | The operator flow drifts back into device-first pages | V1 becomes a generic dashboard instead of the required Session / Setup / Results workflow | Keep only the three v1 pages and keep setup sections ordered Pump, Timescale, Probe, Lock-In Amplifier, Run controls | UI model and rendered-route tests for navigation and section order | High |
| `R2` | Session and run metadata are merged | Wavelength, timescale, and run snapshots can become editable session truth | Persist session metadata separately from draft run headers and immutable run settings snapshots | Contract, persistence, and workflow tests for save gating and snapshot freeze | High |
| `R3` | Timescale is implemented as a user-managed scan grid | Operators see forbidden step, point, or spacing controls and backend behavior becomes ambiguous | Treat timescale as an acquisition-window regime and derive capture windows, sample volume, and file-size estimates internally | Contract tests that acquisition plans expose no grid controls and setup validation blocks invalid plans | High |
| `R4` | UI code becomes a hardware or persistence authority | Page handlers can bypass engine validation, artifact manifests, or driver boundaries | Keep UI-shell as a command/query client; keep orchestration in `experiment-engine` and persistence in `data-pipeline` | Import boundary scans and integration tests through the runtime gateway | High |
| `R5` | MIRcat single-wavelength behavior accidentally carries scan controls forward | The v1 probe setup grows scan modes, arm/scan buttons, queues, or wavelength lists | Salvage only single wavelength, CW/pulsed emission, readiness, and fault semantics | UI tests for forbidden scan controls and driver tests for unsupported scan requests as explicit faults | High |
| `R6` | HF2LI data capture omits required raw channels | Later review cannot switch metric families or compute sample/reference ratio | Persist time plus sample/reference X, Y, R, and Theta for every run | Raw-record, export, and reopen tests | High |
| `R7` | File-size constraints are hidden until acquisition fails | Long acquisitions can exceed the practical HF2LI file-size limit | Derive an acquisition plan before Run and block invalid plans inline in Setup | Unit tests for derived plan validation and at least one faulted or blocked path | High |
| `R8` | Results require reopened hardware | Review and export become impossible after devices disconnect | Render results only from persisted run data, processed records, and metadata snapshots | Reopen tests with no live runtime/device state | High |
| `R9` | Simulator behavior diverges from real workflow contracts | Tests pass through shortcuts that hardware paths cannot use | Simulators must use the same contracts, run lifecycle, persistence, and artifact layout as real integrations | Simulator-backed happy-path and fault-path tests | High |
| `R10` | Broad future controls are added before v1 needs them | Product scope expands into advanced/service/multi-experiment surfaces | Defer wavelength scanning, multi-experiment workflows, broad service pages, and real-time plotting until after v1 acceptance | Documentation scan and UI tests for forbidden surfaces | Medium |
