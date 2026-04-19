"""Page and panel builders for the simulator-backed UI runtime."""

from __future__ import annotations

import math
from pathlib import Path

from ircp_contracts import DeviceStatus, PreflightReport, RunPhase, RunState, SessionStatus
from ircp_data_pipeline import SessionDetail, SessionSummary
from ircp_experiment_engine import LiveDataPoint, RunTimeline
from ircp_simulators import SimulatorScenarioContext
from ircp_ui_shell import (
    ActionButtonModel,
    AdvancedPageModel,
    AdvancedSectionModel,
    AnalyzePageModel,
    CalloutModel,
    DeviceSummaryCard,
    EventLogItem,
    FormFieldModel,
    FormOptionModel,
    HeaderStatus,
    OperatePageModel,
    OperatePanelModel,
    PageStateModel,
    ResultsArtifactRowModel,
    ResultsFilterModel,
    ResultsPageModel,
    ResultsTracePreviewModel,
    RunPageModel,
    ServicePageModel,
    SessionSummaryCard,
    SetupPageModel,
    StatusBadge,
    StatusItemModel,
    SummaryPanel,
    SurfaceActionModel,
    TableModel,
    TracePreviewModel,
)
from ircp_ui_shell.page_state import (
    blocked_state,
    empty_state,
    fault_state,
    success_state,
    unavailable_state,
    warning_state,
)

from .operator_state import (
    FIXED_WAVELENGTH_EXPERIMENT_TYPE,
    HF2_DIO_0,
    HF2_DIO_0_1,
    HF2_DIO_1,
    MIRCAT_WAVENUMBER_MAX_CM1,
    MIRCAT_WAVENUMBER_MIN_CM1,
    NDYAG_REPETITION_RATE_MIN_HZ,
    NDYAG_SHOT_COUNT_MAX,
    OperatorDraftState,
    PULSE_DUTY_CYCLE_MAX_PERCENT,
    PULSE_REPETITION_RATE_MAX_HZ,
    PULSE_REPETITION_RATE_MIN_HZ,
    PULSE_WIDTH_MAX_NS,
    PULSE_WIDTH_MIN_NS,
    SCAN_SPEED_MAX,
    SCAN_SPEED_MIN,
    WAVELENGTH_SCAN_EXPERIMENT_TYPE,
    experiment_type_label,
)
from .runtime_helpers import artifact_summary_line, bool_vendor_status, event_tone, phase_tone, run_badge_tone


def build_header_status(
    *,
    active_route: str,
    scenario: SimulatorScenarioContext,
    draft: OperatorDraftState,
    preflight: PreflightReport,
    device_statuses: tuple[DeviceStatus, ...],
    current_session_id: str,
    run_phase_label: str,
    ready_to_start: bool,
) -> HeaderStatus:
    route_titles = {
        "experiment": "Experiment",
        "setup": "Setup",
        "run": "Run",
        "results": "Results",
        "analyze": "Analyze",
        "advanced": "Advanced",
        "service": "Service",
    }
    route_summaries = {
        "experiment": "Operator workflow",
        "setup": "Preparation",
        "run": "Live run",
        "results": "Saved sessions",
        "analyze": "Saved analysis",
        "advanced": "Expert tuning",
        "service": "Diagnostics",
    }
    ready_devices = sum(1 for status in device_statuses if status.ready)
    connected_devices = sum(1 for status in device_statuses if status.connected)
    faulted_devices = sum(1 for status in device_statuses if status.reported_faults)
    blocking_count = len(_operator_preflight_messages(preflight, blocking_only=True))
    warning_count = len(_operator_preflight_messages(preflight, warning_only=True))
    device_tone = "good"
    if faulted_devices:
        device_tone = "bad"
    elif ready_devices < len(device_statuses) or connected_devices < len(device_statuses):
        device_tone = "warn"
    return HeaderStatus(
        title="IR Control Platform",
        active_route=active_route,
        scenario_options=(),
        navigation=(),
        badges=(
            StatusBadge(label=route_titles.get(active_route, active_route.title()), tone="info"),
            StatusBadge(label=f"Devices {ready_devices}/{len(device_statuses)} ready", tone=device_tone),
            StatusBadge(
                label="Ready" if ready_to_start else "Attention",
                tone="good" if ready_to_start else "warn",
            ),
            StatusBadge(
                label=f"Issues {blocking_count}/{warning_count}",
                tone="good" if blocking_count == 0 else "bad",
            ),
            StatusBadge(label=f"Run {run_phase_label}", tone=run_badge_tone(run_phase_label)),
        ),
        summary=f"{route_summaries.get(active_route, '')} · {scenario.label}".strip(),
    )


def build_operate_page(
    *,
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
    preflight: PreflightReport,
    latest_state: RunState | None,
    latest_timeline: RunTimeline | None,
    sessions: tuple[SessionSummary, ...],
    laser_status: DeviceStatus,
    hf2_status: DeviceStatus,
    device_cards: tuple[DeviceSummaryCard, ...],
    draft_session_id: str | None,
    selected_session_id: str | None,
) -> OperatePageModel:
    current_session_id = draft_session_id or selected_session_id
    return OperatePageModel(
        title="Experiment",
        subtitle="Session, laser, acquisition, and run control.",
        state=_operate_page_state(draft.experiment_type, preflight, latest_state),
        surface_badges=_surface_badges("experiment", draft),
        session_panel=_build_session_panel(draft, sessions, draft_session_id, selected_session_id),
        laser_panel=_build_laser_panel(draft, laser_status),
        ndyag_panel=_build_ndyag_panel(draft),
        acquisition_panel=_build_acquisition_panel(draft, hf2_status),
        run_panel=_build_run_panel(draft.experiment_type, preflight, latest_state),
        summary_metrics=_experiment_summary_metrics(
            draft.experiment_type,
            preflight,
            latest_state,
            current_session_id,
            latest_timeline,
        ),
        workflow_actions=_experiment_workflow_actions(current_session_id, latest_state),
        callouts=_experiment_callouts(scenario, draft.experiment_type, preflight, latest_state),
        configuration_panels=_experiment_configuration_panels(draft, scenario, preflight),
        hardware_cards=device_cards,
        live_data_previews=_timeline_trace_previews(latest_timeline),
        event_log=_timeline_event_log(latest_timeline),
        results_handoff=_operate_results_handoff(draft_session_id, latest_state),
    )


def build_setup_page(
    *,
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
    preflight: PreflightReport,
    latest_state: RunState | None,
    sessions: tuple[SessionSummary, ...],
    laser_status: DeviceStatus,
    hf2_status: DeviceStatus,
    device_cards: tuple[DeviceSummaryCard, ...],
    draft_session_id: str | None,
    selected_session_id: str | None,
) -> SetupPageModel:
    current_session_id = draft_session_id or selected_session_id
    return SetupPageModel(
        title="Setup",
        subtitle="Recipe, hardware, and preflight.",
        state=_setup_page_state(draft.experiment_type, preflight, latest_state),
        surface_badges=_surface_badges("setup", draft),
        summary_metrics=_setup_summary_metrics(draft.experiment_type, preflight, current_session_id, device_cards),
        workflow_actions=_setup_workflow_actions(current_session_id, preflight),
        callouts=_setup_callouts(scenario, draft.experiment_type, preflight),
        session_panel=_build_session_panel(draft, sessions, draft_session_id, selected_session_id),
        laser_panel=_build_laser_panel(draft, laser_status),
        ndyag_panel=_build_ndyag_panel(draft),
        acquisition_panel=_build_acquisition_panel(draft, hf2_status),
        run_panel=_build_setup_validation_panel(draft.experiment_type, preflight, latest_state),
        readiness_panels=_setup_readiness_panels(draft, scenario, preflight, current_session_id),
        hardware_cards=device_cards,
        advanced_sections=_setup_advanced_sections(scenario, preflight),
    )


def build_run_page(
    *,
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
    preflight: PreflightReport,
    latest_state: RunState | None,
    latest_timeline: RunTimeline | None,
    device_cards: tuple[DeviceSummaryCard, ...],
    draft_session_id: str | None,
    selected_session_id: str | None,
) -> RunPageModel:
    current_session_id = draft_session_id or (latest_state.session_id if latest_state is not None else selected_session_id)
    return RunPageModel(
        title="Run",
        subtitle="Run state, timeline, and live data.",
        state=_run_page_state(draft.experiment_type, preflight, latest_state),
        surface_badges=_surface_badges("run", draft),
        summary_metrics=_run_summary_metrics(
            draft.experiment_type,
            preflight,
            latest_state,
            latest_timeline,
            current_session_id,
        ),
        workflow_actions=_run_workflow_actions(current_session_id),
        callouts=_run_callouts(scenario, draft.experiment_type, preflight, latest_state, latest_timeline),
        run_panel=_build_run_panel(draft.experiment_type, preflight, latest_state),
        metadata_panels=_run_metadata_panels(draft, preflight, latest_state, latest_timeline, current_session_id),
        hardware_cards=device_cards,
        live_data_previews=_timeline_trace_previews(latest_timeline),
        event_log=_timeline_event_log(latest_timeline),
        tables=_run_tables(latest_timeline),
        post_run_actions=_run_post_run_actions(current_session_id, latest_state),
    )


def build_advanced_page(
    *,
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
    preflight: PreflightReport,
) -> AdvancedPageModel:
    readiness_rows = tuple(
        (
            check.target,
            check.state.value,
            check.summary,
            "; ".join(issue.message for issue in check.issues) if check.issues else "No issues",
        )
        for check in preflight.checks
    )
    summary_panels = _summary_panels_from_preflight(scenario, preflight)
    calibration = scenario.recipe.calibration_references[0] if scenario.recipe.calibration_references else None
    mapping = scenario.recipe.time_to_wavenumber_mapping
    return AdvancedPageModel(
        title="Advanced",
        subtitle="Timing detail, routing, acquisition tuning, and guarded defaults stay here instead of crowding Experiment.",
        state=_preflight_page_state(
            preflight,
            title="Advanced detail blocked",
            warning_title="Advanced detail warning",
        ),
        surface_badges=_surface_badges("advanced", draft),
        sections=(
            AdvancedSectionModel(
                title="Timing and marker detail",
                subtitle="T0 timing, pump/probe relationships, and selected markers for the current supported recipe.",
                summary_panels=(summary_panels[1], summary_panels[2], summary_panels[3]),
                open_by_default=True,
            ),
            AdvancedSectionModel(
                title="Acquisition and routing detail",
                subtitle="HF2 profile, Pico monitoring selection, and named MUX routing kept out of the main operator flow.",
                summary_panels=(summary_panels[0], summary_panels[4], summary_panels[5]),
            ),
            AdvancedSectionModel(
                title="Calibration and guarded defaults",
                subtitle="Guarded defaults stay reviewable here; calibration changes and recovery stay under Service.",
                summary_panels=(
                    SummaryPanel(
                        title="Calibration context",
                        subtitle="The current reviewable calibration and mapping inputs.",
                        items=(
                            f"Calibration reference: {calibration.calibration_id if calibration else 'none'}",
                            f"Calibration version: {calibration.version if calibration else 'none'}",
                            f"Time-to-wavenumber mapping: {mapping.mapping_id if mapping else 'none'}",
                            f"Mapping scan speed: {mapping.scan_speed_cm1_per_s if mapping else 'n/a'}",
                        ),
                    ),
                ),
                notes=("These values are visible for review and provenance, not routine operator editing.",),
            ),
            AdvancedSectionModel(
                title="Readiness detail",
                subtitle="The explicit preflight checks that used to crowd the landing experience.",
                tables=(
                    TableModel(
                        title="Readiness Matrix",
                        subtitle="Control-plane preflight remains the source for blocked, warning, and ready states.",
                        headers=("Target", "State", "Summary", "Issues"),
                        rows=readiness_rows,
                    ),
                ),
            ),
        ),
        callouts=(
            CalloutModel(
                title="Expert-only detail moved out of Operate",
                body="Timing, routing, calibration, and readiness inspection still exists, but it no longer leads the first five minutes of use.",
                tone="info",
            ),
            CalloutModel(
                title="Service owns bench workflows",
                body="Use Service for diagnostics, calibration custody, and recovery instead of treating Advanced as a generic settings bucket.",
                tone="warn",
            ),
        ),
    )


