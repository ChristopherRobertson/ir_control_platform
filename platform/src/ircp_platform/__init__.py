"""Cross-cutting runtime primitives for the IR control platform."""

from .bootstrap import create_simulator_app, create_simulator_runtime_map, run_simulator_demo
from .errors import DriverFailure, DriverOperationError, VendorErrorEnvelope
from .events import EventEnvelope, EventPublisher, StatePublisher
from .simulator_runtime import SimulatorUiRuntime

__all__ = [
    "create_simulator_app",
    "create_simulator_runtime_map",
    "DriverFailure",
    "DriverOperationError",
    "EventEnvelope",
    "EventPublisher",
    "SimulatorUiRuntime",
    "StatePublisher",
    "VendorErrorEnvelope",
    "run_simulator_demo",
]
