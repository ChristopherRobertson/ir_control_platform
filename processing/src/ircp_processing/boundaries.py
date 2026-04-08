"""Processing job boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ircp_contracts import ProcessedArtifact, ProcessingRecipe


@dataclass(frozen=True)
class ProcessingRequest:
    session_id: str
    raw_artifact_ids: tuple[str, ...]
    processing_recipe: ProcessingRecipe
    requested_at: datetime


@runtime_checkable
class ProcessingJobRunner(Protocol):
    async def run(self, request: ProcessingRequest) -> ProcessedArtifact:
        """Produce one processed artifact from persisted raw inputs."""
