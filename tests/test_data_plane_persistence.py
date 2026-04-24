"""Persistence tests for single-wavelength session/run artifacts."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

try:
    from _path_setup import ROOT  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    from tests._path_setup import ROOT
from ircp_contracts import (
    EXPERIMENT_ID,
    LockInSettings,
    ProbeEmissionMode,
    ProbeSettings,
    PumpSettings,
    RunHeader,
    RunLifecycleState,
    TimescaleRegime,
)
from ircp_data_pipeline import SingleWavelengthRunStore
from ircp_experiment_engine import SingleWavelengthPumpProbeCoordinator


class SingleWavelengthPersistenceTests(unittest.TestCase):
    def _temp_root(self) -> Path:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return Path(tempdir.name)

    def _saved_inputs(self, root: Path):
        store = SingleWavelengthRunStore(root)
        session = store.create_session(
            session_id="session-001",
            experiment_type=EXPERIMENT_ID,
            session_name="Session 001",
            operator="Operator",
            sample_id="Sample",
            sample_notes="",
            experiment_notes="",
        )
        header = store.create_run_header(
            session_id=session.session_id,
            run_id="run-001",
            run_name="Run 001",
            run_notes="",
        )
        header = store.save_run_header(header)
        return store, session, header

    def test_persistence_separates_session_run_snapshot_raw_processed_and_manifest(self) -> None:
        root = self._temp_root()
        store, session, header = self._saved_inputs(root)
        coordinator = SingleWavelengthPumpProbeCoordinator(store)
        lockin = LockInSettings(order=2, time_constant_seconds=0.1, transfer_rate_hz=224.9)
        setup = coordinator.build_setup_state(
            session_saved=True,
            run_header_saved=True,
            pump=PumpSettings(enabled=True, shot_count=10),
            timescale=TimescaleRegime.MICROSECONDS,
            probe=ProbeSettings(wavelength_cm1=1850.0, emission_mode=ProbeEmissionMode.CW),
            lockin=lockin,
        )

        run = coordinator.start_run(session=session, run_header=header, setup=setup)

        self.assertEqual(run.completion_status, RunLifecycleState.COMPLETED)
        run_dir = root / "sessions" / session.session_id / "runs" / header.run_id
        self.assertTrue((root / "sessions" / session.session_id / "session.json").is_file())
        self.assertTrue((run_dir / "run_header.json").is_file())
        self.assertTrue((run_dir / "run.json").is_file())
        self.assertTrue((run_dir / "settings_snapshot.json").is_file())
        self.assertTrue((run_dir / "raw" / "raw_signals.csv").is_file())
        self.assertTrue((run_dir / "raw" / "raw_record.json").is_file())
        self.assertTrue((run_dir / "processed" / "processed_record.json").is_file())
        self.assertTrue((run_dir / "artifact_manifest.json").is_file())

        reopened = SingleWavelengthRunStore(root)
        loaded = reopened.load_run_record(session.session_id, header.run_id)
        raw = reopened.load_raw_run_record(session.session_id, header.run_id)
        processed = reopened.load_processed_run_record(session.session_id, header.run_id)
        manifest = reopened.load_artifact_manifest(session.session_id, header.run_id)

        self.assertEqual(loaded.run_id, run.run_id)
        self.assertEqual(raw.settings_snapshot_id, loaded.settings_snapshot.snapshot_id)
        self.assertEqual(processed.raw_record_id, raw.raw_record_id)
        self.assertEqual(manifest.raw_record_id, raw.raw_record_id)
        self.assertEqual(manifest.processed_record_id, processed.processed_record_id)

    def test_faulted_run_keeps_partial_raw_without_processed_record(self) -> None:
        root = self._temp_root()
        store, session, header = self._saved_inputs(root)
        coordinator = SingleWavelengthPumpProbeCoordinator(store, fault_on_start=True)
        setup = coordinator.build_setup_state(
            session_saved=True,
            run_header_saved=True,
            pump=PumpSettings(enabled=True, shot_count=10),
            timescale=TimescaleRegime.MICROSECONDS,
            probe=ProbeSettings(wavelength_cm1=1850.0, emission_mode=ProbeEmissionMode.CW),
            lockin=LockInSettings(order=2, time_constant_seconds=0.1, transfer_rate_hz=224.9),
        )

        run = coordinator.start_run(session=session, run_header=header, setup=setup)
        raw = store.load_raw_run_record(session.session_id, header.run_id)
        manifest = store.load_artifact_manifest(session.session_id, header.run_id)

        self.assertEqual(run.completion_status, RunLifecycleState.FAULTED)
        self.assertIsNotNone(run.fault_error_state)
        self.assertGreater(len(raw.signals), 0)
        self.assertIsNone(manifest.processed_record_id)
        self.assertIsNone(manifest.processed_data_path)


if __name__ == "__main__":
    unittest.main()
