from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .dispatch import ResourceConfig
from .network import GridModel
from .powerflow import FlowValidation
from .restoration import StrategyResult
from .scenarios import DisasterScenario


@dataclass(frozen=True)
class IslandPassportResult:
    hourly: pd.DataFrame
    episodes: pd.DataFrame


ISLAND_HOURLY_COLUMNS = (
    "scenario", "strategy", "hour", "island_episode_id", "component_id",
    "component_key", "node_count", "node_ids", "passport_status", "heat_class",
    "blocked_reason_codes", "data_confidence", "gfm_candidate_count",
    "gfm_primary_node", "gfm_status", "gfm_evidence_level", "black_start_status",
    "gfm_available_kw", "pv_grid_following_kw", "installed_island_der_kw",
    "validator_slack_capacity_kw", "required_source_kw", "p_reserve_kw",
    "p_reserve_pct", "required_reactive_kvar", "reactive_capacity_kvar",
    "q_reserve_kvar", "q_reserve_pct", "reactive_shortfall_kvar", "soc_kwh",
    "soc_pct", "usable_bess_energy_kwh", "bess_discharge_kw", "bess_charge_kw",
    "bess_net_support_kw", "bess_duration_h", "diesel_generation_kw",
    "fuel_duration_h", "service_load_kw", "critical_service_kw",
    "critical_service_pct", "source_feasible", "powerflow_converged",
    "min_voltage_pu", "max_voltage_pu", "min_voltage_node_id",
    "max_loading_pct", "worst_branch_id", "thermal_headroom_pct",
    "thermal_headroom_kva", "weakest_constraint", "weakest_margin_pct",
    "topology_window_remaining_h", "safe_duration_h", "duration_confidence",
)

ISLAND_EPISODE_COLUMNS = (
    "scenario", "strategy", "island_episode_id", "start_hour", "end_hour",
    "duration_h", "component_keys", "worst_status", "minimum_margin_pct",
    "minimum_voltage_pu", "maximum_loading_pct", "blocked_reason_codes",
)


def _node_ids(component_key: str) -> list[int]:
    if not component_key:
        return []
    return [int(value) for value in str(component_key).split("-") if value != ""]


def _episode_ids(components: pd.DataFrame) -> dict[tuple[int, str], str]:
    episodes: dict[tuple[int, str], str] = {}
    last_seen: dict[str, tuple[int, str]] = {}
    counters: dict[str, int] = {}
    for row in components.sort_values(["hour", "component_key"]).itertuples():
        hour = int(row.hour)
        key = str(row.component_key)
        previous = last_seen.get(key)
        if previous is None or previous[0] != hour - 1:
            counters[key] = counters.get(key, 0) + 1
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
            episode = f"isl-{digest}-e{counters[key]:02d}-h{hour:02d}"
        else:
            episode = previous[1]
        episodes[(hour, key)] = episode
        last_seen[key] = (hour, episode)
    return episodes


def _first_hard_reason(reasons: list[str]) -> str | None:
    priority = (
        "NO_GFM",
        "P_SHORTFALL",
        "Q_SHORTFALL",
        "POWERFLOW_NONCONVERGENCE",
        "VOLTAGE",
        "THERMAL",
    )
    return next((reason for reason in priority if reason in reasons), reasons[0] if reasons else None)


