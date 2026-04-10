# REFACTOR.md — Transition Rules for the IR Control Platform

## Document set
Use the repository documents this way:

- `AGENTS.md` defines the finished product.
- `docs/ui_foundation.md` defines the active UI foundation and presentation-surface model for ongoing work.
- `REFACTOR.md` defines how to replace the current implementation.
- `PLANS.md` defines milestone order, workstreams, and Codex execution.

## Purpose
This document governs the replacement of the current control implementation with the new control platform described in `AGENTS.md`.

Use this file to decide:
- what must be preserved,
- what must be extracted and rewritten,
- what must be replaced,
- what must be deleted,
- and what constraints apply during the rewrite.

This is not an in-place cleanup. It is a controlled replacement.

## Instruction precedence
When these documents coexist, use them in this order:

1. `AGENTS.md` defines the required end-state product and architecture.
2. `REFACTOR.md` defines what happens to the current codebase during the rewrite.
3. `PLANS.md` defines sequencing, workstreams, and milestone execution.

If there is a conflict about the final architecture, `AGENTS.md` wins.
If there is a conflict about treatment of current code, `REFACTOR.md` wins.
If there is a conflict about execution order, `PLANS.md` wins.

## Core direction
Treat the current implementation as a source of:
- hardware integration knowledge,
- vendor API usage patterns,
- scientific logic,
- data-format knowledge,
- error-code handling knowledge,
- useful datasets and fixtures,
- and practical lessons from bench use,

not as the structural template for the new product.

### The key decisions
- Preserve valuable knowledge and assets.
- Do not preserve the current UI architecture.
- Do not preserve direct UI ownership of orchestration, persistence, processing, or analysis.
- Complete the remaining work from the user-facing workflow inward so real interaction can determine what additional backend detail is actually needed.
- Do not introduce compatibility layers that keep the old structure alive inside the new product.
- Delete anything that does not fit the target architecture once its useful content has been extracted.

A copy of the current UI already exists outside the active refactor. Do not create an in-repo `legacy/` application or temporary archive tree.

## Remaining execution emphasis
For the remaining work after the completed Phase 3A shell foundation:

- execute in a UI-first / workflow-first order
- use Setup, Advanced, Calibrated, Run, Results, Analyze, and Service / Maintenance as the planning lens
- expose real saved settings metadata, raw outputs, provenance, and faults through the product surfaces early
- refine backend detail according to what the workflow surfaces actually need
- avoid speculative backend overbuild that has no validated user-facing requirement yet

This sequencing does not change authority:

- orchestration and authoritative run state still belong outside the UI
- sessions, artifacts, replay, and provenance still belong outside the UI
- processing, analysis, and reports still remain headless and reproducible outside the UI

Completed phase documents are historical records only. Use `docs/ui_foundation.md` for active UI guidance, not `docs/phase3a_ui_foundation.md`.

## Non-negotiable rewrite rules
1. **One implementation path per workflow.**  
   Do not keep alternate legacy paths, toggle-based compatibility modes, or fallback branches for the same product behavior.

2. **No legacy code in the new UI.**  
   The new UI may consume new drivers, contracts, and services. It must not embed inherited screen logic, callbacks, or view-model structures from the previous UI.

3. **Delete aggressively after extraction.**  
   Once useful logic, assets, or knowledge have been moved into the new structure, remove the old code from the active path.

4. **Preserve only what serves the target architecture.**  
   Vendor SDKs, low-level bindings, data readers, scientific formulas, datasets, and proven utilities may be retained. Structural UI code and workaround code should not be retained.

5. **No direct UI-to-device orchestration.**  
   Coordinated device control belongs in `experiment-engine/` and `drivers/`, never in pages or widgets.

6. **No UI-owned persistence, processing, or analysis.**  
   Those concerns move into `data-pipeline/`, `processing/`, `analysis/`, and `reports/`.

7. **Fail hard instead of bypassing.**  
   If a device reports a fault, a dependency is missing, or a required artifact cannot be written, surface the reason explicitly and stop the affected workflow.

8. **Prefer device-reported status and vendor errors over duplicated protection logic.**  
   Preserve error-code mappings and fault handling. Do not add software rules that attempt to replicate external protections or vendor-enforced limits.

9. **No silent retries or hidden correction.**  
   Retry behavior must be explicit and deliberate. Do not auto-adjust invalid settings to “make it work.”

