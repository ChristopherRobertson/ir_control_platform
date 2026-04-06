# AGENTS.md — IR Control Platform

## Document set
Use the repository documents this way:

- `AGENTS.md` defines the finished product and steady-state architecture.
- `REFACTOR.md` defines what to keep, rewrite, and delete while replacing the current implementation.
- `PLANS.md` defines milestone order, workstreams, and Codex execution mechanics.
- package-level `AGENTS.md` files refine local rules inside their directories.

## Purpose
This repository defines the finished control platform for the IR spectroscopy system.

The completed product must provide one coherent application for:
1. Device control
2. Experiment execution
3. Data collection
4. Data processing
5. Data analysis
6. Result output and visualization

This file describes the target product only. It is not a migration plan.

## Product goals
- Let an operator verify the current setup and press **START** to run a standard experiment with minimal friction.
- Let an advanced user open deeper controls for calibration, synchronization, timing, acquisition, and device-specific tuning.
- Present the system as one product, not a collection of unrelated device panels.
- Surface device status, vendor error codes, and run faults clearly.
- Support live operation and offline replay, reprocessing, comparison, and export from recorded runs.
- Use one canonical implementation path per workflow. No compatibility layers, hidden fallbacks, or workaround behavior.

## Scope boundary
- External room protections and vendor-enforced parameter limits are outside this software scope.
- The software must read device status, normalize vendor error conditions, stop or block runs when required, and record those failures clearly.
- The software must not attempt to emulate, supersede, or second-guess device-enforced limits.

## Target user experience
The primary workflow should be simple:

1. Confirm hardware availability and experiment validity
2. Review the active experiment configuration
3. Press **START**
4. Observe live progress and incoming data
5. Review processed results, analysis outputs, and exports

The application exposes two levels of interaction.

### Simple mode
Simple mode is the default operator experience.
- Shows only the settings required to validate and run an experiment
- Favors presets, validated defaults, and guided workflows
- Makes device availability, current configuration, saved-session target, and blocking faults obvious
- Avoids device-specific jargon when a product-level concept is available

### Advanced mode
Advanced mode is the expert workflow.
- Exposes calibration controls, synchronization parameters, acquisition tuning, and device-specific settings
- Supports non-standard experimental conditions without creating a separate application
- Uses the same underlying workflow and contracts as simple mode

## Primary product areas
The interface should be organized around user intent.

### Setup
- Experiment recipe selection and editing
- Presets and validated defaults
- Calibration selection
- Configuration review
- Start readiness and blocking issues

### Run
- Final verification
- Start, pause, abort, and completion states
- Progress, warnings, fault visibility, and run summary

### Hardware
- Connection state
- Health and diagnostics
- Device capabilities
- Vendor error visibility
- Recovery entry points

### Live Data
- Incoming acquisition streams
- Status indicators and live plots
- Run metadata and event timeline

### Analysis
- Processing configuration
- Derived metrics and experiment-specific analysis
- Comparison against baselines or prior runs

### Results
- Session browser
- Final visualizations
- Structured artifacts
- Export, report, replay, and reprocessing entry points

### Service / Maintenance
- Expert-only device controls
- Diagnostics and calibration tools
- Configuration snapshots
- Manual recovery actions

## End-state architecture
The product lives in a single repository with strong package boundaries.

```text
/ir_control_platform
  /contracts
  /platform
    /events
    /state
    /logging
    /errors
  /drivers
    /mircat
    /t660
    /labone_hf2
    /picoscope
    /picovna
  /experiment-engine
  /data-pipeline
  /processing
  /analysis
  /ui-shell
  /reports
  /simulators
  /e2e
  AGENTS.md
  REFACTOR.md
  PLANS.md
```

Package responsibilities:

### `contracts/`
Canonical shared definitions.
- Experiment recipe schema
- Device capability model
- Device configuration and status schema
- Validation and fault schema
- Run/session state model
- Event schema
- Session and artifact manifest
- Shared error taxonomy

### `platform/`
Cross-cutting infrastructure.
- Application events
- State management primitives
- Logging and audit infrastructure
- Error normalization and fault handling primitives

