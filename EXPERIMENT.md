# EXPERIMENT.md — Canonical Experiment-Control Model

## 1. Purpose and document role

This file is the canonical experiment-control definition for `ir_control_platform`.

It is normative for:

- what the operator controls
- what the system records
- how the supported v1 experiment is modeled
- how the control model maps into the default `Operate` workflow plus secondary Advanced, Calibrated, Results, Analyze, and Service surfaces

Document relationship:

- `AGENTS.md` defines the finished product, workflow-first architecture, and package boundaries.
- `docs/operator_ui_mvp.md` defines the current operator-facing `Experiment` acceptance target.
- `docs/ui_foundation.md` defines the active UI foundation and workflow surface model.
- `REFACTOR.md` defines migration constraints, salvage rules, and forbidden legacy patterns.
- `PLANS.md` defines sequencing, milestones, and execution mechanics.
- `EXPERIMENT.md` defines the experiment itself: the supported subsystem roles, timing semantics, data semantics, and operator-facing control surface.

Reference basis:

- Highest priority experiment-definition sources: `references/System Description.pdf` and `references/Wiring Table.pdf`
- Technical refinement sources used where relevant: `references/MIRcatSDKGuide.pdf`, `references/Highland Technologies T660 Programming Guide.pdf`, `references/Highland Technologies T660-1 Programming Guide.pdf`, `references/Zurich Insturments HF2LI User Manual.pdf`, `references/Zurich Instruments LabOne API User Manual.pdf`, `references/PicoScope 5000 Series Users Guide.pdf`, `references/PicoScope 5000 Series API Programmers Guide.pdf`, `references/PicoScope SDK Advanced Triggers.pdf`, `references/Arduino R4 Manual.pdf`, `references/ABX00080-datasheet.pdf`, and `references/Surelite NdYAG Laser Manual.pdf`

This document uses the names `T660-2` and `T660-1` from the reference set as the canonical names for the two delay generators. Legacy naming differences are not normative here.

## 2. Supported v1 system

### 2.1 First-class directly modeled v1 subsystems

The supported v1 experiment model includes the following as first-class product concepts:

- MIRcat QCL probe source
- HF2LI lock-in amplifier as the primary demodulation and recorded acquisition device
- T660-2 digital delay generator as the master timing source
- T660-1 digital delay generator as the slave timing source
- PicoScope 5244D as a secondary recorded and live-monitoring device
- Arduino-controlled multiplexor switch (MUX) as the oscilloscope signal-routing and trigger-selection system
- Nd:YAG pump timing semantics as a first-class experiment concept, mediated through T660-2 outputs

### 2.2 Supporting physical subsystems

The following matter to experiment interpretation but are not separate device-first control consoles in v1:

- Nd:YAG + OPO optical pump chain as the physical pump source
- two MCT detectors
- 50/50 beamsplitter
- optical mounts, translation stages, ground bus, and bench wiring

### 2.3 Placeholder future subsystems

The following are explicitly not directly controlled in v1, but remain valid future placeholders:

- direct OPO control
- broader future device additions not required by the supported v1 slice

Direct OPO control is out of scope for v1. The existence of the OPO in the physical system does not make it a first-class controlled subsystem in the current product slice.

## 3. Canonical subsystem roles

| Subsystem | Canonical role in the experiment | Required modeled relationships |
|---|---|---|
| MIRcat QCL | Probe source | Supports pulsed and CW emission, plus single-wavelength, sweep, step-measure, and multispectral operation. Receives synchronized timing from T660-1. |
| Nd:YAG + OPO chain | Physical pump source | The pump source exists physically as the Nd:YAG + OPO chain, but v1 models only the Nd:YAG timing semantics. Direct OPO control is deferred. |
| T660-2 | Master timing source and master clock provider | Provides the master clock to T660-1 and HF2LI. Drives Nd:YAG fire on `CHA`, Nd:YAG Q-switch on `CHB`, and drives the slave trigger path on `CHD`. |
| T660-1 | Slave timing source for MIRcat and related probe timing actions | Receives its clock from T660-2 and its trigger input from T660-2 `CHD`. Drives MIRcat `TRIG IN` on `CHA`, MIRcat process trigger on `CHB`, MIRcat laser output on/off on `CHC`, and exposes a slave timing marker to HF2LI on `CHD`. |
| HF2LI | Primary scientific signal path and primary recorded acquisition device | Receives detector sample and reference signals from the two MCT detectors, demodulates and filters them, receives timing markers from the timing chain, and exposes analog and digital monitor outputs used by the MUX. Remains the primary scientific recorder even when PicoScope recording is also enabled. |
| Arduino-controlled MUX | Oscilloscope signal-routing and trigger-selection system | Selects which analog and digital signals are sent to PicoScope channel A, channel B, and the external trigger input. |
| PicoScope 5244D | Secondary recorded and live-monitoring device | Records selected analog or digital monitor signals, supports validation and timing inspection, and can be triggered from a selected digital marker through the MUX. It may record simultaneously with HF2LI, but does not replace HF2LI as the primary scientific acquisition source. |

