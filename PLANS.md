# PLANS.md — Codex Execution Plan for the IR Control Platform

## 1. Objective
Build the new control application for the IR spectroscopy system in the ir_control_platform repository. It must provide:
1. Device control
2. Experiment execution
3. Data collection
4. Data processing
5. Data analysis
6. Result output and visualization

The product must present a simple operator workflow for standard runs while still supporting advanced calibration and device-specific configuration for expert users.

This document is the execution plan for Codex.
- Product definition belongs in `AGENTS.md`.
- Rewrite rules belong in `REFACTOR.md`.

## 2. Operating principle
Do not treat this as a UI-only rewrite.

The target system has three architectural planes:
- **Control plane**: device orchestration, validation, run lifecycle, commands, typed runtime state
- **Data plane**: acquisition, session persistence, processing, analysis, export, replay
- **Presentation plane**: setup, run monitoring, live data display, analysis workflows, results browsing

The UI configures, monitors, and inspects the system.
It does not directly own vendor-SDK control logic, raw data collection, or authoritative run state.

## 3. Codex execution model

### Repository model
Use the ir_control_platform repository with strong package boundaries:
- `contracts`
- `platform`
- `drivers/*`
- `experiment-engine`
- `data-pipeline`
- `processing`
- `analysis`
- `ui-shell`
- `reports`
- `simulators`
- `e2e`

### Codex project model
In Codex App, register separate projects for the major subtrees rather than treating the entire repository as one undifferentiated project:
- root project for architecture and integration
- `contracts`
- `experiment-engine`
- `ui-shell`
- `data-pipeline`
- `processing`
- `analysis`
- `drivers`
- `reports`
- `simulators`
- `e2e`

### Thread model
Use:
- one orchestration thread at repo root
- one worktree per major workstream
- subagents only where work can be independently owned

### Required source-of-truth documents
Before implementation begins, Codex should rely on:
- `AGENTS.md` — final desired product and architecture
- `EXPERIMENT.md` — canonical experiment-control model and supported v1 control semantics
- `REFACTOR.md` — explicit keep/rewrite/delete rules
- `PLANS.md` — execution sequencing and milestone scope
- package-level `AGENTS.md` files for local rules where needed

## 4. Non-negotiable rules for Codex
1. **Plan before coding.**
2. **No direct UI-to-device orchestration.**
3. **No direct UI ownership of raw data persistence, processing, or analysis.**
4. **No package may reach across boundaries without an explicit contract.**
5. **Every device integration must have a simulator or stub implementation.**
6. **Every major feature must ship with tests and a validation path.**
7. **Every run must create a session record with reproducible metadata.**
8. **Device-reported faults and vendor errors must be preserved and surfaced clearly.**
9. **No compatibility layers, hidden fallback branches, or workaround code.**
10. **When the system cannot proceed, fail explicitly and record the reason.**

## 5. Final user-facing workflows

### Workflow A — Standard operator run
1. Open Setup
2. Confirm hardware availability and experiment validity
3. Review or load experiment preset
4. Review preflight summary
5. Press Start
6. Observe run progress and live data
7. Review processed results and analysis outputs
8. Export or save the session for later replay

### Workflow B — Expert calibration and troubleshooting
1. Open Service / Maintenance
2. Inspect one subsystem at a time
3. Tune or calibrate device-specific settings
4. Save calibration or configuration snapshot
5. Return to the normal Setup and Run workflow

### Workflow C — Offline scientific review
1. Open Results / Analyze
2. Load a prior session
3. Re-run processing on saved raw data
4. Compare against references or prior runs
5. Generate exports and reports without hardware connected

## 6. Workstreams and ownership

### Workstream 1 — Product architecture and contracts
**Owner:** Architecture agent

**Deliverables:**
- package map
- public interface map
- typed domain contracts
- state machines
- event schema
- artifact and session schema
- shared error taxonomy

**Must define:**
- `ExperimentRecipe`
- `ExperimentPreset`
- canonical T0-based pump/probe/acquisition timing model
- `DeviceCapability`
- `DeviceConfiguration`
- `DeviceStatus`
- `DeviceFault`
- `ValidationIssue`
- `RunState`
- `RunCommand`
- `RunEvent`
- `SessionManifest`
- `RawDataArtifact`
- `ProcessedArtifact`
- `AnalysisArtifact`
- `ExportArtifact`
- `CalibrationReference`
- `RunFailureReason`
- MUX route and PicoScope secondary-recording selection semantics

