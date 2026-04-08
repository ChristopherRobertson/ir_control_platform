"""Analysis job boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ircp_contracts import AnalysisArtifact, AnalysisRecipe


@dataclass(frozen=True)
class AnalysisRequest:
    session_id: str
    processed_artifact_ids: tuple[str, ...]
    analysis_recipe: AnalysisRecipe
    requested_at: datetime
    raw_artifact_ids: tuple[str, ...] = ()


@runtime_checkable
class AnalysisJobRunner(Protocol):
    async def run(self, request: AnalysisRequest) -> AnalysisArtifact:
        """Produce one analysis artifact from persisted upstream artifacts."""
