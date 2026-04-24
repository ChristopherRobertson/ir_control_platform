# Salvage Matrix

`Control_System` is read-only in this workspace. The classifications below identify what should be kept as knowledge, rewritten into `ir_control_platform`, replaced, or deleted from the target product direction.

| Source | Classification | Target | Rationale |
| --- | --- | --- | --- |
| `backend/src/modules/daylight_mircat/controller.py` | EXTRACT-AND-REWRITE | `drivers/mircat`, `simulators` | Keep SDK loading, explicit missing-SDK failure, interlock/key/temperature readiness, single-wavelength tune, arm/disarm/emission semantics, CW/pulsed parameter validation, and MIRcat error vocabulary. Do not keep sweep/step/multispectral control paths for v1. |
| `backend/src/modules/daylight_mircat/routes.py` | REPLACE | `experiment-engine`, `ui-shell` | Device routes expose a device-first API. Keep endpoint lessons only; v1 UI calls workflow runtime methods. |
| `frontend/src/modules/DaylightMIRcat/components/LaserSettingsPanel.tsx` | KEEP-CODE-WITH-BOUNDARY | `ui-shell` concepts, `contracts` validation | Keep pulse rate, pulse width, duty-cycle validation ranges and CW/pulsed mode concepts. Strip notifications, process-trigger, wavelength-trigger, broad service settings, and scan controls. |
| `frontend/src/modules/DaylightMIRcat/components/TuningControls.tsx` | EXTRACT-AND-REWRITE | `ui-shell` Probe settings | Keep single wavelength input concept. Remove tune/arm/emission buttons from the v1 operator setup. |
| `frontend/src/modules/DaylightMIRcat/components/ScanModePanel.tsx` | DELETE | none | Scan UI is forbidden in v1. |
| `frontend/src/modules/DaylightMIRcat/context/MIRcatScanSettingsContext.tsx` | DELETE | none | Scan state is forbidden in v1. |
| `backend/src/modules/zurich_hf2li/controller.py` | EXTRACT-AND-REWRITE | `drivers/labone_hf2`, `data-pipeline` | Keep LabOne connection/discovery failure behavior, demod sample polling, X/Y/R/phase extraction, timestamp handling, and file-writing lessons. Remove generic node dashboard and live plot ownership from v1 UI. |
| `frontend/src/modules/ZurichHF2LI/context/HF2SettingsProvider.tsx` | KEEP-CODE-WITH-BOUNDARY | `contracts`, `ui-shell` | Keep time constant and transfer rate as operator overrides. Remove broad generic HF2LI surface and extra tabs. |
| `backend/src/modules/experiment/routes.py` | REPLACE | `experiment-engine`, `data-pipeline` | Old route starts HF2LI recording and MIRcat sweep directly. V1 requires engine-owned orchestration, session/run persistence, and single-wavelength acquisition. |
| `backend/scripts/convert_hf2li.py` | EXTRACT-AND-REWRITE | `processing` | Keep sample/reference split knowledge and ratio formula. V1 transforms operate on persisted raw records, not watched files. |
| `backend/src/utils/highland_delay.py` | EXTRACT-AND-REWRITE | `drivers/t660`, `experiment-engine` | Keep command formatting, status/error interpretation, timing resolution, trigger/channel semantics. Do not expose raw channel editing in operator setup. |
| `hardware_configuration.toml` | KEEP-ASSET | `contracts`, `drivers`, docs | Keep MIRcat ranges, pulse defaults, HF2LI order/time constant/transfer defaults, T660 command semantics, and SDK path lessons. Do not copy broad UI options into v1. |
| `frontend/src/App.tsx` and global nav | REPLACE | `ui-shell` | Old primary navigation is device-first. V1 primary navigation is Session / Setup / Results. |
| `frontend/src/components/DashboardView.tsx` | DELETE | none | Generic dashboard is not v1 scope. |
| `docs/gui_screenshots/*` | KEEP-ASSET | docs/reference only | Useful visual reference for device settings and status. Not a UI template. |
| `backend/data/raw/*`, `backend/data/converted/*`, `data/hf2li_*` | KEEP-ASSET | `tests`, `data-pipeline` fixtures later | Useful for replay/format tests after v1 raw schema stabilizes. Sample-specific labels must not enter product language. |
| WebSocket live status in `backend/src/main.py` | EXTRACT-AND-REWRITE | later runtime status surfaces | Keep status polling cadence lessons. Do not add real-time plotting or device dashboards in v1. |
