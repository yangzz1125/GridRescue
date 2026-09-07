import json

import pytest

from gridrescue.islands import build_island_passports, write_island_passports
from gridrescue.pipeline import run_pipeline


@pytest.fixture(scope="module")
def flood_pipeline():
    return run_pipeline("暴雨内涝")


def test_island_passport_distinguishes_source_free_and_gfm_islands(flood_pipeline):
    strategy = "传统顺序恢复"
    passports = build_island_passports(
        flood_pipeline.model,
        flood_pipeline.scenario,
        flood_pipeline.strategies[strategy],
        flood_pipeline.validations[strategy],
    )

    assert not passports.hourly.empty
    assert not passports.episodes.empty
    assert set(passports.hourly["data_confidence"]) == {"assumed"}
    assert set(passports.hourly["gfm_evidence_level"]) == {"model_assumption_v1"}

    blocked = passports.hourly[passports.hourly["passport_status"] == "BLOCKED"]
    assert not blocked.empty
    assert blocked["blocked_reason_codes"].str.contains("NO_GFM").all()
    assert (blocked["service_load_kw"] <= 1e-3).all()
    assert set(blocked["gfm_status"]).issubset({"none", "grid_following_only"})

    supported = passports.hourly[passports.hourly["passport_status"] != "BLOCKED"]
    assert not supported.empty
    assert set(supported["gfm_status"]) == {"assumed_from_model"}
    assert supported["source_feasible"].all()
    assert supported["powerflow_converged"].all()
    assert (supported["min_voltage_pu"] >= 0.95).all()
    assert (supported["max_loading_pct"] <= 100.0).all()


def test_island_episode_and_export_contract(flood_pipeline, tmp_path):
    strategy = "传统顺序恢复"
    passports = build_island_passports(
        flood_pipeline.model,
        flood_pipeline.scenario,
        flood_pipeline.strategies[strategy],
        flood_pipeline.validations[strategy],
    )
    paths = write_island_passports(passports, tmp_path, "traditional")

    assert set(paths) == {"hourly", "episodes", "summary"}
    assert all(path.exists() for path in paths.values())
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["hourly_rows"] == len(passports.hourly)
    assert summary["episode_count"] == len(passports.episodes)
    assert summary["status_counts"]["BLOCKED"] > 0
    assert passports.hourly["island_episode_id"].notna().all()
    assert (passports.hourly["topology_window_remaining_h"] >= 1).all()


def test_no_nonroot_island_returns_stable_empty_schema(flood_pipeline):
    strategy = "最小失供恢复"
    passports = build_island_passports(
        flood_pipeline.model,
        flood_pipeline.scenario,
        flood_pipeline.strategies[strategy],
        flood_pipeline.validations[strategy],
    )

    assert passports.hourly.empty
    assert passports.episodes.empty
    assert {"passport_status", "gfm_status", "weakest_constraint"}.issubset(
        passports.hourly.columns
    )