Essential wiring relationships from `references/Wiring Table.pdf`:

- T660-2 `CHA` -> Nd:YAG fire command
- T660-2 `CHB` -> Nd:YAG Q-switch command
- T660-2 clock output -> T660-1 clock input and HF2LI clock input
- T660-2 `CHD` -> T660-1 `TRIG IN`
- T660-1 `CHA` -> MIRcat `TRIG IN`
- T660-1 `CHB` -> MIRcat DB9 pin 4, process trigger
- T660-1 `CHC` -> MIRcat DB9 pin 5, laser output on/off
- T660-1 `CHD` -> HF2LI `DIO 1`
- Nd:YAG fixed, variable, and flashlamp sync outputs -> HF2LI `DIO 16`, `DIO 17`, `DIO 18`
- MIRcat `TRIG OUT`, scan direction, tuned or scan firing, and wavelength trigger -> HF2LI `DIO 19`, `DIO 20`, `DIO 21`, `DIO 22`
- HF2LI `AUX 1-4` -> analog MUX inputs for PicoScope monitoring
- HF2LI digital outputs used by the digital MUX boards -> PicoScope channel A, channel B, and external trigger routing

Interpretation notes:

- `references/System Description.pdf` and `references/Wiring Table.pdf` together imply that HF2LI is the relay point through which selected timing markers and auxiliary analog signals reach the MUX. The exact internal remap between HF2LI `DIO 16-22` inputs and the `DIO 2-8` outputs feeding the MUX is not spelled out; the canonical model only assumes that these markers are made available to the MUX through HF2LI.
- The wiring table shows both analog and digital MUX outputs tied to PicoScope channel A and channel B. The cleanest operational interpretation is that the Arduino-controlled enable lines make those routes mutually exclusive per scope input. The product model should therefore treat the MUX as a route selector, not as a simultaneous mixed-signal combiner.

## 4. Canonical timing model

The control model must let the operator set and review the timing relationship between pump firing, probe firing, and acquisition triggering on one shared timeline.

### 4.1 Neutral timing origin: T0

All canonical timing is defined relative to a neutral system `T0`.

`T0` is the start of one coordinated experiment timing cycle at the T660-2 master timing layer, before the programmed output events for that cycle assert. It is not defined as "pump zero" or "probe zero". It is the shared origin from which pump, probe, acquisition, and digital-marker timing are all expressed.

Because T660-1 is clocked by T660-2 and triggered from T660-2 `CHD`, T660-1-generated probe timing is still defined on the master `T0` axis. The slave does not introduce a second canonical zero.

### 4.2 Canonical timed events

The timing model must represent the following event families relative to `T0`:

- `pump_fire_command`: T660-2 `CHA` to the Nd:YAG fire input
- `pump_qswitch_command`: T660-2 `CHB` to the Nd:YAG Q-switch input
- `master_to_slave_trigger`: T660-2 `CHD` to T660-1 `TRIG IN`
- `probe_trigger`: T660-1 `CHA` to MIRcat `TRIG IN`
- `probe_process_trigger`: T660-1 `CHB` to MIRcat process trigger
- `probe_enable_window`: T660-1 `CHC` to MIRcat laser output on/off
- `acquisition_reference_event`: the event used to align or trigger acquisition
- `digital_marker[]`: selected timing markers from the Nd:YAG, MIRcat, HF2LI, and timing chain

The operator does not need to edit every low-level edge in normal use, but the model must preserve these semantics explicitly enough that UI, contracts, and orchestration all refer to the same timing truth.

