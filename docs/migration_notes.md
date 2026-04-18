# Migration Notes

Historical context only: these notes capture an earlier migration checkpoint.
Use `PLANS.md` for the active development sequence and current priorities.

## Working assumptions

- `Control_System` remains reference-only for the entire migration.
- At the time these notes were captured, `ir_control_platform` was still a boundaries-and-docs skeleton and needed architecture-first scaffolding before implementation.
- The new system is single-path and fail-fast.
- Vendor status, vendor error codes, explicit validation, and replayable artifacts matter more than preserving legacy UI behavior.

## Decisive keep / rewrite / discard summary

| Theme | Keep | Rewrite | Delete / Discard |
|---|---|---|---|
| Device integration | Vendor SDKs, manuals, error meanings, low-level transport code, node semantics | Driver implementations, orchestration surfaces, capability normalization | Raw command consoles as product UI, startup autoconnect, fallback scan paths |
| Workflow and UI | Workflow nouns, visible state categories, expert-only control needs | Product shell, route map, forms, results views | Device-first navigation, screen-owned orchestration, screen-owned persistence |
| Data and science | Raw files, converted fixtures, absorbance logic, session metadata concepts | Session model, artifact indexing, processing jobs, reports | Comment-only metadata as the final persistence model |
| Tooling and validation | Command transcript, manuals, replay fixtures | Smoke runner into simulator-backed e2e | Legacy HTTP assumptions and convenience runtime clutter |

## Preserve-as-knowledge notes

### Device behavior and vendor semantics

- Preserve MIRcat SDK load rules, connect order, arm, tune, emission, scan start, scan stop, and normalized status fields from `backend/src/modules/daylight_mircat/controller.py`.
- Preserve MIRcat vendor constants and raw error meanings from `docs/sdks/daylight_mircat/MIRcatSDKConstants.py` and related manuals.
- Preserve HF2LI device discovery, demodulator semantics, timestamp handling, recording cadence, and phase-zero behavior from `backend/src/modules/zurich_hf2li/controller.py` and `ZurichHF2LIView.tsx`.
- Preserve Pico range, timebase, trigger, and capture semantics from `backend/src/modules/picoscope_5244d/controller.py` and the checked-in Pico documentation.
- Preserve Highland transport grammar, trigger semantics, and channel delay or width handling from `backend/src/utils/highland_delay.py`, `highland_t660/*`, and `highland_t661/*`.

### Data, file, and scientific logic

- Preserve the old raw and converted file families in `Control_System/data`, `Control_System/backend/data/raw`, and `Control_System/backend/data/converted`.
- Preserve `convert_hf2li.py` logic for split detection, filename-derived wavenumber range, and absorbance calculation, but only as a processing seed.
- Preserve the meaningful run metadata fields currently collected in `ExperimentView.tsx` and comment headers in HF2 recordings, then normalize them into a session manifest.
- Preserve `tools/agent_commands.json` as scenario evidence for simulator and e2e design.

## Must not be carried forward

| Legacy structure or pattern | Why it must not survive | Replacement direction |
|---|---|---|
| Device-first routes and dashboard cards | The target product is workflow-first, not device-first | `ui-shell` routes for Setup, Run, Hardware, Live Data, Analysis, Results, and Service |
| `ExperimentView.tsx` as run authority | The UI must not sequence devices or own authoritative run state | `experiment-engine` commands and run state |
| Browser `sessionStorage` and `useMemoryState.ts` as durable truth | Hidden browser state breaks replay and restart behavior | Typed contracts plus persisted session and preset records |
| `daylight_mircat/user_settings.json` | Route-owned mutable settings create the wrong persistence boundary | Contract-backed presets or controlled configuration owned outside the route layer |
| Raw LabOne node passthrough as a product API | It leaks vendor-native internals into the product surface | Typed driver operations and expert-only workflow surfaces |
| MIRcat advanced or fallback sweep branches | Multiple execution paths violate the single-path rule | One supported scan path per approved workflow, explicit faults otherwise |
| Pico immediate-capture fallback | Hidden fallback behavior masks unsupported trigger conditions | Explicit trigger failure and supported preview modes |
| Startup auto-connect in routes and scripts | Hardware should not be connected as a side effect of booting the app | Explicit preflight connect and readiness flow |
| Raw command consoles in Highland screens | They bypass contracts and encourage vendor-native control as the main UI | Expert-only service actions backed by typed driver commands if truly needed |

## Historical data compatibility notes

- `data/hf2li_stream_*.txt` and `data/hf2li_scan_*.csv` should become replay fixtures and import-validation inputs.
- `backend/data/raw/*.txt` should become raw-ingest and replay fixtures in `simulators` and `e2e`.
- `backend/data/converted/*.txt` should become golden outputs for processing regression checks.
- The new session model must record enough metadata that future processing does not need to read live MIRcat state to recover the axis.
- Unsupported historical layouts should fail explicitly with a clear import error; they should not be silently coerced.

## Historical Next Milestone At Time Of Audit

This section is retained for context only.
It reflects what the migration notes recommended at the time they were written.
Current sequencing now lives in `PLANS.md`.

### Historical Phase 2 scope

1. Scaffold `contracts`, `platform`, `drivers`, `experiment-engine`, `data-pipeline`, `processing`, `analysis`, `ui-shell`, `simulators`, and `e2e`.
2. Define canonical contracts for recipes, device status and faults, readiness issues, run state, run events, session manifests, and artifact manifests.
3. Define driver interfaces for MIRcat and HF2LI first, with simulator counterparts or stubs.
4. Define one run command surface: preflight, start, stop, abort, and explicit failure reasons.
5. Define session and artifact ownership so raw capture, processed outputs, analysis outputs, and exports are separate and traceable.

### Historical non-goals for that checkpoint

- No product UI features beyond route and state scaffolds.
- No direct real-device bench integration work beyond contract design inputs.
- No Pico, Highland, Arduino MUX, or Continuum implementation unless a new blocker proves one of them is mandatory for the first slice.
- No compatibility layer, legacy bridge, or mirrored source tree from `Control_System`.

### Historical exit criteria for that checkpoint

- Downstream work can compile against stable package boundaries and contracts.
- The first simulator-backed vertical slice is fully specified.
- No new code path depends on `Control_System` at runtime.
- The single-path run model is documented clearly enough that Phase 3 can implement it without re-litigating ownership.
