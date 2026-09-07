"""Replay a public weather/outage event through the IEEE-33 study model.

The replay deliberately separates observed evidence from the engineering
translation needed by the synthetic 33-node feeder.  OEDI supplies regional
customer outage and restoration observations; weather supplies a local
forcing profile; branch failures and node impacts remain statistical proxies,
not claimed field telemetry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import numpy as np
import pandas as pd

from .faults import branch_downstream_score
from .network import GridModel, build_ieee33
from .pipeline import PipelineResult, run_scenario
from .real_event_mapping import (
    load_oedi_event_correlated_from_zip,
    map_oedi_event_row,
    outage_fraction_proxy,
)
from .scenarios import DisasterScenario


@dataclass(frozen=True)
class WeatherSummary:
    start: str
    end: str
    rows: int
    max_temperature_c: float
    min_temperature_c: float
    total_precipitation_mm: float
    max_wind_speed_kmh: float
    max_wind_gust_kmh: float
    source_id: str


@dataclass(frozen=True)
class EventReplay:
    event_id: str
    event_type: str
    state: str
    county: str
    fips: str
    event_began: str
    event_restoration: str
    outage_start: str
    outage_end: str
    observed_duration_h: float
    peak_customers: float
    reference_customers: float
    outage_fraction: float
    weather: WeatherSummary
    scenario: DisasterScenario
    mapping_method: str = "regional_statistical_mapping"
    data_class: str = "E_external_aggregate"


def load_weather_csv(path: str | Path) -> pd.DataFrame:
    """Load an hourly weather CSV with the project's stable column contract."""
    frame = pd.read_csv(path)
    required = {"timestamp", "temperature_2m_c", "precipitation_mm", "wind_speed_10m_kmh"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"weather file missing columns: {missing}")
    out = frame.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True)
    if out["timestamp"].isna().any():
        raise ValueError("weather timestamp contains invalid values")
    for column in ("temperature_2m_c", "precipitation_mm", "wind_speed_10m_kmh"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
        if out[column].isna().any():
            raise ValueError(f"weather column {column!r} contains invalid values")
        if column != "temperature_2m_c" and (out[column] < 0).any():
            raise ValueError(f"weather column {column!r} contains negative values")
    if "wind_gusts_10m_kmh" in out:
        out["wind_gusts_10m_kmh"] = pd.to_numeric(out["wind_gusts_10m_kmh"], errors="coerce").fillna(
            out["wind_speed_10m_kmh"]
        )
    else:
        out["wind_gusts_10m_kmh"] = out["wind_speed_10m_kmh"]
    return out.sort_values("timestamp").reset_index(drop=True)


def summarize_weather(frame: pd.DataFrame, *, source_id: str = "Open-Meteo-historical-archive") -> WeatherSummary:
    if frame.empty:
        raise ValueError("weather frame is empty")
    return WeatherSummary(
        start=frame["timestamp"].iloc[0].isoformat(),
        end=frame["timestamp"].iloc[-1].isoformat(),
        rows=int(len(frame)),
        max_temperature_c=float(frame["temperature_2m_c"].max()),
        min_temperature_c=float(frame["temperature_2m_c"].min()),
        total_precipitation_mm=float(frame["precipitation_mm"].sum()),
        max_wind_speed_kmh=float(frame["wind_speed_10m_kmh"].max()),
        max_wind_gust_kmh=float(frame["wind_gusts_10m_kmh"].max()),
        source_id=source_id,
    )


def select_event_row(
    frame: pd.DataFrame,
    *,
    event_id: str,
    county: str | None = None,
) -> pd.Series:
    """Select the peak outage interval for one published event/county."""
    required = {"event_id", "state_event", "Datetime Event Began", "Datetime Restoration", "Event Type", "state", "county", "fips", "start_time", "end_time", "duration", "max_customers"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"event frame missing columns: {missing}")
    selected = frame[frame["event_id"].astype(str) == str(event_id)]
    if county is not None:
        selected = selected[selected["county"].astype(str).str.casefold() == county.casefold()]
    if selected.empty:
        raise ValueError(f"event not found: {event_id!r} county={county!r}")
    return selected.sort_values(["max_customers", "duration"], ascending=False).iloc[0].copy()


def _proxy_branch_failures(model: GridModel, outage_fraction: float) -> tuple[int, ...]:
    """Translate regional severity to deterministic high-impact branches."""
    # Keep the public regional severity translation inside the solvable
    # envelope of the 24-hour IEEE-33 replay.  The largest root-side branches
    # are intentionally excluded: a regional customer fraction is not proof
    # that the feeder head failed.
    count = 2 if outage_fraction < 0.15 else 3 if outage_fraction < 0.30 else 4
    candidates = [branch for branch in model.base_branch_ids if branch > 3]
    ranked = sorted(candidates, key=lambda branch: branch_downstream_score(model, branch), reverse=True)
    return tuple(sorted(ranked[:count]))


def build_replay(
    event_row: pd.Series,
    weather: pd.DataFrame,
    *,
    reference_customers: float,
    model: GridModel | None = None,
    weather_source_id: str = "Open-Meteo-historical-archive",
) -> tuple[EventReplay, pd.DataFrame]:
    """Build a replay manifest and 33-node statistical mapping from evidence."""
    model = model or build_ieee33()
    weather_summary = summarize_weather(weather, source_id=weather_source_id)
    peak = float(event_row["max_customers"])
    fraction = outage_fraction_proxy(peak, reference_customers=reference_customers)
    failed = _proxy_branch_failures(model, fraction)
    observed_duration = float(event_row["duration"])
    per_branch = max(1, int(round(min(observed_duration, 24.0) / len(failed))))
    precip_factor = min(weather_summary.total_precipitation_mm / 80.0, 0.45)
    wind_factor = min(weather_summary.max_wind_gust_kmh / 180.0, 0.30)
    pv_derating = float(np.clip(0.88 - precip_factor - wind_factor, 0.15, 0.90))
    carbon_multiplier = float(np.clip(1.0 + max(weather_summary.max_temperature_c - 20.0, 0.0) / 120.0, 0.95, 1.25))
    scenario = DisasterScenario(
        name=f"real-{event_row['event_id']}-{event_row['fips']}",
        description=(
            f"Public event {event_row['event_id']} ({event_row['Event Type']}) in "
            f"{event_row['state']}/{event_row['county']}; branch failures are a "
            "deterministic 33-node severity proxy, not line telemetry."
        ),
        failed_branch_ids=failed,
        repair_hours=tuple(per_branch for _ in failed),
        pv_derating=pv_derating,
        grid_carbon_multiplier=carbon_multiplier,
        crew_distance_km=float(20.0 + 80.0 * fraction),
        ambient_temperature_c=weather_summary.max_temperature_c,
    )
    mapped = map_oedi_event_row(
        model,
        event_row,
        reference_customers=reference_customers,
        source_id=f"OEDI-EAGLEI-EVENT:{event_row['event_id']}",
    )
    if not mapped["node_weight"].between(0.0, 1.0).all():
        raise ValueError("node mapping weights must be in [0, 1]")
    if not mapped["outage_fraction"].between(0.0, 1.0).all():
        raise ValueError("node mapping outage fraction must be in [0, 1]")
    expected_unserved = mapped["base_load_kw"] * mapped["outage_fraction"]
    if not np.allclose(mapped["estimated_unserved_kw"], expected_unserved, atol=1e-6):
        raise ValueError("node mapping unserved load equation failed")
    replay = EventReplay(
        event_id=str(event_row["event_id"]),
        event_type=str(event_row["Event Type"]),
        state=str(event_row["state"]),
        county=str(event_row["county"]),
        fips=str(event_row["fips"]),
        event_began=pd.Timestamp(event_row["Datetime Event Began"]).isoformat(),
        event_restoration=pd.Timestamp(event_row["Datetime Restoration"]).isoformat(),
        outage_start=pd.Timestamp(event_row["start_time"]).isoformat(),
        outage_end=pd.Timestamp(event_row["end_time"]).isoformat(),
        observed_duration_h=observed_duration,
        peak_customers=peak,
        reference_customers=float(reference_customers),
        outage_fraction=fraction,
        weather=weather_summary,
        scenario=scenario,
    )
    return replay, mapped


def run_event_replay(
    *,
    oedi_zip: str | Path,
    weather_csv: str | Path,
    year: int,
    event_id: str,
    county: str,
    reference_customers: float,
    output_dir: str | Path | None = None,
) -> tuple[EventReplay, pd.DataFrame, PipelineResult]:
    """Execute one real-event case through all three restoration strategies."""
    frame = load_oedi_event_correlated_from_zip(oedi_zip, year=year)
    row = select_event_row(frame, event_id=event_id, county=county)
    weather = load_weather_csv(weather_csv)
    replay, mapped = build_replay(
        row,
        weather,
        reference_customers=reference_customers,
        weather_source_id="Open-Meteo-historical-archive",
    )
    result = run_scenario(replay.scenario)
    if output_dir is not None:
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        payload = asdict(replay)
        payload["scenario"] = asdict(replay.scenario)
        payload["weather"] = asdict(replay.weather)
        payload["strategy_order"] = list(result.strategies)
        (target / "replay_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        mapped.to_csv(target / "node_mapping.csv", index=False)
        result.comparison.to_csv(target / "strategy_comparison.csv", index=False)
        metrics_rows = [
            {"strategy": name, **result.strategies[name].metrics.__dict__}
            for name in result.strategies
        ]
        pd.DataFrame(metrics_rows).to_csv(
            target / "strategy_metrics.csv", index=False
        )
    return replay, mapped, result
