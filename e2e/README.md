# e2e

Lightweight verification lives here for the current operator workflow.

- Owns: scenario-level integration validation and fast smoke checks for the finished simulator-backed shell.
- Depends on: the existing simulator-backed runtime and local WSGI runner.

## Quick Smoke Check

Run:

```bash
python3 e2e/smoke_experiment_page.py
```

What it covers:

- starts `run_ui.py` with a temporary storage root
- checks that the local app responds and `/` redirects to `/experiment`
- checks that `Experiment` shows mission-control markers
- checks that `Setup` shows readiness and advanced-review markers
- starts a simulator-backed run and checks that `Run` shows lifecycle and live-data markers
- checks that `Results` shows persisted-review markers
- checks that `Service` shows diagnostics and recovery markers

What it does not cover:

- full browser rendering or CSS/layout review
- real hardware behavior
- deep workflow automation beyond the fast simulator-backed shell pass
- exhaustive state combinations for every surface
