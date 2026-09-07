from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .carbon import DEFAULT_EMISSION_FACTORS
from .care import (
    CareTask,
    care_task_definition_hash,
    care_task_requirements,
    default_care_tasks,
    evaluate_care_tasks,
)
from .dispatch import DispatchObjective, ServiceContract
from .network import build_ieee33
from .pipeline import PhysicalFeedback, solve_strategy_with_feedback
from .restoration import STRATEGIES, StrategyResult
from .scenarios import DisasterScenario, SCENARIOS, get_scenario


@dataclass(frozen=True)
class ParetoScanSpec:
    """Configuration for a same-service carbon/normal-EENS frontier."""

    strategies: tuple[str, ...] = ("最小失供恢复",)
    normal_allowance_fractions: tuple[float, ...] = (0.0, 0.01, 0.04, 0.08)
    max_feedback_iterations: int = 8
    feedback_tolerance_kw: float = 0.10
    contract_tolerance_kwh: float = 1e-3
    care_tasks: tuple[CareTask, ...] = field(default_factory=default_care_tasks)
    output_dir: Path | None = None

    def __post_init__(self) -> None:
        unknown = set(self.strategies).difference(STRATEGIES)
        if unknown:
            raise ValueError(f"unknown strategies: {sorted(unknown)}")
        if not self.strategies:
            raise ValueError("at least one strategy is required")
        if not self.normal_allowance_fractions:
            raise ValueError("at least one normal allowance fraction is required")
        if any(not 0.0 <= float(value) <= 1.0 for value in self.normal_allowance_fractions):
            raise ValueError("normal allowance fractions must be in [0, 1]")
        if self.max_feedback_iterations < 1:
            raise ValueError("max_feedback_iterations must be positive")
        if self.feedback_tolerance_kw <= 0:
            raise ValueError("feedback_tolerance_kw must be positive")
        if self.contract_tolerance_kwh < 0:
            raise ValueError("contract_tolerance_kwh must be non-negative")


@dataclass(frozen=True)
class ParetoScanResult:
    spec: ParetoScanSpec
    anchors: pd.DataFrame
    points: pd.DataFrame
    frontier: pd.DataFrame
    failures: pd.DataFrame
    care_evaluations: pd.DataFrame
    artifacts: dict[str, Path]


def _service_totals(result: StrategyResult) -> dict[str, float]:
    node_frame = result.dispatch.node_frame
    if node_frame is None:
        raise ValueError("Pareto scan requires node-level dispatch evidence")
    service_class = node_frame["service_class"].astype(str)
    critical_unserved = node_frame["critical_load_kw"] - node_frame["served_critical_kw"]
    normal_unserved = node_frame["normal_load_kw"] - node_frame["served_normal_kw"]
    hospital_mask = service_class.eq("hospital")
    other_essential_mask = service_class.isin(["essential", "critical"])
    return {
        "hospital_demand_kwh": float(node_frame.loc[hospital_mask, "critical_load_kw"].sum()),
        "hospital_eens_kwh": float(critical_unserved.loc[hospital_mask].sum()),
        "other_essential_demand_kwh": float(
            node_frame.loc[other_essential_mask, "critical_load_kw"].sum()
        ),
        "other_essential_eens_kwh": float(critical_unserved.loc[other_essential_mask].sum()),
        "normal_demand_kwh": float(node_frame["normal_load_kw"].sum()),
        "normal_eens_kwh": float(normal_unserved.sum()),
        "served_kwh": float(
            node_frame["served_critical_kw"].sum() + node_frame["served_normal_kw"].sum()
        ),
    }


