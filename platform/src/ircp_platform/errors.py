"""Normalized driver error wrappers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ircp_contracts import ConfigurationScalar, DeviceFault


@dataclass(frozen=True)
class VendorErrorEnvelope:
    vendor_name: str
    vendor_message: str
    vendor_code: str | None = None
    raw_context: Mapping[str, ConfigurationScalar] = field(default_factory=dict)


@dataclass(frozen=True)
class DriverFailure:
    fault: DeviceFault
    vendor_error: VendorErrorEnvelope | None = None


class DriverOperationError(RuntimeError):
    """Typed runtime wrapper for explicit device failures."""

    def __init__(self, failure: DriverFailure) -> None:
        super().__init__(failure.fault.message)
        self.failure = failure
