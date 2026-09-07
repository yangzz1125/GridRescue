from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import networkx as nx
import numpy as np
import pandas as pd

from .dispatch import DispatchResult
from .network import GridModel, graph_from_state
from .scenarios import DisasterScenario

if TYPE_CHECKING:
    from .restoration import RestorationPlan


@dataclass(frozen=True)
class FlowValidation:
    hourly: pd.DataFrame
    branches: pd.DataFrame
    nodes: pd.DataFrame
    components: pd.DataFrame


@dataclass(frozen=True)
class SnapshotFlow:
    converged: bool
    iterations: int
    min_voltage_pu: float
    max_voltage_pu: float
    p_loss_kw: float
    q_loss_kvar: float
    slack_p_kw: float
    slack_q_kvar: float
    branches: pd.DataFrame
    nodes: pd.DataFrame


def _node_dispatch(
    model: GridModel,
    dispatch_row: pd.Series,
    *,
    node_frame: pd.DataFrame | None = None,
    hour: int | None = None,
) -> pd.DataFrame:
    """Map aggregate dispatch to buses without hiding spatial residuals."""

    nodes = model.nodes.copy()
    if node_frame is not None:
        if hour is None:
            raise ValueError("hour is required with spatial node dispatch")
        spatial = node_frame[node_frame["hour"] == int(hour)].set_index("node_id")
        if set(spatial.index) != set(nodes.index):
            raise ValueError(f"node dispatch for hour {hour} does not cover every grid node")
        for column in (
            "served_load_kw",
            "served_reactive_kvar",
            "pv_generation_kw",
            "diesel_generation_kw",
            "battery_charge_kw",
            "battery_discharge_kw",
        ):
            nodes[column] = spatial.loc[nodes.index, column].to_numpy(float)
        nodes["controllable_source_kw"] = nodes["diesel_generation_kw"] + nodes["battery_discharge_kw"]
        nodes["controllable_sink_kw"] = nodes["battery_charge_kw"]
        nodes["net_load_kw"] = (
            nodes["served_load_kw"]
            + nodes["battery_charge_kw"]
            - nodes["pv_generation_kw"]
            - nodes["diesel_generation_kw"]
            - nodes["battery_discharge_kw"]
        )
        nodes["net_reactive_kvar"] = nodes["served_reactive_kvar"]
        return nodes

    critical_mask = nodes["critical_level"] >= 2
    critical_base = float(nodes.loc[critical_mask, "base_load_kw"].sum())
    normal_base = float(nodes.loc[~critical_mask, "base_load_kw"].sum())
    critical_multiplier = float(dispatch_row["critical_load_kw"]) / max(critical_base, 1e-9)
    normal_multiplier = float(dispatch_row["normal_load_kw"]) / max(normal_base, 1e-9)
    critical_ratio = min(
        float(dispatch_row["served_critical_kw"]) / max(float(dispatch_row["critical_load_kw"]), 1e-9),
        1.0,
    )
    normal_ratio = min(
        float(dispatch_row["served_normal_kw"]) / max(float(dispatch_row["normal_load_kw"]), 1e-9),
        1.0,
    )
    served_fraction = np.where(
        critical_mask,
        critical_multiplier * critical_ratio,
        normal_multiplier * normal_ratio,
    )
    nodes["served_load_kw"] = nodes["base_load_kw"] * served_fraction
    nodes["served_reactive_kvar"] = nodes["reactive_load_kvar"] * served_fraction

    pv_capacity = float(nodes["pv_capacity_kw"].sum())
    pv_used = max(float(dispatch_row["pv_available_kw"] - dispatch_row["renewable_curtailment_kw"]), 0.0)
    nodes["pv_generation_kw"] = nodes["pv_capacity_kw"] / max(pv_capacity, 1e-9) * pv_used

    diesel_capacity = float(nodes["diesel_capacity_kw"].sum())
    nodes["diesel_generation_kw"] = (
        nodes["diesel_capacity_kw"] / max(diesel_capacity, 1e-9) * float(dispatch_row["diesel_generation_kw"])
    )
    storage_power = float(nodes["storage_power_kw"].sum())
    storage_share = nodes["storage_power_kw"] / max(storage_power, 1e-9)
    nodes["battery_discharge_kw"] = storage_share * float(dispatch_row["battery_discharge_kw"])
    nodes["battery_charge_kw"] = storage_share * float(dispatch_row["battery_charge_kw"])
    nodes["controllable_source_kw"] = nodes["diesel_generation_kw"] + nodes["battery_discharge_kw"]
    nodes["controllable_sink_kw"] = nodes["battery_charge_kw"]
    nodes["net_load_kw"] = (
        nodes["served_load_kw"]
        + nodes["battery_charge_kw"]
        - nodes["pv_generation_kw"]
        - nodes["diesel_generation_kw"]
        - nodes["battery_discharge_kw"]
    )
    nodes["net_reactive_kvar"] = nodes["served_reactive_kvar"]
    return nodes