def build_results_page(
    *,
    draft: OperatorDraftState,
    storage_root: Path,
    sessions: tuple[SessionSummary, ...],
    total_session_count: int,
    selected_session_id: str | None,
    detail: SessionDetail | None,
    search_value: str = "",
    status_filter: str = "all",
    sort_order: str = "updated_desc",
    invalid_selected_session_id: str | None = None,
    selection_hidden_by_filter: bool = False,
    selection_cleared: bool = False,
) -> ResultsPageModel:
    session_cards = _session_cards(sessions, selected_session_id)
    selected_session = next((card for card in session_cards if card.session_id == selected_session_id), None)
    page_state: PageStateModel | None = None
    selected_session_metrics: tuple[StatusItemModel, ...] = ()
    detail_panels: tuple[SummaryPanel, ...] = ()
    artifact_panels: tuple[SummaryPanel, ...] = ()
    artifact_rows: tuple[ResultsArtifactRowModel, ...] = ()
    visualization_panels: tuple[SummaryPanel, ...] = ()
    trace_previews: tuple[ResultsTracePreviewModel, ...] = ()
    storage_panels: tuple[SummaryPanel, ...] = ()
    export_panels: tuple[SummaryPanel, ...] = ()
    event_log: tuple[EventLogItem, ...] = ()

    if total_session_count == 0:
        page_state = empty_state(
            "No saved sessions",
            "This simulator scenario has not persisted a session yet.",
            details=("Nominal scenarios seed one saved fixture and new runs create more.",),
        )
    elif invalid_selected_session_id is not None:
        page_state = fault_state(
            "Saved session not found",
            "The requested session is not available in the persisted catalog.",
            details=(f"Requested session: {invalid_selected_session_id}",),
        )
    elif not session_cards:
        page_state = empty_state(
            "No sessions match the current filter",
            "Adjust the search or status filter to inspect a saved session.",
            details=(f"Search: {search_value or 'none'}", f"Status filter: {status_filter}"),
        )
    elif selection_hidden_by_filter:
        page_state = empty_state(
            "Selected session hidden by the current filter",
            "The active search or status filter removed the selected session from the visible list.",
            details=(
                f"Session: {selected_session_id}",
                "Clear the current selection or widen the filter to keep reviewing it.",
            ),
        )
    elif selection_cleared or selected_session_id is None:
        page_state = empty_state(
            "No session selected",
            "Choose a saved session from the run history to inspect persisted results and artifacts.",
            details=("Session history stays visible so you can browse without reopening a run.",),
        )
    elif selected_session_id is not None and detail is not None:
        selected_session_metrics = _results_selected_session_metrics(detail)
        detail_panels = _detail_panels_from_session_detail(detail)
        artifact_panels = _artifact_panels_from_session_detail(detail)
        artifact_rows = _results_artifact_rows(detail, storage_root)
        visualization_panels = _results_visualization_panels(detail)
        trace_previews = _results_trace_previews(detail, storage_root)
        storage_panels = (
            SummaryPanel(
                title="Saved paths",
                subtitle="Durable session files and reopen inputs for this selection.",
                items=(
                    f"Session directory: {_session_dir(storage_root, selected_session_id)}",
                    f"Manifest: {_manifest_path(storage_root, selected_session_id)}",
                    f"Events: {_events_path(storage_root, selected_session_id)}",
                    f"Replay ready: {'yes' if detail.summary.replay_ready else 'no'}",
                    f"Device snapshots: {len(detail.manifest.device_status_snapshot)}",
                    f"Session notes: {len(detail.manifest.notes)}",
                ),
            ),
        )
        export_panels = _results_export_panels(detail)
        event_log = tuple(
            EventLogItem(
                timestamp=event.emitted_at,
                source=event.source,
                message=event.message,
                tone=event_tone(event.event_type),
            )
            for event in detail.event_timeline
        )
        if detail.manifest.status == SessionStatus.FAULTED:
            page_state = fault_state(
                "Saved session faulted",
                "The selected saved session ended with an explicit persisted fault.",
                details=(
                    (detail.manifest.outcome.latest_fault.message,)
                    if detail.manifest.outcome.latest_fault is not None
                    else (detail.manifest.outcome.failure_reason.value,)
                    if detail.manifest.outcome.failure_reason is not None
                    else ()
                ),
            )
        elif detail.manifest.status == SessionStatus.ABORTED:
            page_state = warning_state(
                "Saved session aborted",
                "The selected saved session was aborted and is being shown from persisted partial state.",
                details=(
                    (detail.manifest.outcome.failure_reason.value,)
                    if detail.manifest.outcome.failure_reason is not None
                    else ()
                ),
            )

    return ResultsPageModel(
        title="Results",
        subtitle="Persisted-session review surface for visualizations, overlays, provenance, and export handoff without turning this into live control.",
        state=page_state,
        surface_badges=_surface_badges("results", draft),
        filters=_results_filters(
            search_value=search_value,
            status_filter=status_filter,
            sort_order=sort_order,
            visible_session_count=len(session_cards),
            total_session_count=total_session_count,
        ),
        sessions=session_cards,
        selected_session=selected_session,
        selected_session_metrics=selected_session_metrics,
        detail_panels=detail_panels,
        artifact_panels=artifact_panels,
        artifact_rows=artifact_rows,
        visualization_panels=visualization_panels,
        trace_previews=trace_previews,
        storage_panels=storage_panels if selected_session_id is not None else (),
        export_panels=export_panels,
        toolbar_actions=_results_toolbar_actions(selected_session_id),
        export_actions=_results_export_actions(selected_session_id, detail),
        callouts=_results_callouts(storage_root, selected_session_id, page_state),
        event_log=event_log,
    )


def build_analyze_page(
    *,
    draft: OperatorDraftState,
    sessions: tuple[SessionSummary, ...],
    selected_session_id: str | None,
    detail: SessionDetail | None,
) -> AnalyzePageModel:
    session_cards = _session_cards(sessions, selected_session_id)
    selected_session = next((card for card in session_cards if card.session_id == selected_session_id), None)
    page_state: PageStateModel | None = None
    summary_panels: tuple[SummaryPanel, ...] = ()
    evaluation_panels: tuple[SummaryPanel, ...] = ()
    callouts: tuple[CalloutModel, ...] = ()
    tables: tuple[TableModel, ...] = ()

    if not session_cards:
        page_state = empty_state(
            "No persisted sessions",
            "Analyze requires a saved session or fixture-backed manifest.",
            details=("Run the nominal simulator path or reopen the saved session fixture first.",),
        )
    elif selected_session_id is not None and detail is not None:
        summary_panels = _analyze_summary_panels(detail)
        evaluation_panels = _analyze_evaluation_panels(detail)
        callouts = _analyze_callouts(detail)
        tables = _analyze_tables(detail)
        if not detail.summary.replay_ready:
            page_state = warning_state(
                "Replay inputs incomplete",
                "This selected session exists, but it cannot be replayed cleanly from persisted raw artifacts.",
                details=("Processing and analysis should continue to depend on persisted inputs only.",),
            )
        elif not detail.processed_artifacts and not detail.analysis_artifacts:
            page_state = warning_state(
                "Analyze scaffold visible",
                "The analysis surface is reviewable now, but processing and analysis runners are not wired yet.",
                details=("The UI is exposing the required controls before headless analysis implementation lands.",),
            )

    return AnalyzePageModel(
        title="Analyze",
        subtitle="Saved-session scientific evaluation surface for reprocessing, comparison, and derived metrics. Live control stays elsewhere.",
        state=page_state,
        surface_badges=_surface_badges("analyze", draft),
        sessions=session_cards,
        selected_session=selected_session,
        summary_panels=summary_panels,
        evaluation_panels=evaluation_panels,
        tables=tables,
        toolbar_actions=_analyze_toolbar_actions(selected_session_id),
        evaluation_actions=_analyze_evaluation_actions(selected_session_id),
        callouts=callouts,
    )


def build_service_page(
    *,
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
    storage_root: Path,
    session_count: int,
    device_cards: tuple[DeviceSummaryCard, ...],
) -> ServicePageModel:
    state = _service_page_state(device_cards)
    return ServicePageModel(
        title="Service",
        subtitle="Bench-owned calibration, diagnostics, timing verification, configuration review, and controlled recovery.",
        state=state,
        surface_badges=_surface_badges("service", draft),
        device_cards=device_cards,
        toolbar_actions=_service_toolbar_actions(session_count),
        maintenance_actions=_service_maintenance_actions(state),
        diagnostic_panels=(
            SummaryPanel(
                title="Timing Roles",
                subtitle="Supported-v1 installed timing identities.",
                items=(
                    "T660-2: master timing source and Nd:YAG fire/Q-switch owner",
                    "T660-1: slave timing source for MIRcat trigger/process/enable outputs",
                ),
            ),
            SummaryPanel(
                title="Local Storage Policy",
                subtitle="Durable session state stays under one storage root for restart-safe reopen and replay.",
                items=(
                    f"Storage root: {storage_root}",
                    "Session manifests live under sessions/<session_id>/manifest.json",
                    "Raw payloads stay under sessions/<session_id>/artifacts/raw/",
                ),
            ),
            SummaryPanel(
                title="Calibration and recovery scope",
                subtitle="Bench-owned truths and recovery actions stay explicit instead of leaking into Experiment.",
                items=(
                    "Calibration references are guarded service-owned inputs.",
                    "Timing verification remains a service review activity.",
                    "Configuration snapshots support restart-safe diagnosis before recovery.",
                ),
            ),
            SummaryPanel(
                title="Scenario Context",
                subtitle="Service review should make the current simulator context explicit.",
                items=(
                    f"Scenario: {scenario.label}",
                    f"Description: {scenario.description}",
                    "Simulator-backed diagnostics remain the default review path before bench hardening.",
                ),
            ),
        ),
        calibration_panels=_service_calibration_panels(scenario),
        recovery_panels=_service_recovery_panels(device_cards, session_count),
        callouts=(
            CalloutModel(
                title="Service stays out of the main path",
                body="Diagnostics and bench-owned recovery remain separate so normal operation can stay compact and task-oriented.",
                tone="warn",
            ),
            *_service_callouts(session_count),
        ),
        tables=_service_tables(storage_root, session_count),
    )


def device_card_from_status(status: DeviceStatus) -> DeviceSummaryCard:
    details = [f"Device ID: {status.device_id}", f"Lifecycle: {status.lifecycle_state.value}"]
    if status.device_role:
        details.append(f"Role: {status.device_role}")
    if status.device_identity:
        details.append(f"Identity: {status.device_identity}")
    details.extend(fault.message for fault in status.reported_faults)
    return DeviceSummaryCard(
        device_label=status.device_kind.value,
        status_label="Ready" if status.ready else ("Offline" if not status.connected else "Attention"),
        tone="good" if status.ready else ("bad" if not status.connected or status.reported_faults else "warn"),
        summary=status.status_summary,
        details=tuple(details),
    )


def _build_session_panel(
    draft: OperatorDraftState,
    sessions: tuple[SessionSummary, ...],
    draft_session_id: str | None,
    selected_session_id: str | None,
) -> OperatePanelModel:
    recent_session_options = tuple(
        FormOptionModel(
            value=session.session_id,
            label=f"{session.session_id} ({session.status.value})",
            selected=session.session_id == selected_session_id,
        )
        for session in sessions[:5]
    )
    return OperatePanelModel(
        title="Session",
        fields=(
            FormFieldModel(
                name="session_label",
                label="Name",
                field_type="text",
                value=draft.session_label,
            ),
            FormFieldModel(
                name="sample_id",
                label="Sample",
                field_type="text",
                value=draft.sample_id,
            ),
            FormFieldModel(
                name="session_id_input",
                label="ID",
                field_type="text",
                value=draft.session_id_input,
            ),
            FormFieldModel(
                name="operator_notes",
                label="Notes",
                field_type="textarea",
                value=draft.operator_notes,
                full_width=True,
            ),
            FormFieldModel(
                name="recent_session_id",
                label="Open Recent",
                field_type="select",
                options=recent_session_options,
                disabled=not bool(recent_session_options),
                full_width=True,
            ),
        ),
        field_columns=3,
        actions=(
            ActionButtonModel(label="Save Session", action="/experiment/session/save"),
            ActionButtonModel(
                label="Open Recent",
                action="/experiment/session/open",
                tone="secondary",
                disabled=not bool(recent_session_options),
            ),
            ActionButtonModel(
                label="Delete Session",
                action="/experiment/session/delete",
                tone="danger",
                disabled=not bool(recent_session_options),
            ),
        ),
    )


