from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
import pandas as pd

from .carbon import DEFAULT_EMISSION_FACTORS, EmissionFactors


@dataclass(frozen=True)
class ResourceConfig:
    battery_capacity_kwh: float = 900.0
    battery_power_kw: float = 280.0
    initial_soc: float = 0.72
    min_soc: float = 0.12
    efficiency: float = 0.94
    diesel_capacity_kw: float = 520.0
    diesel_min_loading: float = 0.0


@dataclass(frozen=True)
class DispatchWeights:
    critical_unserved: float = 220.0
    normal_unserved: float = 42.0
    diesel_energy: float = 1.8
    grid_energy: float = 0.25
    carbon: float = 1.0
    battery_throughput: float = 0.025
    renewable_curtailment: float = 0.45
    max_critical_unserved_kwh: float | None = None
    max_normal_unserved_kwh: float | None = None


@dataclass(frozen=True)
class ServiceTaskRequirement:
    task_id: str
    node_id: int
    start_hour: int
    end_hour: int
    min_kw: float


@dataclass(frozen=True)
class ServiceContract:
    """Hard service and carbon limits for a constrained dispatch candidate.

    All energy quantities are horizon totals. ``crew_emissions_kg`` is a
    fixed scenario/plan term so ``carbon_cap_kg`` uses the same operational
    boundary as :func:`gridrescue.carbon.calculate_carbon`.
    """

    hospital_unserved_cap_kwh: float | None = None
    other_essential_unserved_cap_kwh: float | None = None
    normal_unserved_cap_kwh: float | None = None
    carbon_cap_kg: float | None = None
    crew_emissions_kg: float = 0.0
    tolerance_kwh: float = 1e-4
    task_requirements: tuple[ServiceTaskRequirement, ...] = ()


@dataclass(frozen=True)
class DispatchObjective:
    """Primary objective used by the lexicographic/Pareto solve path."""

    kind: str = "weighted"
    secondary_weight: float = 1e-7


@dataclass(frozen=True)
class DispatchResult:
    frame: pd.DataFrame
    status: str
    objective: float
    node_frame: pd.DataFrame | None = None


