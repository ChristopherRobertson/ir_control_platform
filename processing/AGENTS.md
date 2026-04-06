# AGENTS.md — processing

## Purpose
This package owns deterministic transformations from raw data to processed artifacts.

## Must own
- calibration application
- corrections
- filtering
- normalization
- alignment
- averaging
- feature extraction
- versioned processing recipes

## Rules
- Keep transformations deterministic and reproducible.
- Use the same core code for live and offline processing where practical.
- Do not depend on widget state or UI-only objects.
- Do not silently adjust invalid parameters.
- Emit explicit processing failures with enough context to reproduce them.

## Success criteria
The same raw dataset and processing recipe produce the same processed artifacts every time.