### `drivers/`
One package per device family.
- Connection and lifecycle management
- Capability and status reporting
- Configuration apply
- Execution commands
- Vendor error mapping
- Simulation-compatible interfaces

Driver packages remain modular so additional instrument families can be added without redesigning the product.

### `experiment-engine/`
The central orchestrator.
- Validates experiment recipes and run prerequisites
- Resolves required devices and capabilities
- Sequences device actions
- Owns run lifecycle state
- Emits normalized run events
- Stops or blocks on explicit faults

The experiment engine is the single writer of coordinated run state.

### `data-pipeline/`
Acquisition and persistence.
- Live data ingestion
- Timestamp and metadata normalization
- Session persistence
- Artifact indexing
- Replay support

### `processing/`
Reusable data transformations.
- Calibration application
- Corrections and filtering
- Alignment, normalization, averaging, and feature extraction
- Live and offline processing support

### `analysis/`
Experiment meaning and derived outputs.
- Derived metrics
- Quality checks
- Comparison and fitting workflows
- Domain-specific interpretation

### `ui-shell/`
The product surface.
- Navigation
- Application layout
- Product-level workflows
- Presentation of state, data, results, faults, and recovery actions

### `reports/`
Final outputs.
- Export formats
- Generated summaries and reports
- Reproducible result bundles

### `simulators/`
Development and verification support.
- Mock device implementations
- Recorded-run replay inputs
- Deterministic test fixtures
- Fault scenario fixtures

### `e2e/`
System integration coverage.
- Golden-path workflow tests
- Cross-package integration checks
- Simulator-backed scenarios
- Real-device smoke validation where required

## Core design principles

### Product-first, not device-first
The user experience is organized around running experiments and understanding results. Device-specific behavior belongs behind driver interfaces and expert surfaces.

### One orchestrator, one workflow path
The experiment engine owns coordinated behavior. The UI does not orchestrate hardware. Each major workflow has one approved implementation path.

### Device faults and vendor errors are first-class
The system must show what the devices reported, preserve those reports in the session record, and stop guessing when a fault occurs.

### Data pipeline separation
Acquisition, persistence, processing, analysis, and reporting are distinct concerns. Live workflows and offline workflows use the same core processing and analysis logic where practical.

### Fail fast and fail clearly
Do not hide invalid state behind retries, fallback branches, or silent correction. When the system cannot proceed, surface the reason explicitly and stop.

### Reproducibility
Every run must be traceable to:
- the experiment recipe
- device configuration and status snapshots
- calibration references
- timestamps and operator metadata
- produced artifacts and analysis outputs

### No legacy compatibility in the new product
The new application is not a compatibility shell around the previous UI. Preserve knowledge and assets where useful, but keep one clean architecture.

### Extensibility at boundaries, not through workarounds
Variation belongs at contracts and package boundaries such as drivers, presets, and analysis recipes. It does not belong as alternate code paths inside the same workflow.

## Collaboration model for agents
- Agents own packages or bounded contexts, not disconnected UI fragments.
- Cross-package collaboration happens through shared contracts and integration tests.
- Changes to shared schemas or run semantics belong in `contracts/` first.
- Package-level `AGENTS.md` files refine local implementation guidance and do not override this product definition.

## Required system qualities
- Deterministic run lifecycle handling
- Clear device status, error reporting, and recovery states
- Support for simulation and replay
- Session-centered persistence
- Reusable processing and analysis pipelines
- Clear, interpretable visual outputs
- Testable boundaries between UI, orchestration, drivers, and analysis

## Non-goals
- A UI that directly drives vendor APIs without orchestration boundaries
- A product organized primarily as separate per-device control screens
- Compatibility layers that preserve the old UI structure in the new application
- Silent retries, hidden workarounds, or duplicate ways to perform the same workflow
- Processing or analysis logic embedded exclusively in the UI layer
- Software logic that duplicates external room protections or vendor-enforced parameter limits

## Instruction boundary
Use this file to preserve the desired end-state product, architecture, and user experience.
Use `REFACTOR.md` for transition rules.
Use `PLANS.md` for milestone order and Codex execution.
