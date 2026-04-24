"""Simulator-backed UI runtime for the generic single-wavelength v1 workflow."""

from __future__ import annotations

from pathlib import Path

from ircp_contracts import (
    EXPERIMENT_ID,
    EXPERIMENT_NAME,
    LockInSettings,
    PlotDisplayMode,
    PlotMetricFamily,
    ProbeEmissionMode,
    ProbeSettings,
    PumpSettings,
    RunHeader,
    RunLifecycleState,
    SessionRecord,
    SetupState,
    SingleWavelengthPumpProbeRecipe,
    TimescaleRegime,
    validate_run_header_fields,
    validate_session_fields,
)
from ircp_data_pipeline import SingleWavelengthRunStore
from ircp_experiment_engine import SingleWavelengthPumpProbeCoordinator
from ircp_processing import build_processed_run_record, select_plot_series
from ircp_reports import metadata_export_bytes, processed_export_bytes, raw_export_bytes
from ircp_simulators import SimulatorScenarioContext
from ircp_ui_shell import (
    ActionButtonModel,
    FormFieldModel,
    FormOptionModel,
    HeaderStatus,
    NavigationItem,
    PanelModel,
    PlotPoint,
    ResultsDownload,
    ResultsPageModel,
    ResultsPlotModel,
    RunListItem,
    SessionListItem,
    SessionPageModel,
    SetupPageModel,
    StatusBadge,
    StatusItemModel,
    UiRuntimeGateway,
)
from ircp_ui_shell.page_state import blocked_state, empty_state, fault_state, success_state, warning_state