### 4.3 Pump shots before probe

The UI must support the number of pump shots before the probe fires.

Canonical interpretation:

- `pump_shots_before_probe` is an explicit integer in the experiment model.
- It means that the system schedules a defined count of pump events before the probe-aligned measurement event is considered valid.
- The implementation may realize that count using T660 burst, trigger-divider, train, frame, or related timing features, but the contract must store the experiment intent, not just a vendor-native command sequence.

### 4.4 Continuous probe versus synchronized probe

Probe operation is orthogonal to the MIRcat spectral scan family.

- `continuous_probe`: the MIRcat is allowed to operate continuously across the experiment window. The model still records how continuous operation is entered, held, and exited, and which timing markers remain relevant.
- `synchronized_probe`: MIRcat timing is shot-linked through the T660-1 slave timing path and is represented as an explicit event or enable window relative to `T0`.

This distinction must be visible in the UI and persisted in the session record. It must not be inferred later from ad hoc device state.

### 4.5 Acquisition timing modes

The UI must support these acquisition timing modes:

- `continuous`: acquisition runs continuously over the experiment window and uses timing markers for annotation rather than for start gating
- `delayed`: acquisition start or capture window is defined by an explicit delay from `T0`
- `around_selected_signal`: acquisition is aligned to one or more selected digital timing markers

The selected digital markers must come from the canonical timing marker set, which includes at minimum:

- Nd:YAG fixed sync
- Nd:YAG variable sync
- Nd:YAG flashlamp sync
- MIRcat `TRIG OUT`
- MIRcat scan direction
- MIRcat tuned or scan firing
- MIRcat wavelength trigger

If a later implementation exposes more timing markers, they may extend this set, but must still be normalized back to the `T0` model and persisted by name.

## 5. MIRcat operating model

The MIRcat operating model has three separate axes that must not be collapsed into one control:

- emission mode: `pulsed` or `cw`
- spectral mode: `single_wavelength`, `sweep_scan`, `step_measure_scan`, or `multispectral_scan`
- probe timing mode: `continuous_probe` or `synchronized_probe`

Supported v1 MIRcat modes:

- pulsed
- continuous wave
- single wavelength
- sweep scan
- step-measure scan
- multispectral scan

Operator-visible mode selection must expose:

- whether the probe is pulsed or CW
- whether the experiment is a single-wavelength hold, a sweep, a step-measure scan, or a multispectral sequence
- whether probe operation is continuous or synchronized to the timing chain

Advanced scan parameterization includes items such as:

- scan bounds
- scan speed
- scan count
- bidirectional behavior
- step size or dwell behavior
- multispectral element lists
- preferred QCL selection
- pulse-rate and pulse-width parameters where applicable

Calibrated assumptions include:

- wavelength-to-QCL mapping assumptions
- time-to-wavenumber representation rules for scan modes
- bench-validated defaults that should not be edited during routine operation

## 6. User-adjustable controls by category

### 6.1 Setup

Setup is the normal operator control surface.

| Control family | Setup contents |
|---|---|
| MIRcat mode and scan controls | Select pulsed or CW operation, select single-wavelength, sweep, step-measure, or multispectral mode, and edit the minimum safe operator-facing parameters for that mode. |
| Pump/probe relationship | Select continuous versus synchronized probe operation and choose the number of pump shots before the probe fires. |
| Timing controls | Review and adjust the high-level pump, probe, and acquisition relationship relative to `T0` without exposing raw device command syntax. |
| Acquisition timing mode | Choose `continuous`, `delayed`, or `around_selected_signal`. |
| HF2LI acquisition choices | Choose the approved primary acquisition profile to record for the run. |
| MUX selection | Choose a named route set for PicoScope channel A, channel B, and the external trigger path. |
| Oscilloscope monitoring and recording selection | Decide whether PicoScope monitoring and secondary recording are enabled for the run. |
| Saved reference or configuration assumptions | Select an approved calibration or timing preset, but do not edit its underlying calibrated values here. |

### 6.2 Advanced

Advanced contains legitimate experiment-to-experiment tuning and hardware-programming controls.

