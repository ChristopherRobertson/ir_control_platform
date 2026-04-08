"""Minimal validation for Phase 2 contract consistency."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from _path_setup import ROOT  # noqa: F401
from ircp_contracts import (
    AnalysisArtifact,
    DeviceConfiguration,
    DeviceKind,
    DeviceLifecycleState,
    DeviceStatus,
    ExperimentRecipe,
    ExportArtifact,
    HF2AcquisitionRecipe,
    HF2DemodulatorConfiguration,
    HF2SampleComponent,
    HF2StreamSelection,
    MircatSweepRecipe,
    ProcessedArtifact,
    RawDataArtifact,
    RunEvent,
    RunEventType,
    RunPhase,
    SessionManifest,
    SessionStatus,
)


class Phase2ContractTests(unittest.TestCase):
    def test_golden_path_recipe_construction(self) -> None:
        recipe = ExperimentRecipe(
            recipe_id="recipe-mircat-hf2",
            title="Golden path sweep",
            mircat_sweep=MircatSweepRecipe(
                start_wavenumber_cm1=1700.0,
                end_wavenumber_cm1=1800.0,
                scan_speed_cm1_per_s=5.0,
                scan_count=1,
            ),
            hf2_acquisition=HF2AcquisitionRecipe(
                stream_selections=(
                    HF2StreamSelection(demod_index=0, component=HF2SampleComponent.R),
                ),
                demodulators=(
                    HF2DemodulatorConfiguration(demod_index=0, sample_rate_hz=224.9),
                ),
            ),
        )

        self.assertEqual(recipe.required_devices, (DeviceKind.MIRCAT, DeviceKind.LABONE_HF2LI))

    def test_session_manifest_accepts_traceable_artifact_chain(self) -> None:
        now = datetime.now(timezone.utc)
        recipe = ExperimentRecipe(
            recipe_id="recipe-mircat-hf2",
            title="Golden path sweep",
            mircat_sweep=MircatSweepRecipe(
                start_wavenumber_cm1=1700.0,
                end_wavenumber_cm1=1800.0,
                scan_speed_cm1_per_s=5.0,
                scan_count=1,
            ),
            hf2_acquisition=HF2AcquisitionRecipe(
                stream_selections=(
                    HF2StreamSelection(demod_index=0, component=HF2SampleComponent.R),
                ),
                demodulators=(
                    HF2DemodulatorConfiguration(demod_index=0, sample_rate_hz=224.9),
                ),
            ),
        )
        raw = RawDataArtifact(
            artifact_id="raw-1",
            session_id="session-1",
            device_kind=DeviceKind.LABONE_HF2LI,
            stream_name="demod0.r",
            relative_path="raw/hf2li_stream.txt",
            created_at=now,
        )
        processed = ProcessedArtifact(
            artifact_id="processed-1",
            session_id="session-1",
            relative_path="processed/absorbance.txt",
            processing_recipe_id="proc-1",
            processing_recipe_version="phase2.v1",
            source_raw_artifact_ids=("raw-1",),
            created_at=now,
        )
        analysis = AnalysisArtifact(
            artifact_id="analysis-1",
            session_id="session-1",
            relative_path="analysis/summary.json",
            analysis_recipe_id="analysis-1",
            analysis_recipe_version="phase2.v1",
            source_processed_artifact_ids=("processed-1",),
            created_at=now,
        )
        export = ExportArtifact(
            artifact_id="export-1",
            session_id="session-1",
            relative_path="exports/report.zip",
            format_name="zip",
            export_name="golden-path-report",
            source_artifact_ids=("analysis-1",),
            created_at=now,
        )
        status = DeviceStatus(
            device_id="mircat-1",
            device_kind=DeviceKind.MIRCAT,
            lifecycle_state=DeviceLifecycleState.IDLE,
            connected=True,
            ready=True,
            busy=False,
            updated_at=now,
            status_summary="Ready for preflight",
        )
        config = DeviceConfiguration(
            configuration_id="cfg-1",
            device_id="mircat-1",
            device_kind=DeviceKind.MIRCAT,
            applied_at=now,
            settings={"scan_speed_cm1_per_s": 5.0},
        )
        event = RunEvent(
            event_id="event-1",
            run_id="run-1",
            event_type=RunEventType.SESSION_CREATED,
            emitted_at=now,
            source="experiment-engine",
            message="Session created",
            phase=RunPhase.STARTING,
            session_id="session-1",
        )

        manifest = SessionManifest(
            session_id="session-1",
            version="phase2.v1",
            created_at=now,
            updated_at=now,
            status=SessionStatus.ACTIVE,
            recipe_snapshot=recipe,
            device_config_snapshot=(config,),
            calibration_references=(),
            raw_artifacts=(raw,),
            event_timeline=(event,),
            processing_outputs=(processed,),
            analysis_outputs=(analysis,),
            export_artifacts=(export,),
            device_status_snapshot=(status,),
        )

        self.assertEqual(manifest.validate_provenance(), ())

    def test_processed_artifact_requires_raw_inputs(self) -> None:
        now = datetime.now(timezone.utc)
        with self.assertRaises(ValueError):
            ProcessedArtifact(
                artifact_id="processed-1",
                session_id="session-1",
                relative_path="processed/absorbance.txt",
                processing_recipe_id="proc-1",
                processing_recipe_version="phase2.v1",
                source_raw_artifact_ids=(),
                created_at=now,
            )


if __name__ == "__main__":
    unittest.main()
