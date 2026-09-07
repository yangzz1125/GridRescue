"""Stable public API for the GridRescue research prototype.

Use this module from notebooks, small scripts, and the Streamlit UI instead of
importing implementation modules one by one.  The existing module paths stay
available for backwards compatibility.
"""

from __future__ import annotations

from pathlib import Path

from .network import GridModel, build_ieee33
from .pipeline import PipelineResult, run_pipeline, run_scenario
from .real_event_replay import EventReplay, run_event_replay
from .scenarios import DisasterScenario, get_scenario


def build_model() -> GridModel:
    """Return the canonical IEEE-33 model used by the project."""
    return build_ieee33()


def run_named_scenario(name: str | None = None) -> PipelineResult:
    """Run one of the bundled deterministic scenarios."""
    return run_pipeline() if name is None else run_pipeline(name)


def replay_public_event(
    *,
    event_dir: str | Path,
    oedi_zip: str | Path,
    year: int,
    event_id: str,
    county: str,
    reference_customers: float = 4_000_000,
) -> tuple[EventReplay, object, PipelineResult]:
    """Replay a checked-in public event and return evidence plus model output."""
    event_root = Path(event_dir)
    weather_candidates = sorted(event_root.glob("weather_*.csv"))
    if not weather_candidates:
        raise FileNotFoundError(f"no weather_*.csv under {event_root}")
    return run_event_replay(
        oedi_zip=oedi_zip,
        weather_csv=weather_candidates[0],
        year=year,
        event_id=event_id,
        county=county,
        reference_customers=reference_customers,
        output_dir=event_root,
    )


__all__ = [
    "DisasterScenario",
    "EventReplay",
    "GridModel",
    "PipelineResult",
    "build_model",
    "build_ieee33",
    "get_scenario",
    "replay_public_event",
    "run_named_scenario",
    "run_pipeline",
    "run_scenario",
]