**Done when:**
- downstream teams can code against stable types
- contracts compile and are versioned
- cross-package dependency rules are documented

### Workstream 2 — UI information architecture and design system
**Owner:** UI shell agent

**Deliverables:**
- route map
- screen map
- navigation model
- wireframes
- component library
- state semantics
- visual status system

**Top-level product areas:**
- Setup
- Run
- Hardware
- Live Data
- Analysis
- Results
- Service / Maintenance

**Required design behaviors:**
- simple mode default
- advanced mode progressive disclosure
- persistent top status bar
- clear visibility of device status, blocking issues, and current session state
- run controls visible during active runs
- dense scientific UI without overwhelming standard operators

**Done when:**
- every required workflow has a screen path
- error, blocked, fault, offline, and loading states are designed
- the UI shell can be implemented against simulators

### Workstream 3 — Experiment engine and control plane
**Owner:** Control-plane agent

**Deliverables:**
- run lifecycle state machine
- orchestration service
- command handlers
- validation engine
- pause, resume, and abort flow
- device capability resolution

**Must own:**
- preflight validation
- coordinated sequencing
- master/slave timing sequencing
- pump/probe/acquisition relationship control
- authoritative run state
- operator command handling
- event emission

**Must not own:**
- presentation logic
- plot rendering
- report layout

**Done when:**
- a simulated full run can progress from preflight to completion
- faulted and aborted states are deterministic
- the UI can subscribe to state without embedding orchestration logic

### Workstream 4 — Data acquisition and session persistence
**Owner:** Data-plane agent

**Deliverables:**
- acquisition stream interfaces
- normalized sample and event model
- session writer
- metadata writer
- artifact indexing
- replay loader

**Must persist:**
- run or session ID
- recipe snapshot
- device status and configuration snapshot
- calibration references
- timing configuration relative to T0
- pump/probe/acquisition relationships
- selected digital timing references
- pump-shot count behavior
- probe continuous or synchronized mode
- MUX route selection
- PicoScope recording and trigger context
- operator metadata
- raw acquired data
- run events
- processing jobs and outputs
- analysis outputs
- exports

**Done when:**
- a run can be reopened later
- partial and faulted runs still preserve session data correctly
- replay works without live hardware

### Workstream 5 — Processing pipeline
**Owner:** Processing agent

**Deliverables:**
- processing pipeline abstraction
- calibration application
- corrections, filters, normalization, and alignment
- averaging and feature extraction
- deterministic job execution for live and offline contexts

**Must support:**
- processing presets
- reprocessing old raw sessions
- versioned processing recipes
- provenance of outputs

**Done when:**
- the same raw data can be processed repeatedly with identical results
- the pipeline runs both during and after acquisition

### Workstream 6 — Analysis and reporting
**Owner:** Analysis and reporting agent

**Deliverables:**
- analysis job layer
- derived metrics
- comparison tools
- fit or peak logic as required
- report and export service
- artifact manifest integration

**Must support:**
- run comparison
- baseline or reference overlays
- quality summary
- export bundles
- report regeneration from saved sessions

**Done when:**
- results can be reopened and exported without rerunning the experiment
- analysis uses persisted data instead of UI-local state

### Workstream 7 — Device adapters and simulators
**Owner:** Driver agents

**Deliverables per driver:**
- connect and disconnect
- status and health
- config apply
- command surface
- typed errors
- simulator implementation
- smoke tests

**Drivers in scope:**
- MIRcat
- T660-2 master timing
- T660-1 slave timing
- LabOne / HF2
- PicoScope 5244D
- Arduino-controlled MUX

**Future placeholder only:**
- PicoVNA
- direct OPO control

**Done when:**
- the experiment engine can run against simulator adapters
- each driver can be validated independently

### Workstream 8 — Integration, validation, and quality
**Owner:** Integration and QA agent

**Deliverables:**
- end-to-end simulator flows
- hardware smoke matrix
- regression suite
- scenario tests
- release checklist

**Must cover:**
- standard operator flow
- advanced calibration flow
- offline replay flow
- invalid configuration block
- device disconnect during run
- device-reported fault during run
- write failure during persistence
- export and report generation

**Done when:**
- all critical scenarios pass in simulation
- minimum supported hardware smoke passes

