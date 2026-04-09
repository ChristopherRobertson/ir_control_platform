"""Phase 4 data-plane persistence, indexing, and replay tests."""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from _path_setup import ROOT  # noqa: F401
from ircp_contracts import (
    ArtifactKind,
    ArtifactSourceRole,
    DeviceKind,
    RunEventType,
    RunFailureReason,
    RunPhase,
    SessionStatus,
)
from ircp_data_pipeline import ArtifactQuery, InMemorySessionStore, SessionOpenRequest
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
from ircp_simulators import Phase3BScenarioContext, SupportedV1SimulatorCatalog


def _build_coordinator(
    context: Phase3BScenarioContext,
    session_store: InMemorySessionStore,
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
                        relative_path=f"sessions/{session_id}/raw/hf2/demod0_r_partial.txt",
                        record_count=len(hf2_live_points),
                        source_role=ArtifactSourceRole.PRIMARY_RAW,
                        metadata={"mapping_id": recipe.time_to_wavenumber_mapping.mapping_id},
                    ),
                ),
                outcome=StepOutcome.CONTINUE,
            ),
        )
    )


class Phase4DataPlaneTests(unittest.TestCase):
    def test_nominal_run_persists_completed_session_detail_and_artifact_indexes(self) -> None:
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        session_store = InMemorySessionStore(initial_manifests=context.initial_manifests)
        coordinator = _build_coordinator(context, session_store)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        run_state = asyncio.run(
            coordinator.start_run(context.recipe, context.preset, manifest.session_id)
        )
        detail = asyncio.run(session_store.get_session_detail(manifest.session_id))
        primary = asyncio.run(
            session_store.query_artifacts(
                ArtifactQuery(
                    session_id=manifest.session_id,
                    artifact_kind=ArtifactKind.RAW,
                    source_role=ArtifactSourceRole.PRIMARY_RAW,
                )
            )
        )
        secondary = asyncio.run(
            session_store.query_artifacts(
                ArtifactQuery(
                    session_id=manifest.session_id,
                    artifact_kind=ArtifactKind.RAW,
                    source_role=ArtifactSourceRole.SECONDARY_MONITOR,
                )
            )
        )

        self.assertEqual(run_state.phase, RunPhase.COMPLETED)
        self.assertEqual(detail.summary.status, SessionStatus.COMPLETED)
        self.assertTrue(detail.summary.replay_ready)
        self.assertIsNotNone(detail.manifest.outcome.started_at)
        self.assertIsNotNone(detail.manifest.outcome.ended_at)
        self.assertGreaterEqual(detail.summary.event_count, 4)
        self.assertGreaterEqual(len(primary), 1)
        self.assertGreaterEqual(len(secondary), 1)
        self.assertEqual(
            tuple(artifact.artifact_id for artifact in primary),
            detail.replay_plan.primary_raw_artifact_ids,
        )
        self.assertTrue(
            all(
                artifact.registered_by_event_id in detail.manifest.event_ids()
                for artifact in (*primary, *secondary)
                if artifact.registered_by_event_id is not None
            )
        )

    def test_faulted_run_preserves_partial_artifacts_and_explicit_failure_reason(self) -> None:
        context = SupportedV1SimulatorCatalog().get_context("faulted_hf2")
        session_store = InMemorySessionStore(initial_manifests=context.initial_manifests)
        coordinator = _build_coordinator(context, session_store)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        run_state = asyncio.run(
            coordinator.start_run(context.recipe, context.preset, manifest.session_id)
        )
        detail = asyncio.run(session_store.get_session_detail(manifest.session_id))

        self.assertEqual(run_state.phase, RunPhase.FAULTED)
        self.assertEqual(detail.summary.status, SessionStatus.FAULTED)
        self.assertEqual(detail.summary.failure_reason, RunFailureReason.DEVICE_FAULT)
        self.assertIsNotNone(detail.manifest.outcome.latest_fault)
        self.assertGreaterEqual(len(detail.primary_raw_artifacts), 1)
        self.assertGreaterEqual(len(detail.secondary_monitor_artifacts), 1)
        self.assertTrue(
            any(event.event_type == RunEventType.DEVICE_FAULT_REPORTED for event in detail.event_timeline)
        )

    def test_abort_run_finalizes_aborted_session_and_preserves_partial_data(self) -> None:
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        session_store = InMemorySessionStore(initial_manifests=context.initial_manifests)
        coordinator = _build_coordinator(context, session_store, run_plan_factory=_active_run_plan)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        active_state = asyncio.run(
            coordinator.start_run(context.recipe, context.preset, manifest.session_id)
        )
        aborted_state = asyncio.run(coordinator.abort_run(active_state.run_id))
        detail = asyncio.run(session_store.get_session_detail(manifest.session_id))

        self.assertEqual(active_state.phase, RunPhase.RUNNING)
        self.assertEqual(aborted_state.phase, RunPhase.ABORTED)
        self.assertEqual(detail.summary.status, SessionStatus.ABORTED)
        self.assertEqual(detail.summary.failure_reason, RunFailureReason.OPERATOR_ABORT)
        self.assertGreaterEqual(len(detail.primary_raw_artifacts), 1)
        self.assertTrue(
            any(event.event_type == RunEventType.RUN_ABORTED for event in detail.event_timeline)
        )

    def test_saved_session_reopens_from_fresh_store_without_live_run_state(self) -> None:
        context = SupportedV1SimulatorCatalog().get_context("nominal")
        source_store = InMemorySessionStore(initial_manifests=context.initial_manifests)
        coordinator = _build_coordinator(context, source_store)

        manifest = asyncio.run(coordinator.create_session(context.recipe, context.preset))
        asyncio.run(coordinator.start_run(context.recipe, context.preset, manifest.session_id))
        persisted_manifest = asyncio.run(source_store.load_session(manifest.session_id))

        fresh_store = InMemorySessionStore(initial_manifests=(persisted_manifest,))
        open_result = asyncio.run(
            fresh_store.open_session(
                SessionOpenRequest(
                    session_id=manifest.session_id,
                    requested_at=datetime.now(timezone.utc),
                    reopen_for_replay=True,
                )
            )
        )
        detail = asyncio.run(fresh_store.get_session_detail(manifest.session_id))

        self.assertTrue(open_result.replay_ready)
        self.assertEqual(detail.summary.status, SessionStatus.COMPLETED)
        self.assertEqual(detail.summary.event_count, len(persisted_manifest.event_timeline))
        self.assertGreaterEqual(len(detail.primary_raw_artifacts), 1)


if __name__ == "__main__":
    unittest.main()
