"""Stable helper functions for simulator-backed platform runtime."""

from __future__ import annotations

from pathlib import Path


def storage_base_root(storage_root: Path | None = None) -> Path:
    if storage_root is not None:
        return storage_root.resolve()
    return Path(__file__).resolve().parents[3] / ".local_state"