def _build_laser_panel(draft: OperatorDraftState, status: DeviceStatus) -> OperatePanelModel:
    armed = bool_vendor_status(status, "armed")
    emission = bool_vendor_status(status, "emission_enabled")
    scan_active = bool_vendor_status(status, "scan_active")
    tune_confirmed = status.vendor_status.get("tune_state") == "tuned"
    fixed_mode = draft.experiment_type == FIXED_WAVELENGTH_EXPERIMENT_TYPE
    pulsed_mode = draft.emission_mode.value == "pulsed"
    mode_fields = (
        FormFieldModel(
            name="experiment_type",
            label="Operating Mode",
            field_type="select",
            options=(
                FormOptionModel(
                    FIXED_WAVELENGTH_EXPERIMENT_TYPE,
                    "Fixed Wavelength",
                    selected=draft.experiment_type == FIXED_WAVELENGTH_EXPERIMENT_TYPE,
                ),
                FormOptionModel(
                    WAVELENGTH_SCAN_EXPERIMENT_TYPE,
                    "Wavelength Scan",
                    selected=draft.experiment_type == WAVELENGTH_SCAN_EXPERIMENT_TYPE,
                ),
            ),
        ),
        FormFieldModel(
            name="emission_mode",
            label="Emission Mode",
            field_type="select",
            options=(
                FormOptionModel("cw", "Continuous Wave", selected=draft.emission_mode.value == "cw"),
                FormOptionModel("pulsed", "Pulsed", selected=draft.emission_mode.value == "pulsed"),
            ),
        ),
    )
    pulse_fields = (
        FormFieldModel(
            name="pulse_repetition_rate_hz",
            label="Pulse repetition rate (Hz)",
            field_type="number",
            value=f"{draft.pulse_repetition_rate_hz:.0f}",
            help_text=f"{PULSE_REPETITION_RATE_MIN_HZ:.0f} Hz to {PULSE_REPETITION_RATE_MAX_HZ:,.0f} Hz",
            disabled=not pulsed_mode,
            hidden=not pulsed_mode,
            min_value=f"{PULSE_REPETITION_RATE_MIN_HZ:.0f}",
            max_value=f"{PULSE_REPETITION_RATE_MAX_HZ:.0f}",
            step="1",
        ),
        FormFieldModel(
            name="pulse_width_ns",
            label="Pulse width (ns)",
            field_type="number",
            value=f"{draft.pulse_width_ns:.0f}",
            help_text=f"{PULSE_WIDTH_MIN_NS:.0f} ns to {PULSE_WIDTH_MAX_NS:.0f} ns, duty cycle max {PULSE_DUTY_CYCLE_MAX_PERCENT:.0f}%",
            disabled=not pulsed_mode,
            hidden=not pulsed_mode,
            min_value=f"{PULSE_WIDTH_MIN_NS:.0f}",
            max_value=f"{PULSE_WIDTH_MAX_NS:.0f}",
            step="1",
        ),
        FormFieldModel(
            name="pulse_duty_cycle_percent",
            label="Duty cycle (%)",
            field_type="number",
            value=f"{draft.pulse_duty_cycle_percent:.3f}",
            help_text=f"Derived from repetition rate x pulse width, max {PULSE_DUTY_CYCLE_MAX_PERCENT:.0f}%",
            disabled=not pulsed_mode,
            hidden=not pulsed_mode,
            read_only=True,
            max_value=f"{PULSE_DUTY_CYCLE_MAX_PERCENT:.0f}",
            step="0.001",
        ),
    )
    fixed_fields = (
        FormFieldModel(
            name="tune_target_cm1",
            label="Wavenumber (cm^-1)",
            field_type="number",
            value=f"{draft.tune_target_cm1:.2f}",
            help_text=f"{MIRCAT_WAVENUMBER_MIN_CM1:.1f} cm^-1 to {MIRCAT_WAVENUMBER_MAX_CM1:.1f} cm^-1",
            min_value=f"{MIRCAT_WAVENUMBER_MIN_CM1:.1f}",
            max_value=f"{MIRCAT_WAVENUMBER_MAX_CM1:.1f}",
            step="0.1",
            disabled=not fixed_mode,
            hidden=not fixed_mode,
        ),
    )
    scan_fields = (
        FormFieldModel(
            name="scan_start_cm1",
            label="Start wavenumber (cm^-1)",
            field_type="number",
            value=f"{draft.scan_start_cm1:.2f}",
            help_text=f"{MIRCAT_WAVENUMBER_MIN_CM1:.1f} cm^-1 to {MIRCAT_WAVENUMBER_MAX_CM1:.1f} cm^-1",
            min_value=f"{MIRCAT_WAVENUMBER_MIN_CM1:.1f}",
            max_value=f"{MIRCAT_WAVENUMBER_MAX_CM1:.1f}",
            step="0.1",
            disabled=fixed_mode,
            hidden=fixed_mode,
        ),
        FormFieldModel(
            name="scan_stop_cm1",
            label="Stop wavenumber (cm^-1)",
            field_type="number",
            value=f"{draft.scan_stop_cm1:.2f}",
            help_text=f"{MIRCAT_WAVENUMBER_MIN_CM1:.1f} cm^-1 to {MIRCAT_WAVENUMBER_MAX_CM1:.1f} cm^-1",
            min_value=f"{MIRCAT_WAVENUMBER_MIN_CM1:.1f}",
            max_value=f"{MIRCAT_WAVENUMBER_MAX_CM1:.1f}",
            step="0.1",
            disabled=fixed_mode,
            hidden=fixed_mode,
        ),
        FormFieldModel(
            name="scan_step_size_cm1",
            label="Scan Speed",
            field_type="number",
            value=f"{draft.scan_step_size_cm1:.2f}",
            help_text=f"{SCAN_SPEED_MIN:.1f} to {SCAN_SPEED_MAX:.0f}",
            min_value=f"{SCAN_SPEED_MIN:.1f}",
            max_value=f"{SCAN_SPEED_MAX:.0f}",
            step="0.1",
            disabled=fixed_mode,
            hidden=fixed_mode,
        ),
    )
    visible_mode_fields = fixed_fields if fixed_mode else scan_fields
    hidden_mode_fields = scan_fields if fixed_mode else fixed_fields
    visible_pulse_fields = pulse_fields if pulsed_mode else ()
    hidden_pulse_fields = () if pulsed_mode else pulse_fields
    return OperatePanelModel(
        title="MIRcat",
        form_action="/experiment/laser/configure",
        fields=(
            *mode_fields,
            *visible_mode_fields,
            *visible_pulse_fields,
        ),
        conditional_fields=(*hidden_mode_fields, *hidden_pulse_fields),
        field_columns=2,
        header_actions=(
            ActionButtonModel(
                "Disconnect" if status.connected else "Connect",
                "/experiment/laser/disconnect" if status.connected else "/experiment/laser/connect",
                tone="danger" if status.connected else "primary",
            ),
        ),
        actions=(
            ActionButtonModel(
                "Disarm" if armed else "Arm",
                "/experiment/laser/disarm" if armed else "/experiment/laser/arm",
                tone="danger" if armed else "secondary",
                disabled=not status.connected,
            ),
            ActionButtonModel(
                "Cancel" if tune_confirmed else "Tune",
                "/experiment/laser/tune",
                disabled=not status.connected,
                hidden=not fixed_mode,
                tone="danger" if tune_confirmed else "primary",
                hidden_fields=(("laser_tune_intent", "cancel"),) if tune_confirmed else (),
            ),
            ActionButtonModel(
                "Start Scan",
                "/experiment/laser/scan/start",
                disabled=not status.connected,
                hidden=fixed_mode,
            ),
            ActionButtonModel(
                "Stop Scan",
                "/experiment/laser/scan/stop",
                tone="danger",
                disabled=not status.connected or not scan_active,
                hidden=fixed_mode,
            ),
            ActionButtonModel(
                "Emission Off" if emission else "Emission On",
                "/experiment/laser/emission/off" if emission else "/experiment/laser/emission/on",
                tone="danger" if emission else "secondary",
                disabled=not status.connected,
            ),
        ),
        footer_callouts=_laser_fault_callouts(status),
    )


def _laser_fault_callouts(status: DeviceStatus) -> tuple[CalloutModel, ...]:
    if not status.reported_faults:
        return ()
    latest_fault = status.reported_faults[-1]
    items = tuple(
        f"{fault.vendor_code}: {fault.vendor_message or fault.message}"
        for fault in status.reported_faults
    )
    return (
        CalloutModel(
            title="MIRcat Errors",
            body=latest_fault.message,
            tone="bad",
            items=items,
        ),
    )


def _build_ndyag_panel(draft: OperatorDraftState) -> OperatePanelModel:
    return OperatePanelModel(
        title="Nd:YAG Settings",
        form_action="/experiment/ndyag/configure",
        field_columns=3,
        header_actions=(
            ActionButtonModel(
                "Off" if draft.ndyag_enabled else "On",
                "/experiment/ndyag/off" if draft.ndyag_enabled else "/experiment/ndyag/on",
                tone="danger" if draft.ndyag_enabled else "secondary",
            ),
        ),
        fields=(
            FormFieldModel(
                name="ndyag_repetition_rate_hz",
                label="Rep. Rate (Hz)",
                field_type="number",
                value=f"{draft.ndyag_repetition_rate_hz:.0f}",
                min_value=f"{NDYAG_REPETITION_RATE_MIN_HZ:.0f}",
                step="1",
                disabled=not draft.ndyag_enabled,
            ),
            FormFieldModel(
                name="ndyag_shot_count",
                label="Shot Count",
                field_type="number",
                value=str(draft.ndyag_shot_count),
                min_value="1",
                max_value=str(NDYAG_SHOT_COUNT_MAX),
                step="1",
                disabled=not draft.ndyag_enabled or draft.ndyag_continuous,
            ),
            FormFieldModel(
                name="ndyag_continuous",
                label="Cont.",
                field_type="checkbox",
                checked=draft.ndyag_continuous,
                disabled=not draft.ndyag_enabled,
            ),
        ),
    )


def _build_acquisition_panel(draft: OperatorDraftState, status: DeviceStatus) -> OperatePanelModel:
    dio_options = (
        FormOptionModel(HF2_DIO_0, "DIO 0", selected=draft.hf2_extref == HF2_DIO_0),
        FormOptionModel(HF2_DIO_1, "DIO 1", selected=draft.hf2_extref == HF2_DIO_1),
        FormOptionModel(HF2_DIO_0_1, "DIO 0|1", selected=draft.hf2_extref == HF2_DIO_0_1),
    )
    trigger_options = (
        FormOptionModel(HF2_DIO_0, "DIO 0", selected=draft.hf2_trigger == HF2_DIO_0),
        FormOptionModel(HF2_DIO_1, "DIO 1", selected=draft.hf2_trigger == HF2_DIO_1),
        FormOptionModel(HF2_DIO_0_1, "DIO 0|1", selected=draft.hf2_trigger == HF2_DIO_0_1),
    )
    return OperatePanelModel(
        title="HF2LI",
        form_action="/experiment/hf2/configure",
        field_columns=2,
        fields=(
            FormFieldModel(
                name="hf2_harmonic",
                label="Order",
                field_type="number",
                value=str(draft.hf2_harmonic),
            ),
            FormFieldModel(
                name="hf2_time_constant_seconds",
                label="Time constant (s)",
                field_type="number",
                value=f"{draft.hf2_time_constant_seconds:.3f}",
            ),
            FormFieldModel(
                name="hf2_sample_rate_hz",
                label="Transfer Rate",
                field_type="number",
                value=f"{draft.hf2_sample_rate_hz:.0f}",
            ),
            FormFieldModel(
                name="hf2_extref",
                label="ExtRef",
                field_type="select",
                options=dio_options,
            ),
            FormFieldModel(
                name="hf2_trigger",
                label="Trigger",
                field_type="select",
                options=trigger_options,
            ),
        ),
        header_actions=(
            ActionButtonModel(
                "Disconnect" if status.connected else "Connect",
                "/experiment/hf2/disconnect" if status.connected else "/experiment/hf2/connect",
                tone="danger" if status.connected else "primary",
            ),
        ),
    )


def _build_run_panel(experiment_type: str, preflight: PreflightReport, latest_state: RunState | None) -> OperatePanelModel:
    ready_to_start = _start_experiment_ready(experiment_type, preflight)
    run_label, run_tone = _experiment_state_summary(experiment_type, preflight, latest_state)
    run_state: PageStateModel | None = None
    blocking_messages = _operator_preflight_messages(preflight, blocking_only=True)
    abort_disabled = latest_state is None or latest_state.phase in {RunPhase.COMPLETED, RunPhase.FAULTED, RunPhase.ABORTED}
    if latest_state is not None and latest_state.phase == RunPhase.FAULTED and latest_state.latest_fault is not None:
        run_state = fault_state("Run faulted", latest_state.latest_fault.message)
    elif latest_state is not None and latest_state.phase == RunPhase.ABORTED:
        run_state = warning_state(
            "Run aborted",
            "The canonical run stopped on an explicit abort path and the partial session remains reviewable.",
            details=((latest_state.failure_reason.value,) if latest_state.failure_reason is not None else ()),
        )
    elif latest_state is not None and latest_state.phase == RunPhase.COMPLETED:
        run_state = success_state(
            "Run complete",
            "The latest run completed successfully and its persisted session is ready for Results review.",
            details=((f"Session {latest_state.session_id}",) if latest_state.session_id is not None else ()),
        )
    elif not preflight.ready_to_start:
        run_state = blocked_state(
            "Experiment blocked",
            "Finish the required setup items before starting the experiment.",
            details=blocking_messages,
        )
    elif not _start_experiment_supported(experiment_type):
        run_state = warning_state(
            "Scan run orchestration still pending",
            "Wavelength scan rendering is live, but full Start Experiment scan orchestration is not yet wired.",
            details=("Use Start Scan / Stop Scan for simulator-backed scan review in this pass.",),
        )
    return OperatePanelModel(
        title="Run Control",
        actions=(
            ActionButtonModel(
                "Run Preflight",
                "/setup/preflight",
                helper_text="Re-evaluate the canonical preflight path before starting.",
            ),
            ActionButtonModel(
                "Start Run",
                "/run/start",
                disabled=not ready_to_start,
                helper_text=(
                    "Clear the blocking setup items before starting."
                    if blocking_messages
                    else "Fixed-wavelength Start Run is the only fully wired run path in this simulator."
                    if not _start_experiment_supported(experiment_type)
                    else "Start the canonical run path."
                ),
            ),
            ActionButtonModel(
                "Abort Run",
                "/run/abort",
                tone="danger",
                disabled=abort_disabled,
                helper_text=(
                    "No active run is currently abortable in this simulator runtime."
                    if abort_disabled
                    else "Abort the active canonical run path explicitly."
                ),
            ),
        ),
        status_items=(
            StatusItemModel(
                "Overall readiness",
                "Ready" if ready_to_start else "Attention",
                tone="good" if ready_to_start else "warn",
            ),
            StatusItemModel("Current run state", run_label, tone=run_tone),
            StatusItemModel(
                "Blocking or warning summary",
                _run_issue_summary(experiment_type, preflight),
                tone="good" if ready_to_start else "warn",
            ),
        ),
        state=run_state,
    )


def _build_setup_validation_panel(
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
) -> OperatePanelModel:
    blocking_messages = _operator_preflight_messages(preflight, blocking_only=True)
    warning_messages = _operator_preflight_messages(preflight, warning_only=True)
    ready_to_start = _start_experiment_ready(experiment_type, preflight)
    status_value = "Validated" if ready_to_start else "Attention"
    if latest_state is not None and latest_state.phase == RunPhase.COMPLETED:
        status_value = "Validated from last successful run"
    return OperatePanelModel(
        title="Preflight / Validation",
        actions=(
            ActionButtonModel(
                "Run Preflight",
                "/setup/preflight",
                helper_text="Refresh the canonical readiness evaluation using the current draft recipe and hardware state.",
            ),
        ),
        status_items=(
            StatusItemModel(
                "Overall readiness",
                status_value,
                tone="good" if ready_to_start else "warn",
                detail="Run uses the same canonical preflight and orchestration path as Experiment.",
            ),
            StatusItemModel(
                "Blocking checks",
                str(len(blocking_messages)),
                tone="good" if not blocking_messages else "bad",
                detail=blocking_messages[0] if blocking_messages else "No blocking checks remain.",
            ),
            StatusItemModel(
                "Warnings",
                str(len(warning_messages)),
                tone="good" if not warning_messages else "warn",
                detail=warning_messages[0] if warning_messages else "No warning-only issues remain.",
            ),
        ),
        state=_setup_page_state(experiment_type, preflight, latest_state),
        notes=(
            "Setup keeps the system honest: validate here, then move into Run for lifecycle monitoring and results handoff.",
        ),
    )