def _component_slack(model: GridModel, component: set[int]) -> int | None:
    if model.root_node in component:
        return model.root_node
    grid_forming = model.nodes.loc[list(component), ["diesel_capacity_kw", "storage_power_kw"]].sum(axis=1)
    if float(grid_forming.max()) <= 0:
        return None
    return int(grid_forming.idxmax())


def _bfs_power_flow(
    model: GridModel,
    graph: nx.Graph,
    component: set[int],
    slack: int,
    p_net_kw: pd.Series,
    q_net_kvar: pd.Series,
    *,
    slack_voltage_pu: float = 1.0,
    tolerance: float = 1e-9,
    max_iterations: int = 100,
) -> tuple[dict[int, complex], list[dict[str, float]], float, float, bool, int]:
    """Balanced radial backward/forward-sweep power flow in per-unit."""

    tree = nx.bfs_tree(graph.subgraph(component), slack)
    order = list(nx.topological_sort(tree))
    reverse_order = list(reversed(order))
    s_base_kva = model.base_mva * 1000.0
    voltage = {node: complex(slack_voltage_pu, 0.0) for node in component}
    branch_current: dict[tuple[int, int], complex] = {}
    converged = False

    for iteration in range(1, max_iterations + 1):
        previous = voltage.copy()
        node_current: dict[int, complex] = {}
        for node in component:
            if node == slack:
                node_current[node] = 0.0 + 0.0j
                continue
            s_pu = complex(float(p_net_kw.loc[node]), float(q_net_kvar.loc[node])) / s_base_kva
            v = voltage[node] if abs(voltage[node]) > 1e-6 else 1.0 + 0.0j
            node_current[node] = np.conj(s_pu / v)

        accumulated = node_current.copy()
        for node in reverse_order:
            if node == slack:
                continue
            parent = next(tree.predecessors(node))
            current = accumulated[node]
            branch_current[(parent, node)] = current
            accumulated[parent] = accumulated.get(parent, 0.0 + 0.0j) + current

        voltage[slack] = complex(slack_voltage_pu, 0.0)
        for parent in order:
            for child in tree.successors(parent):
                edge = graph.edges[parent, child]
                impedance = complex(float(edge["resistance_pu"]), float(edge["reactance_pu"]))
                voltage[child] = voltage[parent] - impedance * branch_current[(parent, child)]

        error = max(abs(voltage[node] - previous[node]) for node in component)
        if error <= tolerance:
            converged = True
            break

    branch_rows: list[dict[str, float]] = []
    total_p_loss = 0.0
    total_q_loss = 0.0
    for parent in order:
        for child in tree.successors(parent):
            edge = graph.edges[parent, child]
            current = branch_current[(parent, child)]
            sending_kva = voltage[parent] * np.conj(current) * s_base_kva
            current_sq = abs(current) ** 2
            p_loss = current_sq * float(edge["resistance_pu"]) * s_base_kva
            q_loss = current_sq * float(edge["reactance_pu"]) * s_base_kva
            apparent = abs(sending_kva)
            total_p_loss += p_loss
            total_q_loss += q_loss
            branch_rows.append(
                {
                    "branch_id": int(edge["branch_id"]),
                    "from_node": int(parent),
                    "to_node": int(child),
                    "p_flow_kw": float(sending_kva.real),
                    "q_flow_kvar": float(sending_kva.imag),
                    "apparent_flow_kva": apparent,
                    "loading_pct": apparent / float(edge["capacity_kva"]) * 100.0,
                    "p_loss_kw": p_loss,
                    "q_loss_kvar": q_loss,
                }
            )
    return voltage, branch_rows, total_p_loss, total_q_loss, converged, iteration


