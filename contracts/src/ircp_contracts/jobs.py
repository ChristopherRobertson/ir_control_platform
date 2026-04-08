"""Shared processing, analysis, and export request contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from .common import CONTRACT_VERSION, ConfigurationScalar


@dataclass(frozen=True)
class ProcessingRecipe:
    recipe_id: str
    name: str
    parameters: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
    version: str = CONTRACT_VERSION
    description: str = ""


@dataclass(frozen=True)
class AnalysisRecipe:
    recipe_id: str
    name: str
    parameters: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
    version: str = CONTRACT_VERSION
    description: str = ""


@dataclass(frozen=True)
class ExportRequest:
    request_id: str
    session_id: str
    format_name: str
    source_artifact_ids: tuple[str, ...]
    requested_at: datetime
    version: str = CONTRACT_VERSION
    destination_name: str | None = None
    include_analysis_outputs: bool = True

    def __post_init__(self) -> None:
        if not self.source_artifact_ids:
            raise ValueError("Export requests must cite at least one source artifact.")
