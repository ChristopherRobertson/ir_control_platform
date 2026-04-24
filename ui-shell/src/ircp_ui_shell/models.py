"""Typed page models for the three-page single-wavelength pump-probe UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .page_state import PageStateModel


@dataclass(frozen=True)
class StatusBadge:
    label: str
    tone: str = "neutral"


@dataclass(frozen=True)
class NavigationItem:
    label: str
    href: str
    active: bool = False
    disabled: bool = False


@dataclass(frozen=True)
class HeaderStatus:
    title: str
    active_route: str
    navigation: tuple[NavigationItem, ...]
    badges: tuple[StatusBadge, ...]
    summary: str


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
    options: tuple[FormOptionModel, ...] = ()
    required: bool = False
    disabled: bool = False
    read_only: bool = False
    checked: bool = False
    help_text: str = ""
    invalid: bool = False
    min_value: str = ""
    max_value: str = ""
    step: str = ""


@dataclass(frozen=True)
class ActionButtonModel:
    label: str
    action: str
    tone: str = "primary"
    disabled: bool = False
    helper_text: str = ""


@dataclass(frozen=True)
class StatusItemModel:
    label: str
    value: str
    tone: str = "neutral"
    detail: str = ""


@dataclass(frozen=True)
class PanelModel:
    title: str
    form_action: str = ""
    fields: tuple[FormFieldModel, ...] = ()
    header_actions: tuple[ActionButtonModel, ...] = ()
    actions: tuple[ActionButtonModel, ...] = ()
    status_items: tuple[StatusItemModel, ...] = ()
    state: PageStateModel | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionListItem:
    session_id: str
    label: str
    updated_at: datetime
    open_enabled: bool = True


@dataclass(frozen=True)
class RunListItem:
    session_id: str
    run_id: str
    label: str
    status: str
    updated_at: datetime
    open_enabled: bool = False


@dataclass(frozen=True)
class SessionPageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    session_panel: PanelModel
    run_header_panel: PanelModel
    existing_sessions: tuple[SessionListItem, ...]
    existing_runs: tuple[RunListItem, ...]


@dataclass(frozen=True)
class SetupPageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    save_action: ActionButtonModel
    pump_panel: PanelModel
    timescale_panel: PanelModel
    probe_panel: PanelModel
    lockin_panel: PanelModel
    run_controls_panel: PanelModel


@dataclass(frozen=True)
class PlotPoint:
    time_seconds: float
    sample: float | None = None
    reference: float | None = None
    ratio: float | None = None


@dataclass(frozen=True)
class ResultsPlotModel:
    metric_family: str
    display_mode: str
    points: tuple[PlotPoint, ...]


@dataclass(frozen=True)
class ResultsPageModel:
    title: str
    subtitle: str
    state: PageStateModel | None
    selected_session_id: str | None
    selected_run_id: str | None
    selector_panel: PanelModel
    metadata_panel: PanelModel
    plot: ResultsPlotModel | None
    export_panel: PanelModel
    run_history: tuple[RunListItem, ...]


@dataclass(frozen=True)
class ResultsDownload:
    filename: str
    content_type: str
    body: bytes