def solve_base_case(model: GridModel) -> SnapshotFlow:
    """Solve the canonical normally-open-tie base case for regression tests."""

    graph = graph_from_state(model)
    component = set(model.nodes.index)
    voltage, branch_rows, p_loss, q_loss, converged, iterations = _bfs_power_flow(
        model,
        graph,
        component,
        model.root_node,
        model.nodes["base_load_kw"],
        model.nodes["reactive_load_kvar"],
    )
    node_rows = [
        {
            "node_id": int(node),
            "voltage_pu": abs(value),
            "voltage_angle_deg": float(np.degrees(np.angle(value))),
        }
        for node, value in voltage.items()
    ]
    return SnapshotFlow(
        converged=converged,
        iterations=iterations,
        min_voltage_pu=min(abs(value) for value in voltage.values()),
        max_voltage_pu=max(abs(value) for value in voltage.values()),
        p_loss_kw=p_loss,
        q_loss_kvar=q_loss,
        slack_p_kw=float(model.nodes["base_load_kw"].sum() + p_loss),
        slack_q_kvar=float(model.nodes["reactive_load_kvar"].sum() + q_loss),
        branches=pd.DataFrame(branch_rows).round(6),
        nodes=pd.DataFrame(node_rows).sort_values("node_id").reset_index(drop=True).round(6),
    )


