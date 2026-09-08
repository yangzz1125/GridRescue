from __future__ import annotations

from dataclasses import dataclass, replace

import networkx as nx
import pandas as pd

from .carbon import CarbonBreakdown, calculate_carbon
from .dispatch import (
    DispatchObjective,
    DispatchResult,
    DispatchWeights,
    ResourceConfig,
    ServiceContract,
    dispatch_resources_spatial,
)
from .faults import FaultState, branch_downstream_score, close_ties_greedily, evaluate_state
from .metrics import RecoveryMetrics, calculate_metrics
from .network import GridModel
from .report import markdown_report
from .scenarios import DisasterScenario, hourly_profiles


STRATEGIES = ("传统顺序恢复", "最小失供恢复", "碳韧协同恢复")


@dataclass(frozen=True)
class RestorationPlan:
    strategy: str
    repair_order: tuple[int, ...]
    repair_completed_at: dict[int, int]
    initial_tie_ids: tuple[int, ...]
    actions: pd.DataFrame


@dataclass(frozen=True)
class StrategyResult:
    plan: RestorationPlan
    demand: pd.DataFrame
    dispatch: DispatchResult
    carbon: CarbonBreakdown
    metrics: RecoveryMetrics
    report: str


def _repair_duration_map(scenario: DisasterScenario) -> dict[int, int]:
    return dict(zip(scenario.failed_branch_ids, scenario.repair_hours, strict=True))


def make_plan(model: GridModel, scenario: DisasterScenario, strategy: str) -> RestorationPlan:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    durations = _repair_duration_map(scenario)
    if strategy == "传统顺序恢复":
        repair_order = tuple(scenario.failed_branch_ids)
        tie_ids: tuple[int, ...] = ()
    elif strategy == "最小失供恢复":
        repair_order = tuple(
            sorted(
                scenario.failed_branch_ids,
                key=lambda branch: branch_downstream_score(model, branch) / durations[branch],
                reverse=True,
            )
        )
        tie_ids = close_ties_greedily(model, scenario.failed_branch_ids, score="load")
    else:
        # Keep the physical restoration sequence identical to the minimum-EENS
        # benchmark. Carbon differences then come from resource dispatch and
        # service-level choices rather than a hidden topology advantage.
        repair_order = tuple(
            sorted(
                scenario.failed_branch_ids,
                key=lambda branch: branch_downstream_score(model, branch) / durations[branch],
                reverse=True,
            )
        )
        tie_ids = close_ties_greedily(model, scenario.failed_branch_ids, score="load")

    elapsed = 0
    completion: dict[int, int] = {}
    action_rows: list[dict[str, object]] = []
    for tie_id in tie_ids:
        action_rows.append({"hour": 0, "action": f"闭合联络开关 T{tie_id}"})
    for branch_id in repair_order:
        elapsed += durations[branch_id]
        completion[branch_id] = min(elapsed, 24)
        action_rows.append({"hour": min(elapsed, 24), "action": f"修复支路 L{branch_id}"})
    actions = pd.DataFrame(action_rows, columns=["hour", "action"])
    return RestorationPlan(strategy, repair_order, completion, tie_ids, actions)


def _safe_ties(model: GridModel, failed: set[int], candidates: tuple[int, ...]) -> tuple[int, ...]:
    chosen: list[int] = []
    for tie_id in candidates:
        try:
            evaluate_state(model, failed, set(chosen) | {tie_id})
        except ValueError:
            continue
        chosen.append(tie_id)
    return tuple(chosen)


def state_at_hour(
    model: GridModel,
    scenario: DisasterScenario,
    plan: RestorationPlan,
    hour: int,
) -> FaultState:
    failed = {
        branch_id
        for branch_id in scenario.failed_branch_ids
        if plan.repair_completed_at[branch_id] > int(hour)
    }
    ties = _safe_ties(model, failed, plan.initial_tie_ids)
    return evaluate_state(model, failed, ties)


