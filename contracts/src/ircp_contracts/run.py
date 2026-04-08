"""Validation, readiness, run-state, and run-event contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from .common import (
    ConfigurationScalar,
    ReadinessState,
    RunCommandType,
    RunEventType,
    RunFailureReason,
    RunPhase,
    ValidationSeverity,
)
from .device import DeviceFault


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: ValidationSeverity
    message: str
    source: str
    blocking: bool
    field_path: str | None = None
    related_device_id: str | None = None


@dataclass(frozen=True)
class ReadinessCheck:
    check_id: str
    target: str
    state: ReadinessState
    checked_at: datetime
    summary: str
    issues: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True)
class PreflightReport:
    recipe_id: str
    generated_at: datetime
    checks: tuple[ReadinessCheck, ...]
    ready_to_start: bool

    def __post_init__(self) -> None:
        has_blocking_issue = any(
            check.state == ReadinessState.BLOCK or any(issue.blocking for issue in check.issues)
            for check in self.checks
        )
        if self.ready_to_start and has_blocking_issue:
            raise ValueError("A ready preflight report cannot contain blocking checks or issues.")


@dataclass(frozen=True)
class RunCommand:
    command_type: RunCommandType
    issued_at: datetime
    issued_by: str
    recipe_id: str | None = None
    session_id: str | None = None
    payload: Mapping[str, ConfigurationScalar] = field(default_factory=dict)


@dataclass(frozen=True)
class RunState:
    run_id: str
    recipe_id: str
    phase: RunPhase
    updated_at: datetime
    session_id: str | None = None
    active_step: str | None = None
    progress_fraction: float | None = None
    preflight: PreflightReport | None = None
    latest_fault: DeviceFault | None = None
    failure_reason: RunFailureReason | None = None
    last_event_id: str | None = None

    def __post_init__(self) -> None:
        if self.progress_fraction is None:
            return
        if not 0.0 <= self.progress_fraction <= 1.0:
            raise ValueError("Run progress must stay within [0.0, 1.0].")


@dataclass(frozen=True)
class RunEvent:
    event_id: str
    run_id: str
    event_type: RunEventType
    emitted_at: datetime
    source: str
    message: str
    phase: RunPhase
    session_id: str | None = None
    device_fault: DeviceFault | None = None
    failure_reason: RunFailureReason | None = None
    payload: Mapping[str, ConfigurationScalar] = field(default_factory=dict)
