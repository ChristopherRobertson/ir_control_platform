# Experiment Page Control-to-Backend Map

## Scope

This map is only for the current `/experiment` MVP surface in `ir_control_platform`.

Baseline assumed here:
- fixed MIRcat wavenumber control as the canonical run path
- Nd:YAG controls remain visible on the default page
- continuous HF2LI primary acquisition
- Pico kept out of the MVP operator flow
- simulator-backed `SimulatorUiRuntime` is the active adapter behind the page

Visible-but-not-baseline items are included only when they already appear on the current page, so future wiring work does not have to rediscover them.

## Status Key

- `exists and ready`: explicit route/query plus a usable simulator-backed backend path already exists
- `thin adapter needed`: contracts or backend pieces exist, but the current page still relies on draft state, note encoding, or direct driver calls instead of the canonical engine/data-pipeline path
- `fixture-backed only`: the page can show it from saved fixture/session data, but there is no operator write path on the page
- `intentionally deferred`: visible placeholder or omitted MVP behavior that the current page does not wire on purpose

## Where The Page Wires Today

Use these files first when wiring or extending the current Experiment page:

- `ui-shell/src/ircp_ui_shell/app.py`: GET `/experiment` and all POST actions
- `ui-shell/src/ircp_ui_shell/boundaries.py`: `UiRuntimeGateway` command/query surface
- `platform/src/ircp_platform/simulator_runtime.py`: `SimulatorUiRuntime`, the current page-to-backend adapter
- `platform/src/ircp_platform/page_builders.py`: page and panel assembly for the current Experiment, Results, Analyze, Advanced, and Service surfaces
- `platform/src/ircp_platform/operator_state.py`: draft state and recipe-shaping helpers used by the runtime adapter
- `platform/src/ircp_platform/bootstrap.py`: simulator runtime-map and app bootstrap entry points
- `experiment-engine/src/ircp_experiment_engine/runtime.py`: canonical preflight and run authority
- `data-pipeline/src/ircp_data_pipeline/boundaries.py`: session save, reopen, catalog, and replay boundaries
- `contracts/src/ircp_contracts/experiment.py`, `run.py`, `session.py`: current typed recipe, run, and session contracts

Important current split:

- `Run Preflight` and fixed-mode `Start Experiment` use the canonical `experiment-engine` plus `data-pipeline` path.
- Session save/open use `data-pipeline` through the runtime adapter.
- Most simple device actions on the page still terminate in `SimulatorUiRuntime` and call simulator drivers directly.

## Session Controls

All session form fields submit through `POST /experiment/session/save`, except reopen, which uses `POST /experiment/session/open`.

| Control | UI route/query | Backend route / function / boundary / adapter | Status | What it does now |
|---|---|---|---|---|
| Session name | `session_label` field on `/experiment`; persisted on `POST /experiment/session/save` | `IRCPUiApp._handle_post()` -> `UiRuntimeGateway.save_session()` -> `SimulatorUiRuntime.save_session()` -> `build_recipe().session_label` -> `InMemoryRunCoordinator.create_session()` -> `SessionStore.create_session_manifest()` | exists and ready | Saved as `SessionManifest.recipe_snapshot.session_label`; reopened by `apply_manifest_to_draft()`. |
| Sample ID | `sample_id` field on `/experiment`; persisted on `POST /experiment/session/save` | `save_session()` -> `_current_session_notes()` -> `SessionManifest.notes` -> `_load_draft_from_manifest()` | thin adapter needed | Persisted as note text `sample_id:<value>`, not a first-class session contract field. |
| Notes | `operator_notes` field on `/experiment`; persisted on `POST /experiment/session/save` | `save_session()` -> `_current_session_notes()` -> `SessionManifest.notes` -> `_load_draft_from_manifest()` | thin adapter needed | Persisted as note text `operator_notes:<value>`, not a dedicated structured session field. |
| Save Session | `POST /experiment/session/save` | `save_session()` -> `RunCoordinator.create_session()` -> `SessionStore.create_session_manifest()` -> `SessionStore.append_event()` | exists and ready | Creates a planned session before any run, snapshots current device configuration/status, and records bootstrap events. |
| Open recent session | GET `/experiment` populates select; `POST /experiment/session/open` reopens | `get_operate_page()` -> `SessionCatalog.list_sessions()`; `open_saved_session()` -> `SessionReplayer.open_session()` -> `_load_draft_from_manifest()` | exists and ready | Reopens saved session truth without live UI state. The recent list is seeded by saved fixtures and grows with newly saved sessions. |