def build_demand_frame(
    model: GridModel,
    scenario: DisasterScenario,
    plan: RestorationPlan,
    network_loss_kw: pd.Series | None = None,
) -> pd.DataFrame:
    profiles = hourly_profiles(scenario)
    critical_nodes = model.nodes[model.nodes["critical_level"] >= 2]
    normal_nodes = model.nodes[model.nodes["critical_level"] < 2]
    base_critical = float(critical_nodes["base_load_kw"].sum())
    base_normal = float(normal_nodes["base_load_kw"].sum())
    total_pv = float(model.nodes["pv_capacity_kw"].sum())
    rows: list[dict[str, float]] = []
    loss_profile = (
        pd.Series(0.0, index=range(24), dtype=float)
        if network_loss_kw is None
        else pd.Series(network_loss_kw, dtype=float).reindex(range(24), fill_value=0.0)
    )

    for hour, profile in profiles.iterrows():
        state = state_at_hour(model, scenario, plan, int(hour))
        failed = set(state.failed_branch_ids)
        ties = tuple(state.closed_tie_ids)
        connected_load = float(model.nodes.loc[list(state.energized_nodes), "base_load_kw"].sum())
        multiplier = float(profile["load_multiplier"])
        rows.append(
            {
                "hour": int(hour),
                "critical_load_kw": base_critical * multiplier,
                "normal_load_kw": base_normal * multiplier,
                "pv_available_kw": total_pv * float(profile["pv_multiplier"]),
                "grid_carbon_kg_per_kwh": float(profile["grid_carbon_kg_per_kwh"]),
                "network_loss_kw": max(float(loss_profile.loc[int(hour)]), 0.0),
                "grid_capacity_kw": connected_load * multiplier * 1.04,
                "energized_node_count": float(len(state.energized_nodes)),
                "island_count": float(len(state.islands)),
                "active_fault_count": float(len(failed)),
                "closed_tie_count": float(len(ties)),
            }
        )
    return pd.DataFrame(rows).set_index("hour").round(5)


def build_node_demand_frame(
    model: GridModel,
    scenario: DisasterScenario,
    plan: RestorationPlan,
) -> pd.DataFrame:
    """Build hourly nodal demand/resource records with stable component keys."""

    profiles = hourly_profiles(scenario)
    rows: list[dict[str, float | int | str | bool]] = []
    for hour, profile in profiles.iterrows():
        state = state_at_hour(model, scenario, plan, int(hour))
        from .network import graph_from_state

        graph = graph_from_state(model, set(state.failed_branch_ids), set(state.closed_tie_ids))
        components = sorted((set(nodes) for nodes in nx.connected_components(graph)), key=min)
        component_by_node: dict[int, tuple[str, bool]] = {}
        for component in components:
            key = "-".join(str(node) for node in sorted(component))
            is_root = model.root_node in component
            for node in component:
                component_by_node[int(node)] = (key, is_root)

        multiplier = float(profile["load_multiplier"])
        pv_multiplier = float(profile["pv_multiplier"])
        for node, node_row in model.nodes.iterrows():
            base_p = float(node_row["base_load_kw"])
            base_q = float(node_row["reactive_load_kvar"])
            critical = int(node_row["critical_level"]) >= 2
            node_type = str(node_row["node_type"])
            if "医院" in node_type:
                service_class = "hospital"
            elif int(node_row["critical_level"]) >= 3:
                service_class = "essential"
            elif critical:
                service_class = "critical"
            else:
                service_class = "normal"
            component_key, is_root = component_by_node[int(node)]
            rows.append(
                {
                    "hour": int(hour),
                    "node_id": int(node),
                    "component_key": component_key,
                    "is_root_component": is_root,
                    "service_class": service_class,
                    "is_hospital": service_class == "hospital",
                    "is_essential": service_class != "normal",
                    "critical_load_kw": base_p * multiplier if critical else 0.0,
                    "normal_load_kw": base_p * multiplier if not critical else 0.0,
                    "reactive_ratio": base_q / base_p if base_p > 0 else 0.0,
                    "pv_available_kw": float(node_row["pv_capacity_kw"]) * pv_multiplier,
                    "diesel_capacity_kw": float(node_row["diesel_capacity_kw"]),
                    "storage_power_kw": float(node_row["storage_power_kw"]),
                    "storage_energy_kwh": float(node_row["storage_energy_kwh"]),
                }
            )
    return pd.DataFrame(rows).round(6)


