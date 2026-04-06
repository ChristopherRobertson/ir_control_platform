# AGENTS.md — platform

## Purpose
This package owns cross-cutting runtime infrastructure.

## Must own
- structured events
- state primitives
- logging and audit infrastructure
- normalized error and fault primitives
- shared runtime utilities that do not belong to a specific device or workflow

## Rules
- Keep this package generic and reusable.
- Do not embed device-specific logic here.
- Do not embed UI logic here.
- Prefer explicit event and error types over free-form strings.
- Do not use platform code to hide failures or add workaround behavior.

## Success criteria
Other packages rely on `platform/` for runtime primitives, not for product-specific logic.