10. **Every destructive change must be recorded.**  
    Keep a deletion ledger in the rewrite notes that says what was removed, what replaced it, and why.

## Classification labels
Every current module, script, asset, or subsystem must be assigned one of these labels during the initial audit:

- **KEEP-ASSET**  
  Preserve the item as a useful asset with minimal change. Examples: SDK headers, libraries, manuals, calibration files, sample datasets.

- **KEEP-CODE-WITH-BOUNDARY**  
  Preserve working low-level code that can live cleanly behind a new package boundary with minimal reshaping. Examples: a stable vendor binding or parser.

- **EXTRACT-AND-REWRITE**  
  Preserve the underlying knowledge or formulas, but rewrite the surrounding structure to fit the new architecture.

- **REPLACE**  
  Rebuild the subsystem from scratch using the new architecture. The old implementation is reference material only until replacement is complete.

- **DELETE**  
  Remove the item from the active codebase. Use this for obsolete UI structure, duplicate abstractions, dead prototypes, and workaround code.

These labels must appear in the repository audit and salvage matrix.

## What must be preserved

### 1. Vendor integration assets and communication knowledge
Preserve:
- vendor SDK headers, libraries, DLLs, shared objects, and setup notes;
- vendor manuals and protocol references checked into the repo or required by the project;
- known-good serial, USB, network, or SDK command usage patterns;
- device discovery, connection, timeout, and error-code mappings;
- units, conversion factors, capability limits, and valid parameter semantics;
- low-level wrappers that already communicate reliably with real hardware.

**Action:** move these into `drivers/`, `platform/`, or documented external dependency handling as appropriate. Remove UI coupling.

### 2. Scientific and experimental logic
Preserve:
- wavelength, timing, detector, and scan formulas;
- calibration application logic and calibration metadata rules;
- validated correction, normalization, filtering, alignment, averaging, and feature extraction logic;
- validated fitting and derived metric logic;
- experiment presets and default parameter values that carry scientific meaning.

**Action:** move reusable logic into `processing/`, `analysis/`, and `contracts/`. Preserve formulas even if the surrounding code is deleted.

### 3. Data and reproducibility assets
Preserve:
- historical run or session files used for verification or analysis;
- calibration files, baseline datasets, reference runs, and replay fixtures;
- existing file readers and writers that encode important format knowledge;
- metadata fields required to interpret historical runs.

**Action:** keep these readable throughout the rewrite. If the persisted format changes, provide import or conversion support instead of abandoning useful data.

### 4. Useful tests, diagnostics, and bench tools
Preserve:
- hardware smoke tests;
- communication diagnostics;
- device probing tools;
- dataset comparison tests;
- environment checks and dependency verification scripts.

**Action:** move them into `e2e/`, `simulators/`, or package-local test areas. Remove UI coupling.

### 5. Error and fault handling knowledge
Preserve:
- vendor error code mappings;
- device fault interpretation rules;
- known failure modes and their operator-facing meaning;
- existing status parsing that distinguishes normal, blocked, running, and faulted states.

**Action:** normalize this in `contracts/`, `platform/errors`, `drivers/`, and `experiment-engine/`.

## What must be reshaped

### 1. Device wrappers currently mixed into UI code
Preserve the communication knowledge, extract it from the UI, and move it behind driver interfaces.

**Target:** `drivers/*`

### 2. Validation and readiness logic spread across screens
Preserve the rules, centralize them, and expose them as typed validation results and run blockers.

**Target:** `contracts/`, `experiment-engine/`

### 3. Configuration and preset handling
Preserve field definitions and validated defaults, but normalize names, units, and semantics into canonical experiment recipes and presets.

**Target:** `contracts/`

### 4. Data acquisition buffering and saving
Preserve acquisition semantics, but remove presentation ownership and make saving session-centered.

**Target:** `data-pipeline/`

### 5. Processing and analysis tied to operator actions
Preserve the steps, but lift them into reusable packages callable during live runs and offline replay.

**Target:** `processing/`, `analysis/`

### 6. Export and reporting logic
Preserve required output formats, but centralize generation outside UI pages.

**Target:** `reports/`

### 7. Logging and event capture
Preserve useful messages, but normalize them into structured event types with explicit timestamps and severity.

**Target:** `platform/logging`, `contracts/`, `experiment-engine/`

## What must be replaced