def _operate_page_state(
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
) -> PageStateModel | None:
    if latest_state is not None and latest_state.phase == RunPhase.FAULTED and latest_state.latest_fault is not None:
        return fault_state(
            "System attention required",
            "The last experiment stopped on an explicit device fault.",
            details=(latest_state.latest_fault.message,),
        )
    if latest_state is not None and latest_state.phase == RunPhase.ABORTED:
        return warning_state(
            "Last run aborted",
            "The last canonical run was aborted and remains available for partial-session review.",
            details=((latest_state.failure_reason.value,) if latest_state.failure_reason is not None else ()),
        )
    if latest_state is not None and latest_state.phase == RunPhase.COMPLETED:
        return success_state(
            "Latest run complete",
            "The latest run completed and its saved session is ready for Results.",
            details=((f"Session {latest_state.session_id}",) if latest_state.session_id is not None else ()),
        )
    if preflight.ready_to_start and not _start_experiment_supported(experiment_type):
        return warning_state(
            "Scan mode is partially wired",
            "The page now supports wavelength scan controls, but Start Experiment remains fixed-mode only in this pass.",
            details=("Use Start Scan / Stop Scan for the simulator-backed scan path.",),
        )
    return _preflight_page_state(
        preflight,
        title="Experiment not ready",
        warning_title="Experiment ready with warnings",
        success_title="Experiment ready",
        success_message="The current recipe and hardware state passed the required checks for the canonical fixed-wavelength run.",
    )


def _preflight_page_state(
    preflight: PreflightReport,
    *,
    title: str,
    warning_title: str,
    success_title: str | None = None,
    success_message: str | None = None,
    success_details: tuple[str, ...] = (),
) -> PageStateModel | None:
    blocking_messages = _operator_preflight_messages(preflight, blocking_only=True)
    warning_messages = _operator_preflight_messages(preflight, warning_only=True)
    if blocking_messages:
        return blocked_state(
            title,
            "One or more required checks are still blocking the experiment.",
            details=blocking_messages,
        )
    if warning_messages:
        return warning_state(
            warning_title,
            "The experiment can proceed, but something still needs attention.",
            details=warning_messages,
        )
    if success_title is not None:
        return success_state(
            success_title,
            success_message or "The current experiment state passed the required checks.",
            details=success_details,
        )
    return None


def _setup_page_state(
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
) -> PageStateModel | None:
    if latest_state is not None and latest_state.phase == RunPhase.FAULTED and latest_state.latest_fault is not None:
        return fault_state(
            "Setup attention required",
            "The last run fault is still the most urgent operator issue.",
            details=(latest_state.latest_fault.message,),
        )
    if preflight.ready_to_start and not _start_experiment_supported(experiment_type):
        return warning_state(
            "Setup validated with limits",
            "Wavelength scan configuration is reviewable here, but full Start Run support remains fixed-wavelength only.",
            details=("Use the scan recipe controls for simulator-backed scan review until scan run wiring lands.",),
        )
    return _preflight_page_state(
        preflight,
        title="Setup blocked",
        warning_title="Setup ready with warnings",
        success_title="Setup validated",
        success_message="The current draft recipe passed preflight and is ready for the focused Run workspace.",
    )


def _run_page_state(
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
) -> PageStateModel | None:
    if latest_state is not None and latest_state.phase == RunPhase.FAULTED and latest_state.latest_fault is not None:
        return fault_state(
            "Run faulted",
            "The authoritative run state reports an explicit device fault.",
            details=(latest_state.latest_fault.message,),
        )
    if latest_state is not None and latest_state.phase == RunPhase.ABORTED:
        return warning_state(
            "Run aborted",
            "The run ended on the explicit abort path and the partial session remains reviewable.",
            details=((latest_state.failure_reason.value,) if latest_state.failure_reason is not None else ()),
        )
    if latest_state is not None and latest_state.phase == RunPhase.COMPLETED:
        return success_state(
            "Run completed",
            "The latest run completed and can be handed off to Results for persisted review.",
            details=((f"Session {latest_state.session_id}",) if latest_state.session_id is not None else ()),
        )
    if preflight.ready_to_start and not _start_experiment_supported(experiment_type):
        return warning_state(
            "Run surface ready with scan limitations",
            "The Run workspace is available, but the fixed-wavelength canonical start path remains the only fully wired run action.",
            details=("Use the MIRcat scan controls for simulator-backed scan review.",),
        )
    return _preflight_page_state(
        preflight,
        title="Run blocked",
        warning_title="Run ready with warnings",
        success_title="Run ready",
        success_message="The canonical run path is validated and ready to start.",
    )


def _start_experiment_supported(experiment_type: str) -> bool:
    return experiment_type == FIXED_WAVELENGTH_EXPERIMENT_TYPE


def _start_experiment_ready(experiment_type: str, preflight: PreflightReport) -> bool:
    return preflight.ready_to_start and _start_experiment_supported(experiment_type)


def _run_issue_summary(experiment_type: str, preflight: PreflightReport) -> str:
    issues = _operator_preflight_messages(preflight)
    if issues:
        return issues[0]
    if not _start_experiment_supported(experiment_type):
        return "Wavelength scan Start Run orchestration is not yet fully wired."
    return "No blocking or warning issues remain."


def _experiment_state_summary(
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
) -> tuple[str, str]:
    if latest_state is not None:
        if latest_state.phase in {RunPhase.STARTING, RunPhase.RUNNING, RunPhase.STOPPING}:
            return latest_state.phase.value.replace("_", " ").title(), phase_tone(latest_state.phase)
        if latest_state.phase == RunPhase.COMPLETED:
            return "Completed", "good"
        if latest_state.phase == RunPhase.ABORTED:
            return "Aborted", "warn"
        if latest_state.phase == RunPhase.FAULTED:
            return "Faulted", "bad"
        return latest_state.phase.value.replace("_", " ").title(), phase_tone(latest_state.phase)
    if not preflight.ready_to_start:
        return "Preflight blocked", "warn"
    if _start_experiment_ready(experiment_type, preflight):
        return "Validated", "good"
    if preflight.ready_to_start:
        return "Validated with limits", "warn"
    return "Idle", "neutral"


def _operator_preflight_messages(
    preflight: PreflightReport,
    *,
    blocking_only: bool = False,
    warning_only: bool = False,
) -> tuple[str, ...]:
    messages: list[str] = []
    seen: set[str] = set()
    for check in preflight.checks:
        for issue in check.issues:
            if blocking_only and not issue.blocking:
                continue
            if warning_only and issue.blocking:
                continue
            message = _operator_issue_message(check.target)
            if message not in seen:
                seen.add(message)
                messages.append(message)
    return tuple(messages)


def _operator_issue_message(target: str) -> str:
    if target == "mircat-qcl":
        return "Connect and arm the MIRcat probe."
    if target == "hf2li-primary":
        return "Connect the HF2LI and confirm the acquisition setup."
    if target in {"t660-2-master", "t660-1-slave", "arduino-mux"}:
        return "A hidden timing dependency is unavailable for this experiment."
    if target == "picoscope-5244d":
        return "Secondary monitor hardware is unavailable."
    return "One of the required experiment checks is not ready yet."


def _surface_badges(surface: str, draft: OperatorDraftState) -> tuple[StatusBadge, ...]:
    badge_map = {
        "experiment": (
            StatusBadge(label="Operator", tone="good"),
            StatusBadge(label=f"{experiment_type_label(draft.experiment_type)}", tone="neutral"),
        ),
        "setup": (
            StatusBadge(label="Preflight", tone="good"),
            StatusBadge(label="Advanced on demand", tone="info"),
        ),
        "run": (
            StatusBadge(label="Live", tone="good"),
            StatusBadge(label="Results handoff", tone="info"),
        ),
        "advanced": (
            StatusBadge(label="Expert only", tone="warn"),
            StatusBadge(label="Timing and routing", tone="info"),
        ),
        "results": (
            StatusBadge(label="Persisted", tone="good"),
            StatusBadge(label="Artifacts", tone="info"),
        ),
        "analyze": (
            StatusBadge(label="Secondary", tone="warn"),
            StatusBadge(label="Persisted inputs", tone="info"),
        ),
        "service": (
            StatusBadge(label="Expert", tone="warn"),
            StatusBadge(label="Recovery", tone="info"),
        ),
    }
    return badge_map[surface]


def _experiment_summary_metrics(
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
    current_session_id: str | None,
    latest_timeline: RunTimeline | None,
) -> tuple[StatusItemModel, ...]:
    run_label, run_tone = _experiment_state_summary(experiment_type, preflight, latest_state)
    blocking_messages = _operator_preflight_messages(preflight, blocking_only=True)
    return (
        StatusItemModel(
            label="Readiness",
            value="Validated" if _start_experiment_ready(experiment_type, preflight) else "Attention",
            tone="good" if _start_experiment_ready(experiment_type, preflight) else "warn",
            detail="The Experiment page stays on the canonical preflight and orchestration path.",
        ),
        StatusItemModel(label="Run state", value=run_label, tone=run_tone),
        StatusItemModel(
            label="Session",
            value=current_session_id or "Not selected",
            tone="neutral",
            detail="Current draft or selected session context.",
        ),
        StatusItemModel(
            label="Latest timeline",
            value=f"{len(latest_timeline.events)} events" if latest_timeline is not None else "No run yet",
            tone="info" if latest_timeline is not None else "neutral",
            detail=(
                f"{len(latest_timeline.live_data_points)} live samples recorded"
                if latest_timeline is not None
                else (blocking_messages[0] if blocking_messages else "Start a run to populate timeline events and live traces.")
            ),
        ),
    )


def _experiment_workflow_actions(
    current_session_id: str | None,
    latest_state: RunState | None,
) -> tuple[SurfaceActionModel, ...]:
    actions: list[SurfaceActionModel] = [
        SurfaceActionModel(
            label="Open Setup Workspace",
            route="setup",
            tone="secondary",
            helper_text="Focus on recipe review, hardware readiness, and preflight.",
        ),
        SurfaceActionModel(
            label="Open Run Workspace",
            route="run",
            tone="secondary",
            helper_text="Focus on authoritative run state, live traces, and post-run handoff.",
        ),
        SurfaceActionModel(
            label="Service Diagnostics",
            route="service",
            tone="ghost",
            helper_text="Use expert-only diagnostics and recovery without polluting normal operation.",
        ),
    ]
    session_id = current_session_id or (latest_state.session_id if latest_state is not None else None)
    actions.append(
        SurfaceActionModel(
            label="Open Results",
            route="results",
            session_id=session_id,
            tone="secondary",
            helper_text=(
                "Open the current session in Results."
                if session_id is not None
                else "Open the persisted session catalog."
            ),
        )
    )
    return tuple(actions)


def _experiment_callouts(
    scenario: SimulatorScenarioContext,
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
) -> tuple[CalloutModel, ...]:
    callouts = [
        CalloutModel(
            title="Scenario",
            body=scenario.label,
            tone="info",
        ),
    ]
    if not _start_experiment_supported(experiment_type):
        callouts.append(
            CalloutModel(
                title="Scan start remains limited",
                body="Scan controls are visible and honest, but Start Run remains fixed-wavelength only in this runtime.",
                tone="warn",
            )
        )
    if latest_state is not None and latest_state.phase == RunPhase.COMPLETED:
        callouts.append(
            CalloutModel(
                title="Latest run completed",
                body="Results are ready for review.",
                tone="good",
            )
        )
    if latest_state is not None and latest_state.phase == RunPhase.FAULTED and latest_state.latest_fault is not None:
        callouts.append(
            CalloutModel(
                title="Latest run fault",
                body=latest_state.latest_fault.message,
                tone="bad",
            )
        )
    if not preflight.ready_to_start:
        callouts.append(
            CalloutModel(
                title="Blocking issues",
                body="Clear before starting.",
                tone="warn",
                items=_operator_preflight_messages(preflight, blocking_only=True),
            )
        )
    return tuple(callouts)


def _experiment_configuration_panels(
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
    preflight: PreflightReport,
) -> tuple[SummaryPanel, ...]:
    calibration = scenario.recipe.calibration_references[0] if scenario.recipe.calibration_references else None
    return (
        SummaryPanel(
            title="Current configuration",
            subtitle="",
            items=(
                f"Session name: {draft.session_label}",
                f"Sample: {draft.sample_id}",
                f"Operating mode: {experiment_type_label(draft.experiment_type)}",
                f"Emission mode: {draft.emission_mode.value.upper()}",
                (
                    f"Tune target: {draft.tune_target_cm1:.2f} cm^-1"
                    if draft.experiment_type == FIXED_WAVELENGTH_EXPERIMENT_TYPE
                    else f"Scan range: {draft.scan_start_cm1:.2f} to {draft.scan_stop_cm1:.2f} cm^-1"
                ),
            ),
        ),
        SummaryPanel(
            title="Preflight focus",
            subtitle="",
            items=(
                f"Checks evaluated: {len(preflight.checks)}",
                f"Blocking issues: {len(_operator_preflight_messages(preflight, blocking_only=True))}",
                f"Warnings: {len(_operator_preflight_messages(preflight, warning_only=True))}",
                f"Calibration: {calibration.calibration_id if calibration else 'none'}",
                f"MUX route set: {preflight.mux_summary.route_set_name}",
            ),
        ),
    )


