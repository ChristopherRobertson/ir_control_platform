"""Reusable transforms for single-wavelength pump-probe results."""

from __future__ import annotations

from datetime import datetime, timezone

from ircp_contracts import (
    PlotDisplayMode,
    PlotMetricFamily,
    ProcessedRunRecord,
    ProcessedSignalRecord,
    RawRunRecord,
    ratio_value,
)


def build_processed_run_record(
    raw_record: RawRunRecord,
    metric_family: PlotMetricFamily,
) -> ProcessedRunRecord:
    signals: list[ProcessedSignalRecord] = []
    for signal in raw_record.signals:
        sample, reference = signal.metric_pair(metric_family)
        signals.append(
            ProcessedSignalRecord(
                time_seconds=signal.time_seconds,
                metric_family=metric_family,
                sample=sample,
                reference=reference,
                ratio=ratio_value(sample, reference),
            )
        )
    return ProcessedRunRecord(
        processed_record_id=f"{raw_record.run_id}-{metric_family.value.lower()}-processed",
        session_id=raw_record.session_id,
        run_id=raw_record.run_id,
        raw_record_id=raw_record.raw_record_id,
        settings_snapshot_id=raw_record.settings_snapshot_id,
        signals=tuple(signals),
        created_at=datetime.now(timezone.utc),
    )


def select_plot_series(
    processed_record: ProcessedRunRecord,
    display_mode: PlotDisplayMode,
) -> tuple[dict[str, float], ...]:
    if display_mode == PlotDisplayMode.OVERLAY:
        return tuple(
            {
                "time_seconds": signal.time_seconds,
                "sample": signal.sample,
                "reference": signal.reference,
            }
            for signal in processed_record.signals
        )
    if display_mode == PlotDisplayMode.RATIO:
        return tuple(
            {
                "time_seconds": signal.time_seconds,
                "ratio": signal.ratio,
            }
            for signal in processed_record.signals
        )
    raise ValueError(f"Unsupported plot display mode: {display_mode}")
