"""Phase 3A simulator-backed runtime wiring and app bootstrap."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from ircp_contracts import (
    PreflightReport,
    RunEventType,
    RunFailureReason,
    RunPhase,
    RunState,
    SessionManifest,
)
from ircp_data_pipeline import InMemorySessionStore, SessionCatalog, SessionOpenRequest, SessionReplayer
from ircp_experiment_engine import GoldenPathDriverBundle
from ircp_experiment_engine.runtime import GoldenPathPreflightValidator, InMemoryRunCoordinator
from ircp_simulators import Phase3AScenarioContext, Phase3ASimulatorCatalog
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
    UiRuntimeGateway,
    create_ui_app,
)
from ircp_ui_shell.page_state import blocked_state, empty_state, fault_state, unavailable_state


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Phase3ASimulatorRuntime(UiRuntimeGateway):
    """UI-facing adapter layer backed by simulator implementations only."""

    def __init__(
        self,
        *,
        scenario: Phase3AScenarioContext,
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
        self._preflight_validator = GoldenPathPreflightValidator()
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
            title="IR Control Platform Phase 3A",
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
        page_state = None if preflight.ready_to_start else blocked_state(
            "Setup blocked",
            "One or more preflight checks are blocking the MIRcat + HF2LI golden path.",
            details=tuple(
                issue.message
                for check in preflight.checks
                for issue in check.issues
                if issue.blocking
            ),
        )
        return SetupPageModel(
            title="Setup",
            subtitle="Recipe, readiness, and preflight scaffolding for the MIRcat sweep path.",
            state=page_state,
            recipe_title=self._scenario.recipe.title,
            preset_name=self._scenario.preset.name,
            section_header=SectionHeader(
                title="Device Readiness",
                subtitle="Normalized summaries from the typed adapter boundary.",
            ),
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
                    "The simulator runtime is ready, but no run has been started yet.",
                    details=("Use Start Nominal Run to materialize the state progression timeline.",),
                )
            else:
                state = blocked_state(
                    "Run blocked",
                    "The run scaffold stays blocked until Setup passes preflight.",
                    details=tuple(
                        issue.message
                        for check in preflight.checks
                        for issue in check.issues
                        if issue.blocking
                    ),
                )
            return RunPageModel(
                title="Run",
                subtitle="Run-state, event log, and live-data scaffolding.",
                state=state,
                section_header=SectionHeader(
                    title="Run Progression",
                    subtitle="No alternate paths. The timeline shows the one canonical run flow.",
                ),
                run_id=None,
                run_phase_label="Not started",
                session_id=None,
                event_log=(),
                live_data=(),
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
        return RunPageModel(
            title="Run",
            subtitle="Run-state, event log, and live-data scaffolding.",
            state=state,
            section_header=SectionHeader(
                title="Run Progression",
                subtitle="The UI reads authoritative run state instead of owning it.",
            ),
            run_id=timeline.run_id,
            run_phase_label=final_state.phase.value,
            session_id=final_state.session_id,
            event_log=await self.get_run_events(timeline.run_id),
            live_data=await self.get_live_data(timeline.run_id),
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
                raw_artifact_count=summary.raw_artifact_count,
                processed_artifact_count=summary.processed_artifact_count,
                analysis_artifact_count=summary.analysis_artifact_count,
                export_artifact_count=summary.export_artifact_count,
                selected=summary.session_id == selected_id,
            )
            for summary in sessions
        )

        page_state = None
        manifest_details: tuple[str, ...] = ()
        selected_session = next((card for card in session_cards if card.session_id == selected_id), None)
        if not session_cards:
            page_state = empty_state(
                "No saved sessions",
                "This simulator scenario has not persisted a session yet.",
                details=("Nominal scenarios seed one saved fixture and new runs create more.",),
            )
        elif selected_id is not None:
            manifest = await self.reopen_session(selected_id)
            manifest_details = (
                f"Session {manifest.session_id} status {manifest.status.value}",
                f"Recipe {manifest.recipe_snapshot.title}",
                f"Raw artifacts {len(manifest.raw_artifacts)}",
                f"Events {len(manifest.event_timeline)}",
                f"Processing outputs {len(manifest.processing_outputs)}",
                f"Analysis outputs {len(manifest.analysis_outputs)}",
                f"Export artifacts {len(manifest.export_artifacts)}",
            )

        return ResultsPageModel(
            title="Results",
            subtitle="Saved session summary and reopen scaffolding.",
            state=page_state,
            section_header=SectionHeader(
                title="Session Catalog",
                subtitle="Reopen uses the session boundary only. The UI does not own persistence.",
            ),
            sessions=session_cards,
            selected_session=selected_session,
            manifest_details=manifest_details,
        )

    async def get_service_page(self) -> ServicePageModel:
        return ServicePageModel(
            title="Service",
            subtitle="Expert-only scaffold. No raw passthrough controls in Phase 3A.",
            state=unavailable_state(
                "Service scaffold only",
                "Phase 3A exposes device summaries and explicit boundaries, not manual control surfaces.",
            ),
            section_header=SectionHeader(
                title="Connected Devices",
                subtitle="Read-only summaries for expert workflows that will land later.",
            ),
            device_cards=await self._device_cards(),
            notes=(
                "No vendor-native node editor or command console is exposed here.",
                "Recovery and calibration actions stay out of the default Setup and Run flow.",
                "Later phases can fill this page without restructuring the shell.",
            ),
        )

    async def run_preflight(self) -> PreflightReport:
        self._last_preflight = await self._preflight_validator.validate(
            self._scenario.recipe,
            self._scenario.preset,
            GoldenPathDriverBundle(
                mircat=self._scenario.bundle.mircat,
                hf2li=self._scenario.bundle.hf2li,
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

    async def get_live_data(self, run_id: str) -> tuple[LiveDataSeries, ...]:
        timeline = await self._run_monitor.get_run_timeline(run_id)
        grouped: dict[str, list[LiveDataPointModel]] = defaultdict(list)
        for point in timeline.live_data_points:
            grouped[point.stream_name].append(
                LiveDataPointModel(
                    wavenumber_cm1=point.wavenumber_cm1,
                    value=point.value,
                )
            )
        return tuple(
            LiveDataSeries(label=stream_name, units="V", points=tuple(points))
            for stream_name, points in grouped.items()
        )

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
        mircat_status = await self._scenario.bundle.mircat.get_status()
        hf2_status = await self._scenario.bundle.hf2li.get_status()
        return tuple(self._device_card_from_status(status) for status in (mircat_status, hf2_status))

    def _device_card_from_status(self, status) -> DeviceSummaryCard:
        details = [f"Device ID: {status.device_id}", f"Lifecycle: {status.lifecycle_state.value}"]
        details.extend(fault.message for fault in status.reported_faults)
        return DeviceSummaryCard(
            device_label=status.device_kind.value,
            status_label="Ready" if status.ready else ("Offline" if not status.connected else "Attention"),
            tone="good" if status.ready else ("bad" if not status.connected or status.reported_faults else "warn"),
            summary=status.status_summary,
            details=tuple(details),
        )

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


def create_phase3a_runtime_map() -> dict[str, Phase3ASimulatorRuntime]:
    catalog = Phase3ASimulatorCatalog()
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
    runtimes: dict[str, Phase3ASimulatorRuntime] = {}
    for context in contexts:
        session_store = InMemorySessionStore(initial_manifests=context.initial_manifests)
        coordinator = InMemoryRunCoordinator(
            drivers=GoldenPathDriverBundle(
                mircat=context.bundle.mircat,
                hf2li=context.bundle.hf2li,
            ),
            session_store=session_store,
            session_replayer=session_store,
            preflight_validator=GoldenPathPreflightValidator(),
            run_plan_factory=context.run_plan_factory,
        )
        runtimes[context.scenario_id] = Phase3ASimulatorRuntime(
            scenario=context,
            scenario_options=options,
            session_store=session_store,
            coordinator=coordinator,
            session_catalog=session_store,
            session_replayer=session_store,
        )
    return runtimes


def create_phase3a_simulator_app():
    return create_ui_app(create_phase3a_runtime_map(), default_scenario="nominal")


def run_phase3a_demo(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the dependency-light Phase 3A simulator shell."""

    from wsgiref.simple_server import make_server

    app = create_phase3a_simulator_app()
    with make_server(host, port, app) as server:
        server.serve_forever()