def _setup_summary_metrics(
    experiment_type: str,
    preflight: PreflightReport,
    current_session_id: str | None,
    device_cards: tuple[DeviceSummaryCard, ...],
) -> tuple[StatusItemModel, ...]:
    good_devices, warn_devices, bad_devices = _device_card_tone_counts(device_cards)
    return (
        StatusItemModel(
            label="Setup readiness",
            value="Validated" if _start_experiment_ready(experiment_type, preflight) else "Attention",
            tone="good" if _start_experiment_ready(experiment_type, preflight) else "warn",
            detail="Validated setup can move directly into the focused Run workspace.",
        ),
        StatusItemModel(
            label="Blocking issues",
            value=str(len(_operator_preflight_messages(preflight, blocking_only=True))),
            tone="good" if preflight.ready_to_start else "bad",
            detail=_run_issue_summary(experiment_type, preflight),
        ),
        StatusItemModel(
            label="Device posture",
            value=f"{good_devices} ready / {warn_devices} warn / {bad_devices} fault",
            tone="bad" if bad_devices else ("warn" if warn_devices else "good"),
            detail="Hardware visibility is first-class here before the run starts.",
        ),
        StatusItemModel(
            label="Current session",
            value=current_session_id or "Not selected",
            tone="neutral",
            detail="The session context that will carry the next run and results.",
        ),
    )


def _setup_workflow_actions(
    current_session_id: str | None,
    preflight: PreflightReport,
) -> tuple[SurfaceActionModel, ...]:
    return (
        SurfaceActionModel(
            label="Open Run Workspace",
            route="run",
            tone="secondary",
            helper_text=(
                "Setup is validated. Move into Run for lifecycle monitoring."
                if preflight.ready_to_start
                else "Run remains available, but Setup is still reporting blocking or warning states."
            ),
        ),
        SurfaceActionModel(
            label="Review Results",
            route="results",
            session_id=current_session_id,
            tone="ghost",
            helper_text=(
                "Open the current session in Results."
                if current_session_id is not None
                else "Browse saved sessions while Setup work continues."
            ),
        ),
        SurfaceActionModel(
            label="Advanced Detail",
            route="advanced",
            tone="ghost",
            helper_text="Inspect timing, routing, and guarded defaults without crowding the main setup path.",
        ),
    )


def _setup_callouts(
    scenario: SimulatorScenarioContext,
    experiment_type: str,
    preflight: PreflightReport,
) -> tuple[CalloutModel, ...]:
    callouts = [
        CalloutModel(
            title="Setup stays task-oriented",
            body="Routine operators should understand what is selected, what is blocked, and whether the run is safe to start without reading architecture detail.",
            tone="good",
        ),
        CalloutModel(
            title="Scenario",
            body=scenario.label,
            tone="info",
        ),
    ]
    if not preflight.ready_to_start:
        callouts.append(
            CalloutModel(
                title="Blocking issues",
                body="Preflight is blocking start.",
                tone="warn",
                items=_operator_preflight_messages(preflight, blocking_only=True),
            )
        )
    if not _start_experiment_supported(experiment_type):
        callouts.append(
            CalloutModel(
                title="Scan setup is honest about limits",
                body="Scan recipe controls are reviewable here, but Start Run remains fixed-wavelength only in this runtime.",
                tone="warn",
            )
        )
    return tuple(callouts)


def _setup_readiness_panels(
    draft: OperatorDraftState,
    scenario: SimulatorScenarioContext,
    preflight: PreflightReport,
    current_session_id: str | None,
) -> tuple[SummaryPanel, ...]:
    calibration = scenario.recipe.calibration_references[0] if scenario.recipe.calibration_references else None
    mapping = scenario.recipe.time_to_wavenumber_mapping
    return (
        SummaryPanel(
            title="Experiment selection",
            subtitle="",
            items=(
                f"Current session: {current_session_id or 'not selected'}",
                f"Recipe: {scenario.recipe.title}",
                f"Operating mode: {experiment_type_label(draft.experiment_type)}",
                f"Emission mode: {draft.emission_mode.value.upper()}",
                f"HF2 transfer rate: {draft.hf2_sample_rate_hz:.0f} Hz",
            ),
        ),
        SummaryPanel(
            title="Preflight summary",
            subtitle="",
            items=(
                f"Ready to start: {'yes' if preflight.ready_to_start else 'no'}",
                f"Checks evaluated: {len(preflight.checks)}",
                f"Blocking issues: {len(_operator_preflight_messages(preflight, blocking_only=True))}",
                f"Warnings: {len(_operator_preflight_messages(preflight, warning_only=True))}",
                f"Generated: {preflight.generated_at.isoformat()}",
            ),
        ),
        SummaryPanel(
            title="Calibration and defaults",
            subtitle="",
            items=(
                f"Calibration reference: {calibration.calibration_id if calibration else 'none'}",
                f"Mapping id: {mapping.mapping_id if mapping else 'none'}",
                f"MUX route set: {preflight.mux_summary.route_set_name}",
                f"Pico mode: {preflight.pico_summary.mode.value}",
                f"Acquisition mode: {preflight.pump_probe_summary.acquisition_timing_mode.value}",
            ),
        ),
    )


def _setup_advanced_sections(
    scenario: SimulatorScenarioContext,
    preflight: PreflightReport,
) -> tuple[AdvancedSectionModel, ...]:
    summary_panels = _summary_panels_from_preflight(scenario, preflight)
    return (
        AdvancedSectionModel(
            title="Timing and synchronization detail",
            subtitle="",
            summary_panels=(summary_panels[1], summary_panels[2], summary_panels[3]),
        ),
        AdvancedSectionModel(
            title="Acquisition and routing detail",
            subtitle="",
            summary_panels=(summary_panels[0], summary_panels[4], summary_panels[5]),
        ),
    )


def _run_summary_metrics(
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
    latest_timeline: RunTimeline | None,
    current_session_id: str | None,
) -> tuple[StatusItemModel, ...]:
    run_label, run_tone = _experiment_state_summary(experiment_type, preflight, latest_state)
    live_points = len(latest_timeline.live_data_points) if latest_timeline is not None else 0
    return (
        StatusItemModel(label="Current phase", value=run_label, tone=run_tone),
        StatusItemModel(
            label="Session",
            value=current_session_id or "Not selected",
            tone="neutral",
            detail="The session attached to the latest canonical run timeline.",
        ),
        StatusItemModel(
            label="Timeline",
            value=f"{len(latest_timeline.states)} states" if latest_timeline is not None else "No run timeline",
            tone="info" if latest_timeline is not None else "warn",
            detail=(
                f"{len(latest_timeline.events)} events recorded"
                if latest_timeline is not None
                else "Start Run to populate the authoritative timeline."
            ),
        ),
        StatusItemModel(
            label="Live data",
            value=f"{live_points} samples" if live_points else "No live samples",
            tone="good" if live_points else "neutral",
            detail="Live previews come from the authoritative run timeline instead of UI-local buffers.",
        ),
    )


def _run_workflow_actions(current_session_id: str | None) -> tuple[SurfaceActionModel, ...]:
    return (
        SurfaceActionModel(
            label="Back to Setup",
            route="setup",
            tone="secondary",
            helper_text="Review preflight and recipe details without leaving the canonical workflow.",
        ),
        SurfaceActionModel(
            label="Mission Control",
            route="experiment",
            tone="ghost",
            helper_text="Return to the default Experiment overview surface.",
        ),
        SurfaceActionModel(
            label="Open Results",
            route="results",
            session_id=current_session_id,
            tone="secondary",
            helper_text=(
                "Open the current session in Results."
                if current_session_id is not None
                else "Browse persisted sessions after or before a run."
            ),
        ),
    )


def _run_callouts(
    scenario: SimulatorScenarioContext,
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
    latest_timeline: RunTimeline | None,
) -> tuple[CalloutModel, ...]:
    callouts = [
        CalloutModel(
            title="Authoritative run surface",
            body="Run shows control-plane state, live timeline data, and hardware posture. It does not invent orchestration logic in the UI.",
            tone="good",
        ),
        CalloutModel(
            title="Scenario",
            body=scenario.label,
            tone="info",
        ),
    ]
    if latest_timeline is not None:
        callouts.append(
            CalloutModel(
                title="Timeline captured",
                body=f"{len(latest_timeline.events)} events · {len(latest_timeline.live_data_points)} samples",
                tone="good",
            )
        )
    if latest_state is not None and latest_state.phase == RunPhase.FAULTED and latest_state.latest_fault is not None:
        callouts.append(
            CalloutModel(
                title="Fault surfaced explicitly",
                body=latest_state.latest_fault.message,
                tone="bad",
            )
        )
    if not _start_experiment_supported(experiment_type) and preflight.ready_to_start:
        callouts.append(
            CalloutModel(
                title="Scan start remains explicitly unavailable",
                body="The Run surface stays visible for scan review, but the canonical Start Run button remains fixed-wavelength only.",
                tone="warn",
            )
        )
    return tuple(callouts)


def _run_metadata_panels(
    draft: OperatorDraftState,
    preflight: PreflightReport,
    latest_state: RunState | None,
    latest_timeline: RunTimeline | None,
    current_session_id: str | None,
) -> tuple[SummaryPanel, ...]:
    progress_percent = (
        f"{(latest_state.progress_fraction or 0.0) * 100:.0f}%"
        if latest_state is not None and latest_state.progress_fraction is not None
        else "n/a"
    )
    run_id = latest_timeline.run_id if latest_timeline is not None else "n/a"
    return (
        SummaryPanel(
            title="Run context",
            subtitle="The current session and run identifiers that anchor the live workspace.",
            items=(
                f"Run id: {run_id}",
                f"Session: {current_session_id or 'not selected'}",
                f"Operating mode: {experiment_type_label(draft.experiment_type)}",
                f"Emission mode: {draft.emission_mode.value.upper()}",
                f"Progress: {progress_percent}",
            ),
        ),
        SummaryPanel(
            title="Timing and acquisition",
            subtitle="The high-level timing and acquisition context behind the current run view.",
            items=(
                f"T0 label: {preflight.timing_summary.t0_label}",
                f"Probe timing mode: {preflight.pump_probe_summary.probe_timing_mode.value}",
                f"Acquisition timing mode: {preflight.pump_probe_summary.acquisition_timing_mode.value}",
                f"Markers: {', '.join(marker.value for marker in preflight.selected_markers) if preflight.selected_markers else 'none'}",
                f"Pico mode: {preflight.pico_summary.mode.value}",
            ),
        ),
        SummaryPanel(
            title="Run handoff",
            subtitle="What happens next after the current run state.",
            items=(
                (
                    "Open Results for persisted-session review."
                    if latest_state is not None and latest_state.phase == RunPhase.COMPLETED
                    else "Clear blocking issues and start the run."
                    if latest_state is None
                    else "Review Service for diagnostics before retrying."
                    if latest_state.phase == RunPhase.FAULTED
                    else "Results remains available even for partial or aborted sessions."
                ),
                f"Timeline events: {len(latest_timeline.events) if latest_timeline is not None else 0}",
                f"Live samples: {len(latest_timeline.live_data_points) if latest_timeline is not None else 0}",
            ),
        ),
    )


def _run_tables(latest_timeline: RunTimeline | None) -> tuple[TableModel, ...]:
    tables = [
        TableModel(
            title="Lifecycle coverage",
            subtitle="How the current runtime represents the supported run lifecycle.",
            headers=("Lifecycle state", "Current support", "Meaning"),
            rows=(
                ("Idle", "explicit", "No authoritative run has started yet."),
                ("Validated", "explicit", "Preflight passed and Start Run is available."),
                ("Starting", "timeline", "Captured in the authoritative run timeline once a run starts."),
                ("Running", "timeline", "Captured in the authoritative run timeline while acquisition is active."),
                ("Aborting", "not distinct", "Current runtime aborts directly to Aborted without a separate intermediate phase."),
                ("Aborted", "explicit", "Operator abort is recorded and preserved for partial-session review."),
                ("Completed", "explicit", "Successful completion is recorded and handed off to Results."),
                ("Faulted", "explicit", "Vendor or driver faults surface here without UI-side recovery magic."),
            ),
        )
    ]
    if latest_timeline is not None:
        tables.append(
            TableModel(
                title="Latest run timeline",
                subtitle="Authoritative state progression emitted by the current run timeline.",
                headers=("Phase", "Active step", "Progress", "Last event"),
                rows=tuple(
                    (
                        state.phase.value,
                        state.active_step or "n/a",
                        f"{(state.progress_fraction or 0.0) * 100:.0f}%",
                        state.last_event_id or "n/a",
                    )
                    for state in latest_timeline.states
                ),
            )
        )
    return tuple(tables)


def _run_post_run_actions(
    current_session_id: str | None,
    latest_state: RunState | None,
) -> tuple[SurfaceActionModel, ...]:
    if current_session_id is None:
        return ()
    results_helper = (
        "Persisted review is ready."
        if latest_state is not None and latest_state.phase == RunPhase.COMPLETED
        else "Results remains available for completed, aborted, and faulted sessions."
    )
    return (
        SurfaceActionModel(
            label="Open Results",
            route="results",
            session_id=current_session_id,
            tone="secondary",
            helper_text=results_helper,
        ),
        SurfaceActionModel(
            label="Analyze Session",
            route="analyze",
            session_id=current_session_id,
            tone="ghost",
            helper_text="Scientific evaluation remains downstream of persisted session truth.",
        ),
    )


