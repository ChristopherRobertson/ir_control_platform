# AGENTS.md — experiment-engine

## Purpose
This package is the sole orchestrator of coordinated run behavior.

## Must own
- run lifecycle state machine
- preflight validation
- coordinated device sequencing
- run command handling
- run event emission
- explicit fault and abort handling

## Rules
- This package is the single writer of coordinated run state.
- Use one approved path for each workflow.
- Stop on explicit device faults or unrecoverable persistence failures.
- Do not import UI packages.
- Do not own plotting, report layout, or scientific presentation concerns.
- Keep transitions deterministic and testable.

## Success criteria
A simulator-backed run can move from validation to completion with explicit state transitions and explicit failure modes.