def dispatch_resources(
    demand: pd.DataFrame,
    grid_capacity_kw: np.ndarray | pd.Series,
    config: ResourceConfig = ResourceConfig(),
    weights: DispatchWeights = DispatchWeights(),
    emission_factors: EmissionFactors = DEFAULT_EMISSION_FACTORS,
) -> DispatchResult:
    """Dispatch grid, PV, storage and diesel during a restoration horizon.

    ``demand`` must contain ``critical_load_kw``, ``normal_load_kw``,
    ``pv_available_kw`` and ``grid_carbon_kg_per_kwh``. Optional
    ``network_loss_kw`` is a non-flexible auxiliary demand obtained from the
    previous P/Q power-flow iteration.
    """

    required = {
        "critical_load_kw",
        "normal_load_kw",
        "pv_available_kw",
        "grid_carbon_kg_per_kwh",
    }
    missing = required.difference(demand.columns)
    if missing:
        raise ValueError(f"demand frame missing columns: {sorted(missing)}")
    n = len(demand)
    if n < 1:
        raise ValueError("demand frame must be non-empty")
    grid_cap = np.asarray(grid_capacity_kw, dtype=float).reshape(-1)
    if len(grid_cap) != n:
        raise ValueError("grid capacity length must match demand horizon")

    critical = demand["critical_load_kw"].to_numpy(float)
    normal = demand["normal_load_kw"].to_numpy(float)
    pv = demand["pv_available_kw"].to_numpy(float)
    carbon_factor = demand["grid_carbon_kg_per_kwh"].to_numpy(float)
    network_loss = (
        demand["network_loss_kw"].to_numpy(float)
        if "network_loss_kw" in demand.columns
        else np.zeros(n, dtype=float)
    )
    if (network_loss < -1e-9).any():
        raise ValueError("network_loss_kw must be non-negative")

    served_critical = cp.Variable(n, nonneg=True)
    served_normal = cp.Variable(n, nonneg=True)
    grid = cp.Variable(n, nonneg=True)
    diesel = cp.Variable(n, nonneg=True)
    charge = cp.Variable(n, nonneg=True)
    discharge = cp.Variable(n, nonneg=True)
    curtail = cp.Variable(n, nonneg=True)
    soc = cp.Variable(n + 1)

    constraints = [
        served_critical <= critical,
        served_normal <= normal,
        grid <= np.clip(grid_cap, 0, None),
        diesel <= config.diesel_capacity_kw,
        charge <= config.battery_power_kw,
        discharge <= config.battery_power_kw,
        curtail <= pv,
        soc[0] == config.initial_soc * config.battery_capacity_kwh,
        soc[1:] == soc[:-1] + config.efficiency * charge - discharge / config.efficiency,
        soc >= config.min_soc * config.battery_capacity_kwh,
        soc <= config.battery_capacity_kwh,
        grid + diesel + discharge + pv
        == served_critical + served_normal + charge + curtail + network_loss,
    ]
    if weights.max_normal_unserved_kwh is not None:
        if weights.max_normal_unserved_kwh < 0:
            raise ValueError("max_normal_unserved_kwh must be non-negative")
        constraints.append(
            cp.sum(normal - served_normal)
            <= weights.max_normal_unserved_kwh
        )
    if weights.max_critical_unserved_kwh is not None:
        if weights.max_critical_unserved_kwh < 0:
            raise ValueError("max_critical_unserved_kwh must be non-negative")
        constraints.append(cp.sum(critical - served_critical) <= weights.max_critical_unserved_kwh)

    unserved_critical = critical - served_critical
    unserved_normal = normal - served_normal
    carbon_term = (
        cp.sum(cp.multiply(grid, carbon_factor))
        + emission_factors.diesel_kg_per_kwh * cp.sum(diesel)
    )
    objective = cp.Minimize(
        weights.critical_unserved * cp.sum(unserved_critical)
        + weights.normal_unserved * cp.sum(unserved_normal)
        + weights.diesel_energy * cp.sum(diesel)
        + weights.grid_energy * cp.sum(grid)
        + weights.carbon * carbon_term
        + weights.battery_throughput * cp.sum(charge + discharge)
        + weights.renewable_curtailment * cp.sum(curtail)
    )
    problem = cp.Problem(objective, constraints)
    problem.solve(solver="CLARABEL", max_iter=500)
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
        raise RuntimeError(f"resource dispatch failed: {problem.status}")

    out = demand.copy()
    values = {
        "served_critical_kw": served_critical,
        "served_normal_kw": served_normal,
        "grid_import_kw": grid,
        "diesel_generation_kw": diesel,
        "battery_charge_kw": charge,
        "battery_discharge_kw": discharge,
        "renewable_curtailment_kw": curtail,
    }
    for column, variable in values.items():
        out[column] = np.asarray(variable.value).reshape(-1)
    out["battery_soc_kwh"] = np.asarray(soc.value[1:]).reshape(-1)
    out["unserved_critical_kw"] = critical - out["served_critical_kw"]
    out["unserved_normal_kw"] = normal - out["served_normal_kw"]
    return DispatchResult(out.round(5), problem.status, float(problem.value))