def _timeline_event_log(latest_timeline: RunTimeline | None) -> tuple[EventLogItem, ...]:
    if latest_timeline is None:
        return ()
    return tuple(
        EventLogItem(
            timestamp=event.emitted_at,
            source=event.source,
            message=event.message,
            tone=event_tone(event.event_type),
        )
        for event in latest_timeline.events
    )


def _timeline_trace_previews(latest_timeline: RunTimeline | None) -> tuple[TracePreviewModel, ...]:
    if latest_timeline is None or not latest_timeline.live_data_points:
        return ()
    grouped = _group_live_data_points(latest_timeline.live_data_points)
    previews: list[TracePreviewModel] = []
    for points in grouped[:3]:
        previews.append(_trace_preview_from_live_data(points))
    return tuple(previews)


def _group_live_data_points(live_data_points: tuple[LiveDataPoint, ...]) -> list[tuple[LiveDataPoint, ...]]:
    grouped: dict[tuple[str, str], list[LiveDataPoint]] = {}
    for point in live_data_points:
        key = (point.source_role.value, point.stream_name)
        grouped.setdefault(key, []).append(point)
    return [tuple(points) for points in grouped.values()]


def _trace_preview_from_live_data(points: tuple[LiveDataPoint, ...]) -> TracePreviewModel:
    first = points[0]
    axis_values = tuple(point.axis_value for point in points)
    y_values = tuple(point.value for point in points)
    role_label = "Primary live data" if first.source_role.value == "primary_raw" else "Secondary monitor"
    title = f"{role_label} — {first.stream_name}"
    subtitle = "Authoritative run-timeline preview for the latest simulator-backed run."
    return TracePreviewModel(
        title=title,
        subtitle=subtitle,
        sample_count_label=f"{len(points)} samples",
        axis_label=f"{first.axis_label} ({first.axis_units})" if first.axis_units else first.axis_label,
        axis_start_label=_format_measurement(min(axis_values), first.axis_units),
        axis_end_label=_format_measurement(max(axis_values), first.axis_units),
        value_min_label=_format_measurement(min(y_values), first.units),
        value_max_label=_format_measurement(max(y_values), first.units),
        polyline_points=_sparkline_points(tuple((point.axis_value, point.value) for point in points)),
        note_lines=(
            f"Source role: {first.source_role.value}",
            f"Last captured: {points[-1].captured_at.isoformat()}",
        ),
    )


def _device_card_tone_counts(device_cards: tuple[DeviceSummaryCard, ...]) -> tuple[int, int, int]:
    good = sum(1 for card in device_cards if card.tone == "good")
    warn = sum(1 for card in device_cards if card.tone == "warn")
    bad = sum(1 for card in device_cards if card.tone == "bad")
    return good, warn, bad


def _summary_panels_from_preflight(
    scenario: SimulatorScenarioContext,
    preflight: PreflightReport,
) -> tuple[SummaryPanel, ...]:
    return (
        SummaryPanel(
            title="Recipe Mode",
            subtitle="Experiment-first recipe and acquisition shape.",
            items=(
                f"Probe spectral mode: {scenario.recipe.mircat.spectral_mode.value}",
                f"Probe emission mode: {scenario.recipe.mircat.emission_mode.value}",
                f"HF2 profile: {scenario.recipe.hf2_primary_acquisition.profile_name}",
            ),
        ),
        SummaryPanel(
            title="T0 Timing",
            subtitle="Canonical timing summary relative to the neutral master-layer origin.",
            items=tuple(f"{entry.label}: {entry.offset_ns:.0f} ns" for entry in preflight.timing_summary.entries),
        ),
        SummaryPanel(
            title="Pump / Probe / Acquisition",
            subtitle="Supported-v1 relationship semantics.",
            items=(
                f"Pump shots before probe: {preflight.pump_probe_summary.pump_shots_before_probe}",
                f"Probe timing mode: {preflight.pump_probe_summary.probe_timing_mode.value}",
                f"Acquisition timing mode: {preflight.pump_probe_summary.acquisition_timing_mode.value}",
                (
                    "Acquisition reference: "
                    f"{preflight.pump_probe_summary.acquisition_reference_marker.value if preflight.pump_probe_summary.acquisition_reference_marker else 'n/a'}"
                ),
            ),
        ),
        SummaryPanel(
            title="Selected Markers",
            subtitle="Persisted digital timing references for acquisition and diagnostics.",
            items=tuple(marker.value for marker in preflight.selected_markers),
        ),
        SummaryPanel(
            title="MUX Routes",
            subtitle="Named route selection for Pico channel A, channel B, and external trigger.",
            items=(
                f"Route set: {preflight.mux_summary.route_set_name}",
                f"Channel A: {preflight.mux_summary.channel_a}",
                f"Channel B: {preflight.mux_summary.channel_b}",
                f"External trigger: {preflight.mux_summary.external_trigger}",
            ),
        ),
        SummaryPanel(
            title="Pico Secondary",
            subtitle="Secondary monitoring and recording selection.",
            items=(
                f"Mode: {preflight.pico_summary.mode.value}",
                (
                    "Trigger marker: "
                    f"{preflight.pico_summary.trigger_marker.value if preflight.pico_summary.trigger_marker else 'none'}"
                ),
                (
                    "Recorded inputs: "
                    f"{', '.join(preflight.pico_summary.recorded_inputs) if preflight.pico_summary.recorded_inputs else 'none'}"
                ),
            ),
        ),
    )


def _session_cards(
    sessions: tuple[SessionSummary, ...],
    selected_session_id: str | None,
) -> tuple[SessionSummaryCard, ...]:
    return tuple(
        SessionSummaryCard(
            session_id=summary.session_id,
            recipe_title=summary.recipe_title,
            status_label=summary.status.value.title(),
            updated_at=summary.updated_at,
            primary_raw_artifact_count=summary.primary_raw_artifact_count,
            secondary_monitor_artifact_count=summary.secondary_monitor_artifact_count,
            processed_artifact_count=summary.processed_artifact_count,
            analysis_artifact_count=summary.analysis_artifact_count,
            export_artifact_count=summary.export_artifact_count,
            event_count=summary.event_count,
            replay_ready=summary.replay_ready,
            failure_reason_label=summary.failure_reason.value if summary.failure_reason else None,
            selected=summary.session_id == selected_session_id,
        )
        for summary in sessions
    )


def _results_filters(
    *,
    search_value: str,
    status_filter: str,
    sort_order: str,
    visible_session_count: int,
    total_session_count: int,
) -> ResultsFilterModel:
    return ResultsFilterModel(
        search_value=search_value,
        status_options=(
            FormOptionModel(value="all", label="All Statuses", selected=status_filter == "all"),
            FormOptionModel(value="completed", label="Completed", selected=status_filter == "completed"),
            FormOptionModel(value="faulted", label="Faulted", selected=status_filter == "faulted"),
            FormOptionModel(value="aborted", label="Aborted", selected=status_filter == "aborted"),
            FormOptionModel(value="planned", label="Planned", selected=status_filter == "planned"),
            FormOptionModel(value="active", label="Active", selected=status_filter == "active"),
        ),
        sort_options=(
            FormOptionModel(value="updated_desc", label="Newest First", selected=sort_order == "updated_desc"),
            FormOptionModel(value="updated_asc", label="Oldest First", selected=sort_order == "updated_asc"),
            FormOptionModel(value="artifacts_desc", label="Most Artifacts", selected=sort_order == "artifacts_desc"),
        ),
        visible_session_count=visible_session_count,
        total_session_count=total_session_count,
    )


def _results_selected_session_metrics(detail: SessionDetail) -> tuple[StatusItemModel, ...]:
    total_artifacts = (
        len(detail.primary_raw_artifacts)
        + len(detail.secondary_monitor_artifacts)
        + len(detail.processed_artifacts)
        + len(detail.analysis_artifacts)
        + len(detail.export_artifacts)
    )
    last_event = detail.summary.last_event_at.isoformat() if detail.summary.last_event_at is not None else "n/a"
    return (
        StatusItemModel(
            label="Status",
            value=detail.summary.status.value.title(),
            tone=_session_status_tone(detail.summary.status),
            detail=f"Updated {detail.summary.updated_at.isoformat()}",
        ),
        StatusItemModel(
            label="Replay",
            value="Ready" if detail.summary.replay_ready else "Unavailable",
            tone="good" if detail.summary.replay_ready else "warn",
            detail=f"Primary inputs {len(detail.replay_plan.primary_raw_artifact_ids)}",
        ),
        StatusItemModel(
            label="Artifacts",
            value=str(total_artifacts),
            tone="neutral",
            detail=(
                f"{len(detail.primary_raw_artifacts)} raw / {len(detail.processed_artifacts)} processed / "
                f"{len(detail.analysis_artifacts)} analysis / {len(detail.export_artifacts)} export"
            ),
        ),
        StatusItemModel(
            label="Timeline",
            value=f"{detail.summary.event_count} events",
            tone="neutral",
            detail=f"Last event {last_event}",
        ),
    )


def _detail_panels_from_session_detail(detail: SessionDetail) -> tuple[SummaryPanel, ...]:
    manifest = detail.manifest
    return (
        SummaryPanel(
            title="Run Summary",
            subtitle="Session-centered identity and terminal state.",
            items=(
                f"Session: {manifest.session_id}",
                f"Status: {manifest.status.value.title()}",
                f"Recipe: {manifest.recipe_snapshot.title}",
                f"Replay ready: {'yes' if detail.summary.replay_ready else 'no'}",
                f"Created: {detail.summary.created_at.isoformat()}",
                f"Updated: {detail.summary.updated_at.isoformat()}",
            ),
        ),
        SummaryPanel(
            title="Outcome and Replay",
            subtitle="Persisted outcome and saved reopen inputs only.",
            items=(
                f"Run started: {manifest.outcome.started_at.isoformat() if manifest.outcome.started_at else 'n/a'}",
                f"Run ended: {manifest.outcome.ended_at.isoformat() if manifest.outcome.ended_at else 'n/a'}",
                f"Failure reason: {manifest.outcome.failure_reason.value if manifest.outcome.failure_reason else 'none'}",
                f"Final event: {manifest.outcome.final_event_id or 'n/a'}",
                f"Primary replay inputs: {len(detail.replay_plan.primary_raw_artifact_ids)}",
                f"Secondary replay inputs: {len(detail.replay_plan.secondary_monitor_artifact_ids)}",
            ),
        ),
        SummaryPanel(
            title="Acquisition Context",
            subtitle="Timing, routing, and acquisition settings that explain the saved run.",
            items=(
                f"T0 label: {manifest.timing_summary.t0_label}",
                f"Pump shots before probe: {manifest.pump_probe_summary.pump_shots_before_probe}",
                f"Probe timing mode: {manifest.pump_probe_summary.probe_timing_mode.value}",
                f"Acquisition timing mode: {manifest.pump_probe_summary.acquisition_timing_mode.value}",
                f"Route set: {manifest.mux_summary.route_set_name}",
            ),
        ),
        SummaryPanel(
            title="Markers and Provenance",
            subtitle="Saved markers, monitor routing, and provenance metadata for review.",
            items=(
                f"Markers: {', '.join(manifest.selected_markers) if manifest.selected_markers else 'none'}",
                f"Pico mode: {manifest.pico_summary.mode.value}",
                (
                    "Pico trigger: "
                    f"{manifest.pico_summary.trigger_marker.value if manifest.pico_summary.trigger_marker else 'none'}"
                ),
                (
                    "Time-to-wavenumber mapping: "
                    f"{manifest.time_to_wavenumber_mapping.mapping_id if manifest.time_to_wavenumber_mapping else 'none'}"
                ),
            ),
        ),
    )


def _artifact_panels_from_session_detail(detail: SessionDetail) -> tuple[SummaryPanel, ...]:
    groups = (
        ("Primary Raw Artifacts", "HF2 remains the primary scientific raw-data authority.", detail.primary_raw_artifacts),
        (
            "Secondary Monitor Artifacts",
            "Pico monitor traces remain secondary context only.",
            detail.secondary_monitor_artifacts,
        ),
        (
            "Processed Artifacts",
            "Persisted processed outputs remain separate from raw authority.",
            detail.processed_artifacts,
        ),
        (
            "Analysis Artifacts",
            "Persisted analysis outputs remain separate from raw and processed outputs.",
            detail.analysis_artifacts,
        ),
        (
            "Export Artifacts",
            "Persisted exports cite their saved source artifacts.",
            detail.export_artifacts,
        ),
    )
    panels: list[SummaryPanel] = []
    for title, subtitle, artifacts in groups:
        items = tuple(artifact_summary_line(artifact) for artifact in artifacts) or (
            "None recorded for this session.",
        )
        panels.append(SummaryPanel(title=title, subtitle=subtitle, items=items))
    return tuple(panels)


def _operate_results_handoff(
    draft_session_id: str | None,
    latest_state: RunState | None,
) -> SurfaceActionModel | None:
    session_id = draft_session_id or (latest_state.session_id if latest_state is not None else None)
    if session_id is None:
        return None
    return SurfaceActionModel(
        label="Open Latest Session in Results",
        route="results",
        session_id=session_id,
        tone="secondary",
        helper_text="Persisted review, visualizations, and export stay off the control surface.",
    )


def _results_toolbar_actions(selected_session_id: str | None) -> tuple[SurfaceActionModel, ...]:
    if selected_session_id is None:
        return ()
    return (
        SurfaceActionModel(
            label="Analyze This Session",
            route="analyze",
            session_id=selected_session_id,
            tone="secondary",
            helper_text="Scientific evaluation starts from the saved session you are already reviewing.",
        ),
        SurfaceActionModel(
            label="Clear Selection",
            route="results",
            tone="ghost",
            helper_text="Keep the session history visible without pinning one selection.",
            query_params=(("session_id", "__none__"),),
        ),
    )


