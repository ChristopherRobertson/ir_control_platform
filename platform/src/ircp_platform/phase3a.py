"""Phase 3B simulator-backed runtime wiring and app bootstrap."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from ircp_contracts import (
    ArtifactSourceRole,
    PreflightReport,
    RunEventType,
    RunFailureReason,
    RunPhase,
    RunState,
    SessionManifest,
    SessionStatus,
)
from ircp_data_pipeline import (
    InMemorySessionStore,
    SessionCatalog,
    SessionDetail,
    SessionOpenRequest,
    SessionReplayer,
)
from ircp_experiment_engine import SupportedV1DriverBundle
from ircp_experiment_engine.runtime import SupportedV1PreflightValidator, InMemoryRunCoordinator
from ircp_simulators import Phase3BScenarioContext, SupportedV1SimulatorCatalog
from ircp_ui_shell import (
    DeviceSummaryCard,
    EventLogItem,
    HeaderStatus,
    LiveDataPointModel,
    LiveDataSeries,
    NavigationItem,
    PageStateModel,
    ReadinessRow,
    ResultsPageModel,
    RunPageModel,
    RunStepSummary,
    ScenarioOption,
    SectionHeader,
    ServicePageModel,
    SessionSummaryCard,
    SetupPageModel,
    StatusBadge,
    SummaryPanel,
    UiRuntimeGateway,
    create_ui_app,
)
from ircp_ui_shell.page_state import blocked_state, empty_state, fault_state, unavailable_state, warning_state


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Phase3BSimulatorRuntime(UiRuntimeGateway):
    """UI-facing adapter layer backed by supported-v1 simulator implementations only."""

    def __init__(
        self,
        *,
        scenario: Phase3BScenarioContext,
        scenario_options: tuple[ScenarioOption, ...],
        session_store: InMemorySessionStore,
        coordinator: InMemoryRunCoordinator,
        session_catalog: SessionCatalog,
        session_replayer: SessionReplayer,
    ) -> None:
        self._scenario = scenario
        self._scenario_options = scenario_options
        self._session_store = session_store
        self._run_monitor = coordinator
        self._session_catalog = session_catalog
        self._session_replayer = session_replayer
        self._preflight_validator = SupportedV1PreflightValidator()
        self._coordinator = coordinator
        self._last_preflight: PreflightReport | None = None
        self._active_run_id: str | None = None
        self._selected_session_id: str | None = None

    async def get_header_status(self, active_route: str) -> HeaderStatus:
        sessions = await self._session_catalog.list_sessions()
        preflight = await self._ensure_preflight()
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
                label=f"Run {await self._current_run_phase_label()}",
                tone="warn" if self._active_run_id else "neutral",
            ),
        )
        return HeaderStatus(
            title="IR Control Platform Phase 3B",
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
                    label="Setup",
                    href=f"/setup?scenario={self._scenario.scenario_id}",
                    active=active_route == "setup",
                ),
                NavigationItem(
                    label="Run",
                    href=f"/run?scenario={self._scenario.scenario_id}",
                    active=active_route == "run",
                ),
                NavigationItem(
                    label="Results",
                    href=f"/results?scenario={self._scenario.scenario_id}",
                    active=active_route == "results",
                ),
                NavigationItem(
                    label="Service",
                    href=f"/service?scenario={self._scenario.scenario_id}",
                    active=active_route == "service",
                ),
            ),
            badges=badges,
            summary=self._scenario.description,
        )

    async def get_setup_page(self) -> SetupPageModel:
        preflight = await self._ensure_preflight()
        warning_messages = tuple(
            issue.message
            for check in preflight.checks
            for issue in check.issues
            if not issue.blocking
        )
        blocking_messages = tuple(
            issue.message
            for check in preflight.checks
            for issue in check.issues
            if issue.blocking
        )
        page_state: PageStateModel | None = None
        if blocking_messages:
            page_state = blocked_state(
                "Setup blocked",
                "One or more required checks are blocking the supported-v1 run.",
                details=blocking_messages,
            )
        elif warning_messages:
            page_state = warning_state(
                "Setup warning",
                "The supported-v1 run can proceed, but optional monitoring is degraded.",
                details=warning_messages,
            )
        return SetupPageModel(
            title="Setup",
            subtitle="Experiment-first review of the supported-v1 recipe, readiness, timing, and routing state.",
            state=page_state,
            recipe_title=self._scenario.recipe.title,
            preset_name=self._scenario.preset.name,
            section_header=SectionHeader(
                title="Device Readiness",
                subtitle="Normalized summaries from the typed adapter boundary.",
            ),
            summary_panels=self._summary_panels_from_preflight(preflight),
            device_cards=await self._device_cards(),
            readiness_rows=tuple(
                ReadinessRow(
                    label=check.target,
                    state=check.state.value,
                    summary=check.summary,
                    details=tuple(issue.message for issue in check.issues),
                )
                for check in preflight.checks
            ),
            preflight_report=preflight,
        )

    async def get_run_page(self) -> RunPageModel:
        if self._active_run_id is None:
            preflight = await self._ensure_preflight()
            state: PageStateModel | None
            if preflight.ready_to_start:
                state = unavailable_state(
                    "Run not started",
                    "The supported-v1 runtime is ready, but no run has been started yet.",
                    details=("Use Start Supported V1 Run to materialize the run timeline.",),
                )
            else:
                state = blocked_state(
                    "Run blocked",
                    "The run scaffold remains blocked until Setup passes preflight.",
                    details=tuple(
                        issue.message
                        for check in preflight.checks
                        for issue in check.issues
                        if issue.blocking
                    ),
                )
            return RunPageModel(
                title="Run",
                subtitle="Authoritative run state, event log, timing summary, and live data shells.",
                state=state,
                section_header=SectionHeader(
                    title="Run Progression",
                    subtitle="The timeline shows the one canonical coordinated run flow.",
                ),
                run_id=None,
                run_phase_label="Not started",
                session_id=None,
                summary_panels=self._summary_panels_from_preflight(preflight),
                event_log=(),
                primary_live_data=(),
                secondary_live_data=(),
                run_steps=(),
            )

        timeline = await self._run_monitor.get_run_timeline(self._active_run_id)
        final_state = timeline.states[-1]
        state = None
        if final_state.phase == RunPhase.FAULTED:
            state = fault_state(
                "Run faulted",
                "The simulator surfaced an explicit device fault on the canonical path.",
                details=(final_state.latest_fault.message,) if final_state.latest_fault else (),
            )
        primary_live_data, secondary_live_data = await self.get_live_data(timeline.run_id)
        return RunPageModel(
            title="Run",
            subtitle="Authoritative run state, event log, timing summary, and live data shells.",
            state=state,
            section_header=SectionHeader(
                title="Run Progression",
                subtitle="The UI reads authoritative run state instead of owning it.",
            ),
            run_id=timeline.run_id,
            run_phase_label=final_state.phase.value,
            session_id=final_state.session_id,
            summary_panels=self._summary_panels_from_run_state(final_state),
            event_log=await self.get_run_events(timeline.run_id),
            primary_live_data=primary_live_data,
            secondary_live_data=secondary_live_data,
            run_steps=await self.get_run_steps(timeline.run_id),
        )

    async def get_results_page(self, selected_session_id: str | None = None) -> ResultsPageModel:
        sessions = await self._session_catalog.list_sessions()
        selected_id = selected_session_id or self._selected_session_id or (sessions[0].session_id if sessions else None)
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
            subtitle="Saved session summaries with persisted outcome, timing, artifact, and event context.",
            state=page_state,
            section_header=SectionHeader(
                title="Session Catalog",
                subtitle="Reopen uses the session boundary only. The UI does not own persistence.",
            ),
            sessions=session_cards,
            selected_session=selected_session,
            detail_panels=detail_panels,
            artifact_panels=artifact_panels,
            event_log=event_log,
        )

    async def get_service_page(self) -> ServicePageModel:
        return ServicePageModel(
            title="Service",
            subtitle="Expert-only scaffold. No raw vendor passthrough controls in Phase 3B.",
            state=unavailable_state(
                "Service scaffold only",
                "Phase 3B exposes read-only diagnostics and summaries, not manual vendor consoles.",
            ),
            section_header=SectionHeader(
                title="Connected Devices",
                subtitle="Read-only summaries for expert workflows that land later.",
            ),
            device_cards=await self._device_cards(),
            notes=(
                "Nd:YAG timing stays modeled through T660-2 timing semantics, not a separate console.",
                "The MUX remains a route selector rather than a manual combiner surface.",
                "Recovery and calibration actions stay out of the default Setup and Run flow.",
            ),
            diagnostic_panels=(
                SummaryPanel(
                    title="Timing Roles",
                    subtitle="Supported-v1 installed timing identities.",
                    items=(
                        "T660-2: master timing source and Nd:YAG fire/Q-switch owner",
                        "T660-1: slave timing source for MIRcat trigger/process/enable outputs",
                    ),
                ),
            ),
        )

    async def run_preflight(self) -> PreflightReport:
        self._last_preflight = await self._preflight_validator.validate(
            self._scenario.recipe,
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
        return self._last_preflight

    async def start_run(self) -> RunState:
        preflight = await self._ensure_preflight()
        if not preflight.ready_to_start:
            raise ValueError("Preflight is blocked.")
        manifest = await self._coordinator.create_session(self._scenario.recipe, self._scenario.preset)
        self._selected_session_id = manifest.session_id
        run_state = await self._coordinator.start_run(
            self._scenario.recipe,
            self._scenario.preset,
            manifest.session_id,
        )
        self._active_run_id = run_state.run_id
        return run_state

    async def abort_active_run(self) -> RunState | None:
        if self._active_run_id is None:
            return None
        current = await self._coordinator.get_run_state(self._active_run_id)
        if current.phase in {RunPhase.COMPLETED, RunPhase.FAULTED, RunPhase.ABORTED}:
            return None
        return await self._coordinator.abort_run(self._active_run_id, RunFailureReason.OPERATOR_ABORT)

    async def reopen_session(self, session_id: str) -> SessionManifest:
        result = await self._session_replayer.open_session(
            SessionOpenRequest(
                session_id=session_id,
                requested_at=_utc_now(),
                reopen_for_replay=True,
            )
        )
        self._selected_session_id = result.manifest.session_id
        return result.manifest

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
        if self._last_preflight is None:
            self._last_preflight = await self.run_preflight()
        return self._last_preflight

    async def _current_run_phase_label(self) -> str:
        if self._active_run_id is None:
            return "Not started"
        state = await self._coordinator.get_run_state(self._active_run_id)
        return state.phase.value.title()


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


def create_phase3b_runtime_map() -> dict[str, Phase3BSimulatorRuntime]:
    catalog = SupportedV1SimulatorCatalog()
    contexts = catalog.list_contexts()
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
        session_store = InMemorySessionStore(initial_manifests=context.initial_manifests)
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
        )
    return runtimes


def create_phase3b_simulator_app():
    return create_ui_app(create_phase3b_runtime_map(), default_scenario="nominal")


def run_phase3b_demo(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the dependency-light Phase 3B simulator shell."""

    from wsgiref.simple_server import make_server

    app = create_phase3b_simulator_app()
    with make_server(host, port, app) as server:
        server.serve_forever()
