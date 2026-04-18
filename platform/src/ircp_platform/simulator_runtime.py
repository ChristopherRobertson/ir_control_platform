"""Simulator-backed UI runtime gateway implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil

from ircp_contracts import (
    DeviceConfiguration,
    DeviceStatus,
    ExperimentRecipe,
    MircatEmissionMode,
    PreflightReport,
    RunFailureReason,
    RunPhase,
    RunState,
    SessionManifest,
)
from ircp_data_pipeline import SessionCatalog, SessionOpenRequest, SessionReplayer, SessionStore
from ircp_experiment_engine import SupportedV1DriverBundle
from ircp_experiment_engine.runtime import InMemoryRunCoordinator, SupportedV1PreflightValidator
from ircp_simulators import SimulatorScenarioContext
from ircp_ui_shell import (
    AnalyzePageModel,
    AdvancedPageModel,
    DeviceSummaryCard,
    HeaderStatus,
    OperatePageModel,
    ResultsDownload,
    ResultsPageModel,
    ServicePageModel,
    UiRuntimeGateway,
)

from .operator_state import (
    ExperimentType,
    FIXED_WAVELENGTH_EXPERIMENT_TYPE,
    OperatorDraftState,
    WAVELENGTH_SCAN_EXPERIMENT_TYPE,
    apply_manifest_to_draft,
    build_mircat_configuration,
    build_recipe,
    build_session_notes,
    create_operator_draft,
    normalize_hf2_dio_selection,
    normalize_ndyag_repetition_rate_hz,
    normalize_ndyag_shot_count,
    normalize_experiment_type,
    normalize_pulse_parameters,
    normalize_scan_speed,
    normalize_wavenumber_cm1,
)
from .page_builders import (
    build_advanced_page,
    build_analyze_page,
    build_header_status,
    build_operate_page,
    build_results_page,
    build_service_page,
    device_card_from_status,
)
from .runtime_helpers import json_bytes, json_lines_bytes


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _results_session_matches(summary, *, search: str, status_filter: str) -> bool:
    if status_filter != "all" and summary.status.value != status_filter:
        return False
    normalized_search = search.strip().casefold()
    if not normalized_search:
        return True
    return normalized_search in summary.session_id.casefold() or normalized_search in summary.recipe_title.casefold()


def _results_sort_key(summary, sort_order: str) -> tuple[object, ...]:
    total_artifacts = (
        summary.primary_raw_artifact_count
        + summary.secondary_monitor_artifact_count
        + summary.processed_artifact_count
        + summary.analysis_artifact_count
        + summary.export_artifact_count
    )
    if sort_order == "updated_asc":
        return (summary.updated_at, summary.created_at, summary.session_id)
    if sort_order == "artifacts_desc":
        return (-total_artifacts, -summary.updated_at.timestamp(), summary.session_id)
    return (-summary.updated_at.timestamp(), -summary.created_at.timestamp(), summary.session_id)


class SimulatorUiRuntime(UiRuntimeGateway):
    """UI-facing adapter layer backed by deterministic supported-v1 simulators."""

    def __init__(
        self,
        *,
        scenario: SimulatorScenarioContext,
        coordinator: InMemoryRunCoordinator,
        session_store: SessionStore,
        session_catalog: SessionCatalog,
        session_replayer: SessionReplayer,
        storage_root: Path,
    ) -> None:
        self._scenario = scenario
        self._coordinator = coordinator
        self._session_store = session_store
        self._session_catalog = session_catalog
        self._session_replayer = session_replayer
        self._preflight_validator = SupportedV1PreflightValidator()
        self._storage_root = storage_root.resolve()
        self._last_preflight: PreflightReport | None = None
        self._draft = create_operator_draft(scenario)
        self._active_run_id: str | None = None
        self._draft_session_id: str | None = None
        self._selected_session_id: str | None = None
        self._preflight_dirty = True
        if scenario.initial_manifests:
            latest_manifest = max(scenario.initial_manifests, key=lambda manifest: manifest.updated_at)
            self._selected_session_id = latest_manifest.session_id
            apply_manifest_to_draft(self._draft, latest_manifest, scenario)

    async def get_header_status(self, active_route: str) -> HeaderStatus:
        preflight = await self._ensure_preflight()
        run_phase_label = await self._current_run_phase_label()
        current_session_id = self._draft_session_id or self._selected_session_id or "none"
        ready_to_start = preflight.ready_to_start and self._start_experiment_supported()
        return build_header_status(
            active_route=active_route,
            draft=self._draft,
            current_session_id=current_session_id,
            run_phase_label=run_phase_label,
            ready_to_start=ready_to_start,
        )

    async def get_operate_page(self) -> OperatePageModel:
        preflight = await self._ensure_preflight()
        latest_state = await self._latest_run_state()
        sessions = await self._session_catalog.list_sessions()
        laser_status = await self._scenario.bundle.mircat.get_status()
        hf2_status = await self._scenario.bundle.hf2li.get_status()
        return build_operate_page(
            draft=self._draft,
            preflight=preflight,
            latest_state=latest_state,
            sessions=sessions,
            laser_status=laser_status,
            hf2_status=hf2_status,
            draft_session_id=self._draft_session_id,
            selected_session_id=self._selected_session_id,
        )

    async def get_advanced_page(self) -> AdvancedPageModel:
        preflight = await self._ensure_preflight()
        return build_advanced_page(
            draft=self._draft,
            scenario=self._scenario,
            preflight=preflight,
        )

    async def get_results_page(
        self,
        selected_session_id: str | None = None,
        *,
        search: str = "",
        status_filter: str = "all",
        sort_order: str = "updated_desc",
    ) -> ResultsPageModel:
        sessions = await self._session_catalog.list_sessions()
        filtered_sessions = tuple(
            sorted(
                (
                    summary
                    for summary in sessions
                    if _results_session_matches(summary, search=search, status_filter=status_filter)
                ),
                key=lambda summary: _results_sort_key(summary, sort_order),
            )
        )
        all_session_ids = {summary.session_id for summary in sessions}
        visible_session_ids = {summary.session_id for summary in filtered_sessions}
        selection_cleared = selected_session_id == "__none__"
        invalid_selected_session_id: str | None = None
        selection_hidden_by_filter = False
        selected_id: str | None = None

        if selection_cleared:
            selected_id = None
        elif selected_session_id is not None:
            if selected_session_id in visible_session_ids:
                selected_id = selected_session_id
            elif selected_session_id in all_session_ids:
                selection_hidden_by_filter = True
            else:
                invalid_selected_session_id = selected_session_id
        elif self._selected_session_id in visible_session_ids:
            selected_id = self._selected_session_id
        elif filtered_sessions:
            selected_id = filtered_sessions[0].session_id

        if selected_id is not None:
            self._selected_session_id = selected_id
        detail = (
            await self._session_catalog.get_session_detail(selected_id)
            if selected_id is not None and selected_id in visible_session_ids
            else None
        )
        return build_results_page(
            draft=self._draft,
            storage_root=self._storage_root,
            sessions=filtered_sessions,
            total_session_count=len(sessions),
            selected_session_id=selected_id,
            detail=detail,
            search_value=search.strip(),
            status_filter=status_filter,
            sort_order=sort_order,
            invalid_selected_session_id=invalid_selected_session_id,
            selection_hidden_by_filter=selection_hidden_by_filter,
            selection_cleared=selection_cleared,
        )

    async def get_results_download(
        self,
        session_id: str,
        *,
        asset: str | None = None,
        artifact_id: str | None = None,
    ) -> ResultsDownload:
        detail = await self._session_catalog.get_session_detail(session_id)
        if artifact_id is not None:
            artifact = next(
                (
                    candidate
                    for candidate in (
                        *detail.primary_raw_artifacts,
                        *detail.secondary_monitor_artifacts,
                        *detail.processed_artifacts,
                        *detail.analysis_artifacts,
                        *detail.export_artifacts,
                    )
                    if candidate.artifact_id == artifact_id
                ),
                None,
            )
            if artifact is None:
                raise KeyError(f"Unknown artifact id for session {session_id}: {artifact_id}")
            payload_path = self._resolve_results_path(artifact.relative_path)
            if not payload_path.is_file():
                raise FileNotFoundError(
                    f"Artifact payload is not available for download: {artifact.relative_path}"
                )
            return ResultsDownload(
                filename=payload_path.name,
                content_type=artifact.content_type or "application/octet-stream",
                body=payload_path.read_bytes(),
            )

        asset_name = asset or "manifest"
        if asset_name == "manifest":
            return ResultsDownload(
                filename=f"{session_id}-manifest.json",
                content_type="application/json; charset=utf-8",
                body=json_bytes(detail.manifest),
            )
        if asset_name == "events":
            return ResultsDownload(
                filename=f"{session_id}-events.ndjson",
                content_type="application/x-ndjson; charset=utf-8",
                body=json_lines_bytes(detail.event_timeline),
            )
        raise ValueError(f"Unknown results download asset: {asset_name}")

    async def get_analyze_page(self, selected_session_id: str | None = None) -> AnalyzePageModel:
        sessions = await self._session_catalog.list_sessions()
        selected_id = selected_session_id or self._selected_session_id or (sessions[0].session_id if sessions else None)
        if selected_id is not None:
            self._selected_session_id = selected_id
        detail = await self._session_catalog.get_session_detail(selected_id) if selected_id is not None else None
        return build_analyze_page(
            draft=self._draft,
            sessions=sessions,
            selected_session_id=selected_id,
            detail=detail,
        )

    async def get_service_page(self) -> ServicePageModel:
        sessions = await self._session_catalog.list_sessions()
        return build_service_page(
            draft=self._draft,
            storage_root=self._storage_root,
            session_count=len(sessions),
            device_cards=await self._device_cards(),
        )

    async def set_experiment_type(self, experiment_type: str) -> ExperimentType:
        normalized = normalize_experiment_type(experiment_type)
        if normalized == self._draft.experiment_type:
            return normalized
        self._draft.experiment_type = normalized
        self._mark_preflight_dirty()
        return normalized

    async def configure_operating_mode(
        self,
        *,
        experiment_type: str,
        emission_mode: str,
        tune_target_cm1: float | None = None,
        scan_start_cm1: float | None = None,
        scan_stop_cm1: float | None = None,
        scan_step_size_cm1: float | None = None,
        scan_dwell_time_ms: float | None = None,
        pulse_repetition_rate_hz: float | None = None,
        pulse_width_ns: float | None = None,
        pulse_duty_cycle_percent: float | None = None,
    ) -> None:
        self._draft.experiment_type = normalize_experiment_type(experiment_type)
        self._draft.emission_mode = (
            MircatEmissionMode.PULSED if emission_mode == MircatEmissionMode.PULSED.value else MircatEmissionMode.CW
        )
        if tune_target_cm1 is not None:
            self._draft.tune_target_cm1 = normalize_wavenumber_cm1(tune_target_cm1)
        if scan_start_cm1 is not None:
            self._draft.scan_start_cm1 = normalize_wavenumber_cm1(scan_start_cm1)
        if scan_stop_cm1 is not None:
            self._draft.scan_stop_cm1 = normalize_wavenumber_cm1(scan_stop_cm1)
        if scan_step_size_cm1 is not None:
            self._draft.scan_step_size_cm1 = normalize_scan_speed(scan_step_size_cm1)
        if scan_dwell_time_ms is not None:
            self._draft.scan_dwell_time_ms = scan_dwell_time_ms
        if pulse_repetition_rate_hz is not None:
            self._draft.pulse_repetition_rate_hz = pulse_repetition_rate_hz
        if pulse_width_ns is not None:
            self._draft.pulse_width_ns = pulse_width_ns
        (
            self._draft.pulse_repetition_rate_hz,
            self._draft.pulse_width_ns,
            self._draft.pulse_duty_cycle_percent,
        ) = normalize_pulse_parameters(
            self._draft.pulse_repetition_rate_hz,
            self._draft.pulse_width_ns,
        )
        self._mark_preflight_dirty()

    async def configure_hf2(
        self,
        *,
        sample_rate_hz: float | None = None,
        harmonic: int | None = None,
        time_constant_seconds: float | None = None,
        extref: str | None = None,
        trigger: str | None = None,
    ) -> None:
        if sample_rate_hz is not None:
            self._draft.hf2_sample_rate_hz = sample_rate_hz
        if harmonic is not None:
            self._draft.hf2_harmonic = harmonic
        if time_constant_seconds is not None:
            self._draft.hf2_time_constant_seconds = time_constant_seconds
        if extref is not None:
            self._draft.hf2_extref = normalize_hf2_dio_selection(extref)
        if trigger is not None:
            self._draft.hf2_trigger = normalize_hf2_dio_selection(trigger)
        self._mark_preflight_dirty()

    async def configure_ndyag(
        self,
        *,
        repetition_rate_hz: float | None = None,
        shot_count: int | None = None,
        continuous: bool,
    ) -> None:
        if repetition_rate_hz is not None:
            self._draft.ndyag_repetition_rate_hz = normalize_ndyag_repetition_rate_hz(repetition_rate_hz)
        if continuous:
            self._draft.ndyag_shot_count = 1
        elif shot_count is not None:
            self._draft.ndyag_shot_count = normalize_ndyag_shot_count(shot_count)
        self._draft.ndyag_continuous = continuous
        self._mark_preflight_dirty()

    async def set_ndyag_enabled(self, enabled: bool) -> None:
        self._draft.ndyag_enabled = enabled
        if enabled and self._draft.ndyag_continuous:
            self._draft.ndyag_shot_count = 1
        self._mark_preflight_dirty()

    async def save_session(
        self,
        session_id: str,
        session_label: str,
        sample_id: str,
        operator_notes: str,
    ) -> SessionManifest:
        session_id_value = session_id.strip()
        session_label_value = session_label.strip()
        sample_id_value = sample_id.strip()
        if session_id_value:
            self._draft.session_id_input = session_id_value
        if session_label_value:
            self._draft.session_label = session_label_value
        if sample_id_value:
            self._draft.sample_id = sample_id_value
        self._draft.operator_notes = operator_notes.strip()
        manifest = await self._coordinator.create_session(
            self._current_recipe(),
            self._scenario.preset,
            session_id=self._draft.session_id_input,
            notes=build_session_notes(self._draft, self._scenario),
        )
        self._draft.session_id_input = manifest.session_id
        self._draft_session_id = manifest.session_id
        self._selected_session_id = manifest.session_id
        self._mark_preflight_dirty()
        return manifest

    async def delete_saved_session(self, session_id: str) -> None:
        await self._session_store.delete_session(session_id)
        session_dir = self._storage_root / "sessions" / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
        if self._draft_session_id == session_id:
            self._draft_session_id = None
        if self._selected_session_id == session_id:
            sessions = await self._session_catalog.list_sessions()
            self._selected_session_id = sessions[0].session_id if sessions else None
        self._mark_preflight_dirty()

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
        apply_manifest_to_draft(self._draft, result.manifest, self._scenario)
        return result.manifest

    async def connect_laser(self) -> DeviceStatus:
        status = await self._scenario.bundle.mircat.connect()
        self._mark_preflight_dirty()
        return status

    async def disconnect_laser(self) -> DeviceStatus:
        status = await self._scenario.bundle.mircat.disconnect()
        self._mark_preflight_dirty()
        return status

    async def arm_laser(self) -> DeviceStatus:
        status = await self._scenario.bundle.mircat.arm()
        self._mark_preflight_dirty()
        return status

    async def disarm_laser(self) -> DeviceStatus:
        status = await self._scenario.bundle.mircat.disarm()
        self._mark_preflight_dirty()
        return status

    async def set_laser_emission(self, enabled: bool) -> DeviceStatus:
        status = await self._scenario.bundle.mircat.set_emission_enabled(enabled)
        self._mark_preflight_dirty()
        return status

    async def tune_laser(self, target_wavenumber_cm1: float) -> DeviceConfiguration:
        self._draft.experiment_type = FIXED_WAVELENGTH_EXPERIMENT_TYPE
        self._draft.tune_target_cm1 = normalize_wavenumber_cm1(target_wavenumber_cm1)
        snapshot = await self._scenario.bundle.mircat.apply_configuration(
            build_mircat_configuration(self._draft, self._scenario)
        )
        self._mark_preflight_dirty()
        return snapshot

    async def start_scan(
        self,
        *,
        start_wavenumber_cm1: float,
        end_wavenumber_cm1: float,
        step_size_cm1: float,
        dwell_time_ms: float | None = None,
    ) -> DeviceStatus:
        self._draft.experiment_type = WAVELENGTH_SCAN_EXPERIMENT_TYPE
        self._draft.scan_start_cm1 = normalize_wavenumber_cm1(start_wavenumber_cm1)
        self._draft.scan_stop_cm1 = normalize_wavenumber_cm1(end_wavenumber_cm1)
        self._draft.scan_step_size_cm1 = normalize_scan_speed(step_size_cm1)
        if dwell_time_ms is not None:
            self._draft.scan_dwell_time_ms = dwell_time_ms
        status = await self._scenario.bundle.mircat.start_recipe(
            build_mircat_configuration(self._draft, self._scenario),
            self._scenario.recipe.probe_timing_mode,
        )
        self._mark_preflight_dirty()
        return status

    async def stop_scan(self) -> DeviceStatus:
        status = await self._scenario.bundle.mircat.stop_recipe()
        self._mark_preflight_dirty()
        return status

    async def connect_hf2(self) -> DeviceStatus:
        status = await self._scenario.bundle.hf2li.connect()
        self._mark_preflight_dirty()
        return status

    async def disconnect_hf2(self) -> DeviceStatus:
        status = await self._scenario.bundle.hf2li.disconnect()
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
        return self._last_preflight

    async def start_run(self) -> RunState:
        preflight = await self._ensure_preflight()
        if not preflight.ready_to_start:
            raise ValueError("Preflight is blocked.")
        if not self._start_experiment_supported():
            raise ValueError("Scan Start Experiment orchestration is not yet wired in this pass.")
        session_id = self._draft_session_id
        if session_id is None:
            manifest = await self.save_session(
                self._draft.session_id_input,
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
        self._mark_preflight_dirty()
        return run_state

    async def abort_active_run(self) -> RunState | None:
        if self._active_run_id is None:
            return None
        current = await self._coordinator.get_run_state(self._active_run_id)
        if current.phase in {RunPhase.COMPLETED, RunPhase.FAULTED, RunPhase.ABORTED}:
            return None
        aborted = await self._coordinator.abort_run(
            self._active_run_id,
            RunFailureReason.OPERATOR_ABORT,
        )
        self._mark_preflight_dirty()
        return aborted

    async def reopen_session(self, session_id: str) -> SessionManifest:
        return await self.open_saved_session(session_id)

    def _resolve_results_path(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ValueError(f"Artifact paths must stay relative to the runtime root: {relative_path}")
        resolved = (self._storage_root / candidate).resolve()
        try:
            resolved.relative_to(self._storage_root)
        except ValueError as exc:
            raise ValueError(f"Artifact path escapes the runtime root: {relative_path}") from exc
        return resolved

    def _current_recipe(self) -> ExperimentRecipe:
        return build_recipe(self._draft, self._scenario)

    def _start_experiment_supported(self) -> bool:
        return self._draft.experiment_type == FIXED_WAVELENGTH_EXPERIMENT_TYPE

    def _mark_preflight_dirty(self) -> None:
        self._preflight_dirty = True

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

    async def _device_cards(self) -> tuple[DeviceSummaryCard, ...]:
        statuses = (
            await self._scenario.bundle.mircat.get_status(),
            await self._scenario.bundle.hf2li.get_status(),
            await self._scenario.bundle.t660_master.get_status(),
            await self._scenario.bundle.t660_slave.get_status(),
            await self._scenario.bundle.mux.get_status(),
            await self._scenario.bundle.picoscope.get_status(),
        )
        return tuple(device_card_from_status(status) for status in statuses)