def _results_visualization_panels(detail: SessionDetail) -> tuple[SummaryPanel, ...]:
    manifest = detail.manifest
    return (
        SummaryPanel(
            title="Trace Coverage",
            subtitle="Results owns persisted trace review without pulling live device state back in.",
            items=(
                f"Primary HF2 traces available: {len(detail.primary_raw_artifacts)}",
                f"Secondary monitor traces available: {len(detail.secondary_monitor_artifacts)}",
                f"Processed traces available: {len(detail.processed_artifacts)}",
                f"Saved replay readiness: {'yes' if detail.summary.replay_ready else 'no'}",
                f"Selected session status: {detail.summary.status.value.title()}",
            ),
        ),
        SummaryPanel(
            title="Overlay Context",
            subtitle="Overlay views stay provenance-aware and keep HF2LI primary raw data authoritative.",
            items=(
                f"Secondary monitor traces available: {len(detail.secondary_monitor_artifacts)}",
                f"Digital markers: {', '.join(manifest.selected_markers) if manifest.selected_markers else 'none'}",
                f"Pico trigger marker: {manifest.pico_summary.trigger_marker.value if manifest.pico_summary.trigger_marker else 'none'}",
                (
                    "Time-to-wavenumber mapping: "
                    f"{manifest.time_to_wavenumber_mapping.mapping_id if manifest.time_to_wavenumber_mapping else 'none'}"
                ),
            ),
        ),
    )


def _results_export_panels(detail: SessionDetail) -> tuple[SummaryPanel, ...]:
    return (
        SummaryPanel(
            title="Download Readiness",
            subtitle="Downloads can come from persisted manifests, events, and artifact files without live hardware.",
            items=(
                f"Manifest available: yes",
                f"Event log entries: {len(detail.event_timeline)}",
                f"Artifact rows listed: {len(detail.primary_raw_artifacts) + len(detail.secondary_monitor_artifacts) + len(detail.processed_artifacts) + len(detail.analysis_artifacts) + len(detail.export_artifacts)}",
                f"Saved export artifacts: {len(detail.export_artifacts)}",
            ),
        ),
        SummaryPanel(
            title="Unsupported Actions Stay Explicit",
            subtitle="Replay, reprocess, and report generation remain disabled until dedicated backend owners are wired.",
            items=(
                f"Selected session: {detail.manifest.session_id}",
                f"Replay ready: {'yes' if detail.summary.replay_ready else 'no'}",
                f"Failure reason: {detail.manifest.outcome.failure_reason.value if detail.manifest.outcome.failure_reason else 'none'}",
                "Results shows disabled states instead of pretending unsupported processing and report workflows are complete.",
            ),
        ),
    )


def _results_export_actions(
    selected_session_id: str | None,
    detail: SessionDetail | None,
) -> tuple[SurfaceActionModel, ...]:
    disabled = selected_session_id is None or detail is None
    return (
        SurfaceActionModel(
            label="Download Manifest",
            route="results/download",
            tone="secondary",
            session_id=selected_session_id,
            disabled=disabled,
            helper_text="Download the authoritative saved manifest for this session.",
            query_params=(("asset", "manifest"),),
        ),
        SurfaceActionModel(
            label="Download Event Log",
            route="results/download",
            tone="secondary",
            session_id=selected_session_id,
            disabled=disabled,
            helper_text="Download the persisted event timeline as newline-delimited JSON.",
            query_params=(("asset", "events"),),
        ),
        SurfaceActionModel(
            label="Replay Saved Session",
            tone="primary",
            disabled=True,
            helper_text=(
                "Select a saved session first."
                if disabled
                else "Replay is not exposed as a Results action yet. Reopen the session in Experiment instead."
            ),
        ),
        SurfaceActionModel(
            label="Reprocess Saved Data",
            tone="ghost",
            disabled=True,
            helper_text=(
                "Select a saved session first."
                if disabled
                else "Reprocessing is reserved for a later Analyze/backend pass."
            ),
        ),
        SurfaceActionModel(
            label="Compare to Baseline",
            tone="ghost",
            disabled=True,
            helper_text=(
                "Select a saved session first."
                if disabled
                else "Baseline comparison is recognized here but remains an Analyze/backend-owned capability."
            ),
        ),
        SurfaceActionModel(
            label="Generate Session Report",
            tone="ghost",
            disabled=True,
            helper_text=(
                "Select a saved session first."
                if disabled
                else "Report generation is intentionally disabled until the reports boundary is wired."
            ),
        ),
    )


def _results_artifact_rows(
    detail: SessionDetail,
    storage_root: Path,
) -> tuple[ResultsArtifactRowModel, ...]:
    rows: list[ResultsArtifactRowModel] = []
    groups = (
        ("Primary Raw", detail.primary_raw_artifacts),
        ("Secondary Monitor", detail.secondary_monitor_artifacts),
        ("Processed", detail.processed_artifacts),
        ("Analysis", detail.analysis_artifacts),
        ("Export", detail.export_artifacts),
    )
    for kind_label, artifacts in groups:
        for artifact in artifacts:
            source_bits = []
            if artifact.source_role is not None:
                source_bits.append(artifact.source_role.value.replace("_", " ").title())
            if artifact.device_kind is not None:
                source_bits.append(artifact.device_kind.value)
            source_label = " / ".join(source_bits) or kind_label
            details = tuple(
                bit
                for bit in (
                    f"Content type: {artifact.content_type or 'unknown'}",
                    f"Registered by: {artifact.registered_by_event_id}" if artifact.registered_by_event_id else None,
                    f"Mux target: {artifact.mux_output_target}" if artifact.mux_output_target else None,
                    f"Marker: {artifact.related_marker}" if artifact.related_marker else None,
                )
                if bit is not None
            )
            rows.append(
                ResultsArtifactRowModel(
                    kind_label=kind_label,
                    artifact_id=artifact.artifact_id,
                    source_label=source_label,
                    stream_label=artifact.stream_name or artifact.relative_path.rsplit("/", 1)[-1],
                    records_label=(
                        f"{artifact.record_count} rows"
                        if artifact.record_count is not None
                        else "Record count unavailable"
                    ),
                    created_at=artifact.created_at,
                    path=artifact.relative_path,
                    details=details,
                    download_action=_results_artifact_download_action(
                        detail.manifest.session_id,
                        artifact.artifact_id,
                        artifact.relative_path,
                        storage_root,
                    ),
                )
            )
    return tuple(rows)


def _results_artifact_download_action(
    session_id: str,
    artifact_id: str,
    relative_path: str,
    storage_root: Path,
) -> SurfaceActionModel:
    artifact_path = _artifact_file_path(storage_root, relative_path)
    if artifact_path is not None and artifact_path.is_file():
        return SurfaceActionModel(
            label="Download",
            route="results/download",
            session_id=session_id,
            tone="secondary",
            helper_text="Download the persisted artifact file.",
            query_params=(("artifact_id", artifact_id),),
        )
    return SurfaceActionModel(
        label="Unavailable",
        tone="ghost",
        disabled=True,
        helper_text="This runtime does not have a persisted file available for this artifact.",
    )


def _results_trace_previews(
    detail: SessionDetail,
    storage_root: Path,
) -> tuple[ResultsTracePreviewModel, ...]:
    previews: list[ResultsTracePreviewModel] = []
    raw_artifacts = (
        *(("Primary Trace", artifact) for artifact in detail.primary_raw_artifacts[:2]),
        *(("Secondary Monitor", artifact) for artifact in detail.secondary_monitor_artifacts[:1]),
    )
    for label, artifact in raw_artifacts:
        previews.append(_trace_preview_from_artifact(label, artifact, storage_root))
    return tuple(previews)


def _trace_preview_from_artifact(
    label: str,
    artifact,
    storage_root: Path,
) -> ResultsTracePreviewModel:
    artifact_path = _artifact_file_path(storage_root, artifact.relative_path)
    title = f"{label} — {artifact.stream_name or artifact.artifact_id}"
    subtitle = "Persisted raw-trace preview built from the saved artifact payload."
    if artifact_path is None or not artifact_path.is_file():
        return ResultsTracePreviewModel(
            title=title,
            subtitle=subtitle,
            sample_count_label="No preview available",
            axis_label="Axis unavailable",
            axis_start_label="n/a",
            axis_end_label="n/a",
            value_min_label="n/a",
            value_max_label="n/a",
            note_lines=(artifact.relative_path,),
            state=unavailable_state(
                "Artifact file unavailable",
                "The persisted artifact summary exists, but this runtime does not have the payload file on disk.",
            ),
        )
    if artifact_path.suffix != ".parquet":
        return ResultsTracePreviewModel(
            title=title,
            subtitle=subtitle,
            sample_count_label="Preview unsupported",
            axis_label="Axis unavailable",
            axis_start_label="n/a",
            axis_end_label="n/a",
            value_min_label="n/a",
            value_max_label="n/a",
            note_lines=(artifact.relative_path,),
            state=unavailable_state(
                "Preview unsupported",
                "Results trace previews are currently limited to persisted Parquet raw artifacts.",
            ),
        )
    try:
        import pyarrow.parquet as pq  # type: ignore[reportMissingImports]
    except ModuleNotFoundError:
        return ResultsTracePreviewModel(
            title=title,
            subtitle=subtitle,
            sample_count_label="Preview unavailable",
            axis_label="Axis unavailable",
            axis_start_label="n/a",
            axis_end_label="n/a",
            value_min_label="n/a",
            value_max_label="n/a",
            note_lines=(artifact.relative_path,),
            state=unavailable_state(
                "Preview dependency unavailable",
                "Parquet preview rendering requires pyarrow in this environment.",
            ),
        )
    try:
        rows = pq.read_table(artifact_path).to_pylist()
    except Exception as exc:
        return ResultsTracePreviewModel(
            title=title,
            subtitle=subtitle,
            sample_count_label="Preview unavailable",
            axis_label="Axis unavailable",
            axis_start_label="n/a",
            axis_end_label="n/a",
            value_min_label="n/a",
            value_max_label="n/a",
            note_lines=(artifact.relative_path,),
            state=unavailable_state(
                "Preview load failed",
                "The persisted artifact file could not be read for preview.",
                details=(str(exc),),
            ),
        )

    numeric_rows = [
        row
        for row in rows
        if _coerce_float(row.get("axis_value")) is not None and _coerce_float(row.get("value")) is not None
    ]
    if not numeric_rows:
        return ResultsTracePreviewModel(
            title=title,
            subtitle=subtitle,
            sample_count_label="0 samples",
            axis_label="Axis unavailable",
            axis_start_label="n/a",
            axis_end_label="n/a",
            value_min_label="n/a",
            value_max_label="n/a",
            note_lines=(artifact.relative_path,),
            state=empty_state(
                "No preview samples",
                "The artifact file exists, but it does not contain numeric axis/value rows that can be previewed.",
            ),
        )

    points = tuple(
        (
            float(_coerce_float(row["axis_value"])),
            float(_coerce_float(row["value"])),
        )
        for row in numeric_rows
    )
    sampled_points = _downsample_points(points)
    axis_values = tuple(point[0] for point in points)
    y_values = tuple(point[1] for point in points)
    first_row = numeric_rows[0]
    axis_label = str(first_row.get("axis_label") or "Axis")
    axis_units = str(first_row.get("axis_units") or "")
    value_units = str(first_row.get("units") or "")
    notes = (
        f"Artifact {artifact.artifact_id}",
        artifact.relative_path,
        f"Source role {artifact.source_role.value}" if artifact.source_role is not None else "Source role unknown",
    )
    return ResultsTracePreviewModel(
        title=title,
        subtitle=subtitle,
        sample_count_label=f"{len(points)} samples",
        axis_label=f"{axis_label} ({axis_units})" if axis_units else axis_label,
        axis_start_label=_format_measurement(min(axis_values), axis_units),
        axis_end_label=_format_measurement(max(axis_values), axis_units),
        value_min_label=_format_measurement(min(y_values), value_units),
        value_max_label=_format_measurement(max(y_values), value_units),
        polyline_points=_sparkline_points(sampled_points),
        note_lines=notes,
    )


def _downsample_points(points: tuple[tuple[float, float], ...], max_points: int = 72) -> tuple[tuple[float, float], ...]:
    if len(points) <= max_points:
        return points
    step = max(1, math.ceil(len(points) / max_points))
    sampled = points[::step]
    if sampled[-1] != points[-1]:
        sampled = (*sampled, points[-1])
    return sampled


def _sparkline_points(points: tuple[tuple[float, float], ...]) -> str:
    if not points:
        return ""
    x_values = tuple(point[0] for point in points)
    y_values = tuple(point[1] for point in points)
    min_x = min(x_values)
    max_x = max(x_values)
    min_y = min(y_values)
    max_y = max(y_values)
    width = 320.0
    height = 120.0
    x_span = max(max_x - min_x, 1e-9)
    y_span = max(max_y - min_y, 1e-9)
    if max_x == min_x:
        x_positions = tuple(width * index / max(len(points) - 1, 1) for index in range(len(points)))
    else:
        x_positions = tuple(((x - min_x) / x_span) * width for x in x_values)
    return " ".join(
        f"{x:.1f},{height - (((y - min_y) / y_span) * height):.1f}"
        for x, y in zip(x_positions, y_values, strict=True)
    )


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _format_measurement(value: float, units: str) -> str:
    rendered = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{rendered} {units}".strip()


