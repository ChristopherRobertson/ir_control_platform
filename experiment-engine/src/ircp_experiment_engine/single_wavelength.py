"""Single-path coordinator for the generic single-wavelength pump-probe v1 workflow."""

from __future__ import annotations

from dataclasses import replace
import math

from ircp_contracts import (
    ArtifactManifest,
    EXPERIMENT_ID,
    LockInSettings,
    PlotMetricFamily,
    ProbeSettings,
    PumpSettings,
    RawRunRecord,
    RawSignalRecord,
    RunHeader,
    RunLifecycleState,
    RunRecord,
    RunSettingsSnapshot,
    SessionRecord,
    SetupState,
    TimescaleRegime,
    derive_acquisition_window_plan,
    utc_now,
    validate_setup_state,
)
from ircp_data_pipeline import SingleWavelengthRunStore
from ircp_processing import build_processed_run_record


class SingleWavelengthPumpProbeCoordinator:
    """Owns setup validation, run lifecycle, snapshot freeze, and simulator acquisition."""

    def __init__(
        self,
        store: SingleWavelengthRunStore,
        *,
        fault_on_start: bool = False,
    ) -> None:
        self._store = store
        self._fault_on_start = fault_on_start
        self._active_run: tuple[str, str] | None = None

    def build_setup_state(
        self,
        *,
        session_saved: bool,
        run_header_saved: bool,
        pump: PumpSettings | None,
        timescale: TimescaleRegime | None,
        probe: ProbeSettings | None,
        lockin: LockInSettings | None,
    ) -> SetupState:
        plan = (
            derive_acquisition_window_plan(timescale, lockin.transfer_rate_hz)
            if timescale is not None and lockin is not None
            else None
        )
        return validate_setup_state(
            SetupState(
                session_saved=session_saved,
                run_header_saved=run_header_saved,
                pump=pump,
                timescale=timescale,
                probe=probe,
                lockin=lockin,
                acquisition_plan=plan,
            )
        )

    def start_run(
        self,
        *,
        session: SessionRecord,
        run_header: RunHeader,
        setup: SetupState,
    ) -> RunRecord:
        setup = validate_setup_state(setup)
        if not setup.can_run:
            messages = "; ".join(issue.message for issue in setup.validation_issues if issue.blocking)
            raise ValueError(messages or "Run setup is not valid.")
        assert setup.pump is not None
        assert setup.probe is not None
        assert setup.lockin is not None
        assert setup.timescale is not None
        assert setup.acquisition_plan is not None

        snapshot = RunSettingsSnapshot(
            snapshot_id=f"{run_header.run_id}-settings-snapshot",
            session_id=session.session_id,
            run_id=run_header.run_id,
            experiment_type=EXPERIMENT_ID,
            frozen_at=utc_now(),
            timescale=setup.timescale,
            pump=setup.pump,
            probe=setup.probe,
            lockin=setup.lockin,
            acquisition_plan=setup.acquisition_plan,
        )
        self._store.save_settings_snapshot(snapshot)

        started_at = utc_now()
        running = RunRecord(
            run_id=run_header.run_id,
            session_id=session.session_id,
            run_name=run_header.run_name,
            run_notes=run_header.run_notes,
            settings_snapshot=snapshot,
            raw_record_id=None,
            processed_record_id=None,
            started_at=started_at,
            ended_at=None,
            completion_status=RunLifecycleState.RUNNING,
            created_at=run_header.created_at,
            updated_at=started_at,
        )
        self._store.save_run_record(running)
        self._active_run = (session.session_id, run_header.run_id)

        if self._fault_on_start or setup.pump.fault or setup.probe.fault or setup.lockin.fault:
            return self._fault_run(running, snapshot, "Simulated HF2LI overload fault during acquisition.")

        raw = RawRunRecord(
            raw_record_id=f"{run_header.run_id}-raw",
            session_id=session.session_id,
            run_id=run_header.run_id,
            settings_snapshot_id=snapshot.snapshot_id,
            signals=self._generate_raw_signals(snapshot),
            created_at=utc_now(),
        )
        self._store.save_raw_run_record(raw)
        processed = build_processed_run_record(raw, PlotMetricFamily.R)
        self._store.save_processed_run_record(processed)
        manifest = self._artifact_manifest(
            session=session,
            run_id=run_header.run_id,
            snapshot=snapshot,
            raw_record_id=raw.raw_record_id,
            processed_record_id=processed.processed_record_id,
        )
        self._store.save_artifact_manifest(manifest)
        ended_at = utc_now()
        completed = replace(
            running,
            raw_record_id=raw.raw_record_id,
            processed_record_id=processed.processed_record_id,
            ended_at=ended_at,
            completion_status=RunLifecycleState.COMPLETED,
            updated_at=ended_at,
        )
        self._active_run = None
        return self._store.save_run_record(completed)

    def stop_run(self, session_id: str, run_id: str) -> RunRecord:
        record = self._store.load_run_record(session_id, run_id)
        if record.completion_status != RunLifecycleState.RUNNING:
            return record
        stopped = replace(
            record,
            completion_status=RunLifecycleState.STOPPED,
            ended_at=utc_now(),
            updated_at=utc_now(),
        )
        self._active_run = None
        return self._store.save_run_record(stopped)

    def abort_run(self, session_id: str, run_id: str, reason: str) -> RunRecord:
        record = self._store.load_run_record(session_id, run_id)
        if record.completion_status in {
            RunLifecycleState.COMPLETED,
            RunLifecycleState.FAULTED,
            RunLifecycleState.ABORTED,
            RunLifecycleState.STOPPED,
        }:
            return record
        aborted = replace(
            record,
            completion_status=RunLifecycleState.ABORTED,
            ended_at=utc_now(),
            fault_error_state=reason,
            updated_at=utc_now(),
        )
        self._active_run = None
        return self._store.save_run_record(aborted)

    def _fault_run(
        self,
        running: RunRecord,
        snapshot: RunSettingsSnapshot,
        fault: str,
    ) -> RunRecord:
        raw = RawRunRecord(
            raw_record_id=f"{running.run_id}-raw-partial",
            session_id=running.session_id,
            run_id=running.run_id,
            settings_snapshot_id=snapshot.snapshot_id,
            signals=self._generate_raw_signals(snapshot, count=12),
            created_at=utc_now(),
        )
        self._store.save_raw_run_record(raw)
        manifest = self._artifact_manifest(
            session=self._store.load_session(running.session_id),
            run_id=running.run_id,
            snapshot=snapshot,
            raw_record_id=raw.raw_record_id,
            processed_record_id=None,
        )
        self._store.save_artifact_manifest(manifest)
        faulted = replace(
            running,
            raw_record_id=raw.raw_record_id,
            ended_at=utc_now(),
            completion_status=RunLifecycleState.FAULTED,
            fault_error_state=fault,
            updated_at=utc_now(),
        )
        self._active_run = None
        return self._store.save_run_record(faulted)

    def _generate_raw_signals(
        self,
        snapshot: RunSettingsSnapshot,
        *,
        count: int | None = None,
    ) -> tuple[RawSignalRecord, ...]:
        plan = snapshot.acquisition_plan
        sample_count = count or min(max(plan.estimated_sample_count, 24), 240)
        start = -plan.pre_trigger_seconds
        span = plan.capture_window_seconds
        rows: list[RawSignalRecord] = []
        wavelength_factor = snapshot.probe.wavelength_cm1 / 2000.0
        pump_factor = 1.0 if snapshot.pump.enabled else 0.25
        for index in range(sample_count):
            fraction = index / max(sample_count - 1, 1)
            t = start + span * fraction
            envelope = math.exp(-((fraction - 0.45) ** 2) / 0.018)
            sample_x = 0.85 + 0.035 * math.sin(index / 7.0) - 0.08 * pump_factor * envelope
            sample_y = 0.18 + 0.020 * math.cos(index / 9.0) - 0.025 * pump_factor * envelope
            reference_x = 0.95 + 0.018 * math.sin(index / 8.0 + wavelength_factor)
            reference_y = 0.20 + 0.010 * math.cos(index / 10.0)
            sample_r = math.hypot(sample_x, sample_y)
            reference_r = math.hypot(reference_x, reference_y)
            rows.append(
                RawSignalRecord(
                    time_seconds=t,
                    sample_X=sample_x,
                    sample_Y=sample_y,
                    sample_R=sample_r,
                    sample_Theta=math.degrees(math.atan2(sample_y, sample_x)),
                    reference_X=reference_x,
                    reference_Y=reference_y,
                    reference_R=reference_r,
                    reference_Theta=math.degrees(math.atan2(reference_y, reference_x)),
                )
            )
        return tuple(rows)

    def _artifact_manifest(
        self,
        *,
        session: SessionRecord,
        run_id: str,
        snapshot: RunSettingsSnapshot,
        raw_record_id: str,
        processed_record_id: str | None,
    ) -> ArtifactManifest:
        run_dir = self._store.root / "sessions" / session.session_id / "runs" / run_id
        processed_path = run_dir / "processed" / "processed_record.json"
        return ArtifactManifest(
            manifest_id=f"{run_id}-artifact-manifest",
            session_id=session.session_id,
            run_id=run_id,
            settings_snapshot_id=snapshot.snapshot_id,
            raw_record_id=raw_record_id,
            processed_record_id=processed_record_id,
            session_metadata_path=self._store.relative_path(self._store.root / "sessions" / session.session_id / "session.json"),
            run_metadata_path=self._store.relative_path(run_dir / "run.json"),
            settings_snapshot_path=self._store.relative_path(run_dir / "settings_snapshot.json"),
            raw_data_path=self._store.relative_path(run_dir / "raw" / "raw_signals.csv"),
            processed_data_path=(
                self._store.relative_path(processed_path)
                if processed_record_id is not None
                else None
            ),
            export_paths=(
                self._store.relative_path(run_dir / "raw" / "raw_signals.csv"),
                self._store.relative_path(run_dir / "settings_snapshot.json"),
            ),
            created_at=utc_now(),
        )
