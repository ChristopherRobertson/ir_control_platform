# AGENTS.md — data-pipeline

## Purpose
This package owns acquisition ingestion, session persistence, artifact indexing, and replay.

## Must own
- raw acquisition capture
- event timeline persistence
- session manifests
- artifact registration
- replay loaders
- partial and faulted session handling

## Rules
- Raw captured data is authoritative and immutable once written.
- Persist continuously enough that a faulted run still leaves a usable session record.
- Do not let UI code author raw files directly.
- Keep format versions explicit.
- Surface write failures explicitly; do not silently drop data.

## Success criteria
A saved session can be reopened, replayed, and used for later processing without the original live UI state.
