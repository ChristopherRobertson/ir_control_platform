# ui-shell

Presentation shell for the generic single-wavelength pump-probe v1 workflow.

- Owns: navigation, typed page models, server-rendered components, route dispatch, and form rendering.
- Depends on: `contracts` and UI-facing protocols.
- Must not own drivers, persistence, processing, analysis, or export truth.

## Route Map

- `/session`: Page 1, session metadata and run settings
- `/setup`: Page 2, run-time setup and run controls
- `/results`: Page 3, saved run review and exports

`/` redirects to `/session`.

There is no separate Run page, no preflight page, no data acquisition page, no advanced page, no service page, and no generic device dashboard in v1.

## Setup Section Order

1. Pump settings
2. Timescale
3. Probe settings
4. Lock-In Amplifier settings
5. Run controls

Timescale is rendered as an acquisition-window regime selector with Nanoseconds, Microseconds, and Milliseconds only.

## Results

Results render from persisted run data. They support metric families X, Y, R, Theta and display modes overlay and ratio.

## Local Review

```bash
python3 run_ui.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 e2e/smoke_experiment_page.py
```
