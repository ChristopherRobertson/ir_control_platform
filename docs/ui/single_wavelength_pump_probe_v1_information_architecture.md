# Single-Wavelength Pump-Probe V1 Information Architecture

## Primary Navigation
The primary navigation is exactly:

1. Session
2. Setup
3. Results

No fourth page is part of v1.

## Page 1 - Session
Purpose:

- require session metadata before setup
- save draft run settings before setup

Required sections:

- Session Information
- Run Information

Required actions:

- Save session settings
- Save run settings
- Open existing session
- Open existing run for review

Setup remains blocked until the session and run settings are saved.

## Page 2 - Setup
Purpose:

- contain all run-time configuration
- contain run controls at the bottom
- avoid generic device panels

Section order:

1. Pump settings
2. Timescale
3. Probe settings
4. Lock-In Amplifier settings
5. Run controls

Timescale selection displays derived acquisition-window values inline when useful. These values come from backend validation.

Run controls are disabled until:

- session is saved
- run settings are saved
- required setup fields are complete
- current configuration is valid

Blocking errors appear near the relevant section or control.

## Page 3 - Results
Purpose:

- review processed data after acquisition
- work from saved run data without reopened hardware
- export raw data, processed data, and metadata/settings

Plot controls:

- metric family: X, Y, R, Theta
- display mode: overlay or ratio

Ratio mode is `-log(sample/reference)`.

## Explicit Non-UI
V1 does not include:

- wavelength sweep UI
- scan buttons
- Arm button in operator probe setup
- broad MIRcat service controls
- broad HF2LI dashboard
- separate data acquisition section
- separate run page
- live plot dashboard
- preflight page or card
- advanced scaffolding
