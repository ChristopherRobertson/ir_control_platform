# Package Boundaries

This document records the approved Phase 2 package direction for the MIRcat + HF2LI golden path. It is intentionally strict so later driver, engine, data, and UI work can land without re-litigating ownership.

## Approved dependency direction

```mermaid
flowchart LR
  Contracts["contracts"]
  Platform["platform"]
  Drivers["drivers"]
  Engine["experiment-engine"]
  Data["data-pipeline"]
  Processing["processing"]
  Analysis["analysis"]
  Reports["reports"]
  UIShell["ui-shell"]
  Simulators["simulators"]
  E2E["e2e"]

  Contracts --> Platform
  Contracts --> Drivers
  Contracts --> Engine
  Contracts --> Data
  Contracts --> Processing
  Contracts --> Analysis
  Contracts --> Reports
  Contracts --> UIShell

  Platform --> Drivers
  Platform --> Engine

  Drivers --> Engine
  Data --> Engine
  Data --> Processing
  Processing --> Analysis
  Analysis --> Reports

  Simulators --> Drivers
  Simulators --> Engine
  E2E --> Simulators
  E2E --> UIShell
```

## Package roles

| Package | Owns | Must not own |
|---|---|---|
| `contracts` | Canonical shared types, recipe shape, run state, session manifest, and artifact provenance | Device I/O, orchestration, persistence implementation, UI behavior |
| `platform` | Generic event and error primitives | Device-specific logic or workflow decisions |
| `drivers` | One typed adapter contract per device family | Multi-device coordination, persistence, UI state |
| `experiment-engine` | Preflight, coordinated start/abort flow, run state, device fault projection | Raw file writes, analysis, view logic |
| `data-pipeline` | Session creation, event persistence, artifact registration, reopen/replay | Driver logic, presentation logic |
| `processing` | Deterministic raw-to-processed jobs | Session truth or UI state |
| `analysis` | Deterministic processed-to-analysis jobs | Session truth or UI state |
| `reports` | Export generation from persisted artifacts | Live orchestration or screen-scrape output |
| `ui-shell` | Presentation-facing commands and queries only | Direct driver imports, persistence, processing, analysis authority |
| `simulators` | Deterministic simulator bundles and scenario catalogs | Production shortcuts |
| `e2e` | Scenario-level verification | Product runtime ownership |

## Golden-path command flow

1. `ui-shell` requests `run_preflight()` through a control-plane client.
2. `experiment-engine` evaluates `ExperimentRecipe` plus current `drivers` status and returns a `PreflightReport`.
3. `experiment-engine` requests session creation through `data-pipeline` before the run is considered live.
4. `experiment-engine` starts HF2LI capture, then starts the MIRcat sweep. This order is fixed for the first slice.
5. `data-pipeline` records session updates, raw artifacts, and run events continuously enough that a faulted run can still be reopened.
6. `processing`, `analysis`, and `reports` operate only on persisted artifacts and session manifests.

## Explicit bans

- No runtime imports or file reads from `Control_System`.
- No direct `ui-shell` imports of `drivers`, `data-pipeline`, `processing`, or `analysis` implementation packages.
- No startup auto-connect behavior.
- No raw node passthrough surface for HF2LI in the product contract.
- No fallback or alternate sweep path for MIRcat in the Phase 2 design.

## Phase 2 contract choices

- `ExperimentRecipe` is intentionally scoped to the golden path: one MIRcat sweep block plus one HF2 acquisition block.
- `DeviceConfiguration` is the normalized applied snapshot; driver command methods consume typed recipe sections and return normalized snapshots.
- `SessionManifest` is authoritative and versioned from creation onward, even if the run later faults or aborts.
- Raw, processed, analysis, and export artifacts are separate contract types with explicit provenance links.
