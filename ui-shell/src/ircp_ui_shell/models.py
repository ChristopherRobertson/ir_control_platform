"""Typed UI models for the Phase 3A shell."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ircp_contracts import PreflightReport

from .page_state import PageStateModel


@dataclass(frozen=True)
class ScenarioOption:
    scenario_id: str
    label: str
    description: str
    active: bool = False


@dataclass(frozen=True)
class StatusBadge:
    label: str
    tone: str


@dataclass(frozen=True)
class NavigationItem:
    label: str
    href: str
    active: bool = False


@dataclass(frozen=True)
class HeaderStatus:
    title: str
    active_route: str
    scenario_options: tuple[ScenarioOption, ...]
    navigation: tuple[NavigationItem, ...]
    badges: tuple[StatusBadge, ...]
    summary: str


@dataclass(frozen=True)
class SectionHeader:
    title: str
    subtitle: str


@dataclass(frozen=True)
class DeviceSummaryCard:
    device_label: str
    status_label: str
    tone: str
    summary: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReadinessRow:
    label: str
    state: str
    summary: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventLogItem:
    timestamp: datetime
    source: str
    message: str
    tone: str


@dataclass(frozen=True)
class LiveDataPointModel:
    wavenumber_cm1: float
    value: float


@dataclass(frozen=True)
class LiveDataSeries:
    label: str
    units: str
    points: tuple[LiveDataPointModel, ...]


@dataclass(frozen=True)
class SessionSummaryCard:
    session_id: str
    recipe_title: str
    status_label: str
    updated_at: datetime
    raw_artifact_count: int
    processed_artifact_count: int
    analysis_artifact_count: int
    export_artifact_count: int
    selected: bool = False


@dataclass(frozen=True)
class RunStepSummary:
    phase_label: str
    active_step: str
    progress_fraction: float
    summary: str
    tone: str


@dataclass(frozen=True)
class SetupPageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    recipe_title: str
    preset_name: str
    section_header: SectionHeader
    device_cards: tuple[DeviceSummaryCard, ...]
    readiness_rows: tuple[ReadinessRow, ...]
    preflight_report: PreflightReport | None = None


@dataclass(frozen=True)
class RunPageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    section_header: SectionHeader
    run_id: str | None
    run_phase_label: str
    session_id: str | None
    event_log: tuple[EventLogItem, ...]
    live_data: tuple[LiveDataSeries, ...]
    run_steps: tuple[RunStepSummary, ...]


@dataclass(frozen=True)
class ResultsPageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    section_header: SectionHeader
    sessions: tuple[SessionSummaryCard, ...]
    selected_session: SessionSummaryCard | None
    manifest_details: tuple[str, ...]


@dataclass(frozen=True)
class ServicePageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    section_header: SectionHeader
    device_cards: tuple[DeviceSummaryCard, ...]
    notes: tuple[str, ...]