### 1. The current control interface structure
Replace:
- the current navigation model;
- the current page layout if it is device-first or vendor-first;
- the current widget hierarchy as the organizational basis of the product;
- the current “screen owns logic” approach.

Do not port the old interface screen-by-screen.

### 2. UI-owned orchestration
Replace any code where the UI:
- coordinates multiple devices directly,
- sequences a run,
- tracks authoritative run state,
- decides when data collection starts or stops at the system level,
- or embeds abort and fault semantics in page logic.

**Target:** `experiment-engine/`

### 3. UI-owned persistence
Replace any code where the UI:
- writes raw data directly,
- constructs the only authoritative metadata,
- saves partial results in screen-specific formats,
- or defines the structure of a completed run.

**Target:** `data-pipeline/`

### 4. UI-owned processing and analysis
Replace any code where the UI:
- computes final scientific outputs that cannot be reproduced headlessly,
- stores analysis truth in widget state,
- or hardcodes scientific transforms in presentation code.

**Target:** `processing/`, `analysis/`, `reports/`

### 5. Hidden global state and workaround layers
Replace:
- global mutable state shared by screens;
- compatibility shims for old behaviors;
- hidden retry chains;
- alternate branches that exist only to keep old logic alive;
- background workers controlled only by UI object references.

## What must be deleted

### Delete immediately after audit
Delete from the active codebase as soon as classification is complete:
- obsolete screen and component trees;
- dead prototypes and abandoned experiments;
- duplicate wrappers for the same device behavior;
- temporary files, local caches, generated outputs, and checked-in convenience artifacts;
- machine-specific runtime directories.

### Delete once replacement exists
Delete when the replacement path is validated:
- direct vendor API calls from presentation code;
- screen controllers or view-models that embed orchestration;
- UI-triggered persistence code;
- UI-local processing and analysis pipelines;
- duplicated validation logic across forms;
- old route structures and workflow scaffolding.

### Delete regardless of prior usefulness
Delete these patterns rather than preserving them:
- compatibility code that keeps legacy flows alive;
- hidden fallback logic;
- automatic parameter adjustment to bypass failures;
- architecture-breaking shortcuts that reintroduce direct UI ownership of hardware or data authority;
- any in-repo `legacy/` tree created during the rewrite.

## What must never be ported as-is
Do not transplant these patterns unchanged into the new system:
- the current screen hierarchy;
- direct button-to-device command chains;
- business logic inside widgets or windows;
- run state inferred from what the UI is showing;
- save behavior driven by whichever tab initiated it;
- processing pipelines embedded in plotting components;
- global mutable state shared across screens;
- magic numbers, hidden units, or implicit calibration assumptions;
- workaround branches added to preserve old behavior.

## Required mapping from current concerns to target packages

| Current concern | Required action | Target package |
|---|---|---|
| Direct device communication | Keep behind clean boundaries or rewrite | `drivers/*` |
| Validation and run blockers | Centralize and type | `contracts/`, `experiment-engine/` |
| Run sequencing/orchestration | Replace current implementation | `experiment-engine/` |
| UI state and navigation | Replace | `ui-shell/` |
| Experiment form schemas and presets | Preserve and normalize | `contracts/` |
| Raw acquisition logic | Preserve and reshape | `data-pipeline/` |
| Session persistence and file writing | Replace with session-centered persistence | `data-pipeline/` |
| Calibration and correction logic | Preserve and move | `processing/` |
| Derived metrics, fitting, comparison | Preserve and move | `analysis/` |
| Reports and exports | Preserve formats, replace scattered implementation | `reports/` |
| Simulators and replay data | Preserve and expand | `simulators/` |
| Integration scripts and system tests | Preserve and reorganize | `e2e/` |

## Required rewrite phases

### Phase 0 — Audit and classification
Required outputs:
- repository inventory;
- salvage matrix with classification labels;
- dependency map;
- data-format inventory;
- error-code and fault inventory;
- test and tooling inventory;
- blocker list.

No broad deletion before this phase is complete.

### Phase 1 — Remove dependence on the old UI structure
Required actions:
- stop product development in the old UI;
- identify reusable bindings, formulas, datasets, and tests;
- identify throwaway structure and workaround code;
- identify the minimum viable replacement workflow.

### Phase 2 — Establish new package boundaries and contracts
Required actions:
- scaffold target packages;
- add package-level `AGENTS.md` files;
- define shared contracts;
- define session manifest and artifact model;
- define run-state and fault model;
- define driver and simulator interfaces.

