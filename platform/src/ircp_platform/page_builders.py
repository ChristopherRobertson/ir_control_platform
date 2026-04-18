"""Page and panel builders for the simulator-backed UI runtime."""

from __future__ import annotations

from pathlib import Path

from ircp_contracts import DeviceStatus, PreflightReport, RunPhase, RunState, SessionStatus
from ircp_data_pipeline import SessionDetail, SessionSummary
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
    ResultsPageModel,
    ServicePageModel,
    SessionSummaryCard,
    StatusBadge,
    StatusItemModel,
    SummaryPanel,
    TableModel,
)
from ircp_ui_shell.page_state import blocked_state, empty_state, fault_state, unavailable_state, warning_state

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
    draft: OperatorDraftState,
    current_session_id: str,
    run_phase_label: str,
    ready_to_start: bool,
) -> HeaderStatus:
    return HeaderStatus(
        title="IR Control Platform",
        active_route=active_route,
        scenario_options=(),
        navigation=(),
        badges=(
            StatusBadge(
                label="Ready to Start" if ready_to_start else "Needs Attention",
                tone="good" if ready_to_start else "warn",
            ),
            StatusBadge(label=f"Current Session {current_session_id}", tone="neutral"),
            StatusBadge(label=f"Run {run_phase_label}", tone=run_badge_tone(run_phase_label)),
        ),
        summary="",
    )


def build_operate_page(
    *,
    draft: OperatorDraftState,
    preflight: PreflightReport,
    latest_state: RunState | None,
    sessions: tuple[SessionSummary, ...],
    laser_status: DeviceStatus,
    hf2_status: DeviceStatus,
    draft_session_id: str | None,
    selected_session_id: str | None,
) -> OperatePageModel:
    return OperatePageModel(
        state=_operate_page_state(draft.experiment_type, preflight, latest_state),
        session_panel=_build_session_panel(draft, sessions, draft_session_id, selected_session_id),
        laser_panel=_build_laser_panel(draft, laser_status),
        ndyag_panel=_build_ndyag_panel(draft),
        acquisition_panel=_build_acquisition_panel(draft, hf2_status),
        run_panel=_build_run_panel(draft.experiment_type, preflight, latest_state),
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
        subtitle="Timing, routing, calibration, and readiness detail stays here instead of crowding the operator path.",
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
                subtitle="Bench-owned references that exist now but should not dominate routine operation.",
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
        ),
    )


def build_results_page(
    *,
    draft: OperatorDraftState,
    storage_root: Path,
    sessions: tuple[SessionSummary, ...],
    selected_session_id: str | None,
    detail: SessionDetail | None,
) -> ResultsPageModel:
    session_cards = _session_cards(sessions, selected_session_id)
    selected_session = next((card for card in session_cards if card.session_id == selected_session_id), None)
    page_state: PageStateModel | None = None
    detail_panels: tuple[SummaryPanel, ...] = ()
    artifact_panels: tuple[SummaryPanel, ...] = ()
    storage_panels: tuple[SummaryPanel, ...] = ()
    event_log: tuple[EventLogItem, ...] = ()

    if not session_cards:
        page_state = empty_state(
            "No saved sessions",
            "This simulator scenario has not persisted a session yet.",
            details=("Nominal scenarios seed one saved fixture and new runs create more.",),
        )
    elif selected_session_id is not None and detail is not None:
        detail_panels = _detail_panels_from_session_detail(detail)
        artifact_panels = _artifact_panels_from_session_detail(detail)
        storage_panels = (
            SummaryPanel(
                title="Saved paths",
                subtitle="Basic durable session details available now.",
                items=(
                    f"Session directory: {_session_dir(storage_root, selected_session_id)}",
                    f"Manifest: {_manifest_path(storage_root, selected_session_id)}",
                    f"Events: {_events_path(storage_root, selected_session_id)}",
                    f"Replay ready: {'yes' if detail.summary.replay_ready else 'no'}",
                ),
            ),
        )
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
        subtitle="Review saved sessions, raw artifacts, and human-readable provenance without turning this into an analysis workstation.",
        state=page_state,
        surface_badges=_surface_badges("results", draft),
        sessions=session_cards,
        selected_session=selected_session,
        detail_panels=detail_panels,
        artifact_panels=artifact_panels,
        storage_panels=storage_panels if selected_session_id is not None else (),
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
        subtitle="Secondary persisted-session review surface. Real inputs are shown clearly; deeper analysis wiring remains separate.",
        state=page_state,
        surface_badges=_surface_badges("analyze", draft),
        sessions=session_cards,
        selected_session=selected_session,
        summary_panels=summary_panels,
        tables=tables,
        callouts=callouts,
    )


