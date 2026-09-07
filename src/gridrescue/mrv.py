from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cvxpy as cp
import pandas as pd

from .carbon import DEFAULT_EMISSION_FACTORS
from .care import default_care_tasks, evaluate_care_tasks
from .pipeline import PipelineResult
from .restoration import state_at_hour


SCHEMA_VERSION = "gridrescue-mrv-1.0"
DEFAULT_TIME_STEP_H = 1.0
STRATEGY_SLUGS = {
    "传统顺序恢复": "traditional",
    "最小失供恢复": "eens",
    "碳韧协同恢复": "carbon_resilient",
}


def _normalize_hash_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_hash_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_hash_value(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite values cannot be hashed canonically")
        # Dispatch outputs are frozen at five decimals. Six-decimal semantic
        # hashing survives CSV float round-trips while the evidence index still
        # preserves byte-exact file hashes.
        rounded = round(value, 6)
        return 0.0 if rounded == 0 else rounded
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _normalize_hash_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _record_hash(record: dict[str, Any]) -> str:
    return _sha256_json({key: value for key, value in record.items() if key != "record_hash"})


def default_factor_registry(scenario=None) -> pd.DataFrame:
    rows = [
        {
            "factor_id": "grid-base-demo",
            "factor_version": "1.0",
            "activity": "grid_import",
            "gas_basis": "CO2",
            "value": DEFAULT_EMISSION_FACTORS.grid_base_kg_per_kwh,
            "unit": "kgCO2/kWh",
            "geography": "synthetic-demo",
            "year": 2026,
            "temporal_resolution": "annual",
            "method": "engineering_prior",
            "source_class": "E",
            "source_id": "gridrescue-assumption-grid-001",
            "source_title": "GridRescue synthetic grid-factor assumption",
            "source_url": "",
            "source_file_sha256": "",
            "uncertainty_pct": 20.0,
            "applicability": "competition synthetic scenario only",
            "approval_status": "conditional",
        },
        {
            "factor_id": "diesel-demo",
            "factor_version": "1.0",
            "activity": "diesel_generation",
            "gas_basis": "CO2",
            "value": DEFAULT_EMISSION_FACTORS.diesel_kg_per_kwh,
            "unit": "kgCO2/kWh",
            "geography": "synthetic-demo",
            "year": 2026,
            "temporal_resolution": "event",
            "method": "engineering_prior",
            "source_class": "E",
            "source_id": "gridrescue-assumption-diesel-001",
            "source_title": "GridRescue synthetic diesel-factor assumption",
            "source_url": "",
            "source_file_sha256": "",
            "uncertainty_pct": 20.0,
            "applicability": "competition synthetic scenario only",
            "approval_status": "conditional",
        },
        {
            "factor_id": "crew-vehicle-demo",
            "factor_version": "1.0",
            "activity": "crew_vehicle",
            "gas_basis": "CO2",
            "value": DEFAULT_EMISSION_FACTORS.crew_vehicle_kg_per_km,
            "unit": "kgCO2/km",
            "geography": "synthetic-demo",
            "year": 2026,
            "temporal_resolution": "event",
            "method": "engineering_prior",
            "source_class": "E",
            "source_id": "gridrescue-assumption-vehicle-001",
            "source_title": "GridRescue synthetic repair-vehicle assumption",
            "source_url": "",
            "source_file_sha256": "",
            "uncertainty_pct": 20.0,
            "applicability": "competition synthetic scenario only",
            "approval_status": "conditional",
        },
    ]
    if scenario is not None and getattr(scenario, "grid_factor", None) is not None:
        source = json.loads(scenario.provenance_json)["grid_factor"]
        rows[0].update({"factor_id": "china-electricity-2023", "value": scenario.grid_factor,
                        "year": 2023, "geography": "China national", "source_class": "official_statistics",
                        "method": "annual_location_based", "source_id": source["id"],
                        "source_title": "National Energy Administration report of 2023 electricity CO2 factor",
                        "source_url": source["url"], "source_file_sha256": source["sha256"],
                        "applicability": "annual average reference scenario; not historical hourly reconstruction",
                        "approval_status": "public_source_reference"})
    for row in rows:
        row["record_hash"] = _record_hash(row)
    return pd.DataFrame(rows)


def _factor_snapshot(run_id: str, result: PipelineResult) -> pd.DataFrame:
    registry = default_factor_registry(result.scenario).set_index("activity")
    reference = result.strategies["最小失供恢复"].dispatch.frame
    rows: list[dict[str, Any]] = []
    for hour in range(24):
        grid = registry.loc["grid_import"]
        row = {
            "run_id": run_id,
            "hour": hour,
            "activity": "grid_import",
            "factor_id": grid.factor_id,
            "factor_version": grid.factor_version,
            "value": float(reference.loc[hour, "grid_carbon_kg_per_kwh"]),
            "unit": grid.unit,
            "gas_basis": grid.gas_basis,
            "geography": grid.geography,
            "year": int(grid.year),
            "temporal_resolution": "hourly",
            "method": grid.method,
            "source_class": grid.source_class,
            "source_file_sha256": grid.source_file_sha256,
            "scenario_multiplier": float(result.scenario.grid_carbon_multiplier),
            "profile_generator_version": "gridrescue-hourly-profile-v1",
            "registry_record_hash": grid.record_hash,
        }
        row["record_hash"] = _record_hash(row)
        rows.append(row)
        for activity in ("diesel_generation", "crew_vehicle"):
            factor = registry.loc[activity]
            factor_row = {
                "run_id": run_id,
                "hour": hour,
                "activity": activity,
                "factor_id": factor.factor_id,
                "factor_version": factor.factor_version,
                "value": float(factor.value),
                "unit": factor.unit,
                "gas_basis": factor.gas_basis,
                "geography": factor.geography,
                "year": int(factor.year),
                "temporal_resolution": factor.temporal_resolution,
                "method": factor.method,
                "source_class": factor.source_class,
                "source_file_sha256": factor.source_file_sha256,
                "scenario_multiplier": 1.0,
                "profile_generator_version": "none",
                "registry_record_hash": factor.record_hash,
            }
            factor_row["record_hash"] = _record_hash(factor_row)
            rows.append(factor_row)
    return pd.DataFrame(rows)


def _activity_rows(
    run_id: str,
    result: PipelineResult,
    *,
    time_step_h: float = DEFAULT_TIME_STEP_H,
) -> pd.DataFrame:
    if abs(float(time_step_h) - DEFAULT_TIME_STEP_H) > 1e-12:
        raise ValueError("GridRescue v1 supports only time_step_h=1.0")
    mapping = {
        "grid_import": "grid_import_kw",
        "diesel_generation": "diesel_generation_kw",
        "pv_available": "pv_available_kw",
        "bess_charge": "battery_charge_kw",
        "bess_discharge": "battery_discharge_kw",
        "renewable_curtailment": "renewable_curtailment_kw",
        "unserved_critical": "unserved_critical_kw",
        "unserved_normal": "unserved_normal_kw",
    }
    rows: list[dict[str, Any]] = []
    for strategy, strategy_result in result.strategies.items():
        slug = STRATEGY_SLUGS[strategy]
        frame = strategy_result.dispatch.frame
        for hour, dispatch_row in frame.iterrows():
            for flow, column in mapping.items():
                power = max(float(dispatch_row[column]), 0.0)
                row = {
                    "activity_id": f"actv-{slug}-{int(hour):02d}-{flow}",
                    "run_id": run_id,
                    "strategy_id": slug,
                    "hour": int(hour),
                    "time_step_h": float(time_step_h),
                    "primary_action_id": "",
                    "energy_flow": flow,
                    "power_kw": power,
                    "energy_kwh": power * float(time_step_h),
                    "data_mode": "synthetic_demo",
                    "dispatch_ref": f"dispatch_{slug}.csv#hour={int(hour)}",
                }
                row["record_hash"] = _record_hash(row)
                rows.append(row)
    return pd.DataFrame(rows)


def _inventory_rows(
    run_id: str,
    result: PipelineResult,
    activities: pd.DataFrame,
    factors: pd.DataFrame,
) -> pd.DataFrame:
    factor_lookup = factors.set_index(["hour", "activity"])
    rows: list[dict[str, Any]] = []
    for activity in activities.itertuples():
        if activity.energy_flow not in {"grid_import", "diesel_generation"}:
            continue
        factor = factor_lookup.loc[(int(activity.hour), str(activity.energy_flow))]
        emission = float(activity.energy_kwh) * float(factor.value)
        boundary = (
            "grid_scope2_location"
            if activity.energy_flow == "grid_import"
            else "diesel_scope1"
        )
        row = {
            "inventory_id": f"inv-{activity.strategy_id}-{int(activity.hour):02d}-{activity.energy_flow}",
            "run_id": run_id,
            "strategy_id": activity.strategy_id,
            "hour": int(activity.hour),
            "activity_id": activity.activity_id,
            "activity_value": float(activity.energy_kwh),
            "activity_unit": "kWh",
            "factor_id": factor.factor_id,
            "factor_version": factor.factor_version,
            "factor_value": float(factor.value),
            "factor_unit": factor.unit,
            "gas_basis": factor.gas_basis,
            "emission_value": emission,
            "emission_unit": "kgCO2",
            "boundary_module": boundary,
            "activity_record_hash": activity.record_hash,
            "factor_record_hash": factor.record_hash,
        }
        row["record_hash"] = _record_hash(row)
        rows.append(row)

    crew_factor = factor_lookup.loc[(0, "crew_vehicle")]
    for strategy in result.strategies:
        slug = STRATEGY_SLUGS[strategy]
        distance = float(result.scenario.crew_distance_km)
        row = {
            "inventory_id": f"inv-{slug}-00-crew_vehicle",
            "run_id": run_id,
            "strategy_id": slug,
            "hour": 0,
            "activity_id": f"event-{slug}-crew_vehicle",
            "activity_value": distance,
            "activity_unit": "km",
            "factor_id": crew_factor.factor_id,
            "factor_version": crew_factor.factor_version,
            "factor_value": float(crew_factor.value),
            "factor_unit": crew_factor.unit,
            "gas_basis": crew_factor.gas_basis,
            "emission_value": distance * float(crew_factor.value),
            "emission_unit": "kgCO2",
            "boundary_module": "crew_estimated",
            "activity_record_hash": "event:scenario.crew_distance_km",
            "factor_record_hash": crew_factor.record_hash,
        }
        row["record_hash"] = _record_hash(row)
        rows.append(row)
    return pd.DataFrame(rows)


def _action_rows(run_id: str, result: PipelineResult) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for strategy, strategy_result in result.strategies.items():
        slug = STRATEGY_SLUGS[strategy]
        prev_hash = f"GENESIS:{run_id}:{slug}"
        sequence = 0
        previous_failed = set(int(branch) for branch in result.scenario.failed_branch_ids)
        previous_ties: set[int] = set()
        actions: list[tuple[int, str, int, str, str]] = []
        for hour in range(24):
            state = state_at_hour(result.model, result.scenario, strategy_result.plan, hour)
            current_failed = set(int(branch) for branch in state.failed_branch_ids)
            current_ties = set(int(branch) for branch in state.closed_tie_ids)
            actions.extend(
                (
                    hour,
                    "repair_branch",
                    branch,
                    f"修复支路 L{branch}",
                    "REPAIR_COMPLETED",
                )
                for branch in sorted(previous_failed - current_failed)
            )
            actions.extend(
                (
                    hour,
                    "open_tie",
                    branch,
                    f"断开联络开关 T{branch}",
                    "RADIALITY_GATE_TRANSITION",
                )
                for branch in sorted(previous_ties - current_ties)
            )
            actions.extend(
                (
                    hour,
                    "close_tie",
                    branch,
                    f"闭合联络开关 T{branch}",
                    "SAFE_TIE_GATE_PASSED",
                )
                for branch in sorted(current_ties - previous_ties)
            )
            previous_failed = current_failed
            previous_ties = current_ties

        for hour, action_type, target_id, display, reason_code in actions:
            sequence += 1
            if action_type == "repair_branch":
                before = {"availability": "failed"}
                after = {"availability": "repaired"}
            elif action_type == "close_tie":
                before = {"switch": "open"}
                after = {"switch": "closed"}
            else:
                before = {"switch": "closed"}
                after = {"switch": "open"}
            row = {
                "run_id": run_id,
                "sequence_no": sequence,
                "action_id": f"act-{slug}-{sequence:04d}",
                "strategy_id": slug,
                "plan_id": f"plan-{slug}",
                "hour": hour,
                "action_type": action_type,
                "target_type": "branch",
                "target_id": target_id,
                "before_state_json": _canonical_json(before),
                "requested_state_json": _canonical_json(after),
                "after_state_json": _canonical_json(after),
                "origin": "simulated_state_transition",
                "status": "simulated_applied",
                "reason_code": reason_code,
                "physical_gate_status": "passed",
                "evidence_ref": f"topology_state_{slug}.csv#hour={hour}",
                "prev_hash": prev_hash,
                "display_text": display,
            }
            row["record_hash"] = _record_hash(row)
            prev_hash = row["record_hash"]
            rows.append(row)
    return pd.DataFrame(rows)


def _claim_gates(result: PipelineResult) -> dict[str, Any]:
    tasks = default_care_tasks()
    strategies: dict[str, Any] = {}
    all_strategy_pass = True
    for strategy, strategy_result in result.strategies.items():
        slug = STRATEGY_SLUGS[strategy]
        validation = result.validations[strategy]
        feedback = result.feedbacks[strategy]
        care = evaluate_care_tasks(tasks, strategy_result, validation)
        gates = {
            "solver_pass": strategy_result.dispatch.status in {"optimal", "optimal_inaccurate"},
            "feedback_converged": bool(feedback.converged),
            "grid_physical_pass": bool(validation.hourly["is_feasible"].all()),
            "care_task_pass": bool(care["task_complete"].all()),
            "data_quality": "conditional",
            "data_class": "mixed_public_and_synthetic" if getattr(result.scenario, "provenance_json", "") else "E_synthetic_demo",
        }
        gates["inventory_eligible"] = bool(
            gates["solver_pass"]
            and gates["feedback_converged"]
            and gates["grid_physical_pass"]
            and gates["care_task_pass"]
        )
        all_strategy_pass = all_strategy_pass and gates["inventory_eligible"]
        strategies[slug] = gates

    reference = result.strategies["最小失供恢复"].dispatch.frame
    candidate = result.strategies["碳韧协同恢复"].dispatch.frame
    critical_ref = float(reference["unserved_critical_kw"].sum())
    normal_ref = float(reference["unserved_normal_kw"].sum())
    critical_candidate = float(candidate["unserved_critical_kw"].sum())
    normal_candidate = float(candidate["unserved_normal_kw"].sum())
    normal_demand = float(reference["normal_load_kw"].sum())
    controlled_budget = normal_ref + 0.08 * normal_demand
    comparison = {
        "reference_strategy": "eens",
        "candidate_strategy": "carbon_resilient",
        "normal_service_budget_fraction": 0.08,
        "critical_service_pass": critical_candidate <= critical_ref + 1e-3,
        "normal_budget_pass": normal_candidate <= controlled_budget + 1e-3,
        "same_service_pass": (
            critical_candidate <= critical_ref + 1e-3
            and normal_candidate <= normal_ref + 1e-3
        ),
        "reference_inventory_kgCO2": result.strategies["最小失供恢复"].carbon.total_operational_kg,
        "candidate_inventory_kgCO2": result.strategies["碳韧协同恢复"].carbon.total_operational_kg,
    }
    comparison["inventory_difference_kgCO2"] = (
        comparison["candidate_inventory_kgCO2"] - comparison["reference_inventory_kgCO2"]
    )
    comparison["controlled_tradeoff_pass"] = bool(
        all_strategy_pass
        and comparison["critical_service_pass"]
        and comparison["normal_budget_pass"]
    )
    comparison["same_service_reduction_claim_allowed"] = bool(
        comparison["same_service_pass"]
        and comparison["inventory_difference_kgCO2"] < 0
        and all_strategy_pass
    )
    comparison["claim_status"] = (
        "same_service_inventory_reduction"
        if comparison["same_service_reduction_claim_allowed"]
        else (
            "controlled_service_budget_inventory_difference"
            if comparison["controlled_tradeoff_pass"]
            else "inventory_only"
        )
    )
    return {
        "schema_version": "gridrescue-claim-gates-1.0",
        "strategies": strategies,
        "comparison": comparison,
        "boundary_note": (
            "Synthetic competition run. Sealed means file integrity only, not field "
            "measurement or third-party verification."
        ),
    }


def _code_bundle_hash(project_root: Path) -> str:
    hasher = hashlib.sha256()
    candidates = [project_root / "pyproject.toml", project_root / "requirements.txt"]
    candidates.extend(sorted((project_root / "src").rglob("*.py")))
    for path in candidates:
        if path.exists():
            hasher.update(path.relative_to(project_root).as_posix().encode("utf-8"))
            hasher.update(path.read_bytes())
    return "sha256:" + hasher.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _evidence_index(bundle: Path, run_id: str) -> dict[str, Any]:
    files = []
    for path in sorted(bundle.rglob("*")):
        if not path.is_file() or "evidence" in path.relative_to(bundle).parts:
            continue
        files.append(
            {
                "path": path.relative_to(bundle).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return {"schema_version": "gridrescue-evidence-1.0", "run_id": run_id, "files": files}


def write_mrv_bundle(
    result: PipelineResult,
    output_dir: str | Path,
    *,
    project_root: str | Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
    scenario_payload = asdict(result.scenario)
    network_payload = {
        "source_name": result.model.source_name,
        "source_sha256": result.model.source_sha256,
        "base_mva": result.model.base_mva,
        "base_kv": result.model.base_kv,
        "nodes": result.model.nodes.reset_index().to_dict(orient="records"),
        "branches": result.model.branches.reset_index(drop=True).to_dict(orient="records"),
    }
    config_payload = {
        "horizon_h": 24,
        "time_step_h": DEFAULT_TIME_STEP_H,
        "gas_basis": "CO2",
        "normal_service_budget_fraction": 0.08,
        "strategies": STRATEGY_SLUGS,
    }
    registry = default_factor_registry(result.scenario)
    identity = {
        "scenario": _sha256_json(scenario_payload),
        "network": _sha256_json(network_payload),
        "code": _code_bundle_hash(root),
        "config": _sha256_json(config_payload),
        "registry": _sha256_bytes(registry.to_csv(index=False).encode("utf-8")),
    }
    run_id = "run-" + hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()[:16]
    bundle = output / run_id
    inputs = bundle / "inputs"
    outputs = bundle / "outputs"
    evidence = bundle / "evidence"
    for directory in (inputs, outputs, evidence):
        directory.mkdir(parents=True, exist_ok=True)

    _write_json(inputs / "scenario.json", scenario_payload)
    if getattr(result.scenario, "provenance_json", ""):
        provenance = json.loads(result.scenario.provenance_json)
        for key in ("weather", "grid_factor"):
            source = provenance[key]
            source_path = root / "data" / "public" / source["path"]
            raw = source_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                raise ValueError("public source checksum mismatch during export")
            (inputs / (key + source_path.suffix)).write_bytes(raw)
        _write_json(inputs / "public_source_manifest.json", provenance)
    _write_json(inputs / "network_snapshot.json", network_payload)
    _write_json(inputs / "config.json", config_payload)
    registry.to_csv(inputs / "factor_registry.csv", index=False)
    factors = _factor_snapshot(run_id, result)
    factors.to_csv(inputs / "factor_snapshot.csv", index=False)
    for strategy, strategy_result in result.strategies.items():
        slug = STRATEGY_SLUGS[strategy]
        strategy_result.dispatch.frame.to_csv(
            outputs / f"dispatch_{slug}.csv",
            index_label="hour",
        )
        topology_rows = []
        for hour in range(24):
            state = state_at_hour(result.model, result.scenario, strategy_result.plan, hour)
            topology_rows.append(
                {
                    "run_id": run_id,
                    "strategy_id": slug,
                    "hour": hour,
                    "failed_branch_ids_json": _canonical_json(sorted(int(x) for x in state.failed_branch_ids)),
                    "closed_tie_ids_json": _canonical_json(sorted(int(x) for x in state.closed_tie_ids)),
                    "energized_node_count": len(state.energized_nodes),
                    "island_count": len(state.islands),
                }
            )
        pd.DataFrame(topology_rows).to_csv(
            outputs / f"topology_state_{slug}.csv",
            index=False,
        )
    activities = _activity_rows(
        run_id,
        result,
        time_step_h=float(config_payload["time_step_h"]),
    )
    activities.to_csv(outputs / "activity_energy_hourly.csv", index=False)
    inventory = _inventory_rows(run_id, result, activities, factors)
    inventory.to_csv(outputs / "emission_inventory_hourly.csv", index=False)
    actions = _action_rows(run_id, result)
    actions.to_csv(outputs / "actions.csv", index=False)
    gates = _claim_gates(result)
    _write_json(outputs / "claim_gates.json", gates)

    reconciliation_rows = []
    for strategy, strategy_result in result.strategies.items():
        slug = STRATEGY_SLUGS[strategy]
        subtotal = float(inventory.loc[inventory["strategy_id"] == slug, "emission_value"].sum())
        reconciliation_rows.append(
            {
                "strategy_id": slug,
                "inventory_total_kgCO2": subtotal,
                "carbon_breakdown_total_kgCO2": strategy_result.carbon.total_operational_kg,
                "difference_kgCO2": subtotal - strategy_result.carbon.total_operational_kg,
                "reconciled": abs(subtotal - strategy_result.carbon.total_operational_kg) <= 1e-5,
            }
        )
    reconciliation = pd.DataFrame(reconciliation_rows)
    reconciliation.to_csv(outputs / "carbon_reconciliation.csv", index=False)

    terminal_hashes = {
        slug: (
            str(group.sort_values("sequence_no").iloc[-1]["record_hash"])
            if not group.empty
            else f"GENESIS:{run_id}:{slug}"
        )
        for slug, group in actions.groupby("strategy_id")
    }
    created_at_value = created_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    try:
        parsed_created_at = datetime.fromisoformat(created_at_value)
    except ValueError as exc:
        raise ValueError("created_at must be an ISO-8601 timestamp") from exc
    if parsed_created_at.tzinfo is None:
        raise ValueError("created_at must include a UTC offset")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": created_at_value,
        "status": "sealed",
        "command": "python -m gridrescue.cli --scenario <SCENARIO> --output <DIR>",
        "runtime": {
            "python": sys.version.split()[0],
            "os": platform.platform(),
            "solver": f"cvxpy:{cp.__version__}/CLARABEL",
            "dependency_lock_sha256": _sha256_file(root / "requirements.txt"),
        },
        "code": {"git_commit": None, "code_bundle_sha256": _code_bundle_hash(root)},
        "boundary": config_payload,
        "scenario": {"name": result.scenario.name, "sha256": _sha256_file(inputs / "scenario.json")},
        "network": {
            "source_id": result.model.source_name,
            "source_sha256": result.model.source_sha256,
            "snapshot_sha256": _sha256_file(inputs / "network_snapshot.json"),
        },
        "config_sha256": _sha256_file(inputs / "config.json"),
        "factor_registry_sha256": _sha256_file(inputs / "factor_registry.csv"),
        "factor_snapshot_sha256": _sha256_file(inputs / "factor_snapshot.csv"),
        "strategies": [
            {
                "strategy_id": slug,
                "plan_id": f"plan-{slug}",
                "action_ledger_terminal_hash": terminal_hashes.get(slug, f"GENESIS:{run_id}:{slug}"),
            }
            for slug in STRATEGY_SLUGS.values()
        ],
        "gates": gates,
    }
    _write_json(bundle / "run_manifest.json", manifest)
    index = _evidence_index(bundle, run_id)
    _write_json(evidence / "evidence_index.json", index)
    seal = {
        "schema_version": "gridrescue-seal-1.0",
        "run_id": run_id,
        "manifest_sha256": _sha256_file(bundle / "run_manifest.json"),
        "evidence_index_sha256": _sha256_file(evidence / "evidence_index.json"),
        "action_ledger_terminal_hashes": terminal_hashes,
        "meaning": "File-integrity seal only; not third-party assurance.",
    }
    _write_json(evidence / "seal.json", seal)
    verification = verify_mrv_bundle(bundle, write_result=True)
    return {"run_id": run_id, "bundle": bundle, "verification": verification}


def _verify_action_chain(actions: pd.DataFrame, run_id: str) -> list[str]:
    errors: list[str] = []
    for slug, group in actions.groupby("strategy_id"):
        expected_prev = f"GENESIS:{run_id}:{slug}"
        expected_sequence = 1
        for row in group.sort_values("sequence_no").to_dict(orient="records"):
            if int(row["sequence_no"]) != expected_sequence:
                errors.append(f"{slug}: non-contiguous action sequence")
            if row["prev_hash"] != expected_prev:
                errors.append(f"{slug}: action prev_hash mismatch at {row['action_id']}")
            if row["record_hash"] != _record_hash(row):
                errors.append(f"{slug}: action record_hash mismatch at {row['action_id']}")
            expected_prev = row["record_hash"]
            expected_sequence += 1
    return errors


def _verify_record_hashes(frame: pd.DataFrame, label: str) -> list[str]:
    errors: list[str] = []
    if "record_hash" not in frame.columns:
        return [f"{label}: missing record_hash column"]
    for row in frame.to_dict(orient="records"):
        actual = str(row.get("record_hash", ""))
        expected = _record_hash(row)
        if actual != expected:
            identifier = row.get("activity_id") or row.get("inventory_id") or row.get("factor_id") or "row"
            errors.append(f"{label}: record_hash mismatch at {identifier}")
    return errors


def _verification_result(
    bundle: Path,
    run_id: str,
    errors: list[str],
    checked_files: int,
    *,
    write_result: bool,
) -> dict[str, Any]:
    result = {
        "schema_version": "gridrescue-verification-1.0",
        "run_id": run_id,
        "verified": not errors,
        "errors": errors,
        "checked_files": checked_files,
        "meaning": "Verification checks reproducibility equations and file integrity only.",
    }
    if write_result:
        _write_json(bundle / "evidence" / "verification.json", result)
    return result


def _verify_mrv_bundle(bundle_dir: str | Path, *, write_result: bool = False) -> dict[str, Any]:
    bundle = Path(bundle_dir)
    errors: list[str] = []
    run_id = "unknown"
    critical_paths = [
        bundle / "run_manifest.json",
        bundle / "evidence" / "evidence_index.json",
        bundle / "evidence" / "seal.json",
        bundle / "inputs" / "scenario.json",
        bundle / "inputs" / "network_snapshot.json",
        bundle / "outputs" / "claim_gates.json",
        *[bundle / "outputs" / f"dispatch_{slug}.csv" for slug in STRATEGY_SLUGS.values()],
        *[bundle / "outputs" / f"topology_state_{slug}.csv" for slug in STRATEGY_SLUGS.values()],
        bundle / "inputs" / "config.json",
        bundle / "inputs" / "factor_registry.csv",
        bundle / "inputs" / "factor_snapshot.csv",
        bundle / "outputs" / "activity_energy_hourly.csv",
        bundle / "outputs" / "emission_inventory_hourly.csv",
        bundle / "outputs" / "actions.csv",
        bundle / "outputs" / "carbon_reconciliation.csv",
    ]
    missing_critical = [path.relative_to(bundle).as_posix() for path in critical_paths if not path.exists()]
    if missing_critical:
        errors.extend(f"missing required file: {path}" for path in missing_critical)
        return _verification_result(bundle, run_id, errors, 0, write_result=write_result)

    try:
        manifest = json.loads((bundle / "run_manifest.json").read_text(encoding="utf-8"))
        run_id = str(manifest["run_id"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        errors.append(f"invalid run manifest: {exc}")
        return _verification_result(bundle, run_id, errors, 0, write_result=write_result)

    index_path = bundle / "evidence" / "evidence_index.json"
    seal_path = bundle / "evidence" / "seal.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        errors.append(f"invalid evidence metadata: {exc}")
        return _verification_result(bundle, run_id, errors, 0, write_result=write_result)

    if str(index.get("run_id")) != run_id:
        errors.append("evidence index run_id mismatch")
    if str(seal.get("run_id")) != run_id:
        errors.append("seal run_id mismatch")
    if seal.get("manifest_sha256") != _sha256_file(bundle / "run_manifest.json"):
        errors.append("manifest hash mismatch")
    if seal.get("evidence_index_sha256") != _sha256_file(index_path):
        errors.append("evidence index hash mismatch")
    indexed_files = index.get("files", [])
    if not isinstance(indexed_files, list):
        errors.append("evidence index files must be a list")
        indexed_files = []
    indexed_paths: set[str] = set()
    for item in indexed_files:
        relative = str(item.get("path", ""))
        if not relative:
            errors.append("evidence index contains empty path")
            continue
        if relative in indexed_paths:
            errors.append(f"duplicate indexed path: {relative}")
        indexed_paths.add(relative)
        path = (bundle / relative).resolve()
        if not path.is_relative_to(bundle.resolve()) or not path.is_file():
            errors.append(f"invalid or missing indexed file: {relative}")
            continue
        if not path.exists():
            errors.append(f"missing file: {item['path']}")
            continue
        if path.stat().st_size != int(item["bytes"]):
            errors.append(f"size mismatch: {item['path']}")
        if _sha256_file(path) != item["sha256"]:
            errors.append(f"hash mismatch: {item['path']}")

    config = json.loads((bundle / "inputs" / "config.json").read_text(encoding="utf-8"))
    time_step_h = float(config.get("time_step_h", 0.0))
    if not math.isfinite(time_step_h) or time_step_h != 1.0:
        errors.append("config supports only time_step_h=1.0")
    gates = json.loads((bundle / "outputs" / "claim_gates.json").read_text(encoding="utf-8"))
    if manifest.get("gates") != gates:
        errors.append("manifest/claim gates mismatch")
    if float(manifest.get("boundary", {}).get("time_step_h", 0.0)) != time_step_h:
        errors.append("manifest/config time_step_h mismatch")

    manifest_hash_checks = {
        "scenario sha256": (
            manifest.get("scenario", {}).get("sha256"),
            bundle / "inputs" / "scenario.json",
        ),
        "network snapshot sha256": (
            manifest.get("network", {}).get("snapshot_sha256"),
            bundle / "inputs" / "network_snapshot.json",
        ),
        "config sha256": (manifest.get("config_sha256"), bundle / "inputs" / "config.json"),
        "factor registry sha256": (
            manifest.get("factor_registry_sha256"),
            bundle / "inputs" / "factor_registry.csv",
        ),
        "factor snapshot sha256": (
            manifest.get("factor_snapshot_sha256"),
            bundle / "inputs" / "factor_snapshot.csv",
        ),
    }
    for label, (recorded, path) in manifest_hash_checks.items():
        if not path.exists() or recorded != _sha256_file(path):
            errors.append(f"manifest {label} mismatch")

    registry = pd.read_csv(
        bundle / "inputs" / "factor_registry.csv",
        keep_default_na=False,
        dtype={"factor_version": str},
    )
    factors = pd.read_csv(
        bundle / "inputs" / "factor_snapshot.csv",
        keep_default_na=False,
        dtype={"factor_version": str},
    )
    activities = pd.read_csv(
        bundle / "outputs" / "activity_energy_hourly.csv",
        keep_default_na=False,
    )
    errors.extend(_verify_record_hashes(registry, "factor registry"))
    errors.extend(_verify_record_hashes(factors, "factor snapshot"))
    errors.extend(_verify_record_hashes(activities, "activity ledger"))
    if activities.duplicated(["strategy_id", "hour", "energy_flow"]).any():
        errors.append("duplicate activity key")
    dispatch_columns = {"grid_import": "grid_import_kw", "diesel_generation": "diesel_generation_kw", "pv_available": "pv_available_kw", "bess_charge": "battery_charge_kw", "bess_discharge": "battery_discharge_kw", "renewable_curtailment": "renewable_curtailment_kw", "unserved_critical": "unserved_critical_kw", "unserved_normal": "unserved_normal_kw"}
    for slug in STRATEGY_SLUGS.values():
        frame = pd.read_csv(bundle / "outputs" / f"dispatch_{slug}.csv").set_index("hour")
        subset = activities[activities["strategy_id"] == slug]
        if set(frame.index) != set(range(24)) or len(frame) != 24 or len(subset) != 192:
            errors.append(f"{slug}: incomplete dispatch/activity horizon")
            continue
        for row in subset.itertuples():
            column = dispatch_columns.get(str(row.energy_flow))
            if column is None or int(row.hour) not in frame.index or abs(float(row.power_kw) - max(float(frame.loc[int(row.hour), column]), 0.0)) > 1e-6:
                errors.append(f"{slug}: dispatch/activity value mismatch")
    if not activities.empty and not (activities["run_id"].astype(str) == run_id).all():
        errors.append("activity run_id mismatch")
    if not activities.empty and not (activities["time_step_h"].astype(float) == time_step_h).all():
        errors.append("activity/config time_step_h mismatch")
    energy_error = (activities["energy_kwh"] - activities["power_kw"] * activities["time_step_h"]).abs()
    if not energy_error.empty and float(energy_error.max()) > 1e-6:
        errors.append("activity power/energy equation failed")
    if (activities[["power_kw", "energy_kwh"]].to_numpy(float) < -1e-9).any():
        errors.append("negative activity value")
    inventory = pd.read_csv(
        bundle / "outputs" / "emission_inventory_hourly.csv",
        keep_default_na=False,
        dtype={"factor_version": str},
    )
    errors.extend(_verify_record_hashes(inventory, "emission inventory"))
    if not inventory.empty and not (inventory["run_id"].astype(str) == run_id).all():
        errors.append("inventory run_id mismatch")
    inventory_error = (
        inventory["emission_value"]
        - inventory["activity_value"] * inventory["factor_value"]
    ).abs()
    if not inventory_error.empty and float(inventory_error.max()) > 1e-6:
        errors.append("inventory equation failed")

    activity_hashes = set(activities["record_hash"].astype(str))
    factor_hashes = set(factors["record_hash"].astype(str))
    activity_links = inventory.loc[
        inventory["activity_record_hash"].astype(str).str.startswith("sha256:"),
        "activity_record_hash",
    ].astype(str)
    if not activity_links.isin(activity_hashes).all():
        errors.append("inventory activity hash reference failed")
    if not inventory["factor_record_hash"].astype(str).isin(factor_hashes).all():
        errors.append("inventory factor hash reference failed")
    factor_by_hash = factors.set_index("record_hash")
    activity_by_hash = activities.set_index("record_hash")
    for row in inventory.itertuples():
        if row.factor_record_hash in factor_by_hash.index:
            factor = factor_by_hash.loc[row.factor_record_hash]
            if float(row.factor_value) != float(factor["value"]) or str(row.factor_id) != str(factor["factor_id"]) or int(row.hour) != int(factor["hour"]):
                errors.append("inventory factor value/key mismatch")
        if row.activity_record_hash in activity_by_hash.index:
            activity = activity_by_hash.loc[row.activity_record_hash]
            if abs(float(row.activity_value) - float(activity["energy_kwh"])) > 1e-6 or str(row.strategy_id) != str(activity["strategy_id"]) or int(row.hour) != int(activity["hour"]):
                errors.append("inventory activity value/key mismatch")

    registry_hashes = set(registry["record_hash"].astype(str))
    if not factors["registry_record_hash"].astype(str).isin(registry_hashes).all():
        errors.append("factor snapshot registry reference failed")

    for reference in activities["dispatch_ref"].astype(str):
        relative = reference.split("#", 1)[0]
        indexed_key = f"outputs/{relative}"
        if indexed_key not in indexed_paths or not (bundle / "outputs" / relative).exists():
            errors.append(f"missing activity evidence reference: {reference}")

    actions = pd.read_csv(bundle / "outputs" / "actions.csv", keep_default_na=False)
    if not actions.empty and not (actions["run_id"].astype(str) == run_id).all():
        errors.append("action run_id mismatch")
    errors.extend(_verify_action_chain(actions, run_id))
    for reference in actions["evidence_ref"].astype(str):
        relative = reference.split("#", 1)[0]
        indexed_key = f"outputs/{relative}"
        if indexed_key not in indexed_paths or not (bundle / "outputs" / relative).exists():
            errors.append(f"missing action evidence reference: {reference}")
    reconciliation = pd.read_csv(bundle / "outputs" / "carbon_reconciliation.csv")
    for row in reconciliation.to_dict(orient="records"):
        slug = str(row["strategy_id"])
        inventory_total = float(
            inventory.loc[inventory["strategy_id"].astype(str) == slug, "emission_value"].sum()
        )
        recorded_inventory = float(row["inventory_total_kgCO2"])
        carbon_total = float(row["carbon_breakdown_total_kgCO2"])
        recorded_difference = float(row["difference_kgCO2"])
        expected_difference = recorded_inventory - carbon_total
        expected_reconciled = abs(expected_difference) <= 1e-5
        if abs(inventory_total - recorded_inventory) > 1e-6:
            errors.append(f"{slug}: reconciliation inventory subtotal mismatch")
        if abs(expected_difference - recorded_difference) > 1e-6:
            errors.append(f"{slug}: reconciliation difference equation failed")
        if bool(row["reconciled"]) != expected_reconciled or not expected_reconciled:
            errors.append(f"{slug}: carbon reconciliation failed")

    calculated_terminal = {
        slug: (
            str(group.sort_values("sequence_no").iloc[-1]["record_hash"])
            if not group.empty
            else f"GENESIS:{run_id}:{slug}"
        )
        for slug, group in actions.groupby("strategy_id")
    }
    manifest_terminal = {
        str(item.get("strategy_id")): str(item.get("action_ledger_terminal_hash"))
        for item in manifest.get("strategies", [])
    }
    seal_terminal = {
        str(key): str(value)
        for key, value in seal.get("action_ledger_terminal_hashes", {}).items()
    }
    for slug in STRATEGY_SLUGS.values():
        expected = calculated_terminal.get(slug, f"GENESIS:{run_id}:{slug}")
        if manifest_terminal.get(slug) != expected:
            errors.append(f"{slug}: manifest action terminal hash mismatch")
        if seal_terminal.get(slug) != expected:
            errors.append(f"{slug}: seal action terminal hash mismatch")

    return _verification_result(
        bundle,
        run_id,
        errors,
        len(indexed_files),
        write_result=write_result,
    )


def verify_mrv_bundle(bundle_dir: str | Path, *, write_result: bool = False) -> dict[str, Any]:
    """Fail closed for malformed evidence, without exposing parser exceptions to UI."""
    try:
        return _verify_mrv_bundle(bundle_dir, write_result=write_result)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return _verification_result(Path(bundle_dir), "unknown", [f"invalid evidence: {exc}"], 0, write_result=write_result)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="GridRescue MRV evidence utilities")
    commands = parser.add_subparsers(dest="command", required=True)
    verify_parser = commands.add_parser("verify", help="verify an existing MRV bundle")
    verify_parser.add_argument("bundle", help="path to a run-* MRV bundle")
    verify_parser.add_argument(
        "--write-result",
        action="store_true",
        help="write evidence/verification.json after verification",
    )
    args = parser.parse_args(argv)
    if args.command == "verify":
        result = verify_mrv_bundle(args.bundle, write_result=args.write_result)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(0 if result["verified"] else 1)


if __name__ == "__main__":
    main()
