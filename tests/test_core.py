import networkx as nx
import numpy as np

from gridrescue.faults import close_ties_greedily, evaluate_state
from gridrescue.experiments import run_monte_carlo
from gridrescue.network import build_ieee33, graph_from_state, is_radial
from gridrescue.pipeline import run_pipeline
from gridrescue.powerflow import solve_base_case, validate_dispatch
from gridrescue.restoration import simulate_strategy
from gridrescue.scenarios import DisasterScenario, SCENARIOS, sample_fault_scenarios


def test_ieee33_base_is_radial_and_connected():
    model = build_ieee33()
    graph = graph_from_state(model)
    assert graph.number_of_nodes() == 33
    assert graph.number_of_edges() == 32
    assert nx.is_connected(graph)
    assert is_radial(graph)
    assert model.nodes["base_load_kw"].sum() == 3715.0
    assert model.nodes["reactive_load_kvar"].sum() == 2300.0
    assert len(model.tie_branch_ids) == 5
    assert model.base_mva == 10.0
    assert model.base_kv == 12.66
    assert model.source_sha256 == "B40831EEB444669AE876E2996F0DDA9F05CD83E81B314B8DFCA51E4890CCA95D"


def test_case33_impedance_conversion_and_base_powerflow_match_golden_values():
    model = build_ieee33()
    first = model.branches.loc[1]
    assert np.isclose(first["resistance_pu"], 0.0922 / 16.02756, rtol=1e-7)
    assert np.isclose(first["reactance_pu"], 0.0470 / 16.02756, rtol=1e-7)
    base = solve_base_case(model)
    assert base.converged
    assert np.isclose(base.p_loss_kw, 202.6771, atol=0.02)
    assert np.isclose(base.min_voltage_pu, 0.91309, atol=2e-5)
    assert np.isclose(base.slack_p_kw, 3917.6771, atol=0.02)
    assert base.branches["loading_pct"].max() < 100.0


def test_fault_state_and_tie_closure_remain_radial():
    model = build_ieee33()
    failed = {6, 13, 27}
    ties = close_ties_greedily(model, failed, score="critical")
    state = evaluate_state(model, failed, set(ties))
    assert len(state.energized_nodes) >= 1
    assert set(ties).issubset(set(model.tie_branch_ids))


def test_three_strategies_produce_finite_metrics():
    result = run_pipeline("暴雨内涝")
    assert len(result.comparison) == 3
    numeric = result.comparison.select_dtypes(include=["number"])
    assert np.isfinite(numeric.to_numpy()).all()
    assert (result.comparison["critical_recovery_pct"] >= 0).all()
    assert (result.comparison["critical_recovery_pct"] <= 100.001).all()


def test_carbon_strategy_exposes_a_valid_pareto_tradeoff():
    result = run_pipeline("台风")
    values = result.comparison.set_index("strategy")
    assert values.loc["碳韧协同恢复", "total_carbon_kg"] <= values.loc["最小失供恢复", "total_carbon_kg"] + 1e-5
    assert values.loc["碳韧协同恢复", "critical_recovery_pct"] >= values.loc["最小失供恢复", "critical_recovery_pct"] - 1e-5
    assert result.validations["最小失供恢复"].hourly["is_feasible"].all()
    assert result.validations["碳韧协同恢复"].hourly["is_feasible"].all()


def test_scenarios_and_monte_carlo_are_valid():
    assert set(SCENARIOS) == {"暴雨内涝", "台风", "极端高温"}
    samples = sample_fault_scenarios(30)
    assert len(samples) == 30
    assert all(len(s.failed_branch_ids) >= 2 for s in samples)


def test_small_monte_carlo_batch_completes():
    result = run_monte_carlo(2, seed=77, physical=False)
    assert len(result) == 6
    assert set(result["strategy"]) == {"传统顺序恢复", "最小失供恢复", "碳韧协同恢复"}


def test_powerflow_post_validation_is_finite():
    result = run_pipeline("暴雨内涝")
    selected = result.strategies["碳韧协同恢复"]
    validation = validate_dispatch(result.model, result.scenario, selected.plan, selected.dispatch)
    assert len(validation.hourly) == 24
    numeric = validation.hourly.select_dtypes(include=["number"])
    assert np.isfinite(numeric.to_numpy()).all()
    assert (validation.hourly["min_voltage_pu"] > 0.0).all()
    assert (validation.hourly["max_branch_loading_pct"] >= 0).all()
    assert {"thermal_violation", "voltage_violation", "balance_violation", "is_feasible"}.issubset(
        validation.hourly.columns
    )
    assert validation.hourly["is_feasible"].all()
    assert validation.hourly["source_adjustment_kw"].abs().max() < 0.1
    assert selected.dispatch.node_frame is not None
    assert len(selected.dispatch.node_frame) == 24 * 33
    assert np.allclose(
        selected.dispatch.frame["network_loss_kw"],
        validation.hourly["estimated_loss_kw"],
        atol=0.1,
    )


def test_source_free_island_is_a_hard_balance_failure():
    model = build_ieee33()
    scenario = DisasterScenario(
        name="无源孤岛测试",
        description="支路18断开后，19-22节点形成无本地成网电源孤岛。",
        failed_branch_ids=(18,),
        repair_hours=(24,),
        pv_derating=0.5,
        grid_carbon_multiplier=1.0,
        crew_distance_km=1.0,
        ambient_temperature_c=25.0,
    )
    result = simulate_strategy(model, scenario, "传统顺序恢复")
    # The spatial optimizer must de-energize the source-free island rather
    # than silently assigning remote DER output to it.
    spatial = result.dispatch.node_frame
    assert spatial is not None
    island_nodes = {18, 19, 20, 21}
    hour_zero = spatial[(spatial["hour"] == 0) & spatial["node_id"].isin(island_nodes)]
    assert np.isclose(hour_zero["served_load_kw"].sum(), 0.0, atol=1e-4)
    physical = validate_dispatch(model, scenario, result.plan, result.dispatch)
    source_free = physical.components.query("hour == 0 and slack_node == -1")
    assert not source_free.empty
    assert source_free["source_feasible"].all()
    assert np.isclose(source_free["unserved_balance_kw"].sum(), 0.0, atol=1e-6)

    # A legacy aggregate-only schedule still receives a hard failure because
    # it has no spatial evidence for serving those buses.
    validation = validate_dispatch(model, scenario, result.plan, result.dispatch.frame)
    assert validation.hourly.loc[0, "balance_violation"]
    assert validation.hourly.loc[0, "infeasible_island_count"] >= 1
    assert validation.hourly.loc[0, "unserved_balance_kw"] > 0
    island = validation.components.query("hour == 0 and slack_node == -1")
    assert not island.empty
    assert not island["source_feasible"].all()
