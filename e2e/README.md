# e2e

Lightweight verification for the single-wavelength pump-probe v1 workflow.

## Quick Smoke Check

Run:

```bash
python3 e2e/smoke_experiment_page.py
```

It covers:

- local `run_ui.py` startup
- `/` redirecting to `/session`
- Session Information and Run Information sections
- Setup page section order
- Run control execution from Setup
- Results rendering from saved run data
- ratio display mode and export links

It does not cover real hardware behavior or full browser layout review.
