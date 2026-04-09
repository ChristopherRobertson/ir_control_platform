"""Phase 3B contract validation for the supported-v1 experiment slice."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from _path_setup import ROOT  # noqa: F401
from ircp_contracts import (
    AcquisitionTimingMode,
    AnalogMonitorRoute,
    ArtifactSourceRole,
    CalibrationReference,
    CanonicalTimingBlock,
    DeviceConfiguration,
    DeviceKind,
    DeviceLifecycleState,
    DeviceStatus,
    ExperimentRecipe,
    MuxOutputTarget,
    MuxRoute,
    MuxRouteSelection,
    MuxSignalDomain,
    PicoMonitoringMode,
    PicoSecondaryCapture,
    ProbeTimingMode,
    RawDataArtifact,
    RunEvent,
    RunEventType,
    RunFailureReason,
    RunOutcomeSummary,
    RunPhase,
    SessionManifest,
    SessionStatus,
    SessionStatusTimestamp,
    T660MasterTimingConfiguration,
    T660SlaveTimingConfiguration,
    TimeToWavenumberMapping,
    TimingControllerIdentity,
    TimingControllerRole,
    TimingEvent,
    TimingMarker,
    TimingWindow,
    summarize_mux_routes,
    summarize_pico_capture,
    HF2PrimaryAcquisition,
    HF2DemodulatorConfiguration,
    HF2SampleComponent,
    HF2StreamSelection,
    MircatEmissionMode,
    MircatExperimentConfiguration,
    MircatSpectralMode,
    MircatSweepScan,
)
from ircp_experiment_engine.runtime import build_fault, build_pump_probe_summary, build_timing_summary


def _build_recipe(*, with_mapping: bool = True) -> ExperimentRecipe:
    calibration = CalibrationReference(
        calibration_id="cal-1",
        version="phase3b.v1",
        kind="time_to_wavenumber",
        location="calibration.json",
    )
    return ExperimentRecipe(
        recipe_id="recipe-supported-v1",
        title="Supported v1 pump-probe scan",
        mircat=MircatExperimentConfiguration(
            emission_mode=MircatEmissionMode.PULSED,
            spectral_mode=MircatSpectralMode.SWEEP_SCAN,
            pulse_rate_hz=10_000.0,
            pulse_width_ns=180.0,
            sweep_scan=MircatSweepScan(
                start_wavenumber_cm1=1700.0,
                end_wavenumber_cm1=1800.0,
                scan_speed_cm1_per_s=4.0,
            ),
        ),
        hf2_primary_acquisition=HF2PrimaryAcquisition(
            profile_name="dual-detector-r",
            stream_selections=(HF2StreamSelection(demod_index=0, component=HF2SampleComponent.R),),
            demodulators=(HF2DemodulatorConfiguration(demod_index=0, sample_rate_hz=224.9),),
        ),
        pump_shots_before_probe=3,
        probe_timing_mode=ProbeTimingMode.SYNCHRONIZED_PROBE,
        timing=CanonicalTimingBlock(
            t0_label="master_cycle_start",
            master=T660MasterTimingConfiguration(
                device_identity=TimingControllerIdentity.T660_2_MASTER,
                role=TimingControllerRole.MASTER,
                master_clock_hz=10_000_000.0,
                cycle_period_ns=1_000_000.0,
                pump_fire_command=TimingEvent(TimingMarker.PUMP_FIRE_COMMAND, 0.0, 100.0),
                pump_qswitch_command=TimingEvent(TimingMarker.PUMP_QSWITCH_COMMAND, 140_000.0, 100.0),
                master_to_slave_trigger=TimingEvent(TimingMarker.MASTER_TO_SLAVE_TRIGGER, 600_000.0, 100.0),
            ),
            slave=T660SlaveTimingConfiguration(
                device_identity=TimingControllerIdentity.T660_1_SLAVE,
                role=TimingControllerRole.SLAVE,
                trigger_source=TimingMarker.MASTER_TO_SLAVE_TRIGGER,
                probe_trigger=TimingEvent(TimingMarker.PROBE_TRIGGER, 620_000.0, 100.0),
                probe_process_trigger=TimingEvent(TimingMarker.PROBE_PROCESS_TRIGGER, 624_000.0, 100.0),
                probe_enable_window=TimingWindow(TimingMarker.PROBE_ENABLE_WINDOW, 610_000.0, 40_000.0),
                slave_timing_marker=TimingEvent(TimingMarker.SLAVE_TIMING_MARKER, 620_000.0, 100.0),
            ),
            acquisition_timing_mode=AcquisitionTimingMode.AROUND_SELECTED_SIGNAL,
            acquisition_reference_marker=TimingMarker.MIRCAT_WAVELENGTH_TRIGGER,
            selected_digital_markers=(
                TimingMarker.NDYAG_FIXED_SYNC,
                TimingMarker.MIRCAT_WAVELENGTH_TRIGGER,
                TimingMarker.SLAVE_TIMING_MARKER,
            ),
        ),
        mux_route_selection=MuxRouteSelection(
            route_set_id="mux-default",
            route_set_name="HF2 R plus MIRcat trigger",
            channel_a=MuxRoute(
                target=MuxOutputTarget.PICO_CHANNEL_A,
                signal_domain=MuxSignalDomain.ANALOG_MONITOR,
                analog_source=AnalogMonitorRoute.HF2_AUX_R,
            ),
            channel_b=MuxRoute(
                target=MuxOutputTarget.PICO_CHANNEL_B,
                signal_domain=MuxSignalDomain.DIGITAL_MARKER,
                digital_marker=TimingMarker.MIRCAT_TRIGGER_OUT,
            ),
            external_trigger=MuxRoute(
                target=MuxOutputTarget.PICO_EXTERNAL_TRIGGER,
                signal_domain=MuxSignalDomain.DIGITAL_MARKER,
                digital_marker=TimingMarker.NDYAG_FIXED_SYNC,
            ),
        ),
        pico_secondary_capture=PicoSecondaryCapture(
            mode=PicoMonitoringMode.MONITOR_AND_RECORD,
            trigger_marker=TimingMarker.NDYAG_FIXED_SYNC,
            record_inputs=(MuxOutputTarget.PICO_CHANNEL_A, MuxOutputTarget.PICO_CHANNEL_B),
            capture_window_ns=120_000.0,
            sample_interval_ns=50.0,
        ),
        time_to_wavenumber_mapping=(
            TimeToWavenumberMapping(
                mapping_id="mapping-1",
                calibration_reference_id=calibration.calibration_id,
                applicable_spectral_modes=(MircatSpectralMode.SWEEP_SCAN,),
                start_wavenumber_cm1=1700.0,
                end_wavenumber_cm1=1800.0,
                scan_speed_cm1_per_s=4.0,
            )
            if with_mapping
            else None
        ),
        calibration_references=(calibration,),
    )


class Phase3BContractTests(unittest.TestCase):
    def test_supported_v1_recipe_construction_preserves_required_device_roles(self) -> None:
        recipe = _build_recipe()

        required_roles = {device.role_label for device in recipe.required_devices if device.required}
        required_kinds = {device.device_kind for device in recipe.required_devices if device.required}

        self.assertIn("master_timing", required_roles)
        self.assertIn("slave_timing", required_roles)
        self.assertIn("scope_route_selector", required_roles)
        self.assertIn(DeviceKind.T660_TIMING, required_kinds)
        self.assertIn(DeviceKind.ARDUINO_MUX, required_kinds)

    def test_scan_recipe_requires_time_to_wavenumber_mapping(self) -> None:
        with self.assertRaises(ValueError):
            _build_recipe(with_mapping=False)

    def test_session_manifest_accepts_primary_and_secondary_raw_artifacts(self) -> None:
        now = datetime.now(timezone.utc)
        recipe = _build_recipe()
        primary_raw = RawDataArtifact(
            artifact_id="raw-hf2-1",
            session_id="session-1",
            device_kind=DeviceKind.LABONE_HF2LI,
            stream_name="hf2.demod0.r",
            relative_path="raw/hf2/demod0_r.txt",
            created_at=now,
            source_role=ArtifactSourceRole.PRIMARY_RAW,
        )
        secondary_raw = RawDataArtifact(
            artifact_id="raw-pico-1",
            session_id="session-1",
            device_kind=DeviceKind.PICOSCOPE_5244D,
            stream_name="pico.channel_a",
            relative_path="raw/pico/channel_a.txt",
            created_at=now,
            source_role=ArtifactSourceRole.SECONDARY_MONITOR,
        )
        event = RunEvent(
            event_id="event-1",
            run_id="run-1",
            event_type=RunEventType.RUN_COMPLETED,
            emitted_at=now,
            source="experiment-engine",
            message="Session completed",
            phase=RunPhase.COMPLETED,
            session_id="session-1",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
        )
        status = DeviceStatus(
            device_id="hf2li-primary",
            device_kind=DeviceKind.LABONE_HF2LI,
            lifecycle_state=DeviceLifecycleState.IDLE,
            connected=True,
            ready=True,
            busy=False,
            updated_at=now,
            status_summary="Ready for preflight",
        )
        config = DeviceConfiguration(
            configuration_id="cfg-1",
            device_id="hf2li-primary",
            device_kind=DeviceKind.LABONE_HF2LI,
            applied_at=now,
            settings={"profile_name": "dual-detector-r"},
        )

        manifest = SessionManifest(
            session_id="session-1",
            version="phase3b.v1",
            created_at=now,
            updated_at=now,
            status=SessionStatus.COMPLETED,
            recipe_snapshot=recipe,
            device_config_snapshot=(config,),
            calibration_references=recipe.calibration_references,
            raw_artifacts=(primary_raw, secondary_raw),
            event_timeline=(event,),
            processing_outputs=(),
            analysis_outputs=(),
            export_artifacts=(),
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=tuple(marker.value for marker in recipe.timing.selected_digital_markers),
            mux_route_snapshot=recipe.mux_route_selection,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_capture_snapshot=recipe.pico_secondary_capture,
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
            time_to_wavenumber_mapping=recipe.time_to_wavenumber_mapping,
            device_status_snapshot=(status,),
            status_timestamps=(
                SessionStatusTimestamp(status=SessionStatus.PLANNED, recorded_at=now),
                SessionStatusTimestamp(status=SessionStatus.ACTIVE, recorded_at=now),
                SessionStatusTimestamp(status=SessionStatus.COMPLETED, recorded_at=now),
            ),
            outcome=RunOutcomeSummary(
                started_at=now,
                ended_at=now,
                final_event_id="event-1",
            ),
        )

        self.assertEqual(manifest.validate_provenance(), ())
        self.assertEqual(len(manifest.primary_raw_artifacts()), 1)
        self.assertEqual(len(manifest.secondary_monitor_artifacts()), 1)

    def test_completed_session_rejects_secondary_only_raw_authority(self) -> None:
        now = datetime.now(timezone.utc)
        recipe = _build_recipe()
        secondary_raw = RawDataArtifact(
            artifact_id="raw-pico-1",
            session_id="session-1",
            device_kind=DeviceKind.PICOSCOPE_5244D,
            stream_name="pico.channel_a",
            relative_path="raw/pico/channel_a.txt",
            created_at=now,
            source_role=ArtifactSourceRole.SECONDARY_MONITOR,
        )
        event = RunEvent(
            event_id="event-1",
            run_id="run-1",
            event_type=RunEventType.RUN_COMPLETED,
            emitted_at=now,
            source="experiment-engine",
            message="Session completed",
            phase=RunPhase.COMPLETED,
            session_id="session-1",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
        )

        with self.assertRaises(ValueError):
            SessionManifest(
                session_id="session-1",
                version="phase3b.v1",
                created_at=now,
                updated_at=now,
                status=SessionStatus.COMPLETED,
                recipe_snapshot=recipe,
                device_config_snapshot=(),
                calibration_references=recipe.calibration_references,
                raw_artifacts=(secondary_raw,),
                event_timeline=(event,),
                processing_outputs=(),
                analysis_outputs=(),
                export_artifacts=(),
                timing_summary=build_timing_summary(recipe),
                pump_probe_summary=build_pump_probe_summary(recipe),
                selected_markers=tuple(marker.value for marker in recipe.timing.selected_digital_markers),
                mux_route_snapshot=recipe.mux_route_selection,
                mux_summary=summarize_mux_routes(recipe.mux_route_selection),
                pico_capture_snapshot=recipe.pico_secondary_capture,
                pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
                time_to_wavenumber_mapping=recipe.time_to_wavenumber_mapping,
                status_timestamps=(
                    SessionStatusTimestamp(status=SessionStatus.PLANNED, recorded_at=now),
                    SessionStatusTimestamp(status=SessionStatus.ACTIVE, recorded_at=now),
                    SessionStatusTimestamp(status=SessionStatus.COMPLETED, recorded_at=now),
                ),
                outcome=RunOutcomeSummary(
                    started_at=now,
                    ended_at=now,
                    final_event_id="event-1",
                ),
            )

    def test_faulted_session_accepts_partial_primary_raw_with_explicit_failure_reason(self) -> None:
        now = datetime.now(timezone.utc)
        recipe = _build_recipe()
        primary_raw = RawDataArtifact(
            artifact_id="raw-hf2-partial-1",
            session_id="session-faulted-1",
            device_kind=DeviceKind.LABONE_HF2LI,
            stream_name="hf2.demod0.r",
            relative_path="raw/hf2/demod0_r_partial.txt",
            created_at=now,
            source_role=ArtifactSourceRole.PRIMARY_RAW,
            registered_by_event_id="event-raw-1",
        )
        fault = build_fault(
            fault_id="fault-1",
            device_id="hf2li-primary",
            device_kind=DeviceKind.LABONE_HF2LI,
            code="hf2_capture_overload",
            message="HF2 capture faulted during the run.",
            vendor_code="LABONE:OVERLOAD",
            vendor_message="Simulated overload.",
        )
        raw_event = RunEvent(
            event_id="event-raw-1",
            run_id="run-faulted-1",
            event_type=RunEventType.RAW_ARTIFACT_REGISTERED,
            emitted_at=now,
            source="data-pipeline",
            message="Partial HF2 raw artifact registered.",
            phase=RunPhase.RUNNING,
            session_id="session-faulted-1",
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
        )
        fault_event = RunEvent(
            event_id="event-fault-1",
            run_id="run-faulted-1",
            event_type=RunEventType.DEVICE_FAULT_REPORTED,
            emitted_at=now,
            source="experiment-engine",
            message=fault.message,
            phase=RunPhase.FAULTED,
            session_id="session-faulted-1",
            device_fault=fault,
            failure_reason=RunFailureReason.DEVICE_FAULT,
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=recipe.timing.selected_digital_markers,
        )

        manifest = SessionManifest(
            session_id="session-faulted-1",
            version="phase3b.v1",
            created_at=now,
            updated_at=now,
            status=SessionStatus.FAULTED,
            recipe_snapshot=recipe,
            device_config_snapshot=(),
            calibration_references=recipe.calibration_references,
            raw_artifacts=(primary_raw,),
            event_timeline=(raw_event, fault_event),
            processing_outputs=(),
            analysis_outputs=(),
            export_artifacts=(),
            timing_summary=build_timing_summary(recipe),
            pump_probe_summary=build_pump_probe_summary(recipe),
            selected_markers=tuple(marker.value for marker in recipe.timing.selected_digital_markers),
            mux_route_snapshot=recipe.mux_route_selection,
            mux_summary=summarize_mux_routes(recipe.mux_route_selection),
            pico_capture_snapshot=recipe.pico_secondary_capture,
            pico_summary=summarize_pico_capture(recipe.pico_secondary_capture),
            time_to_wavenumber_mapping=recipe.time_to_wavenumber_mapping,
            status_timestamps=(
                SessionStatusTimestamp(status=SessionStatus.PLANNED, recorded_at=now),
                SessionStatusTimestamp(status=SessionStatus.ACTIVE, recorded_at=now),
                SessionStatusTimestamp(status=SessionStatus.FAULTED, recorded_at=now),
            ),
            outcome=RunOutcomeSummary(
                started_at=now,
                ended_at=now,
                failure_reason=RunFailureReason.DEVICE_FAULT,
                latest_fault=fault,
                final_event_id="event-fault-1",
            ),
        )

        self.assertEqual(manifest.validate_provenance(), ())


if __name__ == "__main__":
    unittest.main()