## 7. Delivery phases

### Phase 0 — Repo and Codex setup
**Goal:** make the repo operable for parallel Codex development.

**Tasks:**
1. Create or update root `AGENTS.md`.
2. Create or update `REFACTOR.md`.
3. Create `PLANS.md`.
4. Add package-level `AGENTS.md` files where local rules are needed.
5. Configure `.codex` local environments and setup scripts.
6. Add project actions for build, test, lint, typecheck, dev UI, and e2e.
7. Add simulator-first validation commands.

**Exit criteria:**
- a new Codex worktree can bootstrap and run checks automatically
- every major package has an obvious entry point and local guidance

### Phase 1 — Discovery and planning
**Goal:** produce a concrete implementation map before code changes.

**Tasks:**
1. Inventory the current codebase.
2. Inventory current UI routes, screens, and hidden coupling.
3. Inventory current device integrations.
4. Separate reusable knowledge from throwaway structure.
5. Identify the minimum viable golden path.
6. Produce a dependency graph and risk register.
7. Produce a screen inventory and data-flow map.

**Mandatory outputs:**
- architecture diagram
- dependency map
- route map
- data-flow map
- keep/rewrite/delete table
- milestone plan

**Exit criteria:**
- the team knows what will be kept, rewritten, or deleted
- the first vertical slice is chosen

### Phase 2 — Contracts and package scaffolding
**Goal:** establish stable boundaries before feature work.

**Tasks:**
1. Scaffold all target packages.
2. Create shared domain types.
3. Define event, state-stream, and command contracts.
4. Define session and artifact models.
5. Define driver interfaces.
6. Define processing and analysis job interfaces.
7. Define UI-facing query and command interfaces.

**Exit criteria:**
- no team is blocked waiting for missing types
- cross-package imports follow the approved direction only

### Phase 3 — Simulator-backed vertical slice
**Goal:** prove the architecture with one complete operator path.

**Scope of the first slice:**
- Setup page
- validation and readiness summary
- preset selection
- preflight summary
- Start
- Run screen with progress, log, and one live plot
- session creation and raw persistence
- completion screen
- basic result summary
- reopen saved session

**Constraints:**
- must run entirely on simulators
- must not depend on real hardware

**Exit criteria:**
- a user can complete the standard workflow end-to-end using only simulated devices
- the session can be reopened later

### Phase 3B — Supported v1 experiment model expansion
**Goal:** widen the simulator-backed and contract-backed slice from the MIRcat + HF2LI foundation to the full supported v1 experiment model defined in `EXPERIMENT.md`.

**Tasks:**
1. add a canonical T0-based timing block to the recipe, preflight, and run-state model
2. model T660-2 master timing, T660-1 slave timing, and Nd:YAG fire and Q-switch semantics without direct OPO control
3. add probe continuous versus synchronized operation and pump-shot-count-before-probe semantics
4. add MUX route selection and PicoScope secondary recording or trigger selection to the operator model
5. persist timing, digital-marker, MUX, PicoScope, and time-to-wavenumber mapping context in the session model
6. extend simulator scenarios and UI scaffolding to expose the expanded system without breaking package boundaries

**Exit criteria:**
- the typed contracts and simulator-backed UI reflect MIRcat, HF2LI, T660-2, T660-1, PicoScope, MUX, and Nd:YAG timing semantics
- the operator can configure pump, probe, and acquisition relationships without a device-first console
- direct OPO control remains out of scope

### Phase 4 — Data plane completion
**Goal:** make acquisition, persistence, replay, and artifact handling durable.

**Tasks:**
1. finalize session manifest schema
2. persist live run events
3. persist raw acquisition artifacts
4. implement artifact indexing and lookup
5. implement replay mode
6. support partial and faulted sessions
7. implement provenance tracking

**Exit criteria:**
- offline replay works from saved sessions
- result browsing no longer depends on live app state

### Phase 5 — Analysis and results workspace
**Goal:** make saved runs scientifically useful after acquisition.

**Tasks:**
1. implement Results browser
2. implement Analyze workspace
3. add raw versus processed overlays
4. add processing recipe editor
5. add comparison workflow
6. add export and report generation
7. ensure reprocessing without hardware

**Exit criteria:**
- an old run can be reopened, reprocessed, compared, and exported

### Phase 6 — Advanced controls and service surfaces
**Goal:** expose expert functions without polluting the standard workflow.