| Control family | Advanced contents |
|---|---|
| Timing controls | Edit explicit `T0`-relative offsets for pump fire, pump Q-switch, slave-trigger timing, probe timing, and delayed acquisition windows. |
| Burst and pump-shot behavior | Edit the detailed timing-program parameters that realize `pump_shots_before_probe`, including burst, divider, train, or related timing-program choices. |
| MIRcat scan parameterization | Edit scan speed, scan count, bidirectional behavior, preferred QCL, step spacing or dwell, and multispectral element details. |
| MIRcat pulse controls | Edit pulse-rate, pulse-width, and related trigger-sensitive operating parameters where the selected mode supports them. |
| Selected digital timing references | Choose which digital marker drives acquisition alignment, oscilloscope triggering, and diagnostic timing views. |
| HF2LI acquisition choices | Edit demodulator selection, transfer enablement, sample rate, component selection, and monitor-output choices. |
| Oscilloscope monitoring and recording selection | Edit PicoScope capture duration, timebase, trigger thresholds, trigger mode, and recording detail. |
| MUX route selection | Edit the explicit signal routing from the available analog and digital sources to PicoScope channel A, channel B, and external trigger. |

Nd:YAG timing behavior belongs here as part of experiment timing and timing-program configuration. It must not appear as a separate raw vendor-control console.

### 6.3 Calibrated

Calibrated contains values that should normally remain fixed once the system is installed and validated.

| Control family | Calibrated contents |
|---|---|
| Time-to-wavenumber calibration | The mapping needed to represent MIRcat scan-mode data on a wavenumber axis while preserving raw-data status. |
| Timing and mapping defaults | Bench-validated default timing offsets, marker naming, and safe channel-role assumptions. |
| Signal-route definitions | Default mapping from HF2LI digital and auxiliary outputs through the MUX to PicoScope inputs and trigger path. |
| Detector and acquisition identity | Sample versus reference detector assignment, HF2LI input identity, and other fixed scientific wiring assumptions. |
| Saved reference or configuration assumptions | Approved configuration sets, calibration references, and installation-specific assumptions that should change only through controlled service workflows. |

## 7. UI mapping by product area

The product surface must remain experiment-first, not device-first.

| Product area | What must be visible there | What it must not become |
|---|---|---|
| Setup | Experiment mode, pump/probe/acquisition relationship, `T0` timing summary, pump-shot count, probe mode, acquisition mode, calibration selection, MUX route summary, PicoScope secondary-recording summary, saved-settings summary, and blocking readiness issues. | A collection of separate device panels. |
| Advanced | Detailed timing controls, acquisition tuning, selected digital timing references, MIRcat scan parameterization, and other legitimate experiment-to-experiment expert controls. | A separate device-first console or a place that bypasses the canonical experiment model. |
| Calibrated | Bench-owned calibration references, mapping defaults, signal-route assumptions, detector identity assumptions, and installation-owned truth that should change only through controlled workflows. | Routine operator tuning or an ad hoc escape hatch around validated defaults. |
| Run | Active run state, event log, primary live HF2LI traces, selected PicoScope monitor traces, current timing summary relative to `T0`, selected digital markers, active faults, and hardware state needed to monitor the current execution. | The authoritative owner of orchestration or persistence. |
| Results | Raw HF2LI data, processed data, saved settings metadata, session provenance, recorded PicoScope context, final visualizations, and raw or processed overlays. | A live-device dependency or a place that reconstructs missing timing context from memory. |
| Analyze | Reprocessing controls, comparison tools, derived metrics, provenance-aware overlays, and persisted-session scientific review affordances. | UI-local analysis truth that cannot be reproduced from persisted artifacts. |
| Service | Calibration tools, diagnostics, timing verification aids, configuration snapshots, and controlled recovery actions for MIRcat, HF2LI, T660 master/slave timing, MUX, and PicoScope. | A raw vendor passthrough console or a replacement for the normal Setup and Run path. |

Expanded live-data inspection and hardware detail may exist inside Run and Service, but they are supporting views inside the workflow surfaces, not separate product-defining authorities.

## 8. Execution note for remaining work

The remaining user-facing development should use these surfaces as the organizing lens.

That means:

- complete the interactive workflow so the team can see what the product actually needs
- expose saved settings metadata, raw outputs, and persisted provenance through Results and Analyze early
- let canonical saved sessions and artifacts guide later refinement of processing and analysis affordances

This does not change scientific or architectural ownership:

- the experiment model remains authoritative outside the UI
- run orchestration remains outside the UI
- session truth remains outside the UI
- processing and analysis remain reproducible from persisted artifacts