def strategy_weights(strategy: str) -> DispatchWeights:
    if strategy == "传统顺序恢复":
        return DispatchWeights(carbon=0.05, diesel_energy=0.25, renewable_curtailment=0.05)
    if strategy == "最小失供恢复":
        return DispatchWeights(carbon=0.25, diesel_energy=0.55, renewable_curtailment=0.15)
    if strategy == "碳韧协同恢复":
        # Preserve critical services while allowing non-critical demand to be
        # deferred when serving it would require carbon-intensive emergency
        # diesel. This exposes the resilience/carbon Pareto trade-off instead
        # of falsely treating every restored kWh as an avoided emission.
        return DispatchWeights(
            critical_unserved=320.0,
            normal_unserved=5.5,
            carbon=8.0,
            diesel_energy=5.0,
            renewable_curtailment=2.0,
        )
    raise ValueError(strategy)


def simulate_strategy(
    model: GridModel,
    scenario: DisasterScenario,
    strategy: str,
    resources: ResourceConfig = ResourceConfig(),
    node_loss_kw: pd.Series | None = None,
    node_q_loss_kvar: pd.Series | None = None,
    component_served_caps_kw: dict[tuple[int, str], float] | None = None,
    critical_unserved_limit_kwh: float | None = None,
    normal_unserved_limit_kwh: float | None = None,
    service_contract: ServiceContract | None = None,
    dispatch_objective: DispatchObjective | None = None,
) -> StrategyResult:
    plan = make_plan(model, scenario, strategy)
    aggregate_loss = None
    if node_loss_kw is not None:
        aggregate_loss = pd.Series(node_loss_kw, dtype=float).groupby(level=0).sum()
    demand = build_demand_frame(model, scenario, plan, network_loss_kw=aggregate_loss)
    node_demand = build_node_demand_frame(model, scenario, plan)
    weights = strategy_weights(strategy)
    constrained_solve = service_contract is not None or dispatch_objective is not None
    if strategy == "碳韧协同恢复" and not constrained_solve:
        # First find the physically minimal unserved demand for this network
        # state. The carbon run may defer up to an additional 8% of normal
        # energy, keeping the comparison on a transparent Pareto frontier.
        service_first = dispatch_resources_spatial(
            demand,
            node_demand,
            demand["grid_capacity_kw"],
            config=resources,
            weights=strategy_weights("最小失供恢复"),
            node_loss_kw=node_loss_kw,
            node_q_loss_kvar=node_q_loss_kvar,
            component_served_caps_kw=component_served_caps_kw,
        ).frame
        minimum_critical_unserved = (
            float(service_first["unserved_critical_kw"].sum())
            if critical_unserved_limit_kwh is None
            else float(critical_unserved_limit_kwh)
        )
        minimum_normal_unserved = (
            float(service_first["unserved_normal_kw"].sum())
            if normal_unserved_limit_kwh is None
            else float(normal_unserved_limit_kwh)
        )
        allowance = 0.08 * float(demand["normal_load_kw"].sum())
        weights = replace(
            weights,
            max_critical_unserved_kwh=minimum_critical_unserved + 1e-4,
            max_normal_unserved_kwh=(
                minimum_normal_unserved + allowance
                if normal_unserved_limit_kwh is None
                else minimum_normal_unserved
            ),
        )
    dispatch = dispatch_resources_spatial(
        demand,
        node_demand,
        demand["grid_capacity_kw"],
        config=resources,
        weights=weights,
        node_loss_kw=node_loss_kw,
        node_q_loss_kvar=node_q_loss_kvar,
        component_served_caps_kw=component_served_caps_kw,
        contract=service_contract,
        objective=dispatch_objective,
    )
    carbon = calculate_carbon(dispatch.frame, scenario.crew_distance_km)
    metrics = calculate_metrics(dispatch.frame, carbon, len(plan.actions))
    report = markdown_report(scenario, strategy, metrics, carbon, plan.actions)
    return StrategyResult(plan, demand, dispatch, carbon, metrics, report)
