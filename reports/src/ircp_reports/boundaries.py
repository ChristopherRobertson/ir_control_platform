"""Report and export generation boundaries."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ircp_contracts import ExportArtifact, ExportRequest


@runtime_checkable
class ReportGenerator(Protocol):
    async def run_export(self, request: ExportRequest) -> ExportArtifact:
        """Generate one export artifact from persisted session data."""