def build_island_passports(
    model: GridModel,
    scenario: DisasterScenario,
    strategy_result: StrategyResult,
    validation: FlowValidation,
    *,
    config: ResourceConfig = ResourceConfig(),
) -> IslandPassportResult:
    """Build an auditable hourly capability card for every non-root island.

    Current GFM and black-start evidence is explicitly labelled as a model
    assumption: diesel or BESS capacity makes a node a candidate reference,
    but does not claim a field-verified inverter mode or commissioning test.
    """

    node_dispatch = strategy_result.dispatch.node_frame
    if node_dispatch is None:
        raise ValueError("island passports require node-level dispatch evidence")
    components = validation.components.loc[~validation.components["is_root_component"]].copy()
    if components.empty:
        return IslandPassportResult(
            pd.DataFrame(columns=ISLAND_HOURLY_COLUMNS),
            pd.DataFrame(columns=ISLAND_EPISODE_COLUMNS),
        )
    episode_map = _episode_ids(components)
    rows: list[dict[str, object]] = []

    for component in components.sort_values(["hour", "component_id"]).itertuples():
        hour = int(component.hour)
        component_id = int(component.component_id)
        component_key = str(component.component_key)
        nodes = _node_ids(component_key)
        static = model.nodes.loc[nodes]
        dispatch = node_dispatch[
            (node_dispatch["hour"] == hour)
            & (node_dispatch["component_key"].astype(str) == component_key)
        ]
        flow_nodes = validation.nodes[
            (validation.nodes["hour"] == hour)
            & (validation.nodes["component_id"] == component_id)
        ]
        flow_branches = validation.branches[
            (validation.branches["hour"] == hour)
            & (validation.branches["component_id"] == component_id)
        ]

        gfm_capacity_by_node = static["diesel_capacity_kw"] + static["storage_power_kw"]
        gfm_nodes = [int(node) for node in static.index[gfm_capacity_by_node > 1e-9]]
        pv_capacity = float(static["pv_capacity_kw"].sum())
        if int(component.slack_node) >= 0 and gfm_nodes:
            gfm_status = "assumed_from_model"
            black_start_status = "assumed_ready"
        elif pv_capacity > 1e-9:
            gfm_status = "grid_following_only"
            black_start_status = "not_available"
        else:
            gfm_status = "none"
            black_start_status = "not_available"

        service_load_kw = float(dispatch["served_load_kw"].sum())
        critical_demand_kw = float(dispatch["critical_load_kw"].sum())
        critical_served_kw = float(dispatch["served_critical_kw"].sum())
        critical_service_pct = (
            100.0 * critical_served_kw / critical_demand_kw if critical_demand_kw > 1e-9 else 100.0
        )
        storage_capacity_kwh = float(static["storage_energy_kwh"].sum())
        soc_kwh = float(dispatch["battery_soc_kwh"].sum())
        usable_bess_kwh = max(soc_kwh - config.min_soc * storage_capacity_kwh, 0.0)
        bess_discharge_kw = float(dispatch["battery_discharge_kw"].sum())
        bess_charge_kw = float(dispatch["battery_charge_kw"].sum())
        bess_net_support_kw = max(bess_discharge_kw - bess_charge_kw, 0.0)
        bess_duration_h = (
            usable_bess_kwh / bess_net_support_kw if bess_net_support_kw > 1e-6 else np.nan
        )
        diesel_generation_kw = float(dispatch["diesel_generation_kw"].sum())

        min_voltage_node_id = (
            int(flow_nodes.loc[flow_nodes["voltage_pu"].idxmin(), "node_id"])
            if not flow_nodes.empty
            else -1
        )
        if not flow_branches.empty:
            worst_branch = flow_branches.loc[flow_branches["loading_pct"].idxmax()]
            worst_branch_id = int(worst_branch["branch_id"])
            worst_branch_loading = float(worst_branch["loading_pct"])
            branch_capacity = float(model.branches.loc[worst_branch_id, "capacity_kva"])
            thermal_headroom_kva = branch_capacity - float(worst_branch["apparent_flow_kva"])
        else:
            worst_branch_id = -1
            worst_branch_loading = float(component.max_loading_pct)
            thermal_headroom_kva = np.nan

        p_reserve_kw = float(component.source_capacity_kw) - float(component.required_source_kw)
        q_reserve_kvar = float(component.reactive_capacity_kvar) - float(
            component.required_reactive_kvar
        )
        p_margin = p_reserve_kw / max(float(component.required_source_kw), 1.0)
        q_margin = q_reserve_kvar / max(float(component.required_reactive_kvar), 1.0)
        voltage_margin = min(
            (float(component.min_voltage_pu) - 0.95) / 0.10,
            (1.05 - float(component.max_voltage_pu)) / 0.10,
        )
        thermal_margin = (100.0 - float(component.max_loading_pct)) / 100.0
        soc_margin = (
            usable_bess_kwh / storage_capacity_kwh if storage_capacity_kwh > 1e-9 else np.nan
        )
        margins = {
            "P_RESERVE": p_margin,
            "Q_RESERVE": q_margin,
            "VOLTAGE": voltage_margin,
            "THERMAL": thermal_margin,
        }
        if np.isfinite(soc_margin):
            margins["SOC_ENDURANCE"] = float(soc_margin)

        blocked_reasons: list[str] = []
        if gfm_status in {"none", "grid_following_only"}:
            blocked_reasons.append("NO_GFM")
        if not bool(component.source_feasible):
            blocked_reasons.append("P_SHORTFALL")
        if float(component.reactive_shortfall_kvar) > 1e-3:
            blocked_reasons.append("Q_SHORTFALL")
        if service_load_kw > 1e-3 and not bool(component.powerflow_converged):
            blocked_reasons.append("POWERFLOW_NONCONVERGENCE")
        if service_load_kw > 1e-3 and (
            float(component.min_voltage_pu) < 0.95 - 1e-6
            or float(component.max_voltage_pu) > 1.05 + 1e-6
        ):
            blocked_reasons.append("VOLTAGE")
        if float(component.max_loading_pct) > 100.0 + 1e-6:
            blocked_reasons.append("THERMAL")

        weakest_margin_name = min(margins, key=margins.get) if margins else "NONE"
        weakest_margin = float(margins[weakest_margin_name]) if margins else np.nan
        hard_reason = _first_hard_reason(blocked_reasons)
        weakest_constraint = hard_reason or weakest_margin_name
        if blocked_reasons:
            passport_status = "BLOCKED"
            heat_class = "red"
        elif weakest_margin < 0.10:
            passport_status = "DEGRADED"
            heat_class = "orange"
        elif weakest_margin < 0.25:
            passport_status = "CONDITIONAL"
            heat_class = "yellow"
        else:
            # Current GFM/black-start evidence is inferred, never VERIFIED.
            passport_status = "CONDITIONAL"
            heat_class = "green"

        rows.append(
            {
                "scenario": scenario.name,
                "strategy": strategy_result.plan.strategy,
                "hour": hour,
                "island_episode_id": episode_map[(hour, component_key)],
                "component_id": component_id,
                "component_key": component_key,
                "node_count": len(nodes),
                "node_ids": json.dumps(nodes),
                "passport_status": passport_status,
                "heat_class": heat_class,
                "blocked_reason_codes": json.dumps(blocked_reasons),
                "data_confidence": "assumed",
                "gfm_candidate_count": len(gfm_nodes),
                "gfm_primary_node": int(component.slack_node),
                "gfm_status": gfm_status,
                "gfm_evidence_level": "model_assumption_v1",
                "black_start_status": black_start_status,
                "gfm_available_kw": float(gfm_capacity_by_node.sum()),
                "pv_grid_following_kw": pv_capacity,
                "installed_island_der_kw": float(
                    static["pv_capacity_kw"].sum()
                    + static["diesel_capacity_kw"].sum()
                    + static["storage_power_kw"].sum()
                ),
                "validator_slack_capacity_kw": float(component.source_capacity_kw),
                "required_source_kw": float(component.required_source_kw),
                "p_reserve_kw": p_reserve_kw,
                "p_reserve_pct": 100.0 * p_margin,
                "required_reactive_kvar": float(component.required_reactive_kvar),
                "reactive_capacity_kvar": float(component.reactive_capacity_kvar),
                "q_reserve_kvar": q_reserve_kvar,
                "q_reserve_pct": 100.0 * q_margin,
                "reactive_shortfall_kvar": float(component.reactive_shortfall_kvar),
                "soc_kwh": soc_kwh,
                "soc_pct": 100.0 * soc_kwh / storage_capacity_kwh
                if storage_capacity_kwh > 1e-9
                else np.nan,
                "usable_bess_energy_kwh": usable_bess_kwh,
                "bess_discharge_kw": bess_discharge_kw,
                "bess_charge_kw": bess_charge_kw,
                "bess_net_support_kw": bess_net_support_kw,
                "bess_duration_h": bess_duration_h,
                "diesel_generation_kw": diesel_generation_kw,
                "fuel_duration_h": np.nan,
                "service_load_kw": service_load_kw,
                "critical_service_kw": critical_served_kw,
                "critical_service_pct": critical_service_pct,
                "source_feasible": bool(component.source_feasible),
                "powerflow_converged": bool(component.powerflow_converged),
                "min_voltage_pu": float(component.min_voltage_pu),
                "max_voltage_pu": float(component.max_voltage_pu),
                "min_voltage_node_id": min_voltage_node_id,
                "max_loading_pct": float(component.max_loading_pct),
                "worst_branch_id": worst_branch_id,
                "thermal_headroom_pct": 100.0 - float(component.max_loading_pct),
                "thermal_headroom_kva": thermal_headroom_kva,
                "weakest_constraint": weakest_constraint,
                "weakest_margin_pct": -100.0
                if blocked_reasons
                else 100.0 * weakest_margin
                if np.isfinite(weakest_margin)
                else np.nan,
            }
        )

    hourly = pd.DataFrame(rows).sort_values(["hour", "island_episode_id"]).reset_index(drop=True)
    episode_end = hourly.groupby("island_episode_id")["hour"].transform("max")
    hourly["topology_window_remaining_h"] = episode_end - hourly["hour"] + 1
    hourly["safe_duration_h"] = np.nan
    hourly["duration_confidence"] = "unknown"
    no_diesel = hourly["diesel_generation_kw"] <= 1e-3
    bess_support = hourly["bess_net_support_kw"] > 1e-6
    duration_mask = no_diesel & bess_support & hourly["bess_duration_h"].notna()
    hourly.loc[duration_mask, "safe_duration_h"] = np.minimum(
        hourly.loc[duration_mask, "topology_window_remaining_h"],
        hourly.loc[duration_mask, "bess_duration_h"],
    )
    hourly.loc[duration_mask, "duration_confidence"] = "partial_bess_forecast"

    episode_rows: list[dict[str, object]] = []
    for episode_id, group in hourly.groupby("island_episode_id", sort=True):
        blocked = sorted(
            {
                reason
                for raw in group["blocked_reason_codes"]
                for reason in json.loads(str(raw))
            }
        )
        episode_rows.append(
            {
                "scenario": scenario.name,
                "strategy": strategy_result.plan.strategy,
                "island_episode_id": episode_id,
                "start_hour": int(group["hour"].min()),
                "end_hour": int(group["hour"].max()),
                "duration_h": int(group["hour"].max() - group["hour"].min() + 1),
                "component_keys": json.dumps(sorted(group["component_key"].unique().tolist())),
                "worst_status": "BLOCKED"
                if (group["passport_status"] == "BLOCKED").any()
                else "DEGRADED"
                if (group["passport_status"] == "DEGRADED").any()
                else "CONDITIONAL",
                "minimum_margin_pct": float(group["weakest_margin_pct"].min()),
                "minimum_voltage_pu": float(group["min_voltage_pu"].min()),
                "maximum_loading_pct": float(group["max_loading_pct"].max()),
                "blocked_reason_codes": json.dumps(blocked),
            }
        )
    episodes = pd.DataFrame(episode_rows, columns=ISLAND_EPISODE_COLUMNS).sort_values(
        ["start_hour", "island_episode_id"]
    )
    hourly = hourly.reindex(columns=ISLAND_HOURLY_COLUMNS)
    return IslandPassportResult(hourly.round(6), episodes.round(6))


def write_island_passports(
    result: IslandPassportResult,
    output_dir: str | Path,
    slug: str,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    hourly_path = output / f"island_passport_hourly_{slug}.csv"
    episodes_path = output / f"island_passport_episodes_{slug}.csv"
    summary_path = output / f"island_passport_summary_{slug}.json"
    result.hourly.to_csv(hourly_path, index=False)
    result.episodes.to_csv(episodes_path, index=False)
    summary = {
        "schema_version": 1,
        "hourly_rows": len(result.hourly),
        "episode_count": len(result.episodes),
        "status_counts": result.hourly["passport_status"].value_counts().to_dict()
        if not result.hourly.empty
        else {},
        "evidence_boundary": (
            "GFM and black-start capability are inferred from modelled diesel/BESS capacity; "
            "fuel endurance and field commissioning evidence are not available."
        ),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"hourly": hourly_path, "episodes": episodes_path, "summary": summary_path}
