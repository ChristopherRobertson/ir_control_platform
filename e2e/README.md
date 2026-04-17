# e2e

Lightweight verification lives here for the current operator workflow.

- Owns: scenario-level integration validation and fast smoke checks for the baseline Experiment page.
- Depends on: the existing simulator-backed runtime and local WSGI runner.

## Quick Smoke Check

Run:

```bash
python3 e2e/smoke_experiment_page.py
```

What it covers:

- starts `run_ui.py` with a temporary storage root
- checks that the local app responds and `/` redirects to `/experiment`
- checks that the Experiment page shows the current Session, Operating Mode, Nd:YAG, HF2LI, and Run Control sections
- checks that the baseline scope stays on fixed-wavelength MIRcat controls and hides timing, routing, and analysis detail
- checks that main-page clutter such as timing, MUX, and Pico-specific controls is not visible
- checks fixed-versus-scan control swapping if the experiment-type selector is present

What it does not cover:

- full browser rendering or CSS/layout review
- real hardware behavior
- deep workflow automation beyond the minimal Experiment page
- `Results`, `Analyze`, `Advanced`, or `Service` surfaces