def build_service_page(
    *,
    draft: OperatorDraftState,
    storage_root: Path,
    session_count: int,
    device_cards: tuple[DeviceSummaryCard, ...],
) -> ServicePageModel:
    return ServicePageModel(
        title="Service",
        subtitle="Expert-only diagnostics, maintenance visibility, and guarded service context.",
        state=unavailable_state(
            "Service scaffold only",
            "This pass exposes expert review surfaces and guarded placeholders, not raw vendor consoles.",
        ),
        surface_badges=_surface_badges("service", draft),
        device_cards=device_cards,
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
        ),
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
                "Tune",
                "/experiment/laser/tune",
                disabled=not status.connected,
                hidden=not fixed_mode,
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
    if latest_state is not None and latest_state.phase == RunPhase.FAULTED and latest_state.latest_fault is not None:
        run_state = fault_state("Run faulted", latest_state.latest_fault.message)
    elif not preflight.ready_to_start:
        run_state = blocked_state(
            "Experiment blocked",
            "Finish the required setup items before starting the experiment.",
            details=_operator_preflight_messages(preflight),
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
            ActionButtonModel("Run Preflight", "/experiment/run/preflight"),
            ActionButtonModel("Start Experiment", "/experiment/run/start", disabled=not ready_to_start),
            ActionButtonModel(
                "Stop / Abort Experiment",
                "/experiment/run/abort",
                tone="danger",
                disabled=latest_state is None
                or latest_state.phase in {RunPhase.COMPLETED, RunPhase.FAULTED, RunPhase.ABORTED},
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
                "Error / warning summary",
                _run_issue_summary(experiment_type, preflight),
                tone="good" if ready_to_start else "warn",
            ),
        ),
        state=run_state,
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
    )


def _preflight_page_state(
    preflight: PreflightReport,
    *,
    title: str,
    warning_title: str,
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
    return None


def _start_experiment_supported(experiment_type: str) -> bool:
    return experiment_type == FIXED_WAVELENGTH_EXPERIMENT_TYPE


def _start_experiment_ready(experiment_type: str, preflight: PreflightReport) -> bool:
    return preflight.ready_to_start and _start_experiment_supported(experiment_type)


def _run_issue_summary(experiment_type: str, preflight: PreflightReport) -> str:
    issues = _operator_preflight_messages(preflight)
    if issues:
        return issues[0]
    if not _start_experiment_supported(experiment_type):
        return "Wavelength scan Start Experiment orchestration is not yet fully wired."
    return "Clear"


def _experiment_state_summary(
    experiment_type: str,
    preflight: PreflightReport,
    latest_state: RunState | None,
) -> tuple[str, str]:
    if latest_state is not None:
        if latest_state.phase in {RunPhase.STARTING, RunPhase.RUNNING, RunPhase.STOPPING}:
            return "Experiment running", phase_tone(latest_state.phase)
        if latest_state.phase == RunPhase.COMPLETED:
            return "Experiment stopped", "good"
        if latest_state.phase == RunPhase.ABORTED:
            return "Experiment aborted", "warn"
        if latest_state.phase == RunPhase.FAULTED:
            return "Experiment faulted", "bad"
        return latest_state.phase.value.replace("_", " ").title(), phase_tone(latest_state.phase)
    if not preflight.ready_to_start:
        return "Preflight blocked", "warn"
    if _start_experiment_ready(experiment_type, preflight):
        return "Preflight ok", "good"
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
        "advanced": (
            StatusBadge(label="Expert only", tone="warn"),
            StatusBadge(label="Same canonical path", tone="good"),
            StatusBadge(label="Progressive disclosure", tone="info"),
        ),
        "results": (
            StatusBadge(label="Persisted sessions", tone="good"),
            StatusBadge(label="Raw artifact visibility", tone="good"),
            StatusBadge(label="Human-readable provenance", tone="info"),
        ),
        "analyze": (
            StatusBadge(label="Persisted inputs only", tone="good"),
            StatusBadge(label="Secondary surface", tone="warn"),
            StatusBadge(label="Future wiring explicit", tone="info"),
        ),
        "service": (
            StatusBadge(label="Expert surface", tone="warn"),
            StatusBadge(label="No vendor passthrough", tone="good"),
            StatusBadge(label="Guarded recovery", tone="info"),
        ),
    }
    return badge_map[surface]


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


