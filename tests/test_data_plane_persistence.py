"""Durable persistence, indexing, and replay tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from datetime import datetime, timezone

try:
    from _path_setup import ROOT  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - depends on unittest invocation style
    from tests._path_setup import ROOT
from ircp_contracts import (
    ArtifactKind,
    ArtifactSourceRole,
    DeviceKind,
    RunEventType,
    RunFailureReason,
    RunPhase,
    SessionStatus,
)
from ircp_data_pipeline import (
    ArtifactQuery,
    FilesystemSessionStore,
    InMemorySessionStore,
    SessionOpenRequest,
)
from ircp_experiment_engine import SupportedV1DriverBundle
from ircp_experiment_engine.runtime import (
    InMemoryRunCoordinator,
    RawArtifactTemplate,
    RunEventTemplate,
    RunExecutionPlan,
    RunStepTemplate,
    StepOutcome,
    SupportedV1PreflightValidator,
    build_live_data_points,
)
from ircp_platform import create_simulator_runtime_map
from ircp_simulators import SimulatorScenarioContext, SupportedV1SimulatorCatalog


def _filesystem_persistence_available() -> bool:
    try:
        from ircp_data_pipeline import filesystem as filesystem_module

        filesystem_module._require_pyarrow()
    except Exception:
        return False
    return True


def _build_coordinator(
    context: SimulatorScenarioContext,
    session_store,
    *,
    run_plan_factory=None,
) -> InMemoryRunCoordinator:
    return InMemoryRunCoordinator(
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
        run_plan_factory=run_plan_factory or context.run_plan_factory,
    )


def _active_run_plan(recipe, session_id: str, run_id: str) -> RunExecutionPlan:
    hf2_live_points = build_live_data_points(
        run_id,
        "hf2.demod0.r",
        "Wavenumber",
        "cm^-1",
        (
            (1700.0, 0.14),
            (1725.0, 0.18),
        ),
    )
    return RunExecutionPlan(
        steps=(
            RunStepTemplate(
                phase=RunPhase.STARTING,
                active_step="timing_and_primary_capture_armed",
                progress_fraction=0.15,
                message="The run has started and remains active for abort coverage.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RUN_STARTED,
                        source="experiment-engine",
                        message="Abort coverage run started on the canonical path.",
                    ),
                ),
            ),
            RunStepTemplate(
                phase=RunPhase.RUNNING,
                active_step="primary_capture_active",
                progress_fraction=0.55,
                message="Primary HF2 capture is active and has persisted a partial raw artifact.",
                events=(
                    RunEventTemplate(
                        event_type=RunEventType.RAW_ARTIFACT_REGISTERED,
                        source="data-pipeline",
                        message="Partial HF2 primary artifact registered before abort.",
                    ),
                ),
                live_data_points=hf2_live_points,
                raw_artifacts=(
                    RawArtifactTemplate(
                        device_kind=DeviceKind.LABONE_HF2LI,
                        stream_name="hf2.demod0.r",
                        relative_path=f"sessions/{session_id}/artifacts/raw/hf2_demod0_r_partial.parquet",
                        record_count=len(hf2_live_points),
                        source_role=ArtifactSourceRole.PRIMARY_RAW,
                        metadata={"mapping_id": recipe.time_to_wavenumber_mapping.mapping_id},
                    ),
                ),
                outcome=StepOutcome.CONTINUE,
            ),
        )
    )


class DataPlanePersistenceTests(unittest.TestCase):
    def _require_filesystem_persistence(self) -> None:
        if not _filesystem_persistence_available():
            self.skipTest("pyarrow-backed filesystem persistence is unavailable in this environment.")

    def _read_parquet_rows(self, path: Path) -> list[dict[str, object]]:
        import pyarrow.parquet as pq  # type: ignore[reportMissingImports]

        table = pq.read_table(path)
        return table.to_pylist()

    def _temp_root(self) -> Path:
        tempdir = TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        return Path(tempdir.name)

    def _build_filesystem_store(
        self,
        root: Path,
        context: SimulatorScenarioContext,
        *,
        include_seed_data: bool = False,
    ) -> FilesystemSessionStore:
        return FilesystemSessionStore(
            root=root,
            initial_manifests=context.initial_manifests if include_seed_data else (),
            initial_raw_artifact_payloads=(
                context.initial_raw_artifact_payloads if include_seed_data else {}
            ),
        )

    def test_in_memory_store_remains_available_for_explicit_test_use(self) -> None:
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        session_store = InMemorySessionStore()
        coordinator = _build_coordinator(context, session_store)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        run_state = asyncio.run(
            coordinator.start_run(context.recipe, context.preset, manifest.session_id)
        )
        detail = asyncio.run(session_store.get_session_detail(manifest.session_id))

        self.assertEqual(run_state.phase, RunPhase.COMPLETED)
        self.assertEqual(detail.summary.status, SessionStatus.COMPLETED)
        self.assertTrue(detail.summary.replay_ready)

    def test_completed_session_persists_payloads_and_replay_after_restart(self) -> None:
        self._require_filesystem_persistence()
        root = self._temp_root() / "nominal"
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        store = self._build_filesystem_store(root, context)
        coordinator = _build_coordinator(context, store)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        run_state = asyncio.run(
            coordinator.start_run(context.recipe, context.preset, manifest.session_id)
        )

        fresh_store = self._build_filesystem_store(root, context)
        sessions = asyncio.run(fresh_store.list_sessions())
        detail = asyncio.run(fresh_store.get_session_detail(manifest.session_id))
        open_result = asyncio.run(
            fresh_store.open_session(
                SessionOpenRequest(
                    session_id=manifest.session_id,
                    requested_at=datetime.now(timezone.utc),
                    reopen_for_replay=True,
                )
            )
        )
        replay_plan = asyncio.run(fresh_store.build_replay_plan(manifest.session_id))
        primary = asyncio.run(
            fresh_store.query_artifacts(
                ArtifactQuery(
                    session_id=manifest.session_id,
                    artifact_kind=ArtifactKind.RAW,
                    source_role=ArtifactSourceRole.PRIMARY_RAW,
                )
            )
        )
        secondary = asyncio.run(
            fresh_store.query_artifacts(
                ArtifactQuery(
                    session_id=manifest.session_id,
                    artifact_kind=ArtifactKind.RAW,
                    source_role=ArtifactSourceRole.SECONDARY_MONITOR,
                )
            )
        )

        self.assertEqual(run_state.phase, RunPhase.COMPLETED)
        self.assertTrue(any(summary.session_id == manifest.session_id for summary in sessions))
        self.assertEqual(detail.summary.status, SessionStatus.COMPLETED)
        self.assertTrue(detail.summary.replay_ready)
        self.assertTrue(open_result.replay_ready)
        self.assertTrue((root / "sessions" / manifest.session_id / "manifest.json").is_file())
        self.assertTrue((root / "sessions" / manifest.session_id / "events.jsonl").is_file())
        self.assertGreaterEqual(len(primary), 1)
        self.assertGreaterEqual(len(secondary), 1)
        self.assertEqual(
            tuple(artifact.artifact_id for artifact in primary),
            replay_plan.primary_raw_artifact_ids,
        )
        self.assertEqual(
            tuple(artifact.artifact_id for artifact in secondary),
            replay_plan.secondary_monitor_artifact_ids,
        )
        self.assertTrue(
            all((root / artifact.relative_path).is_file() for artifact in detail.manifest.raw_artifacts)
        )
        parquet_rows = self._read_parquet_rows(root / detail.manifest.raw_artifacts[0].relative_path)
        self.assertGreaterEqual(len(parquet_rows), 1)
        self.assertIn("acquisition_index", parquet_rows[0])
        self.assertIn("stream_name", parquet_rows[0])
        self.assertEqual(detail.manifest.recipe_snapshot.recipe_id, context.recipe.recipe_id)
        self.assertEqual(detail.manifest.mux_summary.route_set_name, context.recipe.mux_route_selection.route_set_name)
        self.assertEqual(
            sum(
                1
                for line in (root / "sessions" / manifest.session_id / "events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line
            ),
            len(detail.event_timeline),
        )

    def test_faulted_session_survives_restart_with_partial_payloads(self) -> None:
        self._require_filesystem_persistence()
        root = self._temp_root() / "faulted"
        context = SupportedV1SimulatorCatalog().get_context("faulted_hf2")
        store = self._build_filesystem_store(root, context)
        coordinator = _build_coordinator(context, store)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        run_state = asyncio.run(
            coordinator.start_run(context.recipe, context.preset, manifest.session_id)
        )

        fresh_store = self._build_filesystem_store(root, context)
        detail = asyncio.run(fresh_store.get_session_detail(manifest.session_id))
        open_result = asyncio.run(
            fresh_store.open_session(
                SessionOpenRequest(
                    session_id=manifest.session_id,
                    requested_at=datetime.now(timezone.utc),
                    reopen_for_replay=True,
                )
            )
        )
        replay_plan = asyncio.run(fresh_store.build_replay_plan(manifest.session_id))

        self.assertEqual(run_state.phase, RunPhase.FAULTED)
        self.assertEqual(detail.summary.status, SessionStatus.FAULTED)
        self.assertEqual(detail.summary.failure_reason, RunFailureReason.DEVICE_FAULT)
        self.assertTrue(open_result.replay_ready)
        self.assertGreaterEqual(len(replay_plan.primary_raw_artifact_ids), 1)
        self.assertGreaterEqual(len(replay_plan.secondary_monitor_artifact_ids), 1)
        self.assertTrue(
            any(event.event_type == RunEventType.DEVICE_FAULT_REPORTED for event in detail.event_timeline)
        )
        self.assertTrue(
            all((root / artifact.relative_path).is_file() for artifact in detail.manifest.raw_artifacts)
        )

    def test_aborted_session_survives_restart_with_partial_payloads(self) -> None:
        self._require_filesystem_persistence()
        root = self._temp_root() / "aborted"
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        store = self._build_filesystem_store(root, context)
        coordinator = _build_coordinator(context, store, run_plan_factory=_active_run_plan)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        active_state = asyncio.run(
            coordinator.start_run(context.recipe, context.preset, manifest.session_id)
        )
        aborted_state = asyncio.run(coordinator.abort_run(active_state.run_id))

        fresh_store = self._build_filesystem_store(root, context)
        detail = asyncio.run(fresh_store.get_session_detail(manifest.session_id))
        open_result = asyncio.run(
            fresh_store.open_session(
                SessionOpenRequest(
                    session_id=manifest.session_id,
                    requested_at=datetime.now(timezone.utc),
                    reopen_for_replay=True,
                )
            )
        )
        replay_plan = asyncio.run(fresh_store.build_replay_plan(manifest.session_id))

        self.assertEqual(active_state.phase, RunPhase.RUNNING)
        self.assertEqual(aborted_state.phase, RunPhase.ABORTED)
        self.assertEqual(detail.summary.status, SessionStatus.ABORTED)
        self.assertEqual(detail.summary.failure_reason, RunFailureReason.OPERATOR_ABORT)
        self.assertTrue(open_result.replay_ready)
        self.assertGreaterEqual(len(replay_plan.primary_raw_artifact_ids), 1)
        self.assertTrue(
            any(event.event_type == RunEventType.RUN_ABORTED for event in detail.event_timeline)
        )
        self.assertTrue(
            all((root / artifact.relative_path).is_file() for artifact in detail.manifest.raw_artifacts)
        )

    def test_restart_rejects_completed_session_with_secondary_only_raw_artifacts(self) -> None:
        self._require_filesystem_persistence()
        root = self._temp_root() / "secondary-only"
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        store = self._build_filesystem_store(root, context)
        coordinator = _build_coordinator(context, store)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        asyncio.run(coordinator.start_run(context.recipe, context.preset, manifest.session_id))

        manifest_path = root / "sessions" / manifest.session_id / "manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["raw_artifacts"] = [
            artifact
            for artifact in payload["raw_artifacts"]
            if artifact["source_role"] == ArtifactSourceRole.SECONDARY_MONITOR.value
        ]
        manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        with self.assertRaises(ValueError):
            self._build_filesystem_store(root, context)

    def test_restart_reports_missing_primary_payload_explicitly(self) -> None:
        self._require_filesystem_persistence()
        root = self._temp_root() / "missing-primary-payload"
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        store = self._build_filesystem_store(root, context)
        coordinator = _build_coordinator(context, store)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        asyncio.run(coordinator.start_run(context.recipe, context.preset, manifest.session_id))

        primary_payload = root / f"sessions/{manifest.session_id}/artifacts/raw/hf2_demod0_r.parquet"
        primary_payload.unlink()

        fresh_store = self._build_filesystem_store(root, context)
        summaries = asyncio.run(fresh_store.list_sessions())
        detail = asyncio.run(fresh_store.get_session_detail(manifest.session_id))

        self.assertFalse(
            next(summary for summary in summaries if summary.session_id == manifest.session_id).replay_ready
        )
        self.assertFalse(detail.summary.replay_ready)
        with self.assertRaises(FileNotFoundError):
            asyncio.run(
                fresh_store.open_session(
                    SessionOpenRequest(
                        session_id=manifest.session_id,
                        requested_at=datetime.now(timezone.utc),
                        reopen_for_replay=True,
                    )
                )
            )
        with self.assertRaises(FileNotFoundError):
            asyncio.run(fresh_store.build_replay_plan(manifest.session_id))

    def test_runtime_results_reopen_flow_survives_runtime_recreation(self) -> None:
        self._require_filesystem_persistence()
        storage_root = self._temp_root()
        runtimes = create_simulator_runtime_map(storage_root=storage_root)
        runtime = runtimes["nominal"]

        run_state = asyncio.run(runtime.start_run())
        self.assertIsNotNone(run_state.session_id)
        assert run_state.session_id is not None

        recreated_runtimes = create_simulator_runtime_map(storage_root=storage_root)
        recreated_runtime = recreated_runtimes["nominal"]
        manifest = asyncio.run(recreated_runtime.reopen_session(run_state.session_id))
        results_page = asyncio.run(recreated_runtime.get_results_page(run_state.session_id))

        self.assertEqual(manifest.session_id, run_state.session_id)
        self.assertEqual(manifest.status, SessionStatus.COMPLETED)
        self.assertIsNotNone(results_page.selected_session)
        assert results_page.selected_session is not None
        self.assertEqual(results_page.selected_session.session_id, run_state.session_id)
        self.assertGreater(len(results_page.selected_session_metrics), 0)
        self.assertGreater(len(results_page.detail_panels), 0)
        self.assertGreater(len(results_page.artifact_panels), 0)
        self.assertGreater(len(results_page.artifact_rows), 0)
        self.assertGreater(len(results_page.trace_previews), 0)
        self.assertGreater(len(results_page.event_log), 0)
        self.assertIn("runtime_mode:simulator:nominal", manifest.notes)
        self.assertTrue((storage_root / "sessions" / run_state.session_id / "manifest.json").is_file())
        self.assertTrue((storage_root / "sessions").is_dir())
        self.assertFalse((storage_root / "nominal").exists())


if __name__ == "__main__":
    unittest.main()