**Tasks:**
1. implement Hardware workspace
2. implement Service / Maintenance workspace
3. expose device diagnostics and calibration controls
4. implement reset, reconnect, and configuration snapshot tools
5. disable conflicting manual operations during active runs

**Exit criteria:**
- advanced users can reach device-specific capabilities
- the standard operator flow remains simple

### Phase 7 — Real-device integration and hardening
**Goal:** replace simulator-only confidence with real-system confidence.

**Tasks:**
1. integrate MIRcat in controlled smoke flows
2. integrate T660-2 master timing, Nd:YAG fire and Q-switch paths, and T660-1 slave timing
3. integrate LabOne / HF2 acquisition
4. integrate PicoScope secondary recording and Arduino-controlled MUX routing
5. validate device fault display and persistence behavior on real hardware
6. measure performance and latency
7. close test gaps and document known limits while keeping direct OPO control out of scope

**Exit criteria:**
- the minimum supported hardware stack passes smoke tests
- critical fault and recovery behavior is verified

## 8. Functional backlog Codex should implement

### A. Setup workspace
Must include:
- validation summary
- connection state
- calibration presence and status
- experiment recipe selection and editing
- preflight summary
- blocked, warn, and ready states
- simple versus advanced settings disclosure

### B. Run workspace
Must include:
- current run state
- current step or timeline
- progress
- event log
- live data panels
- pause, resume, and abort controls
- fault messaging
- session ID and save-state visibility

### C. Hardware workspace
Must include:
- subsystem status cards
- health summary
- device availability and capabilities
- fault explanations
- diagnostics entry points

### D. Live Data workspace
Must include:
- stream selection
- plot panels
- metadata overlays
- acquisition-rate or freshness indicators
- event and data correlation view

### E. Analysis workspace
Must include:
- raw and processed toggles
- pipeline controls
- derived metrics
- comparison tools
- provenance display
- saved analysis results

### F. Results workspace
Must include:
- session browser
- search and filtering
- report and export actions
- artifact inventory
- replay entry points

### G. Service / Maintenance workspace
Must include:
- manual device controls
- calibration tools
- diagnostics
- reset and reconnect tools
- expert-only warnings

## 9. Required domain contracts
Codex should define these contract groups early.

### Command contracts
- connect device
- disconnect device
- apply configuration
- run validation
- start run
- pause run
- resume run
- abort run
- save preset
- save calibration reference
- queue processing job
- queue analysis job
- export result bundle

### Query and subscription contracts
- current device status
- current validation status
- active recipe
- active run state
- live stream descriptors
- session list
- session detail
- artifact list
- processing job status
- analysis job status

### Event contracts
- device connected or disconnected
- validation changed
- device fault raised or cleared
- run state changed
- run progress updated
- sample batch persisted
- processing job started, completed, or failed
- analysis job started, completed, or failed
- export completed or failed

## 10. Session model requirements
Every run session must include:
- unique session ID
- timestamps
- operator metadata
- recipe snapshot
- device capability snapshot
- device configuration snapshot
- validation snapshot
- calibration references
- raw acquisition artifacts
- event timeline
- processing recipes and outputs
- analysis outputs
- export artifacts
- status such as `completed`, `aborted`, `faulted`, or `partial`

A session must be reopenable without the original live UI state.

## 11. Testing strategy

### Unit tests
- contract validation
- reducers and state machines
- data transforms
- analysis functions
- session manifest serialization

### Integration tests
- UI shell to mocked APIs
- experiment engine to simulator drivers
- data persistence and replay
- export generation

### End-to-end tests
- standard run on simulators
- faulted run with explicit failure state
- offline replay and reprocessing
- advanced calibration workflow

### Hardware smoke tests
- device connect and disconnect
- validation evaluation
- controlled low-risk run
- device fault propagation
- data persistence verification

### Acceptance tests
1. Operator can verify settings and press Start.
2. A run persists a recoverable session.
3. Live data is visible during the run.
4. Results can be reopened later.
5. Processing can be rerun without reacquisition.
6. Advanced settings are available without degrading the basic workflow.
7. Faults are explicit and do not silently lose session data.
8. Device-reported errors are visible in the UI and persisted in the session record.

