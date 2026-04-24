# UI Foundation

The active frontend remains a Python, server-rendered shell.

For v1, the shell renders only the generic single-wavelength pump-probe workflow:

- `/session`
- `/setup`
- `/results`

The UI shell owns presentation and route dispatch only. It does not own hardware orchestration, persistence, processing, analysis, or export truth.

Use `docs/ui/single_wavelength_pump_probe_v1_information_architecture.md` for the active page structure.