## 9. Data semantics

### 9.1 Raw data

Raw data is defined as the output signals from the MCT detectors after they have been demodulated and filtered by the HF2LI.

Consequences:

- HF2LI demodulated and filtered outputs are the primary scientific raw data.
- The time-to-wavenumber conversion used to represent MIRcat scan-mode data remains part of raw-data representation, not a processed-data step.
- Any further modification to those raw signals is processed data.

### 9.2 Secondary PicoScope data

PicoScope data is:

- a secondary recorded source
- a live monitoring source
- a timing-validation source
- an overlay-capable source

The supported v1 system can acquire HF2LI and PicoScope data simultaneously. That does not change the primary or secondary distinction.

PicoScope data is not the primary scientific raw-data authority. It may still be persisted as auxiliary raw-monitor artifacts, but it must remain clearly distinguished from the HF2LI primary raw data.

### 9.3 Processed data

Processed data is any further modification applied to the primary raw data or to auxiliary recorded data after raw acquisition representation has been established.

This includes, for example:

- background subtraction
- sample/reference ratioing
- normalization
- filtering beyond the HF2LI demodulation/filter stage
- averaging, alignment, correction, and similar transforms

### 9.4 Analysis output

Analysis output is any derived scientific interpretation built from raw or processed artifacts, such as:

- quality metrics
- comparisons
- fits
- derived parameters
- pass or fail summaries

### 9.5 Exported output

Exported output is any generated report, bundle, table, figure, or external-delivery artifact produced from persisted raw, processed, or analysis artifacts.

### 9.6 Overlay behavior

Overlay behavior is conceptual, not implementation-specific:

- Results may overlay primary HF2LI traces with secondary PicoScope traces and selected digital timing markers on a common aligned axis.
- Such overlays are interpretive views built from persisted provenance.
- An overlay must never redefine PicoScope data as the primary scientific raw-data truth.

## 10. Session provenance requirements

Every session for this experiment model must persist enough information to reproduce what was configured and what was observed.

At minimum, the session record must include:

- MIRcat emission mode and scan definition
- timing configuration relative to `T0`
- explicit pump/probe/acquisition relationship
- selected digital timing references
- pump-shot count behavior
- probe continuous versus synchronized mode
- MUX route selection
- oscilloscope recording and trigger context
- HF2LI recorded context
- time-to-wavenumber mapping context for scan modes
- device status and configuration snapshots
- raw HF2LI artifacts and any secondary PicoScope monitor artifacts
- run events and fault events

The session model must be sufficient for later replay, reprocessing, timing interpretation, and result review without reading live MIRcat state, live timing state, or ad hoc UI memory.

## 11. Explicit non-goals and placeholders

The following are not in scope for v1:

- direct OPO control
- legacy-style device-first UI
- raw vendor passthrough control consoles
- fallback or compatibility paths
- unsupported future device expansion in the current slice

Placeholder note for future work:

- A future phase may introduce direct OPO control only as a new first-class subsystem with its own contracts, timing semantics, validation, and UI mapping. It must not be smuggled into v1 as an expert-only side path.

## 12. Implications for the current implementation direction

The supported v1 implementation slice remains:

- MIRcat
- HF2LI
- T660-2
- T660-1
- Arduino-controlled MUX
- PicoScope 5244D
- Nd:YAG timing semantics through T660-2
- OPO placeholder only

The current implementation direction is the operator-first `Experiment` iteration loop defined by `docs/operator_ui_mvp.md` and sequenced by `PLANS.md`.

Implications for that pass:

- The default operator-facing surface should expose only the routine controls needed to operate the supported v1 slice.
- That default surface should emphasize session and sample identity, laser controls, HF2LI acquisition controls, run control, live status, and recent warnings.
- Detailed timing, MUX routing, PicoScope secondary capture, calibration references, and service tooling belong behind Advanced, Calibrated, or Service surfaces rather than dominating the default path.
- Backend expansion should follow the reviewed UI priority order. Do not widen contracts, engine behavior, or hardware surfaces only because the full v1 model is broader.
- When additional timing or routing detail is surfaced, it must still follow the canonical `T0` model and the existing single-path, fail-fast architecture.
- Direct OPO control remains out of scope while this supported v1 slice is being implemented.