## Operating Mode And MIRcat Controls

| Control | UI route/query | Backend route / function / boundary / adapter | Status | What it does now |
|---|---|---|---|---|
| Connect / Disconnect | `POST /experiment/laser/connect`, `POST /experiment/laser/disconnect` | `connect_laser()` / `disconnect_laser()` -> `scenario.bundle.mircat.connect()` / `.disconnect()` | exists and ready | Changes MIRcat connection state directly in the runtime adapter and refreshes preflight. No session or run write occurs. |
| Arm / Disarm | `POST /experiment/laser/arm`, `POST /experiment/laser/disarm` | `arm_laser()` / `disarm_laser()` -> `scenario.bundle.mircat.arm()` / `.disarm()` | exists and ready | Direct device-state action from the runtime adapter. Canonical fixed-mode `Start Experiment` also arms MIRcat again inside `RunCoordinator.start_run()`. |
| Emission On / Off | `POST /experiment/laser/emission/on`, `POST /experiment/laser/emission/off` | `set_laser_emission()` -> `scenario.bundle.mircat.set_emission_enabled()` | exists and ready | Explicitly toggles MIRcat emission state and updates status/preflight. |
| Wavelength / wavenumber input | Visible field is `tune_target_cm1` only | `tune_target_cm1` -> `_current_mircat_configuration()` -> `MircatExperimentConfiguration.single_wavelength_cm1` | thin adapter needed | The page currently exposes wavenumber only. There is no separate wavelength field or conversion adapter on the page. |
| Tune | `POST /experiment/laser/tune` | `tune_laser()` -> `_current_mircat_configuration()` -> `scenario.bundle.mircat.apply_configuration()` | exists and ready | Stages the fixed single-wavelength MIRcat configuration and updates status. It does not start a run by itself. |
| Fixed vs scan mode selector | `POST /experiment/laser/configure` | `configure_operating_mode()` -> runtime draft state -> later `_current_mircat_configuration()` / `_current_recipe()` | exists and ready | Switches the visible MIRcat controls and changes how the runtime shapes the draft recipe. Fixed mode is the only fully supported `Start Experiment` path. |
| Scan input fields | `scan_start_cm1`, `scan_stop_cm1`, `scan_step_size_cm1`, `scan_dwell_time_ms` on `/experiment` | `start_scan()` -> runtime draft state -> `_current_mircat_configuration()` -> `MircatStepMeasureScan(...)` | thin adapter needed | Visible on the page, but they currently drive a direct simulator scan action instead of the canonical run path. |
| Start Scan | `POST /experiment/laser/scan/start` | `start_scan()` -> `scenario.bundle.mircat.start_recipe()` | thin adapter needed | Starts a simulator-backed MIRcat scan directly from the runtime adapter. It does not go through `RunCoordinator.start_run()` or produce a canonical persisted experiment run. |
| Stop Scan | `POST /experiment/laser/scan/stop` | `stop_scan()` -> `scenario.bundle.mircat.stop_recipe()` | thin adapter needed | Stops the direct simulator scan path only. |
| Emission mode selector | `POST /experiment/laser/configure` via `emission_mode` | `configure_operating_mode()` -> `draft.emission_mode` -> `_current_mircat_configuration()` | exists and ready | The current page supports continuous-wave and pulsed MIRcat draft modes. |
| Pulse repetition rate | `POST /experiment/laser/configure` via `pulse_repetition_rate_hz` | `configure_operating_mode()` -> `draft.pulse_repetition_rate_hz` -> `_current_mircat_configuration()` | exists and ready | Visible when pulsed mode is selected. |
| Pulse width | `POST /experiment/laser/configure` via `pulse_width_ns` | `configure_operating_mode()` -> `draft.pulse_width_ns` -> `_current_mircat_configuration()` | exists and ready | Visible when pulsed mode is selected. |
| Duty cycle | `POST /experiment/laser/configure` via `pulse_duty_cycle_percent` | `configure_operating_mode()` -> `draft.pulse_duty_cycle_percent` | thin adapter needed | The page can display and persist the draft value, but the recipe ultimately derives the effective pulse configuration from rate and width. |

## Nd:YAG Controls

