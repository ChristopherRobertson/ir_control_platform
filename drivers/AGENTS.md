# AGENTS.md — drivers

## Purpose
This directory contains one package per device family.

## Driver contract expectations
Every driver package must provide:
- connect and disconnect
- capability reporting
- status reporting
- configuration apply
- command surface for supported operations
- normalized fault reporting
- vendor error-code exposure
- simulator or stub implementation
- smoke tests

## Rules
- Wrap vendor SDKs and protocols cleanly.
- Return vendor errors clearly instead of trying to “fix” them in the driver.
- Do not implement UI logic in drivers.
- Do not implement cross-device orchestration in drivers.
- Avoid hidden retries, auto-correction, or fallback transport switching.
- Keep the public shape of each driver aligned to shared contracts.

## Success criteria
The experiment engine can run against both real and simulated driver implementations without changing UI code.
