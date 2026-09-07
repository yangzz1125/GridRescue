import json

import numpy as np

import gridrescue.experiments as experiments


def test_monte_carlo_records_all_strategy_rows_when_a_physical_scenario_fails(monkeypatch):
    def broken_pipeline(_scenario):
        raise RuntimeError("synthetic physical pipeline failure")

    monkeypatch.setattr(experiments, "run_scenario", broken_pipeline)
    results = experiments.run_monte_carlo(2, seed=91, physical=True)

    assert len(results) == 2 * len(experiments.STRATEGIES)
    assert not results["solve_success"].any()
    assert set(results["failure_phase"]) == {"physical_pipeline"}
    assert results["failure_reason"].str.contains("RuntimeError: synthetic physical pipeline failure").all()
    assert results["physical_feasible_hours"].isna().all()
    assert results["scenario_definition"].map(json.loads).map(lambda item: "failed_branch_ids" in item).all()


def test_dispatch_only_batch_isolates_one_strategy_failure(monkeypatch):
    original = experiments.simulate_strategy

    def broken_one_strategy(model, scenario, strategy, **kwargs):
        if strategy == "最小失供恢复":
            raise ValueError("synthetic strategy failure")
        return original(model, scenario, strategy, **kwargs)

    monkeypatch.setattr(experiments, "simulate_strategy", broken_one_strategy)
    results = experiments.run_monte_carlo(1, seed=92, physical=False)

    failed = results.loc[~results["solve_success"]]
    assert failed["strategy"].tolist() == ["最小失供恢复"]
    assert failed["failure_phase"].tolist() == ["strategy_simulation"]
    assert "ValueError: synthetic strategy failure" in failed["failure_reason"].iloc[0]
    assert results.loc[results["solve_success"], "physical_feasible_hours"].isna().all()


def test_summary_excludes_failures_from_metric_means_and_adds_confidence_intervals():
    results = experiments.run_monte_carlo(3, seed=93, physical=False)
    # Deliberately corrupt one result to verify that zero/NA is not folded into
    # the reliability metrics while it remains visible in solve accounting.
    results.loc[results.index[0], "solve_success"] = False
    results.loc[results.index[0], "failure_reason"] = "synthetic post-processing failure"
    results.loc[results.index[0], "eens_kwh"] = np.nan

    summary = experiments.summarize(results, bootstrap_samples=100, seed=93)
    row = summary.set_index("strategy").loc[results.iloc[0]["strategy"]]
    assert row["attempt_count"] == 3
    assert row["solved_count"] == 2
    assert row["failed_count"] == 1
    assert 0 <= row["solve_success_rate_ci_lower"] <= row["solve_success_rate"] <= row["solve_success_rate_ci_upper"] <= 1
    assert row["eens_kwh_n"] == 2
    assert row["eens_kwh_ci_lower"] <= row["eens_kwh_mean"] <= row["eens_kwh_ci_upper"]
    assert row["physical_feasible_hours_n"] == 0


def test_failure_manifest_replays_exact_scenario_definition(tmp_path, monkeypatch):
    original = experiments.simulate_strategy

    def broken_one_strategy(model, scenario, strategy, **kwargs):
        if strategy == "传统顺序恢复":
            raise RuntimeError("forced replay fixture")
        return original(model, scenario, strategy, **kwargs)

    monkeypatch.setattr(experiments, "simulate_strategy", broken_one_strategy)
    failed_batch = experiments.run_monte_carlo(1, seed=94, physical=False)
    manifest_path = experiments.write_failure_manifest(failed_batch, tmp_path / "failures.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == experiments.REPLAY_SCHEMA_VERSION
    assert len(manifest["failed_scenarios"]) == 1
    saved_case = manifest["failed_scenarios"][0]
    assert saved_case["failures"][0]["strategy"] == "传统顺序恢复"

    # Restore normal behavior before replay; the saved scenario definition, not
    # a rerun of the batch RNG, is the replay input.
    monkeypatch.setattr(experiments, "simulate_strategy", original)
    replay = experiments.replay_failure_manifest(manifest_path, scenario_id=saved_case["scenario_id"], physical=False)
    assert replay["solve_success"].all()
    assert replay["scenario_definition"].nunique() == 1
    assert replay["scenario_definition"].iloc[0] == failed_batch["scenario_definition"].iloc[0]
