# AGENTS.md — simulators

## Purpose
This package provides deterministic stand-ins for real devices and replay fixtures for system development.

## Must own
- simulator implementations for supported drivers
- nominal run scenarios
- device fault scenarios
- disconnect scenarios
- replay fixtures
- deterministic test inputs

## Rules
- Simulator behavior must be repeatable.
- Cover both success and failure paths.
- Keep scenario data curated and versioned.
- Do not let simulator shortcuts leak into production package behavior.

## Success criteria
Teams can develop and validate the full product flow without blocking on hardware access.
