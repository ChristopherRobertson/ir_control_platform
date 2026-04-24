# Single-Wavelength Pump-Probe V1

## Identity
The only v1 experiment workflow is `Single-Wavelength Pump-Probe`.

It is generic and sample-agnostic. Product architecture, route names, state names, page names, and component names must not include sample-specific language.

## Hardware Families
The v1 vertical slice uses:

- YAG/OPO pump path
- MIRcat probe path
- HF2LI acquisition path
- timing path needed to capture data around the YAG pulse

## Scope
V1 is single-wavelength only. Wavelength belongs to Setup under Probe settings so multiple runs in the same session can use different wavelengths.

Timescale belongs to Setup and the run settings snapshot. It is one of:

- Nanoseconds
- Microseconds
- Milliseconds

Timescale defines the acquisition window around the YAG pulse. It is not a user-managed delay grid.

## Workflow
The workflow has exactly three pages:

1. Session
2. Setup
3. Results

Run controls live at the bottom of Setup. There is no separate Run page.

## Results
Results render from saved run data only. The operator can choose:

- metric family: X, Y, R, Theta
- overlay mode: sample and reference together
- ratio mode: `-log(sample/reference)`

Raw data persists enough information to recalculate every metric family later.

## Forbidden In V1
- wavelength scanning
- spectral maps
- multi-wavelength queues
- generic device dashboards
- separate data acquisition sections
- separate run pages
- real-time plots
- preflight pages or sections
- sample-specific product logic
