# Deletion Ledger

This ledger records product structures intentionally not carried into `ir_control_platform` v1.

| Old pattern or file family | Decision | Replacement | Reason |
| --- | --- | --- | --- |
| Device-first React routes for MIRcat, HF2LI, PicoScope, T660, T661, Arduino MUX, and pump pages | DELETE | Three-page Session / Setup / Results workflow | V1 is page- and workflow-driven, not device-panel-driven. |
| Generic dashboard landing page | DELETE | Session page opens by default | The operator must define session and run metadata before setup. |
| MIRcat sweep, step, multispectral, wavelength trigger, and queue controls | DELETE | Single wavelength input in Probe settings | V1 is single-wavelength only. |
| MIRcat Arm, Scan, and Emission buttons in the operator flow | DELETE | Engine-owned run orchestration and read-only readiness/fault status | Operator setup should not expose low-level device actions as the primary workflow. |
| HF2LI generic node editor and broad dashboard tabs | DELETE | Order, Time Constant, Transfer Rate overrides only | V1 exposes only required lock-in overrides. |
| UI-owned HF2LI recording and file conversion flow | DELETE | Data-pipeline persistence and processing transforms | UI must not own persistence or scientific truth. |
| Separate data acquisition section | DELETE | Run controls at bottom of Setup | V1 has no standalone acquisition surface. |
| Separate Run page | DELETE | Section E - Run controls on Setup | Run lifecycle status is inline; Results handles saved data review. |
| Preflight page or preflight card | DELETE | Validation-driven disabled controls and inline blocking messages | Gating exists without a separate preflight UI surface. |
| Real-time plot dashboard | DELETE | Results from saved run data | V1 has no real-time plotting. |
| Raw delay-generator channel editor in operator flow | DEFER/DELETE | Backend-derived acquisition-window plans | Timescale is not user-managed channel editing. |
| Raw MUX routing editor in operator flow | DEFER/DELETE | Fixed v1 acquisition path behind engine/drivers | V1 should not expose routing internals. |
| Compatibility layers preserving old routes or screen names | DELETE | Canonical contracts and workflow runtime | The new repo is single-path and fail-fast. |
| Sample-specific labels from old data and fixtures | DELETE from product language | Generic session sample ID/name field | Product architecture remains sample-agnostic. |

## Control_System Documentation Note
The parent workspace rules currently prohibit editing `Control_System`. Required old-repo documentation changes are therefore recorded here rather than applied in place:

- mark `Control_System` as salvage/reference only during migration
- stop positioning it as the place to grow a generic UI
- move non-v1 UI ambitions to deferred backlog
- narrow unresolved inputs to blockers for the generic v1 workflow
- point readers to `ir_control_platform` for target architecture and implementation