def _artifact_file_path(storage_root: Path, relative_path: str) -> Path | None:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return None
    resolved = (storage_root / candidate).resolve()
    try:
        resolved.relative_to(storage_root)
    except ValueError:
        return None
    return resolved


def _session_status_tone(status: SessionStatus) -> str:
    if status == SessionStatus.COMPLETED:
        return "good"
    if status == SessionStatus.FAULTED:
        return "bad"
    if status == SessionStatus.ABORTED:
        return "warn"
    return "neutral"


def _results_callouts(
    storage_root: Path,
    selected_session_id: str | None,
    page_state: PageStateModel | None,
) -> tuple[CalloutModel, ...]:
    callouts = [
        CalloutModel(
            title="Persisted session truth",
            body="Results is reading saved session manifests, event timelines, and artifact summaries instead of reconstructing them from live state.",
            tone="good",
        ),
        CalloutModel(
            title="Storage root policy",
            body=f"Sessions persist under {storage_root} so they survive runtime recreation.",
            tone="info",
        ),
        CalloutModel(
            title="Visualization and export live here",
            body="Results is the persisted-session home for plots, overlays, provenance review, and export handoff.",
            tone="good",
        ),
    ]
    if selected_session_id is not None:
        callouts.append(
            CalloutModel(
                title="Selected session focus",
                body=f"Currently inspecting {selected_session_id}. This selection can drive the next Analyze decisions directly.",
                tone="info",
            )
        )
    if page_state is not None and page_state.kind.value in {"fault", "warning"}:
        callouts.append(
            CalloutModel(
                title="Partial or faulted sessions remain visible",
                body="The Results surface is expected to stay usable for completed, aborted, and faulted sessions.",
                tone="warn",
            )
        )
    return tuple(callouts)


def _analyze_summary_panels(detail: SessionDetail) -> tuple[SummaryPanel, ...]:
    return (
        SummaryPanel(
            title="Selected Session",
            subtitle="The Analyze surface starts from saved session identity and replay availability.",
            items=(
                f"Session: {detail.manifest.session_id}",
                f"Status: {detail.summary.status.value}",
                f"Replay ready: {'yes' if detail.summary.replay_ready else 'no'}",
                f"Primary raw artifacts: {len(detail.primary_raw_artifacts)}",
            ),
        ),
        SummaryPanel(
            title="Current Upstream Inputs",
            subtitle="These counts reveal what the backend still needs to produce.",
            items=(
                f"Raw inputs: {len(detail.primary_raw_artifacts) + len(detail.secondary_monitor_artifacts)}",
                f"Processed outputs: {len(detail.processed_artifacts)}",
                f"Analysis outputs: {len(detail.analysis_artifacts)}",
                f"Export outputs: {len(detail.export_artifacts)}",
            ),
        ),
        SummaryPanel(
            title="Analysis Scope Preview",
            subtitle="Analyze stays thinner than Results and starts from saved-session truth only.",
            items=(
                "Reprocess from persisted raw inputs",
                "Compare against prior sessions or baselines",
                "Generate derived metrics and quality summaries",
            ),
        ),
    )


def _analyze_evaluation_panels(detail: SessionDetail) -> tuple[SummaryPanel, ...]:
    return (
        SummaryPanel(
            title="Reprocessing Inputs",
            subtitle="Everything needed for reprocessing must already exist in persisted form before this page acts.",
            items=(
                f"Replay-ready raw inputs: {len(detail.replay_plan.primary_raw_artifact_ids)}",
                f"Secondary monitor inputs: {len(detail.replay_plan.secondary_monitor_artifact_ids)}",
                f"Processed outputs already recorded: {len(detail.processed_artifacts)}",
                f"Analysis outputs already recorded: {len(detail.analysis_artifacts)}",
            ),
        ),
        SummaryPanel(
            title="Comparison and Metrics",
            subtitle="Scientific evaluation work stays here instead of leaking into Results or Experiment.",
            items=(
                "Compare against saved baselines or prior sessions",
                "Inspect derived metrics and quality summaries",
                "Keep export of comparison outputs secondary to Results review",
            ),
        ),
    )


def _analyze_toolbar_actions(selected_session_id: str | None) -> tuple[SurfaceActionModel, ...]:
    if selected_session_id is None:
        return ()
    return (
        SurfaceActionModel(
            label="Back to Results",
            route="results",
            session_id=selected_session_id,
            tone="secondary",
            helper_text="Return to the persisted-session review surface for plots, provenance, and export.",
        ),
    )


def _analyze_evaluation_actions(selected_session_id: str | None) -> tuple[SurfaceActionModel, ...]:
    helper = (
        "Select a saved session first."
        if selected_session_id is None
        else "Placeholder only for now. These actions stay headless and operate on persisted artifacts once wired."
    )
    return (
        SurfaceActionModel(
            label="Reprocess Session",
            tone="primary",
            disabled=True,
            helper_text=helper,
        ),
        SurfaceActionModel(
            label="Compare Against Baseline",
            tone="ghost",
            disabled=True,
            helper_text="Comparison will remain a saved-session workflow, not a live-control action.",
        ),
        SurfaceActionModel(
            label="Generate Metrics",
            tone="secondary",
            disabled=True,
            helper_text="Derived metrics stay in analysis jobs instead of becoming UI-local truth.",
        ),
    )


def _analyze_callouts(detail: SessionDetail) -> tuple[CalloutModel, ...]:
    return (
        CalloutModel(
            title="Persisted-session analysis only",
            body="The Analyze surface is driven from saved session truth and should remain usable without live hardware.",
            tone="good",
        ),
        CalloutModel(
            title="Explicit disabled analysis actions",
            body="Processing, analysis, and export actions stay visibly disabled here until their owning backend boundaries are wired.",
            tone="warn",
            items=(
                f"Processed outputs recorded now: {len(detail.processed_artifacts)}",
                f"Analysis outputs recorded now: {len(detail.analysis_artifacts)}",
            ),
        ),
    )


def _analyze_tables(detail: SessionDetail) -> tuple[TableModel, ...]:
    return (
        TableModel(
            title="Current Artifact Inventory",
            subtitle="Analyze can already see what exists and what still needs backend work.",
            headers=("Artifact Group", "Count", "Current Meaning"),
            rows=(
                ("Primary raw", str(len(detail.primary_raw_artifacts)), "Replayable scientific source inputs"),
                ("Secondary monitor", str(len(detail.secondary_monitor_artifacts)), "Timing or diagnostic context only"),
                ("Processed", str(len(detail.processed_artifacts)), "Headless processing outputs to wire next"),
                ("Analysis", str(len(detail.analysis_artifacts)), "Derived outputs to wire after processing"),
            ),
        ),
        TableModel(
            title="Visible Next Backend Steps",
            subtitle="The UI now makes the immediate backend gaps explicit instead of speculative.",
            headers=("Need", "Why the UI needs it next"),
            rows=(
                ("Processing job runner", "To populate processed outputs from saved raw artifacts"),
                ("Analysis job runner", "To populate derived metrics and comparison sections"),
                ("Export/report generator", "To turn reviewed results into reproducible outputs"),
            ),
        ),
    )


def _service_page_state(device_cards: tuple[DeviceSummaryCard, ...]) -> PageStateModel | None:
    bad_cards = tuple(card for card in device_cards if card.tone == "bad")
    warn_cards = tuple(card for card in device_cards if card.tone == "warn")
    if bad_cards:
        return fault_state(
            "Bench attention required",
            "One or more service subsystems are offline or faulted.",
            details=tuple(f"{card.device_label}: {card.summary}" for card in bad_cards),
        )
    if warn_cards:
        return warning_state(
            "Diagnostics show degraded capacity",
            "At least one subsystem is available with warnings or optional capability limits.",
            details=tuple(f"{card.device_label}: {card.summary}" for card in warn_cards),
        )
    return success_state(
        "Diagnostics nominal",
        "All simulator-backed service subsystems report ready state for this scenario.",
    )


def _service_toolbar_actions(session_count: int) -> tuple[SurfaceActionModel, ...]:
    return (
        SurfaceActionModel(
            label="Back to Experiment",
            route="experiment",
            tone="secondary",
            helper_text="Return to the default operator mission-control surface.",
        ),
        SurfaceActionModel(
            label="Advanced Timing",
            route="advanced",
            tone="ghost",
            helper_text="Use Advanced for expert timing and routing review that is not bench-owned recovery work.",
        ),
        SurfaceActionModel(
            label="Review Results",
            route="results",
            tone="ghost",
            helper_text=f"{session_count} persisted session(s) are available for saved-session review.",
        ),
    )


def _service_maintenance_actions(state: PageStateModel | None) -> tuple[SurfaceActionModel, ...]:
    helper = (
        "This action is intentionally disabled until a dedicated service boundary exists."
        if state is None or state.kind.value != "fault"
        else "The need is visible, but controlled recovery actions are not yet exposed through the runtime boundary."
    )
    return (
        SurfaceActionModel(
            label="Capture Config Snapshot",
            tone="secondary",
            disabled=True,
            helper_text=helper,
        ),
        SurfaceActionModel(
            label="Verify Timing Stack",
            tone="ghost",
            disabled=True,
            helper_text="Timing verification is represented here explicitly, but the action is not yet boundary-backed.",
        ),
        SurfaceActionModel(
            label="Reapply Guarded Calibration",
            tone="ghost",
            disabled=True,
            helper_text="Calibration custody remains bench-owned and is intentionally unavailable as a casual UI action.",
        ),
        SurfaceActionModel(
            label="Attempt Recovery",
            tone="primary",
            disabled=True,
            helper_text=helper,
        ),
    )


def _service_calibration_panels(scenario: SimulatorScenarioContext) -> tuple[SummaryPanel, ...]:
    calibration = scenario.recipe.calibration_references[0] if scenario.recipe.calibration_references else None
    mapping = scenario.recipe.time_to_wavenumber_mapping
    return (
        SummaryPanel(
            title="Calibration custody",
            subtitle="Bench-owned calibration references remain visible without pretending they are operator tuning fields.",
            items=(
                f"Calibration reference: {calibration.calibration_id if calibration else 'none'}",
                f"Calibration version: {calibration.version if calibration else 'none'}",
                f"Location: {calibration.location if calibration else 'n/a'}",
            ),
        ),
        SummaryPanel(
            title="Mapping defaults",
            subtitle="Guarded time-to-wavenumber context stays explicit for diagnostics and provenance review.",
            items=(
                f"Mapping id: {mapping.mapping_id if mapping else 'none'}",
                f"Start wavenumber: {mapping.start_wavenumber_cm1 if mapping else 'n/a'}",
                f"End wavenumber: {mapping.end_wavenumber_cm1 if mapping else 'n/a'}",
                f"Scan speed: {mapping.scan_speed_cm1_per_s if mapping else 'n/a'}",
            ),
        ),
    )


def _service_recovery_panels(
    device_cards: tuple[DeviceSummaryCard, ...],
    session_count: int,
) -> tuple[SummaryPanel, ...]:
    good_devices, warn_devices, bad_devices = _device_card_tone_counts(device_cards)
    return (
        SummaryPanel(
            title="Current diagnostic posture",
            subtitle="Quick expert summary of subsystem health.",
            items=(
                f"Ready devices: {good_devices}",
                f"Warn devices: {warn_devices}",
                f"Fault/offline devices: {bad_devices}",
                f"Persisted sessions available for replay-safe diagnosis: {session_count}",
            ),
        ),
        SummaryPanel(
            title="Recovery rules",
            subtitle="What Service does and does not do in the current runtime.",
            items=(
                "Service shows vendor and subsystem status explicitly.",
                "Disabled controls indicate recognized work that is not yet boundary-backed.",
                "Recovery cannot bypass the canonical control-plane path.",
            ),
        ),
    )


def _service_callouts(session_count: int) -> tuple[CalloutModel, ...]:
    return (
        CalloutModel(
            title="Service is intentionally separated",
            body="Expert diagnostics, guarded calibration work, and recovery actions remain isolated from the default operator workflow.",
            tone="warn",
        ),
        CalloutModel(
            title="Durable review context",
            body=f"The current runtime can already inspect {session_count} persisted session(s) without hardware.",
            tone="good",
        ),
    )


def _service_tables(storage_root: Path, session_count: int) -> tuple[TableModel, ...]:
    return (
        TableModel(
            title="Storage and Replay Policy",
            subtitle="Service is also where storage expectations and reopen behavior are visible for review.",
            headers=("Policy Area", "Current Rule"),
            rows=(
                ("Storage root", str(storage_root)),
                ("Manifest path", "sessions/<session_id>/manifest.json"),
                ("Raw payload path", "sessions/<session_id>/artifacts/raw/*.parquet"),
                ("Current saved sessions", str(session_count)),
            ),
        ),
        TableModel(
            title="Controlled Service Responsibilities",
            subtitle="Bench-owned work stays explicit here instead of leaking into Experiment.",
            headers=("Service Area", "Current Expectation"),
            rows=(
                ("Calibration custody", "Guarded references and mapping defaults remain bench-owned"),
                ("Timing verification", "Use persisted context and diagnostics before recovery"),
                ("Configuration snapshots", "Review saved snapshots before changing installation-owned settings"),
                ("Recovery actions", "Perform explicit recovery here, not through vendor-style passthrough screens"),
            ),
        ),
    )


def _session_dir(storage_root: Path, session_id: str) -> Path:
    return storage_root / "sessions" / session_id


def _manifest_path(storage_root: Path, session_id: str) -> Path:
    return _session_dir(storage_root, session_id) / "manifest.json"


def _events_path(storage_root: Path, session_id: str) -> Path:
    return _session_dir(storage_root, session_id) / "events.jsonl"