| Control | UI route/query | Backend route / function / boundary / adapter | Status | What it does now |
|---|---|---|---|---|
| On / Off | `POST /experiment/ndyag/on`, `POST /experiment/ndyag/off` | `set_ndyag_enabled()` -> draft state | thin adapter needed | The page keeps Nd:YAG state in the operator draft only. It does not yet drive canonical run orchestration. |
| Repetition rate | `POST /experiment/ndyag/configure` via `ndyag_repetition_rate_hz` | `configure_ndyag()` -> draft state | thin adapter needed | Visible and editable on the page, but still adapter-local. |
| Shot count | `POST /experiment/ndyag/configure` via `ndyag_shot_count` | `configure_ndyag()` -> draft state | thin adapter needed | Visible and editable on the page, but still adapter-local. |
| Continuous toggle | `POST /experiment/ndyag/configure` via `ndyag_continuous` | `configure_ndyag()` -> draft state | thin adapter needed | Visible and editable on the page, but still adapter-local. |

## HF2LI Controls

| Control | UI route/query | Backend route / function / boundary / adapter | Status | What it does now |
|---|---|---|---|---|
| Connect / Disconnect | `POST /experiment/hf2/connect`, `POST /experiment/hf2/disconnect` | `connect_hf2()` / `disconnect_hf2()` -> `scenario.bundle.hf2li.connect()` / `.disconnect()` | exists and ready | Direct HF2LI connection state toggle in the runtime adapter. Disconnect also clears the local standalone capture handle. |
| Filter control | `hf2_time_constant_seconds` field | `_current_hf2_acquisition()` -> `HF2DemodulatorConfiguration.time_constant_seconds` | exists and ready | This is the single operator-facing HF2 filter control in the MVP page. |
| Harmonic | `hf2_harmonic` field | `_current_hf2_acquisition()` -> `HF2DemodulatorConfiguration.harmonic` | exists and ready | Shapes the active HF2 demodulator configuration used by standalone start and canonical run start. |
| Sample / acquisition rate | `hf2_sample_rate_hz` field | `_current_hf2_acquisition()` -> `HF2DemodulatorConfiguration.sample_rate_hz` | exists and ready | Shapes the continuous HF2 acquisition profile for the current draft recipe. |

## Run Controls

| Control | UI route/query | Backend route / function / boundary / adapter | Status | What it does now |
|---|---|---|---|---|
| Preflight | `POST /experiment/run/preflight` | `run_preflight()` -> `SupportedV1PreflightValidator.validate()` -> `PreflightReport` | exists and ready | Canonical readiness gate. Uses the current draft recipe plus live device status and exposes blocked/warn/ready state back to the page. |
| Start Experiment | `POST /experiment/run/start` | `start_run()` -> `RunCoordinator.start_run()` -> `SessionStore.update_session_status()` / `append_event()` / `persist_raw_artifact()` / `finalize_session()` | exists and ready | This is the real fixed-baseline run path. It creates or reuses a saved session, arms timing, starts HF2 capture, starts MIRcat, persists HF2 raw artifacts, and finalizes the session. |
| Stop / Abort Experiment | `POST /experiment/run/abort` | `abort_active_run()` -> `RunCoordinator.abort_run()` -> `SessionStore.append_event()` / `finalize_session()` | thin adapter needed | The abort boundary exists, but the current simulator run plan completes synchronously inside `start_run()`, so the operator rarely has a live in-progress run to interrupt from the page. |

## Wiring Summary For Future Codex Tasks

Fully supported now on the baseline path:
- session name save/reopen
- MIRcat connect, disconnect, arm, disarm, emission toggle, fixed-mode tune
- MIRcat pulsed-mode draft controls
- Nd:YAG draft controls
- HF2LI connect/disconnect and core acquisition parameter fields
- canonical preflight
- fixed-mode `Start Experiment`

Thin adapter work remains for:
- making sample ID and notes first-class session fields instead of note strings
- adding a wavelength alias/conversion if the page should accept wavelength as well as wavenumber
- moving visible scan controls onto the canonical engine/run path
- wiring Nd:YAG page controls into canonical run orchestration instead of draft-only state
- making `Stop / Abort Experiment` useful against a genuinely long-lived active run

Intentionally deferred on the current Experiment page:
- pump controls
- Pico controls in the MVP flow
- standalone HF2 acquisition start/stop controls
