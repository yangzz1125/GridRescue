import json

import numpy as np

import gridrescue.pareto as pareto
from gridrescue.care import CareTask
from gridrescue.network import build_ieee33
from gridrescue.restoration import build_node_demand_frame, make_plan
from gridrescue.scenarios import get_scenario


def test_node_demand_contains_stable_service_classes():
    model = build_ieee33()
    scenario = get_scenario("暴雨内涝")
    plan = make_plan(model, scenario, "最小失供恢复")
    demand = build_node_demand_frame(model, scenario, plan)

    assert set(demand["service_class"]) == {"hospital", "essential", "critical", "normal"}
    hospital_nodes = set(demand.loc[demand["service_class"] == "hospital", "node_id"])
    assert hospital_nodes == {2, 17}
    assert demand.loc[demand["service_class"] == "hospital", "is_essential"].all()
    assert not demand.loc[demand["service_class"] == "normal", "is_essential"].any()


def test_same_service_pareto_scan_is_physical_and_auditable(tmp_path):
    result = pareto.scan_pareto(
        "暴雨内涝",
        pareto.ParetoScanSpec(
            strategies=("最小失供恢复",),
            normal_allowance_fractions=(0.0, 0.04),
            output_dir=tmp_path,
        ),
    )

    assert len(result.anchors) == 3
    assert result.anchors["solve_success"].all()
    assert result.anchors["feedback_converged"].all()
    assert result.anchors["feedback_residual_kw"].max() < 0.1
    assert len(result.points) == 2
    assert result.points["solve_success"].all()
    assert result.points["contract_pass"].all()
    assert result.points["care_contract_pass"].all()
    assert (result.points["care_completed_count"] == 4).all()
    assert (result.points["care_tier1_completed"] == 2).all()
    assert result.points["physical_pass"].all()
    assert (result.points["physical_feasible_hours"] == 24).all()
    assert result.points["max_source_adjustment_kw"].max() < 0.1
    assert len(result.frontier) == 2
    assert result.failures.empty

    ordered = result.frontier.sort_values("normal_allowance_fraction")
    assert ordered.iloc[0]["point_kind"] == "service_anchor"
    assert ordered.iloc[-1]["normal_eens_kwh"] >= ordered.iloc[0]["normal_eens_kwh"]
    assert ordered.iloc[-1]["total_carbon_kg"] <= ordered.iloc[0]["total_carbon_kg"]
    assert np.all(
        ordered["hospital_eens_kwh"]
        <= ordered["hospital_eens_cap_kwh"] + 0.02
    )
    assert np.all(
        ordered["other_essential_eens_kwh"]
        <= ordered["other_essential_eens_cap_kwh"] + 0.02
    )

    manifest = json.loads((tmp_path / "pareto_manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"] == {
        "anchors": 3,
        "points": 2,
        "frontier": 2,
        "failures": 0,
        "care_evaluations": 8,
    }
    assert manifest["network_source_sha256"] == build_ieee33().source_sha256
    assert manifest["schema_version"] == 2
    assert len(manifest["spec"]["care_tasks"]) == 4
    assert (tmp_path / "care_task_definitions.json").exists()
    assert (tmp_path / "pareto_care_task_evaluations.csv").exists()
    assert len(result.care_evaluations) == 8
    assert result.care_evaluations["task_complete"].all()


def test_pareto_keeps_failed_epsilon_rows(monkeypatch):
    def broken_solver(*_args, **_kwargs):
        raise RuntimeError("synthetic anchor failure")

    monkeypatch.setattr(pareto, "solve_strategy_with_feedback", broken_solver)
    result = pareto.scan_pareto(
        "暴雨内涝",
        pareto.ParetoScanSpec(
            strategies=("最小失供恢复",),
            normal_allowance_fractions=(0.0, 0.04),
        ),
    )

    assert len(result.points) == 2
    assert not result.points["solve_success"].any()
    assert set(result.points["failure_phase"]) == {"hospital_anchor"}
    assert result.points["failure_reason"].str.contains("synthetic anchor failure").all()
    assert result.frontier.empty
    assert len(result.failures) == 2


def test_impossible_care_task_is_an_auditable_anchor_failure():
    impossible = CareTask(
        task_id="IMPOSSIBLE_ICU",
        name="synthetic impossible task",
        node_id=2,
        tier=1,
        min_kw=10000.0,
        start_hour=0,
        end_hour=0,
        deadline_hour=0,
        min_duration_h=1,
    )
    result = pareto.scan_pareto(
        "暴雨内涝",
        pareto.ParetoScanSpec(
            strategies=("最小失供恢复",),
            normal_allowance_fractions=(0.0, 0.04),
            care_tasks=(impossible,),
        ),
    )

    assert len(result.points) == 2
    assert not result.points["solve_success"].any()
    assert set(result.points["failure_phase"]) == {"hospital_anchor"}
    assert result.points["failure_reason"].str.contains(
        "care-task demand exceeds critical-load envelope"
    ).all()
    assert result.frontier.empty