def _run_id(
    scenario: DisasterScenario,
    strategy: str,
    fraction: float,
    hospital_cap: float,
    essential_cap: float,
    normal_cap: float,
    care_tasks: tuple[CareTask, ...],
) -> str:
    payload = json.dumps(
        {
            "scenario": scenario.name,
            "failed_branch_ids": scenario.failed_branch_ids,
            "repair_hours": scenario.repair_hours,
            "strategy": strategy,
            "normal_allowance_fraction": fraction,
            "hospital_cap": round(hospital_cap, 6),
            "essential_cap": round(essential_cap, 6),
            "normal_cap": round(normal_cap, 6),
            "care_tasks": [asdict(task) for task in care_tasks],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _failure_reason(error: Exception) -> str:
    return f"{type(error).__name__}: {' '.join(str(error).split())}"[:2000]


def _anchor_row(
    scenario: DisasterScenario,
    strategy: str,
    phase: str,
    *,
    success: bool,
    totals: dict[str, float] | None = None,
    feedback: PhysicalFeedback | None = None,
    error: Exception | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "scenario": scenario.name,
        "strategy": strategy,
        "anchor_phase": phase,
        "solve_success": success,
        "feedback_converged": bool(feedback.converged) if feedback is not None else False,
        "feedback_iterations": feedback.iterations if feedback is not None else pd.NA,
        "feedback_residual_kw": feedback.max_residual_kw if feedback is not None else pd.NA,
        "failure_reason": _failure_reason(error) if error is not None else pd.NA,
    }
    for name in (
        "hospital_demand_kwh",
        "hospital_eens_kwh",
        "other_essential_demand_kwh",
        "other_essential_eens_kwh",
        "normal_demand_kwh",
        "normal_eens_kwh",
        "served_kwh",
    ):
        row[name] = totals[name] if totals is not None else pd.NA
    return row


def _solve_anchor(
    model,
    scenario: DisasterScenario,
    strategy: str,
    phase: str,
    objective_kind: str,
    contract: ServiceContract,
    spec: ParetoScanSpec,
    initial_feedback: PhysicalFeedback | None,
    *,
    require_convergence: bool = True,
):
    started = time.perf_counter()
    result, validation, feedback = solve_strategy_with_feedback(
        model,
        scenario,
        strategy,
        service_contract=contract,
        dispatch_objective=DispatchObjective(objective_kind),
        initial_feedback=initial_feedback,
        max_iterations=spec.max_feedback_iterations,
        tolerance_kw=spec.feedback_tolerance_kw,
        strict_contract=True,
    )
    totals = _service_totals(result)
    care_evaluation = evaluate_care_tasks(spec.care_tasks, result, validation)
    care_pass = bool(care_evaluation["task_complete"].all()) if not care_evaluation.empty else True
    physical_pass = bool(
        validation.hourly["is_feasible"].all()
        and (feedback.converged or not require_convergence)
        and care_pass
    )
    if not physical_pass:
        raise RuntimeError(
            f"{phase} physical feedback failed: converged={feedback.converged}, "
            f"feasible_hours={int(validation.hourly['is_feasible'].sum())}/24, "
            f"residual_kw={feedback.max_residual_kw:.6f}, care_pass={care_pass}"
        )
    return result, validation, feedback, totals, care_evaluation, time.perf_counter() - started


def _care_summary(evaluation: pd.DataFrame) -> dict[str, object]:
    if evaluation.empty:
        return {
            "care_task_count": 0,
            "care_completed_count": 0,
            "care_tier1_completed": 0,
            "care_contract_pass": True,
            "care_definition_sha256": pd.NA,
            "care_failure_reason": pd.NA,
        }
    failed = evaluation.loc[~evaluation["task_complete"].astype(bool)]
    return {
        "care_task_count": len(evaluation),
        "care_completed_count": int(evaluation["task_complete"].sum()),
        "care_tier1_completed": int(
            evaluation.loc[evaluation["tier"] == 1, "task_complete"].sum()
        ),
        "care_contract_pass": failed.empty,
        "care_definition_sha256": str(evaluation["definition_sha256"].iloc[0]),
        "care_failure_reason": (
            pd.NA
            if failed.empty
            else "; ".join(
                f"{row.task_id}:{row.failure_reason_codes}" for row in failed.itertuples()
            )
        ),
    }


def _mark_nondominated(points: pd.DataFrame, tolerance: float = 1e-6) -> pd.DataFrame:
    out = points.copy()
    out["nondominated"] = False
    eligible = out.index[out["frontier_eligible"].fillna(False).astype(bool)].tolist()
    for index in eligible:
        candidate = out.loc[index]
        dominated = False
        for other_index in eligible:
            if other_index == index:
                continue
            other = out.loc[other_index]
            no_worse = (
                float(other["normal_eens_kwh"]) <= float(candidate["normal_eens_kwh"]) + tolerance
                and float(other["total_carbon_kg"]) <= float(candidate["total_carbon_kg"]) + tolerance
            )
            strictly_better = (
                float(other["normal_eens_kwh"]) < float(candidate["normal_eens_kwh"]) - tolerance
                or float(other["total_carbon_kg"]) < float(candidate["total_carbon_kg"]) - tolerance
            )
            if no_worse and strictly_better:
                dominated = True
                break
        out.loc[index, "nondominated"] = not dominated
    return out


def _write_artifacts(
    result: ParetoScanResult,
    scenario: DisasterScenario,
    source_sha256: str,
) -> dict[str, Path]:
    if result.spec.output_dir is None:
        return {}
    output = Path(result.spec.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "anchors": output / "pareto_anchors.csv",
        "points": output / "pareto_points.csv",
        "frontier": output / "pareto_frontier.csv",
        "failures": output / "pareto_failures.csv",
        "manifest": output / "pareto_manifest.json",
        "care_tasks": output / "care_task_definitions.json",
        "care_evaluations": output / "pareto_care_task_evaluations.csv",
    }
    result.anchors.to_csv(paths["anchors"], index=False)
    result.points.to_csv(paths["points"], index=False)
    result.frontier.to_csv(paths["frontier"], index=False)
    result.failures.to_csv(paths["failures"], index=False)
    result.care_evaluations.to_csv(paths["care_evaluations"], index=False)
    paths["care_tasks"].write_text(
        json.dumps(
            {
                "schema_version": 1,
                "definition_sha256": care_task_definition_hash(result.spec.care_tasks),
                "tasks": [asdict(task) for task in result.spec.care_tasks],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    spec_payload = asdict(result.spec)
    spec_payload["output_dir"] = str(result.spec.output_dir)
    manifest = {
        "schema_version": 2,
        "scenario": asdict(scenario),
        "network_source_sha256": source_sha256,
        "care_definition_sha256": care_task_definition_hash(result.spec.care_tasks),
        "spec": spec_payload,
        "counts": {
            "anchors": len(result.anchors),
            "points": len(result.points),
            "frontier": len(result.frontier),
            "failures": len(result.failures),
            "care_evaluations": len(result.care_evaluations),
        },
        "data_boundary": (
            "CareTask values are E-class synthetic scenario templates, not real hospital "
            "measurements or clinical standards."
        ),
    }
    paths["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return paths


def scan_pareto(
    scenario: str | DisasterScenario,
    spec: ParetoScanSpec = ParetoScanSpec(),
) -> ParetoScanResult:
    """Compute an auditable same-service normal-EENS/carbon frontier.

    Every epsilon attempt produces a row. Solver failures, feedback failures,
    service-contract violations and physical violations remain visible in the
    points/failures tables and are excluded from the recommended frontier.
    """

    active_scenario = get_scenario(scenario) if isinstance(scenario, str) else scenario
    model = build_ieee33()
    anchor_rows: list[dict[str, object]] = []
    point_rows: list[dict[str, object]] = []
    care_rows: list[dict[str, object]] = []
    crew_kg = active_scenario.crew_distance_km * DEFAULT_EMISSION_FACTORS.crew_vehicle_kg_per_km
    task_requirements = care_task_requirements(spec.care_tasks)

    for strategy in spec.strategies:
        feedback: PhysicalFeedback | None = None
        try:
            _, _, feedback, hospital_totals, _, _ = _solve_anchor(
                model,
                active_scenario,
                strategy,
                "hospital",
                "min_hospital_eens",
                ServiceContract(
                    tolerance_kwh=spec.contract_tolerance_kwh,
                    task_requirements=task_requirements,
                ),
                spec,
                feedback,
            )
            anchor_rows.append(
                _anchor_row(
                    active_scenario,
                    strategy,
                    "hospital",
                    success=True,
                    totals=hospital_totals,
                    feedback=feedback,
                )
            )
        except Exception as error:
            anchor_rows.append(
                _anchor_row(active_scenario, strategy, "hospital", success=False, error=error)
            )
            for fraction in spec.normal_allowance_fractions:
                point_rows.append(
                    {
                        "run_id": pd.NA,
                        "scenario": active_scenario.name,
                        "strategy": strategy,
                        "normal_allowance_fraction": float(fraction),
                        "solve_success": False,
                        "contract_pass": False,
                        "physical_pass": False,
                        "frontier_eligible": False,
                        "failure_phase": "hospital_anchor",
                        "failure_reason": _failure_reason(error),
                    }
                )
            continue

        hospital_tau = max(
            spec.contract_tolerance_kwh,
            1e-6 * hospital_totals["hospital_demand_kwh"],
        )
        hospital_cap = hospital_totals["hospital_eens_kwh"] + hospital_tau
        try:
            _, _, feedback, essential_totals, _, _ = _solve_anchor(
                model,
                active_scenario,
                strategy,
                "other_essential",
                "min_essential_eens",
                ServiceContract(
                    hospital_unserved_cap_kwh=hospital_cap,
                    tolerance_kwh=spec.contract_tolerance_kwh,
                    task_requirements=task_requirements,
                ),
                spec,
                None,
            )
            anchor_rows.append(
                _anchor_row(
                    active_scenario,
                    strategy,
                    "other_essential",
                    success=True,
                    totals=essential_totals,
                    feedback=feedback,
                )
            )
        except Exception as error:
            anchor_rows.append(
                _anchor_row(active_scenario, strategy, "other_essential", success=False, error=error)
            )
            for fraction in spec.normal_allowance_fractions:
                point_rows.append(
                    {
                        "run_id": pd.NA,
                        "scenario": active_scenario.name,
                        "strategy": strategy,
                        "normal_allowance_fraction": float(fraction),
                        "solve_success": False,
                        "contract_pass": False,
                        "physical_pass": False,
                        "frontier_eligible": False,
                        "failure_phase": "essential_anchor",
                        "failure_reason": _failure_reason(error),
                    }
                )
            continue

        essential_tau = max(
            spec.contract_tolerance_kwh,
            1e-6 * essential_totals["other_essential_demand_kwh"],
        )
        essential_cap = essential_totals["other_essential_eens_kwh"] + essential_tau
        anchor_contract = ServiceContract(
            hospital_unserved_cap_kwh=hospital_cap,
            other_essential_unserved_cap_kwh=essential_cap,
            tolerance_kwh=spec.contract_tolerance_kwh,
            task_requirements=task_requirements,
        )
        try:
            (
                normal_result,
                normal_validation,
                feedback,
                normal_totals,
                normal_care,
                normal_solve_seconds,
            ) = _solve_anchor(
                model,
                active_scenario,
                strategy,
                "normal",
                "min_normal_eens",
                anchor_contract,
                spec,
                None,
            )
            anchor_rows.append(
                _anchor_row(
                    active_scenario,
                    strategy,
                    "normal",
                    success=True,
                    totals=normal_totals,
                    feedback=feedback,
                )
            )
        except Exception as error:
            anchor_rows.append(
                _anchor_row(active_scenario, strategy, "normal", success=False, error=error)
            )
            for fraction in spec.normal_allowance_fractions:
                point_rows.append(
                    {
                        "run_id": pd.NA,
                        "scenario": active_scenario.name,
                        "strategy": strategy,
                        "normal_allowance_fraction": float(fraction),
                        "solve_success": False,
                        "contract_pass": False,
                        "physical_pass": False,
                        "frontier_eligible": False,
                        "failure_phase": "normal_anchor",
                        "failure_reason": _failure_reason(error),
                    }
                )
            continue

        normal_star = normal_totals["normal_eens_kwh"]
        normal_demand = normal_totals["normal_demand_kwh"]
        for fraction in sorted(set(float(x) for x in spec.normal_allowance_fractions)):
            normal_cap = normal_star + fraction * normal_demand
            run_id = _run_id(
                active_scenario,
                strategy,
                fraction,
                hospital_cap,
                essential_cap,
                normal_cap,
                spec.care_tasks,
            )
            contract = ServiceContract(
                hospital_unserved_cap_kwh=hospital_cap,
                other_essential_unserved_cap_kwh=essential_cap,
                normal_unserved_cap_kwh=normal_cap,
                crew_emissions_kg=crew_kg,
                tolerance_kwh=spec.contract_tolerance_kwh,
                task_requirements=task_requirements,
            )
            started = time.perf_counter()
            base_row: dict[str, object] = {
                "run_id": run_id,
                "scenario": active_scenario.name,
                "strategy": strategy,
                "scan_axis": "normal_eens",
                "point_kind": "service_anchor" if abs(fraction) <= 1e-12 else "epsilon_candidate",
                "normal_allowance_fraction": fraction,
                "hospital_eens_cap_kwh": hospital_cap,
                "other_essential_eens_cap_kwh": essential_cap,
                "normal_eens_cap_kwh": normal_cap,
                "solve_success": False,
                "contract_pass": False,
                "physical_pass": False,
                "frontier_eligible": False,
                "failure_phase": pd.NA,
                "failure_reason": pd.NA,
            }
            if abs(fraction) <= 1e-12:
                # The lexicographic minimum-normal-EENS anchor is the proven
                # feasible endpoint of the frontier. Re-optimizing carbon at
                # an exactly equal cap can make the iterative component-cap
                # feedback numerically over-conservative even though this
                # endpoint itself is already physically verified.
                base_row.update(
                    {
                        **normal_totals,
                        **_care_summary(normal_care),
                        "total_carbon_kg": normal_result.carbon.total_operational_kg,
                        "grid_carbon_kg": normal_result.carbon.grid_kg,
                        "diesel_carbon_kg": normal_result.carbon.diesel_kg,
                        "crew_carbon_kg": normal_result.carbon.crew_kg,
                        "eens_kwh": normal_result.metrics.eens_kwh,
                        "critical_recovery_pct": normal_result.metrics.critical_recovery_pct,
                        "diesel_energy_kwh": normal_result.metrics.diesel_energy_kwh,
                        "renewable_consumed_kwh": normal_result.metrics.renewable_consumed_kwh,
                        "solver_status": normal_result.dispatch.status,
                        "feedback_converged": feedback.converged,
                        "feedback_iterations": feedback.iterations,
                        "feedback_residual_kw": feedback.max_residual_kw,
                        "physical_feasible_hours": int(normal_validation.hourly["is_feasible"].sum()),
                        "max_branch_loading_pct": float(
                            normal_validation.hourly["max_branch_loading_pct"].max()
                        ),
                        "min_voltage_pu": float(normal_validation.hourly["min_voltage_pu"].min()),
                        "max_source_adjustment_kw": float(
                            normal_validation.hourly["source_adjustment_kw"].abs().max()
                        ),
                        "solve_success": True,
                        "contract_pass": True,
                        "physical_pass": True,
                        "frontier_eligible": True,
                        "solve_seconds": normal_solve_seconds,
                    }
                )
                anchor_care = normal_care.copy()
                anchor_care.insert(0, "run_id", run_id)
                anchor_care.insert(1, "normal_allowance_fraction", fraction)
                care_rows.extend(anchor_care.to_dict(orient="records"))
                point_rows.append(base_row)
                continue
            try:
                candidate, validation, candidate_feedback = solve_strategy_with_feedback(
                    model,
                    active_scenario,
                    strategy,
                    service_contract=contract,
                    dispatch_objective=DispatchObjective("min_carbon"),
                    initial_feedback=feedback,
                    max_iterations=spec.max_feedback_iterations,
                    tolerance_kw=spec.feedback_tolerance_kw,
                    strict_contract=True,
                )
                totals = _service_totals(candidate)
                care_evaluation = evaluate_care_tasks(spec.care_tasks, candidate, validation)
                care_summary = _care_summary(care_evaluation)
                contract_tolerance = max(spec.contract_tolerance_kwh * 10.0, 1e-3)
                contract_pass = bool(
                    totals["hospital_eens_kwh"] <= hospital_cap + contract_tolerance
                    and totals["other_essential_eens_kwh"] <= essential_cap + contract_tolerance
                    and totals["normal_eens_kwh"] <= normal_cap + contract_tolerance
                    and care_summary["care_contract_pass"]
                )
                physical_pass = bool(
                    candidate_feedback.converged and validation.hourly["is_feasible"].all()
                )
                base_row.update(
                    {
                        **totals,
                        **care_summary,
                        "total_carbon_kg": candidate.carbon.total_operational_kg,
                        "grid_carbon_kg": candidate.carbon.grid_kg,
                        "diesel_carbon_kg": candidate.carbon.diesel_kg,
                        "crew_carbon_kg": candidate.carbon.crew_kg,
                        "eens_kwh": candidate.metrics.eens_kwh,
                        "critical_recovery_pct": candidate.metrics.critical_recovery_pct,
                        "diesel_energy_kwh": candidate.metrics.diesel_energy_kwh,
                        "renewable_consumed_kwh": candidate.metrics.renewable_consumed_kwh,
                        "solver_status": candidate.dispatch.status,
                        "feedback_converged": candidate_feedback.converged,
                        "feedback_iterations": candidate_feedback.iterations,
                        "feedback_residual_kw": candidate_feedback.max_residual_kw,
                        "physical_feasible_hours": int(validation.hourly["is_feasible"].sum()),
                        "max_branch_loading_pct": float(
                            validation.hourly["max_branch_loading_pct"].max()
                        ),
                        "min_voltage_pu": float(validation.hourly["min_voltage_pu"].min()),
                        "max_source_adjustment_kw": float(
                            validation.hourly["source_adjustment_kw"].abs().max()
                        ),
                        "solve_success": True,
                        "contract_pass": contract_pass,
                        "physical_pass": physical_pass,
                        "frontier_eligible": contract_pass and physical_pass,
                    }
                )
                candidate_care = care_evaluation.copy()
                candidate_care.insert(0, "run_id", run_id)
                candidate_care.insert(1, "normal_allowance_fraction", fraction)
                care_rows.extend(candidate_care.to_dict(orient="records"))
                if not contract_pass:
                    base_row["failure_phase"] = "contract_validation"
                    base_row["failure_reason"] = "recomputed service totals exceed epsilon contract"
                elif not physical_pass:
                    base_row["failure_phase"] = "physical_feedback"
                    base_row["failure_reason"] = (
                        f"converged={candidate_feedback.converged}; "
                        f"feasible_hours={int(validation.hourly['is_feasible'].sum())}/24"
                    )
            except Exception as error:
                base_row["failure_phase"] = "candidate_solve"
                base_row["failure_reason"] = _failure_reason(error)
            base_row["solve_seconds"] = time.perf_counter() - started
            point_rows.append(base_row)

    anchors = pd.DataFrame(anchor_rows)
    points = _mark_nondominated(pd.DataFrame(point_rows))
    frontier = points.loc[points["nondominated"].fillna(False).astype(bool)].copy()
    if not frontier.empty:
        frontier = frontier.sort_values(["normal_eens_kwh", "total_carbon_kg"]).reset_index(drop=True)
    failures = points.loc[~points["frontier_eligible"].fillna(False).astype(bool)].copy()
    care_evaluations = pd.DataFrame(care_rows)
    provisional = ParetoScanResult(
        spec, anchors, points, frontier, failures, care_evaluations, {}
    )
    artifacts = _write_artifacts(provisional, active_scenario, model.source_sha256)
    return ParetoScanResult(
        spec, anchors, points, frontier, failures, care_evaluations, artifacts
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="GridRescue same-service epsilon Pareto scan")
    parser.add_argument("--scenario", choices=list(SCENARIOS), default="暴雨内涝")
    parser.add_argument("--strategy", choices=list(STRATEGIES), default="最小失供恢复")
    parser.add_argument("--fractions", default="0,0.01,0.04,0.08")
    parser.add_argument("--output", default="artifacts/pareto")
    args = parser.parse_args()
    fractions = tuple(float(value.strip()) for value in args.fractions.split(",") if value.strip())
    result = scan_pareto(
        args.scenario,
        ParetoScanSpec(
            strategies=(args.strategy,),
            normal_allowance_fractions=fractions,
            output_dir=Path(args.output),
        ),
    )
    print(result.frontier.to_string(index=False))
    print(
        f"\npoints={len(result.points)} frontier={len(result.frontier)} "
        f"failures={len(result.failures)} output={Path(args.output).resolve()}"
    )


if __name__ == "__main__":
    main()