## 12. Risk controls
Codex should explicitly manage these risks:
- the rewrite accidentally keeps direct hardware coupling in the UI
- acquisition and persistence remain trapped inside the UI
- no simulator coverage causes teams to block on hardware access
- package boundaries collapse under schedule pressure
- advanced controls leak into the main operator workflow
- run recovery and partial data persistence are overlooked
- analysis depends on transient in-memory UI state
- workaround code accumulates under time pressure

Mitigations:
- contract-first implementation
- simulator-first vertical slice
- review cross-package imports
- require session persistence in the first slice
- keep advanced and service pages separate from the default workflows
- reject workaround branches during code review

## 13. Root orchestration prompt template
Use this in the root orchestration thread:

```text
We are building a new IR spectroscope control platform.

Follow AGENTS.md as the product definition, REFACTOR.md as the rewrite authority, and PLANS.md as the milestone plan.
Do not preserve the old architecture unless REFACTOR.md explicitly says to keep the underlying asset or knowledge.

Approach this as a control-plane + data-plane + presentation-plane system, not a UI-only rewrite.

Task for this thread:
1. Review the repository and existing implementation.
2. Produce a concrete execution plan for the requested milestone.
3. Identify the exact files and packages to create or modify.
4. Spawn subagents only where work can be independently owned.
5. Wait for all subagents and consolidate the outcome.
6. Implement only the approved milestone scope.
7. Run validation commands and summarize results.

Constraints:
- no direct UI orchestration of hardware
- no UI-owned raw data persistence or processing logic
- use stable contracts between packages
- preserve reproducibility and session persistence
- surface device faults and vendor errors explicitly
- do not add compatibility layers, hidden fallbacks, or workaround code
- prefer simulator-backed work unless the milestone explicitly requires real hardware

Done when:
- the milestone acceptance criteria are satisfied
- tests pass or failures are explicitly explained
- the diff is organized and reviewable
```

## 14. Subagent prompt templates

### Architecture agent
```text
Review the repo and define the contracts and package boundaries required for the new control platform. Produce stable types, state models, dependency rules, and package scaffolding. Do not implement UI features yet.
```

### UI shell agent
```text
Implement the product shell, route map, page scaffolds, and reusable components for Setup, Run, Hardware, Live Data, Analysis, Results, and Service. Assume typed backends and simulators are available. Do not embed orchestration, persistence, or scientific logic in the UI.
```

### Control-plane agent
```text
Implement the experiment engine, validation evaluation, run lifecycle, command handling, and event emission. Provide a deterministic simulator-backed golden path. Fail explicitly on device-reported faults.
```

### Data-plane agent
```text
Implement session persistence, raw artifact storage, event timeline storage, replay support, and artifact indexing. Ensure sessions are reopenable independently of the live UI.
```

### Processing agent
```text
Implement processing pipeline abstractions, calibration application, deterministic transforms, the processing job model, and offline reprocessing capability.
```

### Analysis and reporting agent
```text
Implement analysis jobs, result derivation, comparison workflows, and report or export services using persisted sessions and artifacts.
```

### Driver agent
```text
Implement or wrap the device adapter for the assigned instrument, plus a simulator implementation and smoke tests. Keep the interface aligned to shared driver contracts. Return vendor errors clearly and avoid hidden retries or correction logic.
```

### Integration and QA agent
```text
Implement simulator-backed end-to-end scenarios, regression checks, and milestone acceptance validation. Focus on operator flow, replay, fault handling, and export correctness.
```

## 15. Suggested milestone order
1. discovery and contracts
2. package scaffolding
3. simulator-backed Setup → Start → Run → Complete path
4. session persistence and replay
5. analysis and results browsing
6. advanced and service surfaces
7. real-device smoke integration
8. hardening and release preparation

Do not begin with advanced device pages.
Do not begin with report polish.
Do not begin with hardware-specific deep controls.
Start with the operator golden path and the persistence model that makes it real.

## 16. What “done” means for the rewrite
The rewrite is successful only when all of the following are true:
- standard users can verify settings and run an experiment from a simple workflow
- expert users can reach advanced controls without contaminating the default flow
- all coordinated execution goes through the experiment engine
- data collection, persistence, processing, analysis, and exports exist outside the UI layer
- every run produces a durable session record
- saved sessions can be reopened and reanalyzed later
- simulator-backed development remains possible
- device faults and vendor errors are explicit, persisted, and testable
- the active codebase contains no legacy UI structure and no workaround branches
