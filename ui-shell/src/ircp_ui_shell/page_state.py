"""Reusable page-state wrappers for the UI shell."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PageStateKind(str, Enum):
    LOADING = "loading"
    BLOCKED = "blocked"
    WARNING = "warning"
    FAULT = "fault"
    SUCCESS = "success"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    RECOVERY = "recovery"


@dataclass(frozen=True)
class PageStateModel:
    kind: PageStateKind
    title: str
    message: str
    details: tuple[str, ...] = ()


def loading_state(title: str, message: str, details: tuple[str, ...] = ()) -> PageStateModel:
    return PageStateModel(kind=PageStateKind.LOADING, title=title, message=message, details=details)


def blocked_state(title: str, message: str, details: tuple[str, ...] = ()) -> PageStateModel:
    return PageStateModel(kind=PageStateKind.BLOCKED, title=title, message=message, details=details)


def warning_state(title: str, message: str, details: tuple[str, ...] = ()) -> PageStateModel:
    return PageStateModel(kind=PageStateKind.WARNING, title=title, message=message, details=details)


def fault_state(title: str, message: str, details: tuple[str, ...] = ()) -> PageStateModel:
    return PageStateModel(kind=PageStateKind.FAULT, title=title, message=message, details=details)


def success_state(title: str, message: str, details: tuple[str, ...] = ()) -> PageStateModel:
    return PageStateModel(kind=PageStateKind.SUCCESS, title=title, message=message, details=details)


def empty_state(title: str, message: str, details: tuple[str, ...] = ()) -> PageStateModel:
    return PageStateModel(kind=PageStateKind.EMPTY, title=title, message=message, details=details)


def unavailable_state(title: str, message: str, details: tuple[str, ...] = ()) -> PageStateModel:
    return PageStateModel(
        kind=PageStateKind.UNAVAILABLE,
        title=title,
        message=message,
        details=details,
    )


def recovery_state(title: str, message: str, details: tuple[str, ...] = ()) -> PageStateModel:
    return PageStateModel(kind=PageStateKind.RECOVERY, title=title, message=message, details=details)