def dispatch_resources_spatial(
    demand: pd.DataFrame,
    node_demand: pd.DataFrame,
    grid_capacity_kw: np.ndarray | pd.Series,
    config: ResourceConfig = ResourceConfig(),
    weights: DispatchWeights = DispatchWeights(),
    *,
    node_loss_kw: pd.Series | None = None,
    node_q_loss_kvar: pd.Series | None = None,
    component_served_caps_kw: dict[tuple[int, str], float] | None = None,
    island_q_support_ratio: float = 0.60,
    contract: ServiceContract | None = None,
    objective: DispatchObjective | None = None,
    emission_factors: EmissionFactors = DEFAULT_EMISSION_FACTORS,
) -> DispatchResult:
    """Dispatch resources by physical node and hourly connected component.

    The formulation preserves the existing aggregate result schema while
    enforcing an energy balance for every island. Grid import appears only in
    the root component; PV, diesel and storage remain at their installed bus.
    """

    required_node_columns = {
        "hour",
        "node_id",
        "component_key",
        "is_root_component",
        "critical_load_kw",
        "normal_load_kw",
        "reactive_ratio",
        "pv_available_kw",
        "diesel_capacity_kw",
        "storage_power_kw",
        "storage_energy_kwh",
        "service_class",
    }
    missing = required_node_columns.difference(node_demand.columns)
    if missing:
        raise ValueError(f"node demand frame missing columns: {sorted(missing)}")
    hours = list(demand.index)
    nodes = sorted(int(x) for x in node_demand["node_id"].unique())
    if hours != list(range(len(hours))):
        raise ValueError("spatial dispatch currently requires consecutive integer hours")
    n_t, n_n = len(hours), len(nodes)
    node_pos = {node: pos for pos, node in enumerate(nodes)}
    grid_cap = np.asarray(grid_capacity_kw, dtype=float).reshape(-1)
    if len(grid_cap) != n_t:
        raise ValueError("grid capacity length must match demand horizon")

    ordered = node_demand.sort_values(["hour", "node_id"]).reset_index(drop=True)
    if len(ordered) != n_t * n_n:
        raise ValueError("node demand must contain one row per hour and node")

    def matrix(column: str) -> np.ndarray:
        return ordered[column].to_numpy(float).reshape(n_t, n_n)

    critical = matrix("critical_load_kw")
    normal = matrix("normal_load_kw")
    reactive_ratio = matrix("reactive_ratio")
    pv = matrix("pv_available_kw")
    diesel_cap = matrix("diesel_capacity_kw")
    storage_power = matrix("storage_power_kw")
    storage_energy = matrix("storage_energy_kwh")
    service_classes = ordered["service_class"].astype(str).to_numpy().reshape(n_t, n_n)
    valid_service_classes = {"hospital", "essential", "critical", "normal"}
    unknown_service_classes = set(np.unique(service_classes)).difference(valid_service_classes)
    if unknown_service_classes:
        raise ValueError(f"unknown service classes: {sorted(unknown_service_classes)}")
    # Installed capacities are time-invariant; retain the first row for SOC.
    storage_power_bus = storage_power[0]
    storage_energy_bus = storage_energy[0]
    loss = np.zeros((n_t, n_n), dtype=float)
    if node_loss_kw is not None:
        loss_series = pd.Series(node_loss_kw, dtype=float)
        for (hour, node), value in loss_series.items():
            if int(hour) in hours and int(node) in node_pos:
                loss[int(hour), node_pos[int(node)]] = max(float(value), 0.0)
    q_loss = np.zeros((n_t, n_n), dtype=float)
    if node_q_loss_kvar is not None:
        q_loss_series = pd.Series(node_q_loss_kvar, dtype=float)
        for (hour, node), value in q_loss_series.items():
            if int(hour) in hours and int(node) in node_pos:
                q_loss[int(hour), node_pos[int(node)]] = max(float(value), 0.0)

    served_critical = cp.Variable((n_t, n_n), nonneg=True)
    served_normal = cp.Variable((n_t, n_n), nonneg=True)
    grid = cp.Variable(n_t, nonneg=True)
    diesel = cp.Variable((n_t, n_n), nonneg=True)
    charge = cp.Variable((n_t, n_n), nonneg=True)
    discharge = cp.Variable((n_t, n_n), nonneg=True)
    curtail = cp.Variable((n_t, n_n), nonneg=True)
    soc = cp.Variable((n_t + 1, n_n))

    constraints: list[cp.Constraint] = [
        served_critical <= critical,
        served_normal <= normal,
        grid <= np.clip(grid_cap, 0, None),
        diesel <= diesel_cap,
        charge <= storage_power,
        discharge <= storage_power,
        curtail <= pv,
        soc[0, :] == config.initial_soc * storage_energy_bus,
        soc[1:, :] == soc[:-1, :] + config.efficiency * charge - discharge / config.efficiency,
        soc >= np.tile(config.min_soc * storage_energy_bus, (n_t + 1, 1)),
        soc <= np.tile(storage_energy_bus, (n_t + 1, 1)),
    ]

    component_caps = component_served_caps_kw or {}
    for hour in hours:
        hour_rows = ordered[ordered["hour"] == hour]
        for component_key, component_rows in hour_rows.groupby("component_key", sort=True):
            idx = [node_pos[int(node)] for node in component_rows["node_id"]]
            root_component = bool(component_rows["is_root_component"].iloc[0])
            gfm_capacity = float(np.sum(diesel_cap[hour, idx] + storage_power[hour, idx]))
            source = cp.sum(diesel[hour, idx] + discharge[hour, idx] + pv[hour, idx])
            sink = cp.sum(
                served_critical[hour, idx]
                + served_normal[hour, idx]
                + charge[hour, idx]
                + curtail[hour, idx]
                + loss[hour, idx]
            )
            if root_component:
                constraints.append(grid[hour] + source == sink)
            elif gfm_capacity <= 1e-9:
                # Grid-following PV cannot energize an island by itself.
                constraints.extend(
                    [
                        served_critical[hour, idx] == 0,
                        served_normal[hour, idx] == 0,
                        diesel[hour, idx] == 0,
                        charge[hour, idx] == 0,
                        discharge[hour, idx] == 0,
                        curtail[hour, idx] == pv[hour, idx],
                    ]
                )
            else:
                constraints.append(source == sink)
                q_demand = cp.sum(
                    cp.multiply(
                        reactive_ratio[hour, idx],
                        served_critical[hour, idx] + served_normal[hour, idx],
                    )
                )
                q_capacity = island_q_support_ratio * gfm_capacity
                constraints.append(q_demand + float(np.sum(q_loss[hour, idx])) <= q_capacity)
            cap = component_caps.get((hour, str(component_key)))
            if cap is not None:
                constraints.append(
                    cp.sum(served_critical[hour, idx] + served_normal[hour, idx]) <= max(float(cap), 0.0)
                )

    if weights.max_normal_unserved_kwh is not None:
        constraints.append(cp.sum(normal - served_normal) <= weights.max_normal_unserved_kwh)
    if weights.max_critical_unserved_kwh is not None:
        constraints.append(cp.sum(critical - served_critical) <= weights.max_critical_unserved_kwh)

    carbon_factor = demand["grid_carbon_kg_per_kwh"].to_numpy(float)
    unserved_critical = critical - served_critical
    unserved_normal = normal - served_normal
    hospital_mask = (service_classes == "hospital").astype(float)
    other_essential_mask = np.isin(service_classes, ["essential", "critical"]).astype(float)
    hospital_unserved = cp.sum(cp.multiply(hospital_mask, unserved_critical))
    other_essential_unserved = cp.sum(cp.multiply(other_essential_mask, unserved_critical))
    normal_unserved_total = cp.sum(unserved_normal)
    carbon_term = (
        cp.sum(cp.multiply(grid, carbon_factor))
        + emission_factors.diesel_kg_per_kwh * cp.sum(diesel)
    )
    active_contract = contract or ServiceContract()
    for name, value in (
        ("hospital_unserved_cap_kwh", active_contract.hospital_unserved_cap_kwh),
        ("other_essential_unserved_cap_kwh", active_contract.other_essential_unserved_cap_kwh),
        ("normal_unserved_cap_kwh", active_contract.normal_unserved_cap_kwh),
        ("carbon_cap_kg", active_contract.carbon_cap_kg),
        ("crew_emissions_kg", active_contract.crew_emissions_kg),
        ("tolerance_kwh", active_contract.tolerance_kwh),
    ):
        if value is not None and float(value) < 0:
            raise ValueError(f"{name} must be non-negative")
    if active_contract.hospital_unserved_cap_kwh is not None:
        constraints.append(
            hospital_unserved
            <= float(active_contract.hospital_unserved_cap_kwh) + active_contract.tolerance_kwh
        )
    if active_contract.other_essential_unserved_cap_kwh is not None:
        constraints.append(
            other_essential_unserved
            <= float(active_contract.other_essential_unserved_cap_kwh) + active_contract.tolerance_kwh
        )
    if active_contract.normal_unserved_cap_kwh is not None:
        constraints.append(
            normal_unserved_total
            <= float(active_contract.normal_unserved_cap_kwh) + active_contract.tolerance_kwh
        )
    if active_contract.carbon_cap_kg is not None:
        constraints.append(
            carbon_term + active_contract.crew_emissions_kg
            <= float(active_contract.carbon_cap_kg)
        )
    if active_contract.task_requirements:
        task_required_kw = np.zeros((n_t, n_n), dtype=float)
        for requirement in active_contract.task_requirements:
            if requirement.node_id not in node_pos:
                raise ValueError(
                    f"task {requirement.task_id!r} references unknown node {requirement.node_id}"
                )
            if not 0 <= requirement.start_hour <= requirement.end_hour < n_t:
                raise ValueError(
                    f"task {requirement.task_id!r} has invalid service window "
                    f"{requirement.start_hour}..{requirement.end_hour}"
                )
            if requirement.min_kw < 0:
                raise ValueError(f"task {requirement.task_id!r} min_kw must be non-negative")
            task_required_kw[
                requirement.start_hour : requirement.end_hour + 1,
                node_pos[requirement.node_id],
            ] += float(requirement.min_kw)
        if np.any(task_required_kw > critical + 1e-6):
            hour, node_index = np.argwhere(task_required_kw > critical + 1e-6)[0]
            raise ValueError(
                "care-task demand exceeds critical-load envelope at "
                f"hour={int(hour)}, node={nodes[int(node_index)]}"
            )
        constraints.append(served_critical >= task_required_kw)

    active_objective = objective or DispatchObjective()
    secondary = max(float(active_objective.secondary_weight), 0.0)
    total_unserved = cp.sum(unserved_critical) + normal_unserved_total
    throughput = cp.sum(charge + discharge) + cp.sum(curtail)
    primary_expression = None
    secondary_expression = None
    if active_objective.kind == "weighted":
        objective_expression = (
            weights.critical_unserved * cp.sum(unserved_critical)
            + weights.normal_unserved * normal_unserved_total
            + weights.diesel_energy * cp.sum(diesel)
            + weights.grid_energy * cp.sum(grid)
            + weights.carbon * carbon_term
            + weights.battery_throughput * cp.sum(charge + discharge)
            + weights.renewable_curtailment * cp.sum(curtail)
        )
    elif active_objective.kind == "min_hospital_eens":
        primary_expression = hospital_unserved
        secondary_expression = (
            100.0 * other_essential_unserved
            + normal_unserved_total
            + 1e-3 * carbon_term
            + 1e-5 * throughput
        )
    elif active_objective.kind == "min_essential_eens":
        primary_expression = other_essential_unserved
        secondary_expression = normal_unserved_total + 1e-3 * carbon_term + 1e-5 * throughput
    elif active_objective.kind == "min_normal_eens":
        primary_expression = normal_unserved_total
        secondary_expression = carbon_term + 1e-3 * throughput
    elif active_objective.kind == "min_carbon":
        objective_expression = carbon_term + secondary * (total_unserved + 1e-3 * throughput)
    else:
        raise ValueError(f"unknown dispatch objective: {active_objective.kind}")

    if primary_expression is not None and secondary_expression is not None:
        primary_problem = cp.Problem(cp.Minimize(primary_expression), constraints)
        primary_problem.solve(solver="CLARABEL", max_iter=1000)
        if primary_problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
            raise RuntimeError(f"spatial resource dispatch failed: {primary_problem.status}")
        primary_value = float(primary_expression.value)
        lexicographic_tolerance = max(
            float(active_contract.tolerance_kwh),
            1e-7 * max(abs(primary_value), 1.0),
        )
        constraints.append(primary_expression <= primary_value + lexicographic_tolerance)
        objective_expression = secondary_expression

    problem = cp.Problem(cp.Minimize(objective_expression), constraints)
    problem.solve(solver="CLARABEL", max_iter=1000)
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
        raise RuntimeError(f"spatial resource dispatch failed: {problem.status}")

    aggregate = demand.copy()
    aggregate["served_critical_kw"] = np.sum(served_critical.value, axis=1)
    aggregate["served_normal_kw"] = np.sum(served_normal.value, axis=1)
    aggregate["grid_import_kw"] = np.asarray(grid.value).reshape(-1)
    aggregate["diesel_generation_kw"] = np.sum(diesel.value, axis=1)
    aggregate["battery_charge_kw"] = np.sum(charge.value, axis=1)
    aggregate["battery_discharge_kw"] = np.sum(discharge.value, axis=1)
    aggregate["renewable_curtailment_kw"] = np.sum(curtail.value, axis=1)
    aggregate["battery_soc_kwh"] = np.sum(soc.value[1:, :], axis=1)
    aggregate["unserved_critical_kw"] = np.sum(unserved_critical.value, axis=1)
    aggregate["unserved_normal_kw"] = np.sum(unserved_normal.value, axis=1)
    aggregate["network_loss_kw"] = np.sum(loss, axis=1)

    node_rows: list[dict[str, float | int | str | bool]] = []
    for row_idx, row in ordered.iterrows():
        hour = int(row["hour"])
        node = int(row["node_id"])
        pos = node_pos[node]
        node_rows.append(
            {
                **row.to_dict(),
                "served_critical_kw": float(served_critical.value[hour, pos]),
                "served_normal_kw": float(served_normal.value[hour, pos]),
                "served_load_kw": float(served_critical.value[hour, pos] + served_normal.value[hour, pos]),
                "served_reactive_kvar": float(
                    reactive_ratio[hour, pos]
                    * (served_critical.value[hour, pos] + served_normal.value[hour, pos])
                ),
                "pv_generation_kw": float(pv[hour, pos] - curtail.value[hour, pos]),
                "diesel_generation_kw": float(diesel.value[hour, pos]),
                "battery_charge_kw": float(charge.value[hour, pos]),
                "battery_discharge_kw": float(discharge.value[hour, pos]),
                "battery_soc_kwh": float(soc.value[hour + 1, pos]),
                "network_loss_kw": float(loss[hour, pos]),
                "network_q_loss_kvar": float(q_loss[hour, pos]),
            }
        )
    node_frame = pd.DataFrame(node_rows).round(6)
    return DispatchResult(aggregate.round(5), problem.status, float(problem.value), node_frame=node_frame)
