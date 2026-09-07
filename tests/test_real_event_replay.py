import json

import pandas as pd

from gridrescue.real_event_replay import (
    build_replay,
    load_weather_csv,
    select_event_row,
    summarize_weather,
)
from pathlib import Path


def _event_frame():
    return pd.DataFrame([{
        "event_id": "Texas-1", "state_event": "Texas",
        "Datetime Event Began": "2021-02-10 15:00:00",
        "Datetime Restoration": "2021-02-23 15:00:00",
        "Event Type": "Severe Weather", "fips": "48201", "state": "Texas",
        "county": "Harris", "start_time": "2021-02-16 06:15:00",
        "duration": 39.25, "end_time": "2021-02-17 21:30:00",
        "min_customers": 2908, "max_customers": 455986,
        "mean_customers": 299223.15,
    }])


def test_weather_summary_and_replay_mapping(tmp_path):
    weather_path = tmp_path / "weather.csv"
    pd.DataFrame([
        {"timestamp": "2021-02-16T00:00:00Z", "temperature_2m_c": -2.0, "precipitation_mm": 1.0, "wind_speed_10m_kmh": 20.0},
        {"timestamp": "2021-02-16T01:00:00Z", "temperature_2m_c": 1.0, "precipitation_mm": 3.0, "wind_speed_10m_kmh": 35.0},
    ]).to_csv(weather_path, index=False)
    weather = load_weather_csv(weather_path)
    summary = summarize_weather(weather)
    assert summary.rows == 2
    assert summary.total_precipitation_mm == 4.0
    row = select_event_row(_event_frame(), event_id="Texas-1", county="Harris")
    replay, mapped = build_replay(row, weather, reference_customers=4_000_000)
    assert replay.outage_fraction == 455986 / 4_000_000
    assert replay.scenario.name == "real-Texas-1-48201"
    assert len(replay.scenario.failed_branch_ids) == 2
    assert len(mapped) == 33
    assert mapped["data_class"].eq("E_external_aggregate").all()


def test_event_002_artifacts_and_cross_event_comparison():
    root = Path(__file__).resolve().parents[1]
    event = root / "data" / "events" / "event_002"
    assert (event / "replay_manifest.json").exists()
    comparison = pd.read_csv(root / "data" / "events" / "real_event_comparison.csv")
    assert set(comparison["event_id"]) == {"Texas-1", "California-16"}
    assert len(comparison) == 6
    assert comparison["strategy"].nunique() == 3
