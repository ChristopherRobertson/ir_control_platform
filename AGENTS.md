# AGENTS.md - IR Control Platform

## Active Source Of Truth
Use repository guidance in this order:

1. `AGENTS.md` defines the active product direction and architecture rules.
2. `REFACTOR.md` defines migration delete/replace rules.
3. `PLANS.md` defines the active milestone order.
4. `docs/package_boundaries.md` and package-level `AGENTS.md` files refine package ownership.

Historical docs are reference only when they conflict with this direction.

## Near-Term Product Direction
v1 is experiment-first, not device-first.

The first implementation is one generic, sample-agnostic vertical slice:

- experiment: `Single-Wavelength Pump-Probe`
- pump: YAG/OPO path
- probe: MIRcat at one wavelength
- acquisition: HF2LI sample/reference path
- timescales: Nanoseconds, Microseconds, Milliseconds

No sample-specific architecture, route names, state names, page names, or component names are allowed.

## V1 Scope
Only these pages exist in the primary workflow:

1. `Session`
2. `Setup`
3. `Results`

There is no separate run page. Run controls live at the bottom of `Setup`.

`Setup` uses this exact section order:

1. Pump settings
2. Timescale
3. Probe settings
4. Lock-In Amplifier settings
5. Run controls

Timescale is an acquisition-window regime. It is not a delay-scan grid. Do not expose step size, number of points, spacing mode, or grid controls in v1 UI or product docs.

Single-wavelength only means no wavelength list, wavelength sweep, queued spectral acquisition, scan controls, scan buttons, or MIRcat scan mode in v1 operator surfaces.

No real-time plotting is allowed in v1. Results are rendered from saved run data after acquisition or from reopened persisted runs.

No separate data acquisition section, preflight page, preflight section, generic all-device dashboard, generic multi-experiment product shell, broad service page, or advanced page is required for the initial delivery.

Advanced mode is deferred unless basic operation is blocked without it.

## Session And Run Definitions
Session and run are distinct persisted concepts.

A session is user-defined experimental context created before acquisition and capable of containing multiple runs. It contains experiment type, session name or ID, operator, sample ID or name, sample notes, experiment notes, created timestamp, and updated timestamp.

Wavelength and timescale are not session fields. They belong to setup and the run settings snapshot.

A run is one acquisition executed inside a session using a specific immutable settings snapshot. It contains run name or number, run notes, session reference, exact configuration snapshot, timescale regime, probe settings, pump settings, lock-in settings, raw data, processed data, start timestamp, end timestamp, completion status, and explicit fault/error state when aborted or failed.

The run settings snapshot is frozen when Run starts.

## Fixed Architecture
- `contracts/` owns authoritative session, run, recipe, setup, lifecycle, plotting, raw record, and artifact contracts.
- `experiment-engine/` owns validation, run lifecycle, coordinated actions, explicit stop/abort/fault behavior, and settings snapshot freeze.
- `data-pipeline/` owns session/run persistence, raw records, processed records, artifact manifests, and reopen/replay inputs.
- `processing/` owns reusable transforms such as sample/reference overlay and `-log(sample/reference)`.
- `analysis/` owns derived scientific logic when it becomes broader than reusable transforms.
- `reports/` owns export generation from persisted artifacts.
- `ui-shell/` owns navigation and presentation only.
- `drivers/*` hide device-specific integration and vendor errors.
- `simulators/` provides deterministic success and fault paths for every required real-device integration.

The UI must not orchestrate hardware, own persistence, own processing, own analysis truth, or import device/vendor code.

## Migration Rules
`Control_System` is reference material only under the parent workspace rules. Salvage hardware and scientific knowledge, not structure.

Do not port old UI screens, old navigation, device-first dashboards, callback flow, compatibility layers, fallback paths, or broad controls kept only for future possibilities.

The new repository remains single-path and fail-fast. Missing SDKs or hardware must produce explicit faults. Real drivers must not fake success.