### Phase 3 — Build the first simulator-backed vertical slice
Required slice:
- Setup;
- validation and preflight;
- start run;
- live state and one live data path;
- session creation and saving;
- completion summary;
- reopen saved session.

Do this without relying on the old UI.

### Phase 4 — Complete data, processing, and analysis boundaries
Required actions:
- connect session persistence;
- connect processing and analysis jobs;
- support replay and reprocessing;
- connect exports and result browsing.

### Phase 5 — Integrate real devices
Required actions:
- connect real drivers behind the new contracts;
- validate vendor error handling and fault display;
- validate write failures, disconnects, and partial sessions;
- validate minimum supported hardware flows.

### Phase 6 — Remove remaining old code
Required actions:
- delete old UI pathways;
- delete compatibility layers and duplicate logic;
- delete transient transition code that is no longer needed;
- confirm the active repo contains only the new architecture.

## Validation gates before deletion

### Before deleting current device-control code
Must have:
- replacement driver contract in place;
- simulator or stub path available;
- smoke validation against the real device or a bench harness where required.

### Before deleting current run-control code
Must have:
- experiment-engine replacement path;
- deterministic run-state transitions;
- validation, abort, and fault behavior covered by tests.

### Before deleting current persistence code
Must have:
- session-centered persistence working;
- ability to reopen a saved run;
- artifact manifest validated;
- partial and faulted run behavior defined.

### Before deleting current processing and analysis code
Must have:
- replacement pipeline implemented in reusable packages;
- comparison against reference outputs or golden datasets;
- provenance retained.

### Before deleting current export code
Must have:
- required output formats available or an approved replacement note;
- export ownership moved out of UI pages.

### Before deleting current UI workflows
Must have:
- operator path implemented in the new UI;
- expert path implemented or explicitly scheduled in `PLANS.md`;
- no blocking dependency on the old screen tree.

## Data migration rules
1. **Do not strand historical data.**  
   Existing runs, calibrations, and reference datasets must remain readable, importable, or deliberately retired with documentation.

2. **Version all new persisted formats.**  
   Session manifests and artifact descriptors must carry explicit versions.

3. **Preserve provenance.**  
   New processed or analyzed outputs must link back to raw inputs, calibration references, recipe versions, and code versions where practical.

4. **Prefer importers over manual conversion.**  
   If historical formats matter, write code to ingest them.

5. **Do not silently change units or semantics.**  
   All conversions of wavelength, time, trigger, gain, detector, or acquisition semantics must be explicit.

## Test and verification rules during the rewrite

### Contract tests
- schema validation;
- state transition validation;
- artifact manifest validation;
- fault and error normalization validation.

### Unit tests
- driver parsing and mapping logic;
- processing functions;
- analysis functions;
- validation evaluation;
- export generation.

### Simulator-backed integration tests
- Setup → Run → Complete flow;
- abort flow;
- device fault flow;
- disconnect flow;
- session persistence and reopen;
- replay and reprocess.

### Real-device smoke validation
Use where simulator fidelity is not enough, especially for:
- actual device communication;
- vendor error-code handling;
- timing behavior;
- measurement acquisition;
- persistence under real run conditions.

## Required rewrite deliverables
Codex must create and maintain:

1. repository audit report
2. salvage matrix with classification labels
3. dependency graph or module map
4. current-to-target mapping table
5. deletion ledger
6. compatibility or import notes for historical data
7. validation report for each major retirement of old code

## Definition of done for the rewrite
The rewrite is complete only when all of the following are true:

1. The previous control interface is no longer the active product path.
2. The new product path follows the architecture defined in `AGENTS.md`.
3. Preserved hardware logic lives behind drivers and orchestration boundaries.
4. The experiment engine owns coordinated run behavior.
5. Data collection, persistence, processing, analysis, and reporting no longer depend on UI ownership.
6. Historical and reference data remain usable, importable, or explicitly retired with documentation.
7. The active repository contains no legacy UI structure, no compatibility layers, and no workaround branches.
8. Device faults and vendor errors are explicit, recorded, and testable.
9. The new UI supports the operator workflow and expert workflow without reintroducing old coupling.
10. The repository contains a clear record of what was kept, rewritten, and deleted.

## Final instruction
Assume the old UI is not the blueprint.
Assume the old knowledge base is valuable.
Assume the correct outcome is a clean new architecture with selectively preserved assets and decisively removed legacy structure.