class SimulatorUiRuntime(UiRuntimeGateway):
    """Thin UI adapter over data-pipeline persistence and engine orchestration."""

    def __init__(
        self,
        *,
        scenario: SimulatorScenarioContext,
        storage_root: Path,
    ) -> None:
        self._scenario = scenario
        self._store = SingleWavelengthRunStore(storage_root)
        self._coordinator = SingleWavelengthPumpProbeCoordinator(
            self._store,
            fault_on_start=scenario.fault_on_start,
        )
        self._recipe = SingleWavelengthPumpProbeRecipe()
        self._session: SessionRecord | None = None
        self._run_header: RunHeader | None = None
        self._saved_pump: PumpSettings | None = scenario.default_pump
        self._saved_timescale: TimescaleRegime | None = scenario.default_timescale
        self._saved_probe: ProbeSettings | None = scenario.default_probe
        self._saved_lockin: LockInSettings | None = scenario.default_lockin
        self._pump: PumpSettings | None = scenario.default_pump
        self._timescale: TimescaleRegime | None = scenario.default_timescale
        self._probe: ProbeSettings | None = scenario.default_probe
        self._lockin: LockInSettings | None = scenario.default_lockin
        self._setup_saved = False
        self._probe_connected = scenario.default_probe.ready
        self._lockin_connected = scenario.default_lockin.ready
        self._session_form_draft: dict[str, str] | None = None
        self._pending_session_overwrite: dict[str, str] | None = None
        self._session_conflict_name: str | None = None

    async def get_header_status(self, active_route: str) -> HeaderStatus:
        setup = self._setup_state()
        return HeaderStatus(
            title="IR Control Platform",
            active_route=active_route,
            navigation=(
                NavigationItem("Session", "/session", active=active_route == "session"),
                NavigationItem(
                    "Setup",
                    "/setup",
                    active=active_route == "setup",
                    disabled=not (setup.session_saved and setup.run_header_saved),
                ),
                NavigationItem("Results", "/results", active=active_route == "results"),
            ),
            badges=(
                StatusBadge(EXPERIMENT_NAME, "info"),
                StatusBadge("Session saved" if setup.session_saved else "Session needed", "good" if setup.session_saved else "warn"),
                StatusBadge("Run settings saved" if setup.run_header_saved else "Run settings needed", "good" if setup.run_header_saved else "warn"),
                StatusBadge("Ready to run" if setup.can_run else "Setup blocked", "good" if setup.can_run else "warn"),
            ),
            summary=f"{self._scenario.label} simulator",
        )

    async def get_session_page(self) -> SessionPageModel:
        session_state = None
        if self._pending_session_overwrite is not None:
            session_state = warning_state(
                "Session already exists",
                "A saved session with this Name / ID already exists. Overwrite it or cancel to choose another value.",
            )
        elif self._session_conflict_name is not None:
            session_state = warning_state(
                "Session ID conflict",
                "Choose a different Name / ID or overwrite the saved session.",
            )
        elif self._session is None:
            session_state = blocked_state(
                "Session metadata required",
                "Save the session and run settings before setup is available.",
            )
        elif self._run_header is None or not self._run_header.saved:
            session_state = warning_state(
                "Run settings required",
                "Save run settings before moving to setup.",
            )
        else:
            session_state = success_state(
                "Session and run settings saved",
                "Setup can now use editable session metadata while the run snapshot remains frozen at Run.",
            )
        sessions = tuple(
            SessionListItem(
                session_id=session.session_id,
                label=session.session_name,
                updated_at=session.updated_at,
                open_enabled=True,
            )
            for session in self._store.list_sessions()
        )
        runs = self._run_history()
        return SessionPageModel(
            title="Session",
            subtitle="Define the experimental context and draft run metadata before setup.",
            state=session_state,
            session_panel=self._session_panel(),
            run_header_panel=self._run_header_panel(),
            existing_sessions=sessions,
            existing_runs=runs,
        )

    async def get_setup_page(self) -> SetupPageModel:
        setup = self._setup_state()
        return SetupPageModel(
            title="Setup",
            subtitle="Configure pump, timescale, probe, lock-in overrides, and run controls on one page.",
            state=None,
            save_action=ActionButtonModel("Save", "/setup/save", disabled=not (setup.session_saved and setup.run_header_saved)),
            pump_panel=self._pump_panel(setup),
            timescale_panel=self._timescale_panel(setup),
            probe_panel=self._probe_panel(setup),
            lockin_panel=self._lockin_panel(setup),
            run_controls_panel=self._run_controls_panel(setup),
        )

    async def get_results_page(
        self,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
        metric_family: str = "R",
        display_mode: str = "overlay",
    ) -> ResultsPageModel:
        selected = self._resolve_results_selection(session_id, run_id)
        run_history = self._run_history()
        if selected is None:
            return ResultsPageModel(
                title="Results",
                subtitle="Review processed data from saved runs without live hardware.",
                state=empty_state("No completed run selected", "Complete a run or select a saved run for review."),
                selected_session_id=None,
                selected_run_id=None,
                selector_panel=self._results_selector_panel(metric_family, display_mode),
                metadata_panel=PanelModel("Run metadata"),
                plot=None,
                export_panel=PanelModel("Export"),
                run_history=run_history,
            )
        session, run = selected
        metric = PlotMetricFamily(metric_family)
        mode = PlotDisplayMode(display_mode)
        raw = self._store.load_raw_run_record(session.session_id, run.run_id)
        processed = build_processed_run_record(raw, metric)
        points = tuple(
            PlotPoint(
                time_seconds=item["time_seconds"],
                sample=item.get("sample"),
                reference=item.get("reference"),
                ratio=item.get("ratio"),
            )
            for item in select_plot_series(processed, mode)
        )
        state = None
        if run.completion_status == RunLifecycleState.FAULTED:
            state = fault_state("Run faulted", run.fault_error_state or "The run faulted.")
        elif run.completion_status != RunLifecycleState.COMPLETED:
            state = warning_state("Run incomplete", f"Run status is {run.completion_status.value}.")
        return ResultsPageModel(
            title="Results",
            subtitle="Choose metric family and display mode from persisted run data.",
            state=state,
            selected_session_id=session.session_id,
            selected_run_id=run.run_id,
            selector_panel=self._results_selector_panel(metric.value, mode.value, session.session_id, run.run_id),
            metadata_panel=PanelModel(
                "Run metadata / settings snapshot",
                status_items=(
                    StatusItemModel("Session", session.session_id),
                    StatusItemModel("Run", run.run_id),
                    StatusItemModel("Status", run.completion_status.value),
                    StatusItemModel("Timescale", run.settings_snapshot.timescale.value if run.settings_snapshot else "none"),
                    StatusItemModel("Wavelength", f"{run.settings_snapshot.probe.wavelength_cm1:.2f} cm^-1" if run.settings_snapshot else "none"),
                ),
            ),
            plot=ResultsPlotModel(metric_family=metric.value, display_mode=mode.value, points=points),
            export_panel=self._export_panel(session.session_id, run.run_id),
            run_history=run_history,
        )

    async def get_results_download(self, *, session_id: str, run_id: str, asset: str) -> ResultsDownload:
        session = self._store.load_session(session_id)
        run = self._store.load_run_record(session_id, run_id)
        if run.settings_snapshot is None or run.raw_record_id is None:
            raise ValueError("Selected run does not have persisted acquisition data.")
        raw = self._store.load_raw_run_record(session_id, run_id)
        if asset == "raw":
            return ResultsDownload(f"{run_id}-raw.csv", "text/csv; charset=utf-8", raw_export_bytes(raw))
        if asset == "processed":
            processed = self._store.load_processed_run_record(session_id, run_id)
            return ResultsDownload(f"{run_id}-processed.json", "application/json; charset=utf-8", processed_export_bytes(processed))
        manifest = self._store.load_artifact_manifest(session_id, run_id)
        return ResultsDownload(
            f"{run_id}-metadata.json",
            "application/json; charset=utf-8",
            metadata_export_bytes(
                session=session,
                run=run,
                settings_snapshot=run.settings_snapshot,
                artifact_manifest=manifest,
            ),
        )

    async def save_session(
        self,
        *,
        session_name: str,
        operator: str,
        sample_id: str,
        sample_notes: str,
        experiment_notes: str,
    ) -> str:
        issues = validate_session_fields(session_name=session_name, operator=operator, sample_id=sample_id)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))
        form_values = {
            "session_name": session_name,
            "operator": operator,
            "sample_id": sample_id,
            "sample_notes": sample_notes,
            "experiment_notes": experiment_notes,
        }
        self._session_form_draft = dict(form_values)
        if self._session is None:
            session_id = session_name.strip()
            if self._store.session_exists(session_id):
                self._pending_session_overwrite = dict(form_values)
                self._session_conflict_name = session_id
                return "overwrite_pending"
            self._session = self._store.create_session(
                session_id=session_id,
                experiment_type=EXPERIMENT_ID,
                session_name=session_name,
                operator=operator,
                sample_id=sample_id,
                sample_notes=sample_notes,
                experiment_notes=experiment_notes,
            )
        else:
            self._session = self._store.save_session(
                SessionRecord(
                    session_id=self._session.session_id,
                    experiment_type=EXPERIMENT_ID,
                    session_name=session_name,
                    operator=operator,
                    sample_id=sample_id,
                    sample_notes=sample_notes,
                    experiment_notes=experiment_notes,
                    created_at=self._session.created_at,
                    updated_at=self._session.updated_at,
                )
            )
        self._session_form_draft = None
        self._pending_session_overwrite = None
        self._session_conflict_name = None
        return self._session.session_id

    async def confirm_session_overwrite(self) -> str:
        if self._pending_session_overwrite is None:
            raise ValueError("No session overwrite is pending.")
        session_id = self._pending_session_overwrite["session_name"].strip()
        existing = self._store.load_session(session_id)
        self._session = self._store.save_session(
            SessionRecord(
                session_id=existing.session_id,
                experiment_type=EXPERIMENT_ID,
                session_name=self._pending_session_overwrite["session_name"],
                operator=self._pending_session_overwrite["operator"],
                sample_id=self._pending_session_overwrite["sample_id"],
                sample_notes=self._pending_session_overwrite["sample_notes"],
                experiment_notes=self._pending_session_overwrite["experiment_notes"],
                created_at=existing.created_at,
                updated_at=existing.updated_at,
            )
        )
        self._session_form_draft = None
        self._pending_session_overwrite = None
        self._session_conflict_name = None
        return self._session.session_id

    async def cancel_session_overwrite(self) -> None:
        if self._pending_session_overwrite is not None:
            self._session_form_draft = dict(self._pending_session_overwrite)
            self._session_conflict_name = self._pending_session_overwrite["session_name"].strip()
        self._pending_session_overwrite = None

    async def open_session(self, *, session_id: str) -> str:
        self._session = self._store.load_session(session_id)
        self._run_header = None
        self._session_form_draft = None
        self._pending_session_overwrite = None
        self._session_conflict_name = None
        return self._session.session_id

    async def open_run(self, *, session_id: str, run_id: str) -> str:
        if self._session is None or self._session.session_id != session_id:
            raise ValueError("Open the session before opening one of its runs.")
        self._run_header = self._store.load_run_header(session_id, run_id)
        return self._run_header.run_id

    async def create_run(self, *, run_name: str, run_notes: str) -> str:
        if self._session is None:
            raise ValueError("Save the session before creating a run.")
        issues = validate_run_header_fields(run_name=run_name)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))
        run_id = run_name.strip()
        self._run_header = self._store.create_run_header(
            session_id=self._session.session_id,
            run_id=run_id,
            run_name=run_name,
            run_notes=run_notes,
        )
        return run_id

    async def save_run_header(self, *, run_name: str, run_notes: str) -> str:
        if self._session is None:
            raise ValueError("Save the session before saving run settings.")
        issues = validate_run_header_fields(run_name=run_name)
        if issues:
            raise ValueError("; ".join(issue.message for issue in issues))
        if self._run_header is None:
            await self.create_run(run_name=run_name, run_notes=run_notes)
        assert self._run_header is not None
        self._run_header = self._store.save_run_header(
            RunHeader(
                run_id=self._run_header.run_id,
                session_id=self._session.session_id,
                run_name=run_name,
                run_notes=run_notes,
                created_at=self._run_header.created_at,
                updated_at=self._run_header.updated_at,
                saved=True,
            )
        )
        return self._run_header.run_id

    async def configure_pump(self, *, enabled: bool, shot_count: int) -> None:
        self._pump = PumpSettings(enabled=enabled, shot_count=shot_count)
        self._setup_saved = False

    async def configure_timescale(self, *, timescale: str) -> None:
        self._timescale = TimescaleRegime(timescale)
        self._setup_saved = False

    async def configure_probe(
        self,
        *,
        wavelength_cm1: float,
        emission_mode: str,
        pulse_rate_hz: float | None,
        pulse_width_ns: float | None,
    ) -> None:
        self._probe = ProbeSettings(
            wavelength_cm1=wavelength_cm1,
            emission_mode=ProbeEmissionMode(emission_mode),
            pulse_rate_hz=pulse_rate_hz,
            pulse_width_ns=pulse_width_ns,
            ready=self._probe_connected,
            fault=self._probe.fault if self._probe is not None else None,
        )
        self._setup_saved = False

    async def configure_lockin(
        self,
        *,
        order: int,
        time_constant_seconds: float,
        transfer_rate_hz: float,
    ) -> None:
        self._lockin = LockInSettings(
            order=order,
            time_constant_seconds=time_constant_seconds,
            transfer_rate_hz=transfer_rate_hz,
            ready=self._lockin_connected,
            fault=self._lockin.fault if self._lockin is not None else None,
        )
        self._setup_saved = False

    async def save_setup(
        self,
        *,
        pump_enabled: bool,
        shot_count: int,
        timescale: str,
        wavelength_cm1: float,
        emission_mode: str,
        pulse_rate_hz: float | None,
        pulse_width_ns: float | None,
        order: int,
        time_constant_seconds: float,
        transfer_rate_hz: float,
    ) -> None:
        await self.configure_pump(enabled=pump_enabled, shot_count=shot_count)
        await self.configure_timescale(timescale=timescale)
        await self.configure_probe(
            wavelength_cm1=wavelength_cm1,
            emission_mode=emission_mode,
            pulse_rate_hz=pulse_rate_hz if emission_mode == ProbeEmissionMode.PULSED.value else None,
            pulse_width_ns=pulse_width_ns if emission_mode == ProbeEmissionMode.PULSED.value else None,
        )
        await self.configure_lockin(
            order=order,
            time_constant_seconds=time_constant_seconds,
            transfer_rate_hz=transfer_rate_hz,
        )
        self._saved_pump = self._pump
        self._saved_timescale = self._timescale
        self._saved_probe = self._probe
        self._saved_lockin = self._lockin
        self._setup_saved = True

    async def toggle_probe_connection(self) -> None:
        self._probe_connected = not self._probe_connected
        probe = self._probe or self._scenario.default_probe
        self._probe = ProbeSettings(
            wavelength_cm1=probe.wavelength_cm1,
            emission_mode=probe.emission_mode,
            pulse_rate_hz=probe.pulse_rate_hz,
            pulse_width_ns=probe.pulse_width_ns,
            ready=self._probe_connected,
            fault=probe.fault,
        )
        self._setup_saved = False

    async def clear_probe_fault(self) -> None:
        probe = self._probe or self._scenario.default_probe
        self._probe = ProbeSettings(
            wavelength_cm1=probe.wavelength_cm1,
            emission_mode=probe.emission_mode,
            pulse_rate_hz=probe.pulse_rate_hz,
            pulse_width_ns=probe.pulse_width_ns,
            ready=self._probe_connected,
            fault=None,
        )
        self._setup_saved = False

    async def toggle_lockin_connection(self) -> None:
        self._lockin_connected = not self._lockin_connected
        lockin = self._lockin or self._scenario.default_lockin
        self._lockin = LockInSettings(
            order=lockin.order,
            time_constant_seconds=lockin.time_constant_seconds,
            transfer_rate_hz=lockin.transfer_rate_hz,
            ready=self._lockin_connected,
            fault=lockin.fault,
        )
        self._setup_saved = False

    async def start_run(self) -> str:
        if self._session is None or self._run_header is None or not self._run_header.saved:
            raise ValueError("Save session and run settings before starting a run.")
        setup = self._setup_state()
        run = self._coordinator.start_run(
            session=self._session,
            run_header=self._run_header,
            setup=setup,
        )
        return run.run_id

    async def stop_run(self) -> str | None:
        if self._session is None or self._run_header is None:
            return None
        run = self._coordinator.stop_run(self._session.session_id, self._run_header.run_id)
        return run.run_id

    def _setup_state(self) -> SetupState:
        return self._coordinator.build_setup_state(
            session_saved=self._session is not None,
            run_header_saved=self._run_header is not None and self._run_header.saved,
            pump=self._saved_pump,
            timescale=self._saved_timescale,
            probe=self._saved_probe,
            lockin=self._saved_lockin,
        )

    def _session_panel(self) -> PanelModel:
        draft = self._session_form_draft or {}
        session = self._session
        session_name_value = draft.get("session_name", session.session_name if session else "")
        operator_value = draft.get("operator", session.operator if session else "")
        sample_id_value = draft.get("sample_id", session.sample_id if session else "")
        sample_notes_value = draft.get("sample_notes", session.sample_notes if session else "")
        experiment_notes_value = draft.get("experiment_notes", session.experiment_notes if session else "")
        pending_overwrite = self._pending_session_overwrite is not None
        return PanelModel(
            "Session Information",
            form_action="/session/save",
            fields=(
                FormFieldModel(
                    "experiment_type",
                    "Experiment type",
                    "select",
                    options=(FormOptionModel(EXPERIMENT_ID, "Single-Wavelength", selected=True),),
                ),
                FormFieldModel(
                    "session_name",
                    "Name / ID",
                    "text",
                    session_name_value,
                    required=True,
                    invalid=self._session_conflict_name is not None,
                    help_text="A saved session already uses this Name / ID." if self._session_conflict_name is not None else "",
                ),
                FormFieldModel("operator", "Operator", "text", operator_value, required=True),
                FormFieldModel("sample_id", "Sample ID or sample name", "text", sample_id_value, required=True),
                FormFieldModel("sample_notes", "Sample notes", "textarea", sample_notes_value),
                FormFieldModel("experiment_notes", "Notes", "textarea", experiment_notes_value),
            ),
            actions=(
                (ActionButtonModel("Overwrite", "/session/overwrite"), ActionButtonModel("Cancel", "/session/overwrite/cancel", "secondary"))
                if pending_overwrite
                else (ActionButtonModel("Save", "/session/save"),)
            ),
        )

    def _run_header_panel(self) -> PanelModel:
        header = self._run_header
        session_saved = self._session is not None
        return PanelModel(
            "Run Information",
            form_action="/session/run/save",
            fields=(
                FormFieldModel("run_name", "Name / ID", "text", header.run_name if header else "", required=True, disabled=not session_saved),
                FormFieldModel("run_notes", "Notes", "textarea", header.run_notes if header else "", disabled=not session_saved),
            ),
            actions=(ActionButtonModel("Save", "/session/run/save", disabled=not session_saved),),
            state=None if session_saved else blocked_state("Session not saved", "Save a session before editing run settings."),
        )

    def _pump_panel(self, setup: SetupState) -> PanelModel:
        pump = self._pump or self._scenario.default_pump
        return PanelModel(
            "Pump Settings",
            fields=(
                FormFieldModel("pump_enabled", "Pump enabled", "checkbox", checked=pump.enabled, disabled=not setup.session_saved),
                FormFieldModel("shot_count", "Shot count", "number", str(pump.shot_count), min_value="1", step="1", disabled=not setup.session_saved or not pump.enabled),
            ),
        )

    def _timescale_panel(self, setup: SetupState) -> PanelModel:
        selected = self._timescale or self._scenario.default_timescale
        plan = setup.acquisition_plan
        status_items = ()
        if plan is not None:
            status_items = ()
        return PanelModel(
            "Timescale",
            fields=(
                FormFieldModel(
                    "timescale",
                    "",
                    "select",
                    options=tuple(
                        FormOptionModel(regime.value, regime.value.title(), selected=regime == selected)
                        for regime in TimescaleRegime
                    ),
                    disabled=not setup.session_saved,
                ),
            ),
            status_items=status_items,
        )

    def _probe_panel(self, setup: SetupState) -> PanelModel:
        probe = self._probe or self._scenario.default_probe
        pulsed = probe.emission_mode == ProbeEmissionMode.PULSED
        return PanelModel(
            "Probe Settings",
            fields=(
                FormFieldModel("wavelength_cm1", "Wavelength (cm^-1)", "number", f"{probe.wavelength_cm1:.2f}", min_value="1", step="0.1", disabled=not setup.session_saved),
                FormFieldModel(
                    "emission_mode",
                    "Emission mode",
                    "select",
                    options=(
                        FormOptionModel("cw", "Continuous wave", selected=probe.emission_mode == ProbeEmissionMode.CW),
                        FormOptionModel("pulsed", "Pulsed", selected=pulsed),
                    ),
                    disabled=not setup.session_saved,
                ),
                FormFieldModel("pulse_rate_hz", "Pulse rate (Hz)", "number", "" if probe.pulse_rate_hz is None else f"{probe.pulse_rate_hz:.0f}", min_value="1", step="1", disabled=not setup.session_saved or not pulsed),
                FormFieldModel("pulse_width_ns", "Pulse width (ns)", "number", "" if probe.pulse_width_ns is None else f"{probe.pulse_width_ns:.0f}", min_value="1", step="1", disabled=not setup.session_saved or not pulsed),
            ),
            status_items=(
                StatusItemModel("Fault", probe.fault or "none", "bad" if probe.fault else "good"),
            ),
            header_actions=(
                ActionButtonModel("Disconnect" if self._probe_connected else "Connect", "/setup/probe/connection", "success" if self._probe_connected else "danger", disabled=not setup.session_saved),
                ActionButtonModel("Clear fault", "/setup/probe/fault/clear", "secondary", disabled=not setup.session_saved or not bool(probe.fault)),
            ),
        )

    def _lockin_panel(self, setup: SetupState) -> PanelModel:
        lockin = self._lockin or self._scenario.default_lockin
        return PanelModel(
            "Lock-In Amplifier Settings",
            fields=(
                FormFieldModel("order", "Order", "number", str(lockin.order), min_value="1", step="1", disabled=not setup.session_saved),
                FormFieldModel("time_constant_seconds", "Time Constant", "number", f"{lockin.time_constant_seconds:.6g}", min_value="7.832e-7", max_value="582.9", step="any", disabled=not setup.session_saved),
                FormFieldModel("transfer_rate_hz", "Transfer Rate", "number", f"{lockin.transfer_rate_hz:.6g}", min_value="0.2196", max_value="1842000", step="any", disabled=not setup.session_saved),
            ),
            header_actions=(ActionButtonModel("Disconnect" if self._lockin_connected else "Connect", "/setup/lockin/connection", "success" if self._lockin_connected else "danger", disabled=not setup.session_saved),),
        )

    def _run_controls_panel(self, setup: SetupState) -> PanelModel:
        latest = None
        if self._session is not None and self._run_header is not None:
            try:
                latest = self._store.load_run_record(self._session.session_id, self._run_header.run_id)
            except FileNotFoundError:
                latest = None
        details = tuple(issue.message for issue in setup.validation_issues if issue.blocking)
        run_disabled = (not self._setup_saved) or (not setup.can_run)
        state = None
        if not self._setup_saved:
            state = blocked_state("Settings not saved", "Settings must be saved before running.")
        elif not setup.can_run:
            state = blocked_state("Run disabled", "Run remains disabled until saved settings pass validation.", details=details)
        return PanelModel(
            "Run Controls",
            actions=(
                ActionButtonModel("Run", "/setup/run/start", disabled=run_disabled),
                ActionButtonModel("Stop", "/setup/run/stop", "secondary", disabled=latest is None or latest.completion_status != RunLifecycleState.RUNNING),
            ),
            state=state,
        )

    def _results_selector_panel(
        self,
        metric_family: str,
        display_mode: str,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> PanelModel:
        return PanelModel(
            "Plot controls",
            form_action="/results",
            fields=(
                FormFieldModel("session_id", "Session", "text", session_id or "", read_only=True),
                FormFieldModel("run_id", "Run", "text", run_id or "", read_only=True),
                FormFieldModel(
                    "metric",
                    "Metric family",
                    "select",
                    options=tuple(
                        FormOptionModel(metric.value, metric.value, selected=metric.value == metric_family)
                        for metric in PlotMetricFamily
                    ),
                ),
                FormFieldModel(
                    "display",
                    "Display mode",
                    "select",
                    options=(
                        FormOptionModel("overlay", "Overlay mode", selected=display_mode == "overlay"),
                        FormOptionModel("ratio", "Ratio mode", selected=display_mode == "ratio"),
                    ),
                ),
            ),
        )

    def _export_panel(self, session_id: str, run_id: str) -> PanelModel:
        base = f"/results/download?session_id={session_id}&run_id={run_id}"
        return PanelModel(
            "Export",
            notes=(
                f"Raw run data: {base}&asset=raw",
                f"Processed result data: {base}&asset=processed",
                f"Run metadata / settings snapshot: {base}&asset=metadata",
            ),
        )

    def _resolve_results_selection(
        self,
        session_id: str | None,
        run_id: str | None,
    ) -> tuple[SessionRecord, object] | None:
        if session_id and run_id:
            try:
                return self._store.load_session(session_id), self._store.load_run_record(session_id, run_id)
            except FileNotFoundError:
                return None
        if run_id:
            for session in self._store.list_sessions():
                try:
                    return session, self._store.load_run_record(session.session_id, run_id)
                except FileNotFoundError:
                    continue
        latest = self._store.latest_completed_run()
        return latest

    def _run_history(self) -> tuple[RunListItem, ...]:
        items: list[RunListItem] = []
        for session in self._store.list_sessions():
            for header in self._store.list_run_headers(session.session_id):
                try:
                    run = self._store.load_run_record(session.session_id, header.run_id)
                    status = run.completion_status.value
                    updated_at = run.updated_at
                except FileNotFoundError:
                    status = "draft"
                    updated_at = header.updated_at
                items.append(
                    RunListItem(
                        session_id=session.session_id,
                        run_id=header.run_id,
                        label=header.run_name,
                        status=status,
                        updated_at=updated_at,
                        open_enabled=self._session is not None and self._session.session_id == session.session_id,
                    )
                )
        return tuple(sorted(items, key=lambda item: item.updated_at, reverse=True))
