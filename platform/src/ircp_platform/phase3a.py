"""Phase 3B simulator-backed runtime wiring and app bootstrap."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from ircp_contracts import (
    ArtifactSourceRole,
    HF2DemodulatorConfiguration,
    HF2PrimaryAcquisition,
    HF2SampleComponent,
    HF2StreamSelection,
    MircatSpectralMode,
    PreflightReport,
    RunEventType,
    RunFailureReason,
    RunPhase,
    RunState,
    SessionManifest,
    SessionStatus,
)
from ircp_data_pipeline import (
    FilesystemSessionStore,
    InMemorySessionStore,
    SessionCatalog,
    SessionDetail,
    SessionOpenRequest,
    SessionReplayer,
    SessionStore,
)
from ircp_experiment_engine import SupportedV1DriverBundle
from ircp_experiment_engine.runtime import SupportedV1PreflightValidator, InMemoryRunCoordinator
from ircp_simulators import Phase3BScenarioContext, SupportedV1SimulatorCatalog
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
    NavigationItem,
    OperatePageModel,
    OperatePanelModel,
    PageStateModel,
    ResultsPageModel,
    ScenarioOption,
    ServicePageModel,
    SessionSummaryCard,
    StatusBadge,
    StatusItemModel,
    SummaryPanel,
    TableModel,
    UiRuntimeGateway,
    create_ui_app,
)
from ircp_ui_shell.page_state import blocked_state, empty_state, fault_state, unavailable_state, warning_state


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OperatorDraftState:
    session_label: str
    sample_id: str
    operator_notes: str
    tune_target_cm1: float
    hf2_demod_index: int
    hf2_component: HF2SampleComponent
    hf2_sample_rate_hz: float
    hf2_harmonic: int
    hf2_capture_interval_seconds: float


class Phase3BSimulatorRuntime(UiRuntimeGateway):
    """UI-facing adapter layer backed by supported-v1 simulator implementations only."""

    def __init__(
        self,
        *,
        scenario: Phase3BScenarioContext,
        scenario_options: tuple[ScenarioOption, ...],
        session_store: SessionStore,
        coordinator: InMemoryRunCoordinator,
        session_catalog: SessionCatalog,
        session_replayer: SessionReplayer,
        storage_root: Path,
    ) -> None:
        self._scenario = scenario
        self._scenario_options = scenario_options
        self._session_store = session_store
        self._run_monitor = coordinator
        self._session_catalog = session_catalog
        self._session_replayer = session_replayer
        self._preflight_validator = SupportedV1PreflightValidator()
        self._coordinator = coordinator
        self._storage_root = storage_root.resolve()
        self._last_preflight: PreflightReport | None = None
        initial_hf2 = scenario.recipe.hf2_primary_acquisition
        initial_component = initial_hf2.stream_selections[0].component
        initial_demod = initial_hf2.demodulators[0]
        self._draft = OperatorDraftState(
            session_label=scenario.recipe.session_label or "Supported v1 simulator baseline",
            sample_id="sample-A12",
            operator_notes="Simulator-backed operator review session.",
            tune_target_cm1=_default_tune_target(scenario),
            hf2_demod_index=initial_demod.demod_index,
            hf2_component=initial_component,
            hf2_sample_rate_hz=initial_demod.sample_rate_hz,
            hf2_harmonic=initial_demod.harmonic,
            hf2_capture_interval_seconds=initial_hf2.capture_interval_seconds,
        )
        self._active_run_id: str | None = None
        self._draft_session_id: str | None = None
        self._selected_session_id: str | None = None
        self._active_hf2_capture_id: str | None = None
        self._recent_activity: list[EventLogItem] = []
        self._preflight_dirty = True

    async def get_header_status(self, active_route: str) -> HeaderStatus:
        sessions = await self._session_catalog.list_sessions()
        preflight = await self._ensure_preflight()
        run_phase_label = await self._current_run_phase_label()
        badges = (
            StatusBadge(
                label=f"Preflight {'Ready' if preflight.ready_to_start else 'Blocked'}",
                tone="good" if preflight.ready_to_start else "bad",
            ),
            StatusBadge(
                label=f"Saved Sessions {len(sessions)}",
                tone="neutral",
            ),
            StatusBadge(
                label=f"Run {run_phase_label}",
                tone=self._run_badge_tone(run_phase_label),
            ),
        )
        current_session = self._draft_session_id or self._selected_session_id or "none"
        return HeaderStatus(
            title="IR Control Platform",
            active_route=active_route,
            scenario_options=tuple(
                ScenarioOption(
                    scenario_id=option.scenario_id,
                    label=option.label,
                    description=option.description,
                    active=option.scenario_id == self._scenario.scenario_id,
                )
                for option in self._scenario_options
            ),
            navigation=(
                NavigationItem(
                    label="Operate",
                    href=f"/operate?scenario={self._scenario.scenario_id}",
                    active=active_route == "operate",
                ),
                NavigationItem(
                    label="Results",
                    href=f"/results?scenario={self._scenario.scenario_id}",
                    active=active_route == "results",
                ),
                NavigationItem(
                    label="Advanced",
                    href=f"/advanced?scenario={self._scenario.scenario_id}",
                    active=active_route == "advanced",
                ),
                NavigationItem(
                    label="Service",
                    href=f"/service?scenario={self._scenario.scenario_id}",
                    active=active_route == "service",
                ),
            ),
            badges=(
                badges[0],
                StatusBadge(label=f"Current Session {current_session}", tone="neutral"),
                badges[2],
            ),
            summary=self._scenario.description,
        )

    async def get_operate_page(self) -> OperatePageModel:
        preflight = await self._ensure_preflight()
        latest_state = await self._latest_run_state()
        operate_state = self._operate_page_state(preflight, latest_state)
        sessions = await self._session_catalog.list_sessions()
        laser_status = await self._scenario.bundle.mircat.get_status()
        hf2_status = await self._scenario.bundle.hf2li.get_status()

        return OperatePageModel(
            title="Operate",
            subtitle="Start with the current session, make the required device states obvious, then run the supported path.",
            state=operate_state,
            surface_badges=self._surface_badges("operate"),
            session_panel=self._build_session_panel(sessions),
            laser_panel=self._build_laser_panel(laser_status),
            acquisition_panel=self._build_acquisition_panel(hf2_status),
            run_panel=self._build_run_panel(preflight, latest_state),
            live_status=await self._live_status_items(preflight),
            recent_activity=await self._recent_activity_items(),
            callouts=(),
        )

    async def get_advanced_page(self) -> AdvancedPageModel:
        preflight = await self._ensure_preflight()
        readiness_rows = tuple(
            (
                check.target,
                check.state.value,
                check.summary,
                "; ".join(issue.message for issue in check.issues) if check.issues else "No issues",
            )
            for check in preflight.checks
        )
        calibration = self._scenario.recipe.calibration_references[0] if self._scenario.recipe.calibration_references else None
        mapping = self._scenario.recipe.time_to_wavenumber_mapping
        advanced_state = self._preflight_page_state(
            preflight,
            title="Advanced detail blocked",
            warning_title="Advanced detail warning",
        )
        return AdvancedPageModel(
            title="Advanced",
            subtitle="Timing, routing, calibration, and readiness detail stays here instead of crowding the operator path.",
            state=advanced_state,
            surface_badges=self._surface_badges("advanced"),
            sections=(
                AdvancedSectionModel(
                    title="Timing and marker detail",
                    subtitle="T0 timing, pump/probe relationships, and selected markers for the current supported recipe.",
                    summary_panels=(
                        self._summary_panels_from_preflight(preflight)[1],
                        self._summary_panels_from_preflight(preflight)[2],
                        self._summary_panels_from_preflight(preflight)[3],
                    ),
                    open_by_default=True,
                ),
                AdvancedSectionModel(
                    title="Acquisition and routing detail",
                    subtitle="HF2 profile, Pico monitoring selection, and named MUX routing kept out of the main operator flow.",
                    summary_panels=(
                        self._summary_panels_from_preflight(preflight)[0],
                        self._summary_panels_from_preflight(preflight)[4],
                        self._summary_panels_from_preflight(preflight)[5],
                    ),
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
                    notes=(
                        "These values are visible for review and provenance, not routine operator editing.",
                    ),
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

    async def get_results_page(self, selected_session_id: str | None = None) -> ResultsPageModel:
        sessions = await self._session_catalog.list_sessions()
        selected_id = selected_session_id or self._selected_session_id or (sessions[0].session_id if sessions else None)
        if selected_id is not None:
            self._selected_session_id = selected_id
        session_cards = tuple(
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
                selected=summary.session_id == selected_id,
            )
            for summary in sessions
        )

        page_state = None
        detail_panels: tuple[SummaryPanel, ...] = ()
        artifact_panels: tuple[SummaryPanel, ...] = ()
        storage_panels: tuple[SummaryPanel, ...] = ()
        event_log: tuple[EventLogItem, ...] = ()
        selected_session = next((card for card in session_cards if card.session_id == selected_id), None)
        if not session_cards:
            page_state = empty_state(
                "No saved sessions",
                "This simulator scenario has not persisted a session yet.",
                details=("Nominal scenarios seed one saved fixture and new runs create more.",),
            )
        elif selected_id is not None:
            detail = await self._session_catalog.get_session_detail(selected_id)
            detail_panels = self._detail_panels_from_session_detail(detail)
            artifact_panels = self._artifact_panels_from_session_detail(detail)
            storage_panels = (
                SummaryPanel(
                    title="Saved paths",
                    subtitle="Basic durable session details available now.",
                    items=(
                        f"Session directory: {self._session_dir(selected_id)}",
                        f"Manifest: {self._manifest_path(selected_id)}",
                        f"Events: {self._events_path(selected_id)}",
                        f"Replay ready: {'yes' if detail.summary.replay_ready else 'no'}",
                    ),
                ),
            )
            event_log = tuple(
                EventLogItem(
                    timestamp=event.emitted_at,
                    source=event.source,
                    message=event.message,
                    tone=_event_tone(event.event_type),
                )
                for event in detail.event_timeline
            )
            if detail.manifest.status == SessionStatus.FAULTED:
                page_state = fault_state(
                    "Saved session faulted",
                    "The selected saved session ended with an explicit persisted fault.",
                    details=(
                        detail.manifest.outcome.latest_fault.message,
                    )
                    if detail.manifest.outcome.latest_fault is not None
                    else (
                        detail.manifest.outcome.failure_reason.value,
                    )
                    if detail.manifest.outcome.failure_reason is not None
                    else (),
                )
            elif detail.manifest.status == SessionStatus.ABORTED:
                page_state = warning_state(
                    "Saved session aborted",
                    "The selected saved session was aborted and is being shown from persisted partial state.",
                    details=(
                        detail.manifest.outcome.failure_reason.value,
                    )
                    if detail.manifest.outcome.failure_reason is not None
                    else (),
                )

        return ResultsPageModel(
            title="Results",
            subtitle="Review saved sessions, raw artifacts, and human-readable provenance without turning this into an analysis workstation.",
            state=page_state,
            surface_badges=self._surface_badges("results"),
            sessions=session_cards,
            selected_session=selected_session,
            detail_panels=detail_panels,
            artifact_panels=artifact_panels,
            storage_panels=storage_panels if selected_id is not None else (),
            callouts=self._results_callouts(selected_id, page_state),
            event_log=event_log,
        )

    async def get_analyze_page(self, selected_session_id: str | None = None) -> AnalyzePageModel:
        sessions = await self._session_catalog.list_sessions()
        selected_id = selected_session_id or self._selected_session_id or (sessions[0].session_id if sessions else None)
        if selected_id is not None:
            self._selected_session_id = selected_id
        session_cards = tuple(
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
                selected=summary.session_id == selected_id,
            )
            for summary in sessions
        )

        page_state: PageStateModel | None = None
        summary_panels: tuple[SummaryPanel, ...] = ()
        callouts: tuple[CalloutModel, ...] = ()
        tables: tuple[TableModel, ...] = ()
        selected_session = next((card for card in session_cards if card.session_id == selected_id), None)

        if not session_cards:
            page_state = empty_state(
                "No persisted sessions",
                "Analyze requires a saved session or fixture-backed manifest.",
                details=("Run the nominal simulator path or reopen the saved session fixture first.",),
            )
        elif selected_id is not None:
            detail = await self._session_catalog.get_session_detail(selected_id)
            summary_panels = self._analyze_summary_panels(detail)
            callouts = self._analyze_callouts(detail)
            tables = self._analyze_tables(detail)
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
            surface_badges=self._surface_badges("analyze"),
            sessions=session_cards,
            selected_session=selected_session,
            summary_panels=summary_panels,
            tables=tables,
            callouts=callouts,
        )

    async def get_service_page(self) -> ServicePageModel:
        sessions = await self._session_catalog.list_sessions()
        return ServicePageModel(
            title="Service",
            subtitle="Expert-only diagnostics, maintenance visibility, and guarded service context.",
            state=unavailable_state(
                "Service scaffold only",
                "This pass exposes expert review surfaces and guarded placeholders, not raw vendor consoles.",
            ),
            surface_badges=self._surface_badges("service"),
            device_cards=await self._device_cards(),
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
                        f"Storage root: {self._storage_root}",
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
                *self._service_callouts(len(sessions)),
            ),
            tables=self._service_tables(len(sessions)),
        )

    async def save_session(self, session_label: str, sample_id: str, operator_notes: str) -> SessionManifest:
        self._draft.session_label = session_label.strip() or self._draft.session_label
        self._draft.sample_id = sample_id.strip()
        self._draft.operator_notes = operator_notes.strip()
        manifest = await self._coordinator.create_session(
            self._current_recipe(),
            self._scenario.preset,
            notes=self._current_session_notes(),
        )
        self._draft_session_id = manifest.session_id
        self._selected_session_id = manifest.session_id
        self._active_hf2_capture_id = None
        self._remember_activity("session", f"Saved planned session {manifest.session_id}.", tone="good")
        self._mark_preflight_dirty()
        return manifest

    async def open_saved_session(self, session_id: str) -> SessionManifest:
        result = await self._session_replayer.open_session(
            SessionOpenRequest(
                session_id=session_id,
                requested_at=_utc_now(),
                reopen_for_replay=True,
            )
        )
        self._selected_session_id = result.manifest.session_id
        self._draft_session_id = None
        self._load_draft_from_manifest(result.manifest)
        self._remember_activity("session", f"Opened saved session {session_id}.", tone="info")
        return result.manifest

    async def connect_laser(self):
        status = await self._scenario.bundle.mircat.connect()
        self._remember_activity("laser", status.status_summary, tone="good")
        self._mark_preflight_dirty()
        return status

    async def disconnect_laser(self):
        status = await self._scenario.bundle.mircat.disconnect()
        self._remember_activity("laser", status.status_summary, tone="warn")
        self._mark_preflight_dirty()
        return status

    async def arm_laser(self):
        status = await self._scenario.bundle.mircat.arm()
        self._remember_activity("laser", status.status_summary, tone="good")
        self._mark_preflight_dirty()
        return status

    async def disarm_laser(self):
        status = await self._scenario.bundle.mircat.disarm()
        self._remember_activity("laser", status.status_summary, tone="warn")
        self._mark_preflight_dirty()
        return status

    async def set_laser_emission(self, enabled: bool):
        status = await self._scenario.bundle.mircat.set_emission_enabled(enabled)
        self._remember_activity("laser", status.status_summary, tone="good" if enabled else "warn")
        self._mark_preflight_dirty()
        return status

    async def tune_laser(self, target_wavenumber_cm1: float):
        self._draft.tune_target_cm1 = target_wavenumber_cm1
        tuned_configuration = replace(
            self._scenario.recipe.mircat,
            spectral_mode=MircatSpectralMode.SINGLE_WAVELENGTH,
            single_wavelength_cm1=target_wavenumber_cm1,
            sweep_scan=None,
            step_measure_scan=None,
            multispectral_scan=None,
        )
        snapshot = await self._scenario.bundle.mircat.apply_configuration(tuned_configuration)
        self._remember_activity(
            "laser",
            f"Tune target set to {target_wavenumber_cm1:.2f} cm^-1.",
            tone="info",
        )
        self._mark_preflight_dirty()
        return snapshot

    async def start_scan(self):
        status = await self._scenario.bundle.mircat.start_recipe(
            self._scenario.recipe.mircat,
            self._scenario.recipe.probe_timing_mode,
        )
        self._remember_activity("laser", status.status_summary, tone="good")
        self._mark_preflight_dirty()
        return status

    async def stop_scan(self):
        status = await self._scenario.bundle.mircat.stop_recipe()
        self._remember_activity("laser", status.status_summary, tone="warn")
        self._mark_preflight_dirty()
        return status

    async def connect_hf2(self):
        status = await self._scenario.bundle.hf2li.connect()
        self._remember_activity("hf2li", status.status_summary, tone="good")
        self._mark_preflight_dirty()
        return status

    async def disconnect_hf2(self):
        status = await self._scenario.bundle.hf2li.disconnect()
        self._active_hf2_capture_id = None
        self._remember_activity("hf2li", status.status_summary, tone="warn")
        self._mark_preflight_dirty()
        return status

    async def start_hf2_acquisition(
        self,
        *,
        demod_index: int,
        component: HF2SampleComponent,
        sample_rate_hz: float,
        harmonic: int,
        capture_interval_seconds: float,
    ):
        self._draft.hf2_demod_index = demod_index
        self._draft.hf2_component = component
        self._draft.hf2_sample_rate_hz = sample_rate_hz
        self._draft.hf2_harmonic = harmonic
        self._draft.hf2_capture_interval_seconds = capture_interval_seconds
        if self._draft_session_id is None:
            raise ValueError("Save a session before starting standalone acquisition.")
        acquisition = self._current_hf2_acquisition()
        await self._scenario.bundle.hf2li.apply_configuration(acquisition)
        capture = await self._scenario.bundle.hf2li.start_capture(acquisition, self._draft_session_id)
        self._active_hf2_capture_id = capture.capture_id
        self._remember_activity("hf2li", f"Started HF2 acquisition for session {self._draft_session_id}.", tone="good")
        self._mark_preflight_dirty()
        return capture

    async def stop_hf2_acquisition(self):
        if self._active_hf2_capture_id is None:
            return None
        status = await self._scenario.bundle.hf2li.stop_capture(self._active_hf2_capture_id)
        self._active_hf2_capture_id = None
        self._remember_activity("hf2li", status.status_summary, tone="info")
        self._mark_preflight_dirty()
        return status

    async def run_preflight(self) -> PreflightReport:
        self._last_preflight = await self._preflight_validator.validate(
            self._current_recipe(),
            self._scenario.preset,
            SupportedV1DriverBundle(
                mircat=self._scenario.bundle.mircat,
                hf2li=self._scenario.bundle.hf2li,
                t660_master=self._scenario.bundle.t660_master,
                t660_slave=self._scenario.bundle.t660_slave,
                mux=self._scenario.bundle.mux,
                picoscope=self._scenario.bundle.picoscope,
            ),
        )
        self._preflight_dirty = False
        self._remember_activity(
            "preflight",
            f"Preflight {'ready' if self._last_preflight.ready_to_start else 'blocked'}.",
            tone="good" if self._last_preflight.ready_to_start else "warn",
        )
        return self._last_preflight

    async def start_run(self) -> RunState:
        preflight = await self._ensure_preflight()
        if not preflight.ready_to_start:
            raise ValueError("Preflight is blocked.")
        session_id = self._draft_session_id
        if session_id is None:
            manifest = await self.save_session(
                self._draft.session_label,
                self._draft.sample_id,
                self._draft.operator_notes,
            )
            session_id = manifest.session_id
        run_state = await self._coordinator.start_run(
            self._current_recipe(),
            self._scenario.preset,
            session_id,
        )
        self._active_run_id = run_state.run_id
        self._selected_session_id = run_state.session_id
        self._remember_activity("run", f"Started run {run_state.run_id}.", tone="good")
        self._mark_preflight_dirty()
        return run_state

    async def abort_active_run(self) -> RunState | None:
        if self._active_run_id is None:
            return None
        current = await self._coordinator.get_run_state(self._active_run_id)
        if current.phase in {RunPhase.COMPLETED, RunPhase.FAULTED, RunPhase.ABORTED}:
            return None
        aborted = await self._coordinator.abort_run(self._active_run_id, RunFailureReason.OPERATOR_ABORT)
        self._remember_activity("run", f"Aborted run {aborted.run_id}.", tone="warn")
        self._mark_preflight_dirty()
        return aborted

    def _build_session_panel(self, sessions) -> OperatePanelModel:
        recent_session_options = tuple(
            FormOptionModel(
                value=session.session_id,
                label=f"{session.session_id} ({session.status.value})",
                selected=session.session_id == self._selected_session_id,
            )
            for session in sessions[:5]
        )
        current_session_id = self._draft_session_id or self._selected_session_id or "none"
        current_status = self._current_session_status_label(sessions)
        return OperatePanelModel(
            title="Session",
            subtitle="Name the work, keep the sample visible, and decide what session record you are operating in.",
            fields=(
                FormFieldModel(
                    name="session_label",
                    label="Session name / label",
                    field_type="text",
                    value=self._draft.session_label,
                    help_text="Used for the current planned run session.",
                ),
                FormFieldModel(
                    name="sample_id",
                    label="Sample ID",
                    field_type="text",
                    value=self._draft.sample_id,
                    help_text="Small operator-facing identifier for the current review pass.",
                ),
                FormFieldModel(
                    name="operator_notes",
                    label="Operator notes",
                    field_type="textarea",
                    value=self._draft.operator_notes,
                    help_text="Persisted as session notes when the session is saved.",
                ),
                FormFieldModel(
                    name="session_id",
                    label="Open recent session",
                    field_type="select",
                    options=recent_session_options,
                    disabled=not bool(recent_session_options),
                    help_text="Limited recent list for quick reopen during local review.",
                ),
            ),
            actions=(
                ActionButtonModel(label="Save Session", action="/operate/session/save"),
                ActionButtonModel(
                    label="Open Recent",
                    action="/operate/session/open",
                    tone="secondary",
                    disabled=not bool(recent_session_options),
                ),
            ),
            status_items=(
                StatusItemModel("Current session", current_session_id, tone="info", detail=f"Status: {current_status}"),
                StatusItemModel(
                    "Saved sessions",
                    str(len(sessions)),
                    tone="neutral",
                    detail="Results shows the full saved-session review path.",
                ),
            ),
        )

    def _build_laser_panel(self, status) -> OperatePanelModel:
        armed = _bool_vendor_status(status, "armed")
        emission = _bool_vendor_status(status, "emission_enabled")
        scan_active = _bool_vendor_status(status, "scan_active")
        tuned = status.vendor_status.get("tuned_target_cm1")
        return OperatePanelModel(
            title="Laser",
            subtitle="Connect, make the MIRcat state explicit, and keep routine actions next to the current status.",
            fields=(
                FormFieldModel(
                    name="tune_target_cm1",
                    label="Tune target (cm^-1)",
                    field_type="number",
                    value=f"{self._draft.tune_target_cm1:.2f}",
                    help_text="Uses the repo’s current wavenumber convention.",
                ),
            ),
            actions=(
                ActionButtonModel("Connect", "/operate/laser/connect", disabled=status.connected),
                ActionButtonModel("Disconnect", "/operate/laser/disconnect", tone="secondary", disabled=not status.connected),
                ActionButtonModel("Arm", "/operate/laser/arm", disabled=not status.connected or armed),
                ActionButtonModel("Disarm", "/operate/laser/disarm", tone="secondary", disabled=not status.connected or not armed),
                ActionButtonModel("Emission On", "/operate/laser/emission/on", disabled=not status.connected or emission),
                ActionButtonModel("Emission Off", "/operate/laser/emission/off", tone="secondary", disabled=not status.connected or not emission),
                ActionButtonModel("Tune", "/operate/laser/tune", tone="ghost", disabled=not status.connected),
                ActionButtonModel("Start Scan", "/operate/laser/scan/start", disabled=not status.connected or scan_active),
                ActionButtonModel("Stop Scan", "/operate/laser/scan/stop", tone="secondary", disabled=not status.connected or not scan_active),
            ),
            status_items=(
                StatusItemModel("Connection", "Connected" if status.connected else "Disconnected", tone="good" if status.connected else "bad", detail=status.status_summary),
                StatusItemModel("Armed", "Armed" if armed else "Disarmed", tone="good" if armed else "neutral"),
                StatusItemModel("Emission", "On" if emission else "Off", tone="good" if emission else "neutral"),
                StatusItemModel(
                    "Laser state",
                    "Scan active" if scan_active else ("Tuned" if tuned is not None else "Idle"),
                    tone="info" if tuned is not None or scan_active else "neutral",
                    detail=f"Target {tuned:.2f} cm^-1" if isinstance(tuned, (float, int)) else status.status_summary,
                ),
            ),
        )

    def _build_acquisition_panel(self, status) -> OperatePanelModel:
        connected = status.connected
        acquisition_ready = self._draft_session_id is not None and connected
        capture_active = _bool_vendor_status(status, "capture_active")
        return OperatePanelModel(
            title="HF2LI / Acquisition",
            subtitle="Expose only the small operator-meaningful subset needed for the MVP.",
            fields=(
                FormFieldModel(
                    name="hf2_demod_index",
                    label="Demodulator",
                    field_type="number",
                    value=str(self._draft.hf2_demod_index),
                    help_text="Current operator-facing demodulator selection.",
                ),
                FormFieldModel(
                    name="hf2_component",
                    label="Signal component",
                    field_type="select",
                    options=tuple(
                        FormOptionModel(value=component.value, label=component.value.upper(), selected=component == self._draft.hf2_component)
                        for component in (
                            HF2SampleComponent.R,
                            HF2SampleComponent.X,
                            HF2SampleComponent.Y,
                            HF2SampleComponent.PHASE,
                        )
                    ),
                    help_text="Kept intentionally small for the MVP.",
                ),
                FormFieldModel(
                    name="hf2_sample_rate_hz",
                    label="Sample rate (Hz)",
                    field_type="number",
                    value=f"{self._draft.hf2_sample_rate_hz:.0f}",
                    help_text="Maps directly to the supported HF2 demodulator configuration.",
                ),
                FormFieldModel(
                    name="hf2_harmonic",
                    label="Harmonic",
                    field_type="number",
                    value=str(self._draft.hf2_harmonic),
                    help_text="The smallest cleanly supported harmonic control in the current contract.",
                ),
                FormFieldModel(
                    name="hf2_capture_interval_seconds",
                    label="Capture interval (s)",
                    field_type="number",
                    value=f"{self._draft.hf2_capture_interval_seconds:.2f}",
                    help_text="Current primary acquisition interval for simulator-backed review.",
                ),
            ),
            actions=(
                ActionButtonModel("Connect HF2LI", "/operate/hf2/connect", disabled=connected),
                ActionButtonModel("Disconnect HF2LI", "/operate/hf2/disconnect", tone="secondary", disabled=not connected),
                ActionButtonModel(
                    "Start Acquisition",
                    "/operate/hf2/start",
                    disabled=not acquisition_ready or capture_active,
                    helper_text="Save a session first." if self._draft_session_id is None else "",
                ),
                ActionButtonModel("Stop Acquisition", "/operate/hf2/stop", tone="secondary", disabled=not capture_active),
            ),
            status_items=(
                StatusItemModel("Connection", "Connected" if connected else "Disconnected", tone="good" if connected else "bad", detail=status.status_summary),
                StatusItemModel("Acquisition", "Active" if capture_active else "Idle", tone="good" if capture_active else "neutral"),
                StatusItemModel("Session requirement", "Ready" if self._draft_session_id else "Save session first", tone="info" if self._draft_session_id else "warn"),
            ),
        )

    def _build_run_panel(self, preflight: PreflightReport, latest_state: RunState | None) -> OperatePanelModel:
        issue_detail = self._preflight_issue_summary(preflight)
        run_label = latest_state.phase.value if latest_state is not None else "not started"
        run_tone = _phase_tone(latest_state.phase) if latest_state is not None else ("good" if preflight.ready_to_start else "warn")
        run_state: PageStateModel | None = None
        if latest_state is not None and latest_state.phase == RunPhase.FAULTED and latest_state.latest_fault is not None:
            run_state = fault_state("Run faulted", latest_state.latest_fault.message)
        elif not preflight.ready_to_start:
            run_state = blocked_state("Run blocked", "Preflight must pass before the run can start.", details=issue_detail)
        return OperatePanelModel(
            title="Run Control",
            subtitle="Preflight, start, and abort remain explicit so the user can see whether the system is ready now.",
            actions=(
                ActionButtonModel("Run Preflight", "/operate/run/preflight"),
                ActionButtonModel("Start Run", "/operate/run/start", disabled=not preflight.ready_to_start),
                ActionButtonModel("Abort Run", "/operate/run/abort", tone="danger", disabled=latest_state is None or latest_state.phase in {RunPhase.COMPLETED, RunPhase.FAULTED, RunPhase.ABORTED}),
            ),
            status_items=(
                StatusItemModel("Ready", "Yes" if preflight.ready_to_start else "No", tone="good" if preflight.ready_to_start else "bad"),
                StatusItemModel("Run state", run_label.replace("_", " ").title(), tone=run_tone),
                StatusItemModel("Errors / warnings", "Clear" if not issue_detail else f"{len(issue_detail)} item(s)", tone="warn" if issue_detail else "good", detail=issue_detail[0] if issue_detail else "No blocking or warning issues."),
            ),
            state=run_state,
            notes=("Start Run reuses the current planned session when one exists; otherwise it creates one first.",),
        )

    async def _live_status_items(self, preflight: PreflightReport) -> tuple[StatusItemModel, ...]:
        laser = await self._scenario.bundle.mircat.get_status()
        hf2 = await self._scenario.bundle.hf2li.get_status()
        timing_issue = next((check for check in preflight.checks if check.target in {"t660-2-master", "t660-1-slave"} and check.state.value != "pass"), None)
        scan_active = _bool_vendor_status(laser, "scan_active")
        tuned = laser.vendor_status.get("tuned_target_cm1")
        return (
            StatusItemModel("Laser connected", "Yes" if laser.connected else "No", tone="good" if laser.connected else "bad"),
            StatusItemModel("Armed", "Yes" if _bool_vendor_status(laser, "armed") else "No", tone="good" if _bool_vendor_status(laser, "armed") else "neutral"),
            StatusItemModel("Emission", "On" if _bool_vendor_status(laser, "emission_enabled") else "Off", tone="good" if _bool_vendor_status(laser, "emission_enabled") else "neutral"),
            StatusItemModel(
                "Tuned / scan state",
                "Scan active" if scan_active else ("Tuned" if tuned is not None else "Idle"),
                tone="info" if scan_active or tuned is not None else "neutral",
                detail=f"Target {tuned:.2f} cm^-1" if isinstance(tuned, (float, int)) else laser.status_summary,
            ),
            StatusItemModel("HF2LI connected", "Yes" if hf2.connected else "No", tone="good" if hf2.connected else "bad"),
            StatusItemModel(
                "Timing readiness",
                "Ready" if timing_issue is None else "Attention",
                tone="good" if timing_issue is None else "warn",
                detail="Master and slave timing are ready." if timing_issue is None else timing_issue.summary,
            ),
        )

    async def _recent_activity_items(self) -> tuple[EventLogItem, ...]:
        activity = list(self._recent_activity)
        if self._active_run_id is not None:
            activity.extend(await self.get_run_events(self._active_run_id))
        elif self._selected_session_id is not None:
            detail = await self._session_catalog.get_session_detail(self._selected_session_id)
            activity.extend(
                EventLogItem(
                    timestamp=event.emitted_at,
                    source=event.source,
                    message=event.message,
                    tone=_event_tone(event.event_type),
                )
                for event in detail.event_timeline[-4:]
            )
        activity.sort(key=lambda item: item.timestamp, reverse=True)
        return tuple(activity[:8])

    def _operate_page_state(self, preflight: PreflightReport, latest_state: RunState | None) -> PageStateModel | None:
        if latest_state is not None and latest_state.phase == RunPhase.FAULTED and latest_state.latest_fault is not None:
            return fault_state(
                "System attention required",
                "The last run faulted on the canonical path.",
                details=(latest_state.latest_fault.message,),
            )
        return self._preflight_page_state(
            preflight,
            title="System not ready",
            warning_title="System ready with warnings",
        )

    def _preflight_page_state(self, preflight: PreflightReport, *, title: str, warning_title: str) -> PageStateModel | None:
        blocking_messages = tuple(
            issue.message
            for check in preflight.checks
            for issue in check.issues
            if issue.blocking
        )
        warning_messages = tuple(
            issue.message
            for check in preflight.checks
            for issue in check.issues
            if not issue.blocking
        )
        if blocking_messages:
            return blocked_state(title, "One or more required checks are blocking the supported-v1 workflow.", details=blocking_messages)
        if warning_messages:
            return warning_state(warning_title, "The main path can proceed, but optional capability or review detail is degraded.", details=warning_messages)
        return None

    def _preflight_issue_summary(self, preflight: PreflightReport) -> tuple[str, ...]:
        return tuple(
            issue.message
            for check in preflight.checks
            for issue in check.issues
        )

    def _current_hf2_acquisition(self) -> HF2PrimaryAcquisition:
        return HF2PrimaryAcquisition(
            profile_name=self._scenario.recipe.hf2_primary_acquisition.profile_name,
            stream_selections=(
                HF2StreamSelection(
                    demod_index=self._draft.hf2_demod_index,
                    component=self._draft.hf2_component,
                ),
            ),
            demodulators=(
                HF2DemodulatorConfiguration(
                    demod_index=self._draft.hf2_demod_index,
                    sample_rate_hz=self._draft.hf2_sample_rate_hz,
                    harmonic=self._draft.hf2_harmonic,
                ),
            ),
            capture_interval_seconds=self._draft.hf2_capture_interval_seconds,
            preferred_device_id=self._scenario.recipe.hf2_primary_acquisition.preferred_device_id,
        )

    def _current_recipe(self):
        return replace(
            self._scenario.recipe,
            session_label=self._draft.session_label or None,
            hf2_primary_acquisition=self._current_hf2_acquisition(),
        )

    def _current_session_notes(self) -> tuple[str, ...]:
        return (
            f"sample_id:{self._draft.sample_id}",
            f"operator_notes:{self._draft.operator_notes}",
            f"runtime_mode:simulator:{self._scenario.scenario_id}",
            f"runtime_description:{self._scenario.description}",
        )

    def _load_draft_from_manifest(self, manifest: SessionManifest) -> None:
        self._draft.session_label = manifest.recipe_snapshot.session_label or self._draft.session_label
        self._draft.sample_id = _note_value(manifest.notes, "sample_id") or self._draft.sample_id
        self._draft.operator_notes = _note_value(manifest.notes, "operator_notes") or self._draft.operator_notes
        acquisition = manifest.recipe_snapshot.hf2_primary_acquisition
        self._draft.hf2_capture_interval_seconds = acquisition.capture_interval_seconds
        self._draft.hf2_demod_index = acquisition.demodulators[0].demod_index
        self._draft.hf2_component = acquisition.stream_selections[0].component
        self._draft.hf2_sample_rate_hz = acquisition.demodulators[0].sample_rate_hz
        self._draft.hf2_harmonic = acquisition.demodulators[0].harmonic

    def _current_session_status_label(self, sessions) -> str:
        current_session_id = self._draft_session_id or self._selected_session_id
        if current_session_id is None:
            return "not selected"
        session = next((entry for entry in sessions if entry.session_id == current_session_id), None)
        return session.status.value if session is not None else "active in memory"

    def _remember_activity(self, source: str, message: str, *, tone: str) -> None:
        self._recent_activity.insert(
            0,
            EventLogItem(
                timestamp=_utc_now(),
                source=source,
                message=message,
                tone=tone,
            ),
        )
        del self._recent_activity[12:]

    def _mark_preflight_dirty(self) -> None:
        self._preflight_dirty = True

    def _setup_surface_title(self, surface: str) -> str:
        return {
            "setup": "Setup",
            "advanced": "Advanced",
            "calibrated": "Calibrated",
        }.get(surface, "Setup")

    def _setup_surface_subtitle(self, surface: str) -> str:
        subtitles = {
            "setup": "Operator-first setup, readiness, session identity, and core experiment configuration.",
            "advanced": "Expert-only timing, acquisition, scan, and routing controls that stay on the same canonical path.",
            "calibrated": "Guarded bench-owned assumptions, calibrations, and fixed installation context.",
        }
        return subtitles.get(surface, subtitles["setup"])

    def _setup_surface_navigation(self, active_surface: str) -> tuple[NavigationItem, ...]:
        scenario = self._scenario.scenario_id
        return (
            NavigationItem(
                label="Setup",
                href=f"/setup?scenario={scenario}",
                active=active_surface == "setup",
            ),
            NavigationItem(
                label="Advanced",
                href=f"/setup/advanced?scenario={scenario}",
                active=active_surface == "advanced",
            ),
            NavigationItem(
                label="Calibrated",
                href=f"/setup/calibrated?scenario={scenario}",
                active=active_surface == "calibrated",
            ),
        )

    def _surface_badges(self, surface: str) -> tuple[StatusBadge, ...]:
        badge_map = {
            "operate": (
                StatusBadge(label="Operator-first", tone="good"),
                StatusBadge(label="Simulator-backed controls", tone="info"),
                StatusBadge(label="Default path", tone="neutral"),
            ),
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

    def _setup_form_sections(self, surface: str) -> tuple[FormSectionModel, ...]:
        recipe = self._scenario.recipe
        if surface == "advanced":
            return (
                FormSectionModel(
                    title="Timing Program",
                    subtitle="Expert timing controls remain visible here without changing execution ownership.",
                    fields=(
                        FormFieldModel(
                            label="Pump Fire Offset (ns)",
                            field_type="number",
                            value=f"{recipe.timing.master.pump_fire_command.offset_ns:.0f}",
                            help_text="T660-2 master output relative to T0.",
                        ),
                        FormFieldModel(
                            label="Pump Q-Switch Offset (ns)",
                            field_type="number",
                            value=f"{recipe.timing.master.pump_qswitch_command.offset_ns:.0f}",
                            help_text="T660-2 Q-switch output relative to T0.",
                        ),
                        FormFieldModel(
                            label="Probe Trigger Offset (ns)",
                            field_type="number",
                            value=f"{recipe.timing.slave.probe_trigger.offset_ns:.0f}",
                            help_text="T660-1 probe trigger relative to the shared T0 axis.",
                        ),
                        FormFieldModel(
                            label="Acquisition Reference Marker",
                            field_type="select",
                            options=tuple(
                                FormOptionModel(
                                    value=marker.value,
                                    label=marker.value,
                                    selected=marker == recipe.timing.acquisition_reference_marker,
                                )
                                for marker in recipe.timing.selected_digital_markers
                            ),
                            help_text="The selected digital timing reference for alignment or triggering.",
                        ),
                    ),
                    notes=(
                        "These controls are visible to confirm required expert surfaces.",
                        "Editing and apply wiring stay deferred until after workflow review.",
                    ),
                ),
                FormSectionModel(
                    title="Scan and Probe Tuning",
                    subtitle="Probe mode, scan shape, and pulse configuration stay progressive instead of polluting Setup.",
                    fields=(
                        FormFieldModel(
                            label="Probe Timing Mode",
                            field_type="select",
                            options=(
                                FormOptionModel("continuous_probe", "Continuous probe", selected=False),
                                FormOptionModel("synchronized_probe", "Synchronized probe", selected=True),
                            ),
                            help_text="The probe timing mode is explicit and persisted.",
                        ),
                        FormFieldModel(
                            label="Preferred QCL",
                            field_type="number",
                            value=str(recipe.mircat.preferred_qcl or ""),
                            help_text="Preferred MIRcat laser selection for the fixture recipe.",
                        ),
                        FormFieldModel(
                            label="Pulse Rate (Hz)",
                            field_type="number",
                            value=f"{recipe.mircat.pulse_rate_hz or 0:.0f}",
                            help_text="Visible now so expert timing needs can be reviewed early.",
                        ),
                        FormFieldModel(
                            label="Sweep Speed (cm^-1/s)",
                            field_type="number",
                            value=f"{recipe.mircat.sweep_scan.scan_speed_cm1_per_s if recipe.mircat.sweep_scan else 0:.1f}",
                            help_text="Current simulator-backed sweep speed.",
                        ),
                    ),
                ),
                FormSectionModel(
                    title="Capture and Routing",
                    subtitle="HF2, MUX, and Pico controls remain visible here as one coordinated workflow.",
                    fields=(
                        FormFieldModel(
                            label="HF2 Profile",
                            field_type="text",
                            value=recipe.hf2_primary_acquisition.profile_name,
                            help_text="HF2 remains the primary scientific raw-data recorder.",
                        ),
                        FormFieldModel(
                            label="Pico Monitoring Mode",
                            field_type="select",
                            options=(
                                FormOptionModel("disabled", "Disabled", selected=recipe.pico_secondary_capture.mode.value == "disabled"),
                                FormOptionModel("monitor_only", "Monitor only", selected=recipe.pico_secondary_capture.mode.value == "monitor_only"),
                                FormOptionModel("record_only", "Record only", selected=recipe.pico_secondary_capture.mode.value == "record_only"),
                                FormOptionModel("monitor_and_record", "Monitor and record", selected=recipe.pico_secondary_capture.mode.value == "monitor_and_record"),
                            ),
                            help_text="Pico remains secondary context only.",
                        ),
                        FormFieldModel(
                            label="MUX Route Set",
                            field_type="text",
                            value=recipe.mux_route_selection.route_set_name,
                            help_text="The named route set sent to Pico channel A, B, and external trigger.",
                        ),
                        FormFieldModel(
                            label="Recorded Inputs",
                            field_type="text",
                            value=", ".join(item.value for item in recipe.pico_secondary_capture.record_inputs) or "none",
                            help_text="Optional secondary monitor channels selected for the current recipe.",
                        ),
                    ),
                ),
            )

        if surface == "calibrated":
            mapping_id = recipe.time_to_wavenumber_mapping.mapping_id if recipe.time_to_wavenumber_mapping else "none"
            calibration = recipe.calibration_references[0] if recipe.calibration_references else None
            return (
                FormSectionModel(
                    title="Calibration References",
                    subtitle="Bench-owned references are visible here but not treated as routine operator settings.",
                    fields=(
                        FormFieldModel(
                            label="Calibration Reference",
                            field_type="text",
                            value=calibration.calibration_id if calibration else "none",
                            help_text="Current approved calibration reference used by the fixture recipe.",
                        ),
                        FormFieldModel(
                            label="Calibration Version",
                            field_type="text",
                            value=calibration.version if calibration else "none",
                            help_text="Calibration version remains explicit for provenance.",
                        ),
                        FormFieldModel(
                            label="Time-to-Wavenumber Mapping",
                            field_type="text",
                            value=mapping_id,
                            help_text="Required mapping context for scan-based recipes.",
                        ),
                        FormFieldModel(
                            label="Calibration Source",
                            field_type="text",
                            value=calibration.location if calibration else "not configured",
                            help_text="Source path or reference location for the current bench-owned mapping.",
                        ),
                    ),
                ),
                FormSectionModel(
                    title="Fixed Installation Assumptions",
                    subtitle="Guarded defaults and wiring assumptions that should not appear in the day-to-day operator path.",
                    fields=(
                        FormFieldModel(
                            label="Master Timing Identity",
                            field_type="text",
                            value=recipe.timing.master.device_identity.value,
                            help_text="T660-2 stays the canonical master timing identity.",
                        ),
                        FormFieldModel(
                            label="Slave Timing Identity",
                            field_type="text",
                            value=recipe.timing.slave.device_identity.value,
                            help_text="T660-1 stays the canonical slave timing identity.",
                        ),
                        FormFieldModel(
                            label="Default Route Set",
                            field_type="text",
                            value=recipe.mux_route_selection.route_set_name,
                            help_text="Current default routing assumption for secondary monitoring.",
                        ),
                        FormFieldModel(
                            label="Pico Trigger Marker",
                            field_type="text",
                            value=recipe.pico_secondary_capture.trigger_marker.value if recipe.pico_secondary_capture.trigger_marker else "none",
                            help_text="Default trigger identity used for monitor capture when Pico is enabled.",
                        ),
                    ),
                    notes=(
                        "These values should stay guarded from routine run-to-run editing.",
                        "The current pass keeps them visible so the product shape can be reviewed.",
                    ),
                ),
            )

        return (
            FormSectionModel(
                title="Session and Sample Identity",
                subtitle="The minimum operator context that should be visible before a run.",
                fields=(
                    FormFieldModel(
                        label="Session Label",
                        field_type="text",
                        value=recipe.session_label or "Supported v1 simulator baseline",
                        help_text="Fixture-backed session label currently used for local review.",
                    ),
                    FormFieldModel(
                        label="Operator Preset",
                        field_type="text",
                        value=self._scenario.preset.name,
                        help_text="Current preset loaded into the setup surface.",
                    ),
                    FormFieldModel(
                        label="Sample Identifier",
                        field_type="text",
                        value="sample-A12",
                        help_text="Visible placeholder metadata field for run identity review.",
                    ),
                    FormFieldModel(
                        label="Operator Notes",
                        field_type="textarea",
                        value="Fixture-backed setup pass for workflow review. Persistence wiring for edited notes is deferred.",
                        help_text="Visible now so the required metadata area can be reviewed before deeper wiring.",
                    ),
                ),
            ),
            FormSectionModel(
                title="Default Experiment Path",
                subtitle="The simple operator flow stays focused on experiment intent, not device jargon.",
                fields=(
                    FormFieldModel(
                        label="Spectral Mode",
                        field_type="select",
                        options=(
                            FormOptionModel("single_wavelength", "Single wavelength", selected=False),
                            FormOptionModel("sweep_scan", "Sweep scan", selected=recipe.mircat.spectral_mode.value == "sweep_scan"),
                            FormOptionModel("step_measure_scan", "Step-measure scan", selected=False),
                            FormOptionModel("multispectral_scan", "Multispectral scan", selected=False),
                        ),
                        help_text="Visible core mode selection for the current recipe.",
                    ),
                    FormFieldModel(
                        label="Probe Emission Mode",
                        field_type="select",
                        options=(
                            FormOptionModel("pulsed", "Pulsed", selected=recipe.mircat.emission_mode.value == "pulsed"),
                            FormOptionModel("cw", "Continuous wave", selected=recipe.mircat.emission_mode.value == "cw"),
                        ),
                        help_text="Operator-visible emission choice.",
                    ),
                    FormFieldModel(
                        label="Pump Shots Before Probe",
                        field_type="number",
                        value=str(recipe.pump_shots_before_probe),
                        help_text="Current supported-v1 pump/probe relationship.",
                    ),
                    FormFieldModel(
                        label="Acquisition Timing Mode",
                        field_type="select",
                        options=(
                            FormOptionModel("continuous", "Continuous", selected=False),
                            FormOptionModel("delayed", "Delayed from T0", selected=False),
                            FormOptionModel("around_selected_signal", "Around selected signal", selected=recipe.timing.acquisition_timing_mode.value == "around_selected_signal"),
                        ),
                        help_text="Current acquisition timing mode presented without raw device syntax.",
                    ),
                ),
            ),
            FormSectionModel(
                title="Calibration and Monitoring Context",
                subtitle="Normal setup keeps calibration awareness visible without collapsing expert and bench-owned concerns together.",
                fields=(
                    FormFieldModel(
                        label="Calibration Reference",
                        field_type="text",
                        value=recipe.calibration_references[0].calibration_id if recipe.calibration_references else "none",
                        help_text="Selected approved calibration reference.",
                    ),
                    FormFieldModel(
                        label="MUX Route Set",
                        field_type="text",
                        value=recipe.mux_route_selection.route_set_name,
                        help_text="Named secondary monitor route set for review before the run.",
                    ),
                    FormFieldModel(
                        label="Pico Secondary Capture",
                        field_type="checkbox",
                        checked=recipe.pico_secondary_capture.mode.value != "disabled",
                        help_text="Optional secondary monitoring visibility remains explicit.",
                    ),
                    FormFieldModel(
                        label="Preflight Continue Action",
                        field_type="text",
                        value="Run preflight, then continue to Run",
                        help_text="Current real action path in this pass.",
                    ),
                ),
                notes=(
                    "Default setup stays intentionally smaller than the Advanced and Calibrated surfaces.",
                    "The controls shown here are reviewable now even though editing is not yet persisted.",
                ),
            ),
        )

    def _setup_callouts(self, surface: str, preflight: PreflightReport) -> tuple[CalloutModel, ...]:
        base = (
            CalloutModel(
                title="What is real now",
                body="Preflight, device status, session creation, run progression, persisted sessions, and raw artifact visibility are real in this simulator-backed shell.",
                tone="good",
            ),
            CalloutModel(
                title="What is still scaffolded",
                body="Form editing, write-back of setup changes, processing jobs, and analysis jobs remain intentionally deferred in this pass.",
                tone="info",
                items=("The visible controls are here to review workflow shape first.",),
            ),
        )
        if surface == "advanced":
            return base + (
                CalloutModel(
                    title="Advanced stays progressive",
                    body="Expert controls are isolated here so the default Setup path remains smaller and operator-friendly.",
                    tone="warn",
                ),
            )
        if surface == "calibrated":
            return base + (
                CalloutModel(
                    title="Calibrated is guarded",
                    body="These values represent bench-owned context and should not become routine operator edits.",
                    tone="warn",
                ),
            )
        return base + (
            CalloutModel(
                title="Ready-to-run summary",
                body=f"Current preflight status is {'ready' if preflight.ready_to_start else 'blocked'} for the active scenario.",
                tone="good" if preflight.ready_to_start else "warn",
            ),
        )

    def _setup_tables(self, surface: str, preflight: PreflightReport) -> tuple[TableModel, ...]:
        workflow_rows = (
            ("1", "Setup", "Operator identity, core recipe, and readiness", "Visible now"),
            ("2", "Advanced", "Timing, scan, acquisition, and routing tuning", "Visible now"),
            ("3", "Calibrated", "Guarded bench-owned defaults and mappings", "Visible now"),
            ("4", "Run", "Authoritative run state and live context", "Visible now"),
            ("5", "Results / Analyze", "Persisted sessions, provenance, and offline review", "Visible now"),
        )
        preflight_rows = tuple(
            (
                check.target,
                check.state.value,
                check.summary,
                "; ".join(issue.message for issue in check.issues) if check.issues else "No issues",
            )
            for check in preflight.checks
        )
        tables = [
            TableModel(
                title="Workflow Review Map",
                subtitle="This pass is about making the product workflow visible before deeper backend work continues.",
                headers=("Step", "Surface", "Operator View", "Current State"),
                rows=workflow_rows,
            ),
            TableModel(
                title="Readiness Matrix",
                subtitle="Control-plane preflight remains the source for blocked, warning, and ready states.",
                headers=("Target", "State", "Summary", "Issues"),
                rows=preflight_rows,
            ),
        ]
        if surface == "calibrated":
            tables.append(
                TableModel(
                    title="Guarded Edit Policy",
                    subtitle="Calibrated values remain visible, but routine editing is intentionally deferred and separated.",
                    headers=("Area", "Current Visibility", "Write Status"),
                    rows=(
                        ("Calibration references", "Visible", "Read-only"),
                        ("Mapping defaults", "Visible", "Read-only"),
                        ("Fixed wiring assumptions", "Visible", "Read-only"),
                    ),
                )
            )
        return tuple(tables)

    def _run_callouts(
        self,
        *,
        preflight: PreflightReport | None,
        detail: SessionDetail | None = None,
        final_state: RunState | None = None,
    ) -> tuple[CalloutModel, ...]:
        callouts = [
            CalloutModel(
                title="Run authority stays outside the UI",
                body="The control plane owns authoritative run state, and the UI is only projecting it.",
                tone="good",
            ),
            CalloutModel(
                title="Live versus persisted context",
                body="HF2 primary traces and Pico secondary monitor traces are shown during the run, while persisted sessions remain the source for later review.",
                tone="info",
            ),
        ]
        if final_state is None:
            callouts.append(
                CalloutModel(
                    title="Run controls available",
                    body="Start and abort are real. Pause, resume, and richer recovery actions are still planned from the visible workflow.",
                    tone="warn" if preflight and preflight.ready_to_start else "info",
                )
            )
        elif final_state.phase == RunPhase.COMPLETED:
            callouts.append(
                CalloutModel(
                    title="Run complete",
                    body="The selected run finished on the canonical path and the persisted session can now drive Results and Analyze.",
                    tone="good",
                )
            )
        elif final_state.phase == RunPhase.FAULTED:
            callouts.append(
                CalloutModel(
                    title="Fault path visible",
                    body="The UI is showing explicit fault behavior rather than hiding it behind alternate behavior.",
                    tone="bad",
                )
            )
        if detail is not None:
            callouts.append(
                CalloutModel(
                    title="Durable session path",
                    body=f"Current persisted session root: {self._session_dir(detail.manifest.session_id)}",
                    tone="info",
                )
            )
        return tuple(callouts)

    def _run_tables(
        self,
        *,
        preflight: PreflightReport | None,
        detail: SessionDetail | None = None,
    ) -> tuple[TableModel, ...]:
        tables = []
        if preflight is not None:
            tables.append(
                TableModel(
                    title="Preflight Gate Summary",
                    subtitle="Run can only start after the control plane returns a ready preflight report.",
                    headers=("Target", "State", "Blocking"),
                    rows=tuple(
                        (
                            check.target,
                            check.state.value,
                            "yes" if any(issue.blocking for issue in check.issues) else "no",
                        )
                        for check in preflight.checks
                    ),
                )
            )
        if detail is not None:
            tables.append(
                TableModel(
                    title="Persisted Run Storage",
                    subtitle="Run and Results stay connected through the saved session root, not through UI memory.",
                    headers=("Item", "Path or Value"),
                    rows=(
                        ("Session directory", str(self._session_dir(detail.manifest.session_id))),
                        ("Manifest", str(self._manifest_path(detail.manifest.session_id))),
                        ("Events", str(self._events_path(detail.manifest.session_id))),
                        ("Primary raw artifacts", str(len(detail.primary_raw_artifacts))),
                        ("Secondary monitor artifacts", str(len(detail.secondary_monitor_artifacts))),
                    ),
                )
            )
        return tuple(tables)

    def _results_callouts(
        self,
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
                body=f"Sessions persist under {self._storage_root} so they survive runtime recreation.",
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

    def _results_tables(self, selected_session_id: str | None) -> tuple[TableModel, ...]:
        if selected_session_id is None:
            return (
                TableModel(
                    title="Session Storage Policy",
                    subtitle="Saved sessions are durable and reopenable without the live UI.",
                    headers=("Area", "Policy"),
                    rows=(
                        ("Storage root", str(self._storage_root)),
                        ("Manifest location", "sessions/<session_id>/manifest.json"),
                        ("Events location", "sessions/<session_id>/events.jsonl"),
                        ("Replay rule", "Reopen uses persisted raw payloads and manifest state only"),
                    ),
                ),
            )
        return (
            TableModel(
                title="Selected Session Paths",
                subtitle="These filesystem locations are the actual durable targets used by the current runtime.",
                headers=("Item", "Path"),
                rows=(
                    ("Session directory", str(self._session_dir(selected_session_id))),
                    ("Manifest", str(self._manifest_path(selected_session_id))),
                    ("Events", str(self._events_path(selected_session_id))),
                    ("Raw artifact root", str(self._session_dir(selected_session_id) / "artifacts" / "raw")),
                ),
            ),
        )

    def _analyze_summary_panels(self, detail: SessionDetail) -> tuple[SummaryPanel, ...]:
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

    def _analyze_form_sections(self, detail: SessionDetail) -> tuple[FormSectionModel, ...]:
        return (
            FormSectionModel(
                title="Processing Controls",
                subtitle="Visible controls for raw-to-processed review, kept headless and outside the UI layer.",
                fields=(
                    FormFieldModel(
                        label="Source Session",
                        field_type="text",
                        value=detail.manifest.session_id,
                        help_text="The persisted session chosen for reprocessing.",
                    ),
                    FormFieldModel(
                        label="Processing Recipe",
                        field_type="select",
                        options=(
                            FormOptionModel("baseline", "Baseline processing scaffold", selected=True),
                            FormOptionModel("comparison", "Comparison-oriented processing scaffold", selected=False),
                        ),
                        help_text="Visible control only; no processing runner is attached yet.",
                    ),
                    FormFieldModel(
                        label="Use Calibration Mapping",
                        field_type="checkbox",
                        checked=detail.manifest.time_to_wavenumber_mapping is not None,
                        help_text="Current session already carries time-to-wavenumber context where required.",
                    ),
                    FormFieldModel(
                        label="Output Label",
                        field_type="text",
                        value="processed-summary-v1",
                        help_text="Placeholder output naming field for review.",
                    ),
                ),
                notes=(
                    "Processing remains a headless package concern.",
                    "This pass is surfacing the required controls before wiring the job runner.",
                ),
            ),
            FormSectionModel(
                title="Analysis Controls",
                subtitle="Visible scientific review controls that should exist after Results.",
                fields=(
                    FormFieldModel(
                        label="Analysis Recipe",
                        field_type="select",
                        options=(
                            FormOptionModel("quality_summary", "Quality summary scaffold", selected=True),
                            FormOptionModel("comparison_overlay", "Comparison overlay scaffold", selected=False),
                            FormOptionModel("derived_metrics", "Derived metrics scaffold", selected=False),
                        ),
                        help_text="Reviewable analysis-mode selector for the persisted-session workflow.",
                    ),
                    FormFieldModel(
                        label="Comparison Baseline",
                        field_type="text",
                        value="saved-session-001",
                        help_text="Current placeholder baseline for compare-against-prior-run behavior.",
                    ),
                    FormFieldModel(
                        label="Include Secondary Monitor Context",
                        field_type="checkbox",
                        checked=len(detail.secondary_monitor_artifacts) > 0,
                        help_text="Secondary monitor context remains optional and distinct from HF2 raw authority.",
                    ),
                    FormFieldModel(
                        label="Analysis Notes",
                        field_type="textarea",
                        value="Visible output area for planned derived metrics, overlays, and quality checks. Execution remains placeholder-backed in this pass.",
                        help_text="Reviewable notes field that marks this surface as scaffolded where needed.",
                    ),
                ),
            ),
        )

    def _analyze_callouts(self, detail: SessionDetail) -> tuple[CalloutModel, ...]:
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

    def _analyze_tables(self, detail: SessionDetail) -> tuple[TableModel, ...]:
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

    def _service_form_sections(self) -> tuple[FormSectionModel, ...]:
        return (
            FormSectionModel(
                title="Guarded Recovery Actions",
                subtitle="Visible expert-only controls kept out of the operator path during this review pass.",
                fields=(
                    FormFieldModel(
                        label="Zero HF2 Demod Phase",
                        field_type="checkbox",
                        checked=False,
                        help_text="Visible placeholder for an eventual expert action.",
                    ),
                    FormFieldModel(
                        label="Clear MUX Routes",
                        field_type="checkbox",
                        checked=False,
                        help_text="Visible placeholder for a guarded route reset.",
                    ),
                    FormFieldModel(
                        label="Re-arm Timing Outputs",
                        field_type="checkbox",
                        checked=False,
                        help_text="Visible placeholder for expert-only timing recovery.",
                    ),
                ),
                notes=("These controls are visible for review only in this pass.",),
            ),
            FormSectionModel(
                title="Calibration Maintenance",
                subtitle="Bench-owned changes stay isolated here and away from routine Setup use.",
                fields=(
                    FormFieldModel(
                        label="Active Calibration Set",
                        field_type="text",
                        value=self._scenario.recipe.calibration_references[0].calibration_id
                        if self._scenario.recipe.calibration_references
                        else "none",
                        help_text="Current fixture-backed calibration context.",
                    ),
                    FormFieldModel(
                        label="Storage Root",
                        field_type="text",
                        value=str(self._storage_root),
                        help_text="Current runtime storage root for durable sessions.",
                    ),
                ),
            ),
        )

    def _service_callouts(self, session_count: int) -> tuple[CalloutModel, ...]:
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

    def _service_tables(self, session_count: int) -> tuple[TableModel, ...]:
        return (
            TableModel(
                title="Storage and Replay Policy",
                subtitle="Service is also where storage expectations and reopen behavior are visible for review.",
                headers=("Policy Area", "Current Rule"),
                rows=(
                    ("Storage root", str(self._storage_root)),
                    ("Manifest path", "sessions/<session_id>/manifest.json"),
                    ("Raw payload path", "sessions/<session_id>/artifacts/raw/*.parquet"),
                    ("Current saved sessions", str(session_count)),
                ),
            ),
        )

    def _session_dir(self, session_id: str) -> Path:
        return self._storage_root / "sessions" / session_id

    def _manifest_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "manifest.json"

    def _events_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "events.jsonl"

    def _run_badge_tone(self, run_phase_label: str) -> str:
        normalized = run_phase_label.lower()
        if "completed" in normalized or "ready" in normalized:
            return "good"
        if "fault" in normalized or "abort" in normalized:
            return "bad"
        if "running" in normalized or "starting" in normalized:
            return "warn"
        return "neutral"

    async def reopen_session(self, session_id: str) -> SessionManifest:
        return await self.open_saved_session(session_id)

    async def get_known_run_id(self) -> str | None:
        return self._active_run_id

    async def get_run_events(self, run_id: str) -> tuple[EventLogItem, ...]:
        timeline = await self._run_monitor.get_run_timeline(run_id)
        return tuple(
            EventLogItem(
                timestamp=event.emitted_at,
                source=event.source,
                message=event.message,
                tone=_event_tone(event.event_type),
            )
            for event in timeline.events
        )

    async def get_live_data(
        self,
        run_id: str,
    ) -> tuple[tuple[LiveDataSeries, ...], tuple[LiveDataSeries, ...]]:
        timeline = await self._run_monitor.get_run_timeline(run_id)
        grouped: dict[tuple[str, ArtifactSourceRole], list[LiveDataPointModel]] = defaultdict(list)
        metadata: dict[tuple[str, ArtifactSourceRole], tuple[str, str]] = {}
        for point in timeline.live_data_points:
            key = (point.stream_name, point.source_role)
            grouped[key].append(
                LiveDataPointModel(
                    axis_value=point.axis_value,
                    value=point.value,
                )
            )
            metadata[key] = (point.axis_label, point.axis_units)

        primary: list[LiveDataSeries] = []
        secondary: list[LiveDataSeries] = []
        for (stream_name, source_role), points in grouped.items():
            axis_label, axis_units = metadata[(stream_name, source_role)]
            series = LiveDataSeries(
                label=stream_name,
                units="V",
                axis_label=axis_label,
                axis_units=axis_units,
                role_label="Primary raw" if source_role == ArtifactSourceRole.PRIMARY_RAW else "Secondary monitor",
                points=tuple(points),
            )
            if source_role == ArtifactSourceRole.PRIMARY_RAW:
                primary.append(series)
            else:
                secondary.append(series)
        return tuple(primary), tuple(secondary)

    async def get_run_steps(self, run_id: str) -> tuple[RunStepSummary, ...]:
        timeline = await self._run_monitor.get_run_timeline(run_id)
        return tuple(
            RunStepSummary(
                phase_label=state.phase.value.title(),
                active_step=state.active_step or "n/a",
                progress_fraction=state.progress_fraction or 0.0,
                summary=_state_summary(state),
                tone=_phase_tone(state.phase),
            )
            for state in timeline.states
        )

    async def _device_cards(self) -> tuple[DeviceSummaryCard, ...]:
        statuses = (
            await self._scenario.bundle.mircat.get_status(),
            await self._scenario.bundle.hf2li.get_status(),
            await self._scenario.bundle.t660_master.get_status(),
            await self._scenario.bundle.t660_slave.get_status(),
            await self._scenario.bundle.mux.get_status(),
            await self._scenario.bundle.picoscope.get_status(),
        )
        return tuple(self._device_card_from_status(status) for status in statuses)

    def _device_card_from_status(self, status) -> DeviceSummaryCard:
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

    def _summary_panels_from_preflight(self, preflight: PreflightReport) -> tuple[SummaryPanel, ...]:
        return (
            SummaryPanel(
                title="Recipe Mode",
                subtitle="Experiment-first recipe and acquisition shape.",
                items=(
                    f"Probe spectral mode: {self._scenario.recipe.mircat.spectral_mode.value}",
                    f"Probe emission mode: {self._scenario.recipe.mircat.emission_mode.value}",
                    f"HF2 profile: {self._scenario.recipe.hf2_primary_acquisition.profile_name}",
                ),
            ),
            SummaryPanel(
                title="T0 Timing",
                subtitle="Canonical timing summary relative to the neutral master-layer origin.",
                items=tuple(
                    f"{entry.label}: {entry.offset_ns:.0f} ns"
                    for entry in preflight.timing_summary.entries
                ),
            ),
            SummaryPanel(
                title="Pump / Probe / Acquisition",
                subtitle="Supported-v1 relationship semantics.",
                items=(
                    f"Pump shots before probe: {preflight.pump_probe_summary.pump_shots_before_probe}",
                    f"Probe timing mode: {preflight.pump_probe_summary.probe_timing_mode.value}",
                    f"Acquisition timing mode: {preflight.pump_probe_summary.acquisition_timing_mode.value}",
                    f"Acquisition reference: {preflight.pump_probe_summary.acquisition_reference_marker.value if preflight.pump_probe_summary.acquisition_reference_marker else 'n/a'}",
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
                    f"Trigger marker: {preflight.pico_summary.trigger_marker.value if preflight.pico_summary.trigger_marker else 'none'}",
                    f"Recorded inputs: {', '.join(preflight.pico_summary.recorded_inputs) if preflight.pico_summary.recorded_inputs else 'none'}",
                ),
            ),
        )

    def _summary_panels_from_run_state(self, state: RunState) -> tuple[SummaryPanel, ...]:
        timing_items = tuple(
            f"{entry.label}: {entry.offset_ns:.0f} ns"
            for entry in (state.timing_summary.entries if state.timing_summary else ())
        )
        return (
            SummaryPanel(
                title="Run State",
                subtitle="Current authoritative state from the experiment engine.",
                items=(
                    f"Phase: {state.phase.value}",
                    f"Active step: {state.active_step or 'n/a'}",
                    f"Failure reason: {state.failure_reason.value if state.failure_reason else 'none'}",
                ),
            ),
            SummaryPanel(
                title="T0 Timing",
                subtitle="Current timing context relative to T0.",
                items=timing_items,
            ),
            SummaryPanel(
                title="Selected Markers",
                subtitle="Markers carried into the run and saved session.",
                items=tuple(marker.value for marker in state.selected_markers),
            ),
            SummaryPanel(
                title="MUX and Pico",
                subtitle="Secondary monitor routing and capture state.",
                items=(
                    f"Channel A: {state.mux_summary.channel_a if state.mux_summary else 'n/a'}",
                    f"Channel B: {state.mux_summary.channel_b if state.mux_summary else 'n/a'}",
                    f"Pico mode: {state.pico_summary.mode.value if state.pico_summary else 'n/a'}",
                    f"Pico inputs: {', '.join(state.pico_summary.recorded_inputs) if state.pico_summary and state.pico_summary.recorded_inputs else 'none'}",
                ),
            ),
        )

    def _detail_panels_from_session_detail(self, detail: SessionDetail) -> tuple[SummaryPanel, ...]:
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
                    f"Pico trigger: {manifest.pico_summary.trigger_marker.value if manifest.pico_summary.trigger_marker else 'none'}",
                    f"Time-to-wavenumber mapping: {manifest.time_to_wavenumber_mapping.mapping_id if manifest.time_to_wavenumber_mapping else 'none'}",
                ),
            ),
        )

    def _artifact_panels_from_session_detail(self, detail: SessionDetail) -> tuple[SummaryPanel, ...]:
        groups = (
            ("Primary Raw Artifacts", "HF2 remains the primary scientific raw-data authority.", detail.primary_raw_artifacts),
            (
                "Secondary Monitor Artifacts",
                "Pico monitor traces remain secondary context only.",
                detail.secondary_monitor_artifacts,
            ),
            ("Processed Artifacts", "Persisted processed outputs remain separate from raw authority.", detail.processed_artifacts),
            ("Analysis Artifacts", "Persisted analysis outputs remain separate from raw and processed outputs.", detail.analysis_artifacts),
            ("Export Artifacts", "Persisted exports cite their saved source artifacts.", detail.export_artifacts),
        )
        panels: list[SummaryPanel] = []
        for title, subtitle, artifacts in groups:
            items = tuple(
                self._artifact_summary_line(artifact)
                for artifact in artifacts
            ) or ("None recorded for this session.",)
            panels.append(SummaryPanel(title=title, subtitle=subtitle, items=items))
        return tuple(panels)

    def _artifact_summary_line(self, artifact) -> str:
        source_bits = [artifact.artifact_id, artifact.relative_path]
        if artifact.stream_name:
            source_bits.append(f"stream={artifact.stream_name}")
        if artifact.source_role:
            source_bits.append(f"role={artifact.source_role.value}")
        if artifact.device_kind:
            source_bits.append(f"device={artifact.device_kind.value}")
        if artifact.related_marker:
            source_bits.append(f"marker={artifact.related_marker}")
        return " | ".join(source_bits)

    async def _ensure_preflight(self) -> PreflightReport:
        if self._last_preflight is None or self._preflight_dirty:
            self._last_preflight = await self.run_preflight()
        return self._last_preflight

    async def _current_run_phase_label(self) -> str:
        if self._active_run_id is None:
            return "Not started"
        state = await self._coordinator.get_run_state(self._active_run_id)
        return state.phase.value.title()

    async def _latest_run_state(self) -> RunState | None:
        if self._active_run_id is None:
            return None
        return await self._coordinator.get_run_state(self._active_run_id)


def _default_tune_target(scenario: Phase3BScenarioContext) -> float:
    mircat = scenario.recipe.mircat
    if mircat.single_wavelength_cm1 is not None:
        return mircat.single_wavelength_cm1
    if mircat.sweep_scan is not None:
        return (mircat.sweep_scan.start_wavenumber_cm1 + mircat.sweep_scan.end_wavenumber_cm1) / 2.0
    if mircat.multispectral_scan is not None:
        return mircat.multispectral_scan.elements[0].target_wavenumber_cm1
    return 1750.0


def _note_value(notes: tuple[str, ...], prefix: str) -> str | None:
    target = f"{prefix}:"
    for note in notes:
        if note.startswith(target):
            return note[len(target):]
    return None


def _bool_vendor_status(status, key: str) -> bool:
    return bool(status.vendor_status.get(key, False))


def _event_tone(event_type: RunEventType) -> str:
    if event_type == RunEventType.DEVICE_FAULT_REPORTED:
        return "bad"
    if event_type == RunEventType.RUN_COMPLETED:
        return "good"
    return "neutral"


def _phase_tone(phase: RunPhase) -> str:
    if phase == RunPhase.COMPLETED:
        return "good"
    if phase == RunPhase.FAULTED:
        return "bad"
    if phase == RunPhase.RUNNING:
        return "warn"
    return "neutral"


def _state_summary(state: RunState) -> str:
    if state.latest_fault is not None:
        return state.latest_fault.message
    if state.failure_reason is not None:
        return state.failure_reason.value
    return state.phase.value


def _phase3b_storage_base_root(storage_root: Path | None = None) -> Path:
    if storage_root is not None:
        return storage_root.resolve()
    # Repo-local runtime state keeps saved sessions inspectable during local development.
    return Path(__file__).resolve().parents[3] / ".local_state"


def create_phase3b_runtime_map(storage_root: Path | None = None) -> dict[str, Phase3BSimulatorRuntime]:
    catalog = SupportedV1SimulatorCatalog()
    contexts = catalog.list_contexts()
    base_root = _phase3b_storage_base_root(storage_root)
    options = tuple(
        ScenarioOption(
            scenario_id=context.scenario_id,
            label=context.label,
            description=context.description,
            active=False,
        )
        for context in contexts
    )
    runtimes: dict[str, Phase3BSimulatorRuntime] = {}
    for context in contexts:
        try:
            session_store = FilesystemSessionStore(
                root=base_root,
                initial_manifests=context.initial_manifests,
                initial_raw_artifact_payloads=context.initial_raw_artifact_payloads,
            )
        except (ModuleNotFoundError, AttributeError):
            # Local review should still work when Parquet dependencies are unavailable.
            session_store = InMemorySessionStore(
                initial_manifests=context.initial_manifests,
                initial_raw_artifact_payloads=context.initial_raw_artifact_payloads,
            )
        coordinator = InMemoryRunCoordinator(
            drivers=SupportedV1DriverBundle(
                mircat=context.bundle.mircat,
                hf2li=context.bundle.hf2li,
                t660_master=context.bundle.t660_master,
                t660_slave=context.bundle.t660_slave,
                mux=context.bundle.mux,
                picoscope=context.bundle.picoscope,
            ),
            session_store=session_store,
            session_replayer=session_store,
            preflight_validator=SupportedV1PreflightValidator(),
            run_plan_factory=context.run_plan_factory,
        )
        runtimes[context.scenario_id] = Phase3BSimulatorRuntime(
            scenario=context,
            scenario_options=options,
            session_store=session_store,
            coordinator=coordinator,
            session_catalog=session_store,
            session_replayer=session_store,
            storage_root=base_root,
        )
    return runtimes


def create_phase3b_simulator_app(storage_root: Path | None = None):
    return create_ui_app(create_phase3b_runtime_map(storage_root=storage_root), default_scenario="nominal")


def run_phase3b_demo(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the dependency-light Phase 3B simulator shell."""

    from wsgiref.simple_server import make_server

    app = create_phase3b_simulator_app()
    with make_server(host, port, app) as server:
        server.serve_forever()
