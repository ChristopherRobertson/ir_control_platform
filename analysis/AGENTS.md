# AGENTS.md — analysis

## Purpose
This package owns derived metrics, comparison logic, fitting, and experiment-specific interpretation.

## Must own
- analysis jobs
- derived metrics
- comparison workflows
- fit logic where required
- quality summaries
- versioned analysis outputs

## Rules
- Operate on persisted artifacts, not transient UI state.
- Keep derived logic explicit and reviewable.
- Avoid duplicate implementations of the same metric.
- Fail explicitly when required inputs are missing or inconsistent.

## Success criteria
Analysis can be rerun from a saved session without live hardware or the original UI state.
