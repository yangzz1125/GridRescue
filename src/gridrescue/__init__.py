"""GridRescue competition prototype.

High-level imports live in :mod:`gridrescue.api`; implementation modules keep
their historical paths for compatibility with the existing evidence bundle.
"""

__version__ = "0.1.0"

from .api import (  # noqa: E402,F401
    EventReplay,
    GridModel,
    PipelineResult,
    build_model,
    replay_public_event,
    run_named_scenario,
)

__all__ = [
    "EventReplay",
    "GridModel",
    "PipelineResult",
    "build_model",
    "replay_public_event",
    "run_named_scenario",
]
