"""Typed UI models for the operator-first server-rendered shell."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
class CalloutModel:
    title: str
    body: str
    tone: str
    items: tuple[str, ...] = ()


@dataclass(frozen=True)
class FormOptionModel:
    value: str
    label: str
    selected: bool = False


@dataclass(frozen=True)
class FormFieldModel:
    name: str
    label: str
    field_type: str
    value: str = ""
    help_text: str = ""
    disabled: bool = False
    placeholder: str = ""
    options: tuple[FormOptionModel, ...] = ()
    checked: bool = False
    section_label: str = ""
    full_width: bool = False
    auto_submit: bool = False
    hidden: bool = False
    read_only: bool = False
    min_value: str = ""
    max_value: str = ""
    step: str = ""


@dataclass(frozen=True)
class SummaryPanel:
    title: str
    subtitle: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class TableModel:
    title: str
    subtitle: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    empty_message: str = "No rows available."


@dataclass(frozen=True)
class DeviceSummaryCard:
    device_label: str
    status_label: str
    tone: str
    summary: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventLogItem:
    timestamp: datetime
    source: str
    message: str
    tone: str


@dataclass(frozen=True)
class SessionSummaryCard:
    session_id: str
    recipe_title: str
    status_label: str
    updated_at: datetime
    primary_raw_artifact_count: int
    secondary_monitor_artifact_count: int
    processed_artifact_count: int
    analysis_artifact_count: int
    export_artifact_count: int
    event_count: int = 0
    replay_ready: bool = False
    failure_reason_label: str | None = None
    selected: bool = False


@dataclass(frozen=True)
class ResultsFilterModel:
    search_value: str = ""
    status_options: tuple[FormOptionModel, ...] = ()
    sort_options: tuple[FormOptionModel, ...] = ()
    visible_session_count: int = 0
    total_session_count: int = 0


@dataclass(frozen=True)
class StatusItemModel:
    label: str
    value: str
    tone: str = "neutral"
    detail: str = ""


@dataclass(frozen=True)
class ActionButtonModel:
    label: str
    action: str
    tone: str = "primary"
    disabled: bool = False
    hidden: bool = False
    helper_text: str = ""
    hidden_fields: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SurfaceActionModel:
    label: str
    route: str | None = None
    session_id: str | None = None
    tone: str = "primary"
    disabled: bool = False
    helper_text: str = ""
    query_params: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ResultsTracePreviewModel:
    title: str
    subtitle: str
    sample_count_label: str
    axis_label: str
    axis_start_label: str
    axis_end_label: str
    value_min_label: str
    value_max_label: str
    polyline_points: str | None = None
    note_lines: tuple[str, ...] = ()
    state: PageStateModel | None = None


@dataclass(frozen=True)
class ResultsArtifactRowModel:
    kind_label: str
    artifact_id: str
    source_label: str
    stream_label: str
    records_label: str
    created_at: datetime
    path: str
    details: tuple[str, ...] = ()
    download_action: SurfaceActionModel | None = None


@dataclass(frozen=True)
class OperatePanelModel:
    title: str
    fields: tuple[FormFieldModel, ...] = ()
    conditional_fields: tuple[FormFieldModel, ...] = ()
    field_columns: int = 1
    form_action: str = ""
    header_actions: tuple[ActionButtonModel, ...] = ()
    actions: tuple[ActionButtonModel, ...] = ()
    status_items: tuple[StatusItemModel, ...] = ()
    footer_callouts: tuple[CalloutModel, ...] = ()
    notes: tuple[str, ...] = ()
    state: PageStateModel | None = None
    disclosures: tuple["OperateDisclosureModel", ...] = ()


@dataclass(frozen=True)
class OperateDisclosureModel:
    title: str
    subtitle: str = ""
    fields: tuple[FormFieldModel, ...] = ()
    field_columns: int = 1
    notes: tuple[str, ...] = ()
    open_by_default: bool = False


@dataclass(frozen=True)
class OperatePageModel:
    state: PageStateModel | None
    session_panel: OperatePanelModel
    laser_panel: OperatePanelModel
    ndyag_panel: OperatePanelModel
    acquisition_panel: OperatePanelModel
    run_panel: OperatePanelModel
    results_handoff: SurfaceActionModel | None = None


@dataclass(frozen=True)
class AdvancedSectionModel:
    title: str
    subtitle: str
    summary_panels: tuple[SummaryPanel, ...] = ()
    tables: tuple[TableModel, ...] = ()
    notes: tuple[str, ...] = ()
    open_by_default: bool = False


@dataclass(frozen=True)
class AdvancedPageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    surface_badges: tuple[StatusBadge, ...]
    sections: tuple[AdvancedSectionModel, ...]
    callouts: tuple[CalloutModel, ...] = ()


@dataclass(frozen=True)
class ResultsPageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    surface_badges: tuple[StatusBadge, ...]
    filters: ResultsFilterModel
    sessions: tuple[SessionSummaryCard, ...]
    selected_session: SessionSummaryCard | None
    selected_session_metrics: tuple[StatusItemModel, ...]
    detail_panels: tuple[SummaryPanel, ...]
    artifact_panels: tuple[SummaryPanel, ...] = ()
    artifact_rows: tuple[ResultsArtifactRowModel, ...] = ()
    visualization_panels: tuple[SummaryPanel, ...] = ()
    trace_previews: tuple[ResultsTracePreviewModel, ...] = ()
    storage_panels: tuple[SummaryPanel, ...] = ()
    export_panels: tuple[SummaryPanel, ...] = ()
    toolbar_actions: tuple[SurfaceActionModel, ...] = ()
    export_actions: tuple[SurfaceActionModel, ...] = ()
    callouts: tuple[CalloutModel, ...] = ()
    event_log: tuple[EventLogItem, ...] = ()


@dataclass(frozen=True)
class AnalyzePageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    surface_badges: tuple[StatusBadge, ...]
    sessions: tuple[SessionSummaryCard, ...]
    selected_session: SessionSummaryCard | None
    summary_panels: tuple[SummaryPanel, ...]
    evaluation_panels: tuple[SummaryPanel, ...] = ()
    tables: tuple[TableModel, ...] = ()
    toolbar_actions: tuple[SurfaceActionModel, ...] = ()
    evaluation_actions: tuple[SurfaceActionModel, ...] = ()
    callouts: tuple[CalloutModel, ...] = ()


@dataclass(frozen=True)
class ServicePageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    surface_badges: tuple[StatusBadge, ...]
    device_cards: tuple[DeviceSummaryCard, ...]
    diagnostic_panels: tuple[SummaryPanel, ...] = ()
    callouts: tuple[CalloutModel, ...] = ()
    tables: tuple[TableModel, ...] = ()
