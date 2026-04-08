"""Generic event publication primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Protocol, TypeVar, runtime_checkable

PayloadT = TypeVar("PayloadT")


@dataclass(frozen=True)
class EventEnvelope(Generic[PayloadT]):
    topic: str
    emitted_at: datetime
    source: str
    payload: PayloadT


@runtime_checkable
class EventPublisher(Protocol[PayloadT]):
    async def publish(self, event: EventEnvelope[PayloadT]) -> None:
        """Publish a typed event to the runtime event bus."""


@runtime_checkable
class StatePublisher(Protocol[PayloadT]):
    async def publish_snapshot(self, topic: str, snapshot: PayloadT, emitted_at: datetime) -> None:
        """Publish the latest state snapshot for downstream observers."""