def validate_dispatch(
    model: GridModel,
    scenario: DisasterScenario,
    plan: RestorationPlan,
    dispatch: pd.DataFrame | DispatchResult,
    *,
    voltage_min_pu: float = 0.95,
    voltage_max_pu: float = 1.05,
    balance_tolerance_kw: float = 1.0,
    island_q_support_ratio: float = 0.60,
) -> FlowValidation:
    """Validate dispatch with balanced P/Q radial power flow.

    Root-grid losses are supplied by the upstream slack and reported.  An
    island is feasible only when it has a local grid-forming diesel/storage
    resource and the required active/reactive adjustment stays within its
    explicit capability.  Residuals beyond that capability remain unserved;
    no virtual source is inserted.
    """

    from .restoration import state_at_hour

    dispatch_frame = dispatch.frame if isinstance(dispatch, DispatchResult) else dispatch
    node_frame = dispatch.node_frame if isinstance(dispatch, DispatchResult) else None
    hourly_rows: list[dict[str, float | bool]] = []
    branch_rows: list[dict[str, float]] = []
    node_rows: list[dict[str, float | bool]] = []
    component_rows: list[dict[str, float | bool]] = []

    for hour, dispatch_row in dispatch_frame.iterrows():
        state = state_at_hour(model, scenario, plan, int(hour))
        graph = graph_from_state(model, set(state.failed_branch_ids), set(state.closed_tie_ids))
        node_data = _node_dispatch(model, dispatch_row, node_frame=node_frame, hour=int(hour))
        max_loading = 0.0
        min_voltage = 1.0
        max_voltage = 1.0
        total_p_loss = 0.0
        total_q_loss = 0.0
        total_source_adjustment = 0.0
        total_unserved_balance = 0.0
        total_reactive_shortfall = 0.0
        infeasible_islands = 0
        nonconverged_components = 0

        for component_id, component_nodes in enumerate(nx.connected_components(graph), start=1):
            component = set(component_nodes)
            component_key = "-".join(str(node) for node in sorted(component))
            slack = _component_slack(model, component)
            is_root = model.root_node in component
            scheduled_residual = float(node_data.loc[list(component), "net_load_kw"].sum())
            scheduled_q = float(node_data.loc[list(component), "net_reactive_kvar"].sum())
            source_adjustment = 0.0
            unserved_balance = 0.0
            source_capacity = float(dispatch_row["grid_capacity_kw"]) if is_root else 0.0
            q_capacity = model.base_mva * 1000.0 if is_root else 0.0
            source_feasible = True

            if slack is None:
                served_or_output = float(
                    node_data.loc[
                        list(component),
                        [
                            "served_load_kw",
                            "pv_generation_kw",
                            "diesel_generation_kw",
                            "battery_discharge_kw",
                            "battery_charge_kw",
                        ],
                    ]
                    .abs()
                    .to_numpy()
                    .sum()
                )
                source_feasible = (
                    served_or_output <= balance_tolerance_kw
                    and abs(scheduled_residual) <= balance_tolerance_kw
                    and abs(scheduled_q) <= balance_tolerance_kw
                )
                if not source_feasible:
                    unserved_balance = max(scheduled_residual, 0.0)
                    reactive_shortfall = max(scheduled_q, 0.0)
                    infeasible_islands += 1
                else:
                    reactive_shortfall = 0.0
                # A source-free, de-energized island has no meaningful voltage solution.
                for node in component:
                    node_rows.append(
                        {
                            "hour": int(hour),
                            "component_id": component_id,
                            "node_id": int(node),
                            "voltage_pu": 0.0,
                            "net_load_kw": float(node_data.loc[node, "net_load_kw"]),
                            "net_reactive_kvar": float(node_data.loc[node, "net_reactive_kvar"]),
                            "is_slack": False,
                            "energized": False,
                        }
                    )
                component_rows.append(
                    {
                        "hour": int(hour),
                        "component_id": component_id,
                        "component_key": component_key,
                        "is_root_component": False,
                        "slack_node": -1,
                        "node_count": len(component),
                        "source_capacity_kw": 0.0,
                        "required_source_kw": max(scheduled_residual, 0.0),
                        "source_adjustment_kw": 0.0,
                        "unserved_balance_kw": unserved_balance,
                        "reactive_shortfall_kvar": reactive_shortfall,
                        "required_reactive_kvar": max(scheduled_q, 0.0),
                        "reactive_capacity_kvar": 0.0,
                        "source_feasible": source_feasible,
                        "powerflow_converged": False,
                        "p_loss_kw": 0.0,
                        "q_loss_kvar": 0.0,
                        "min_voltage_pu": 0.0,
                        "max_voltage_pu": 0.0,
                        "max_loading_pct": 0.0,
                    }
                )
                total_unserved_balance += unserved_balance
                total_reactive_shortfall += reactive_shortfall
                continue

            p_for_flow = node_data["net_load_kw"].copy()
            expected_source = 0.0
            scheduled_control = 0.0
            source_minimum = 0.0
            if is_root:
                expected_source = float(dispatch_row["grid_import_kw"])
            else:
                scheduled_control = float(
                    node_data.loc[slack, "controllable_source_kw"] - node_data.loc[slack, "controllable_sink_kw"]
                )
                p_for_flow.loc[slack] += scheduled_control
                source_capacity = float(
                    model.nodes.loc[slack, "diesel_capacity_kw"] + model.nodes.loc[slack, "storage_power_kw"]
                )
                source_minimum = -float(model.nodes.loc[slack, "storage_power_kw"])
                component_gfm_capacity = float(
                    model.nodes.loc[list(component), ["diesel_capacity_kw", "storage_power_kw"]]
                    .sum(axis=1)
                    .sum()
                )
                q_capacity = island_q_support_ratio * component_gfm_capacity

            voltage, component_branches, p_loss, q_loss, converged, iterations = _bfs_power_flow(
                model,
                graph,
                component,
                slack,
                p_for_flow,
                node_data["net_reactive_kvar"],
                slack_voltage_pu=1.05 if is_root else 1.0,
            )
            if not converged:
                nonconverged_components += 1
            component_loading = max((row["loading_pct"] for row in component_branches), default=0.0)
            component_min_voltage = min((abs(value) for value in voltage.values()), default=1.0)
            component_max_voltage = max((abs(value) for value in voltage.values()), default=1.0)
            max_loading = max(max_loading, component_loading)
            min_voltage = min(min_voltage, component_min_voltage)
            max_voltage = max(max_voltage, component_max_voltage)
            total_p_loss += p_loss
            total_q_loss += q_loss

            required_source_kw = float(p_for_flow.loc[list(component)].sum() + p_loss)
            required_reactive_kvar = float(scheduled_q + q_loss)
            reactive_shortfall = 0.0
            if is_root:
                source_adjustment = required_source_kw - expected_source
                source_feasible = abs(source_adjustment) <= balance_tolerance_kw
                if not source_feasible:
                    unserved_balance = max(source_adjustment, 0.0)
                    total_unserved_balance += unserved_balance
            else:
                source_adjustment = required_source_kw - scheduled_control
                p_violation = max(required_source_kw - source_capacity, source_minimum - required_source_kw, 0.0)
                reactive_shortfall = max(required_reactive_kvar - q_capacity, 0.0)
                source_feasible = (
                    p_violation <= balance_tolerance_kw
                    and reactive_shortfall <= balance_tolerance_kw
                )
                if not source_feasible:
                    infeasible_islands += 1
                    unserved_balance = max(p_violation, 0.0)
                    total_unserved_balance += unserved_balance
                    total_reactive_shortfall += reactive_shortfall
            total_source_adjustment += abs(source_adjustment)

            for row in component_branches:
                row.update({"hour": int(hour), "component_id": component_id})
                branch_rows.append(row)
            for node, value in voltage.items():
                node_rows.append(
                    {
                        "hour": int(hour),
                        "component_id": component_id,
                        "node_id": int(node),
                        "voltage_pu": abs(value),
                        "voltage_angle_deg": float(np.degrees(np.angle(value))),
                        "net_load_kw": float(p_for_flow.loc[node]),
                        "net_reactive_kvar": float(node_data.loc[node, "net_reactive_kvar"]),
                        "is_slack": node == slack,
                        "energized": True,
                    }
                )
            component_rows.append(
                {
                    "hour": int(hour),
                    "component_id": component_id,
                    "component_key": component_key,
                    "is_root_component": is_root,
                    "slack_node": int(slack),
                    "node_count": len(component),
                    "source_capacity_kw": source_capacity,
                    "required_source_kw": required_source_kw,
                    "source_adjustment_kw": source_adjustment,
                    "unserved_balance_kw": unserved_balance,
                    "required_reactive_kvar": required_reactive_kvar,
                    "reactive_capacity_kvar": q_capacity,
                    "reactive_shortfall_kvar": reactive_shortfall,
                    "source_feasible": source_feasible,
                    "powerflow_converged": converged,
                    "iterations": iterations,
                    "p_loss_kw": p_loss,
                    "q_loss_kvar": q_loss,
                    "min_voltage_pu": component_min_voltage,
                    "max_voltage_pu": component_max_voltage,
                    "max_loading_pct": component_loading,
                }
            )

        thermal_violation = max_loading > 100.0
        voltage_violation = min_voltage < voltage_min_pu or max_voltage > voltage_max_pu
        balance_violation = (
            total_unserved_balance > balance_tolerance_kw
            or total_reactive_shortfall > balance_tolerance_kw
            or infeasible_islands > 0
        )
        is_feasible = not (thermal_violation or voltage_violation or balance_violation or nonconverged_components > 0)
        hourly_rows.append(
            {
                "hour": int(hour),
                "max_branch_loading_pct": max_loading,
                "min_voltage_pu": min_voltage,
                "max_voltage_pu": max_voltage,
                "estimated_loss_kw": total_p_loss,
                "estimated_reactive_loss_kvar": total_q_loss,
                "source_adjustment_kw": total_source_adjustment,
                "slack_adjustment_kw": total_source_adjustment,
                "unserved_balance_kw": total_unserved_balance,
                "reactive_shortfall_kvar": total_reactive_shortfall,
                "infeasible_island_count": infeasible_islands,
                "nonconverged_component_count": nonconverged_components,
                "thermal_violation": thermal_violation,
                "voltage_violation": voltage_violation,
                "balance_violation": balance_violation,
                "is_feasible": is_feasible,
            }
        )

    return FlowValidation(
        hourly=pd.DataFrame(hourly_rows).set_index("hour").round(6),
        branches=pd.DataFrame(branch_rows).round(6),
        nodes=pd.DataFrame(node_rows).round(6),
        components=pd.DataFrame(component_rows).round(6),
    )