def _detail_panels_from_session_detail(detail: SessionDetail) -> tuple[SummaryPanel, ...]:
    manifest = detail.manifest
    return (
        SummaryPanel(
            title="Manifest Summary",
            subtitle="Session-centered authority for reopen and replay.",
            items=(
                f"Session: {manifest.session_id}",
                f"Status: {manifest.status.value}",
                f"Recipe: {manifest.recipe_snapshot.title}",
                f"Replay ready: {'yes' if detail.summary.replay_ready else 'no'}",
                f"Events persisted: {detail.summary.event_count}",
                f"Primary raw artifacts: {len(manifest.primary_raw_artifacts())}",
                f"Secondary monitor artifacts: {len(manifest.secondary_monitor_artifacts())}",
            ),
        ),
        SummaryPanel(
            title="Outcome and Replay",
            subtitle="Explicit persisted terminal state and replay inputs.",
            items=(
                f"Run started: {manifest.outcome.started_at.isoformat() if manifest.outcome.started_at else 'n/a'}",
                f"Run ended: {manifest.outcome.ended_at.isoformat() if manifest.outcome.ended_at else 'n/a'}",
                f"Failure reason: {manifest.outcome.failure_reason.value if manifest.outcome.failure_reason else 'none'}",
                f"Final event: {manifest.outcome.final_event_id or 'n/a'}",
                f"Primary replay inputs: {len(detail.replay_plan.primary_raw_artifact_ids)}",
            ),
        ),
        SummaryPanel(
            title="Timing and Routing",
            subtitle="Persisted context required to interpret the saved run.",
            items=(
                f"T0 label: {manifest.timing_summary.t0_label}",
                f"Pump shots before probe: {manifest.pump_probe_summary.pump_shots_before_probe}",
                f"Probe timing mode: {manifest.pump_probe_summary.probe_timing_mode.value}",
                f"Acquisition timing mode: {manifest.pump_probe_summary.acquisition_timing_mode.value}",
                f"Route set: {manifest.mux_summary.route_set_name}",
            ),
        ),
        SummaryPanel(
            title="Markers and Artifacts",
            subtitle="Saved markers, monitor routing, and artifact authority split.",
            items=(
                f"Markers: {', '.join(manifest.selected_markers)}",
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
            subtitle="This page is making the required review surface visible before the jobs are fully wired.",
            items=(
                "Reprocess from persisted raw inputs",
                "Compare against prior sessions or baselines",
                "Generate derived metrics and quality summaries",
            ),
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
            title="Backend wiring still implied",
            body="Processing, analysis, and export actions remain intentionally placeholder-backed until the visible workflow is reviewed.",
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
    )


def _session_dir(storage_root: Path, session_id: str) -> Path:
    return storage_root / "sessions" / session_id


def _manifest_path(storage_root: Path, session_id: str) -> Path:
    return _session_dir(storage_root, session_id) / "manifest.json"


def _events_path(storage_root: Path, session_id: str) -> Path:
    return _session_dir(storage_root, session_id) / "events.jsonl"
