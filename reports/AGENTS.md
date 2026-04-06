# AGENTS.md — reports

## Purpose
This package owns exports, result bundles, and generated summaries.

## Must own
- export format generation
- report composition
- result bundle creation
- regeneration from saved sessions

## Rules
- Build reports from persisted artifacts, not transient page state.
- Keep outputs reproducible.
- Avoid screen-scrape style exports.
- Make export failures explicit.

## Success criteria
A saved session can produce the same export bundle or report on demand without rerunning acquisition.
