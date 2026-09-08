from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from statistics import NormalDist
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .care import default_care_tasks, evaluate_care_tasks
from .network import build_ieee33
from .pipeline import run_scenario
from .restoration import STRATEGIES, StrategyResult, simulate_strategy
from .scenarios import DisasterScenario, sample_fault_scenarios


# Metrics are deliberately kept in one place so a failed solve has the same
# schema as a successful one.  This makes failed scenarios safe to aggregate
# and avoids accidentally treating missing values as zero outage.
RESULT_METRICS = (
    "eens_kwh",
    "critical_eens_kwh",
    "critical_recovery_pct",
    "diesel_energy_kwh",
    "renewable_consumed_kwh",
    "total_carbon_kg",
)
PHYSICAL_METRICS = (
    "physical_feasible_hours",
    "max_branch_loading_pct",
    "min_voltage_pu",
    "source_adjustment_max_kw",
)
REPLAY_SCHEMA_VERSION = 1


def scenario_to_dict(scenario: DisasterScenario) -> dict[str, object]:
    """Serialize all inputs needed to replay one generated scenario."""

    payload = asdict(scenario)
    # JSON has no tuple type.  Lists also make the saved failure artifact easy
    # to inspect and edit by hand.
    payload["failed_branch_ids"] = list(scenario.failed_branch_ids)
    payload["repair_hours"] = list(scenario.repair_hours)
    return payload


def scenario_from_dict(payload: Mapping[str, Any]) -> DisasterScenario:
    """Recreate a :class:`DisasterScenario` from a result or replay manifest."""

    required = {
        "name",
        "description",
        "failed_branch_ids",
        "repair_hours",
        "pv_derating",
        "grid_carbon_multiplier",
        "crew_distance_km",
        "ambient_temperature_c",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"scenario definition missing fields: {sorted(missing)}")
    return DisasterScenario(
        name=str(payload["name"]),
        disaster_type=str(payload.get("disaster_type", "")),
        load_profile=tuple(float(x) for x in payload.get("load_profile", ())),
        pv_profile=tuple(float(x) for x in payload.get("pv_profile", ())),
        grid_factor=payload.get("grid_factor"),
        provenance_json=str(payload.get("provenance_json", "")),
        description=str(payload["description"]),
        failed_branch_ids=tuple(int(branch) for branch in payload["failed_branch_ids"]),
        repair_hours=tuple(int(hours) for hours in payload["repair_hours"]),
        pv_derating=float(payload["pv_derating"]),
        grid_carbon_multiplier=float(payload["grid_carbon_multiplier"]),
        crew_distance_km=float(payload["crew_distance_km"]),
        ambient_temperature_c=float(payload["ambient_temperature_c"]),
    )


def _scenario_json(scenario: DisasterScenario) -> str:
    return json.dumps(scenario_to_dict(scenario), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _scenario_id(index: int) -> str:
    return f"scenario-{index:04d}"


def _failure_reason(error: Exception) -> str:
    message = " ".join(str(error).split())
    # Keep CSV and JSON artifacts readable even when a solver emits a huge
    # diagnostic payload, while retaining both the exception type and cause.
    return f"{type(error).__name__}: {message}"[:2000]


def _base_row(
    scenario: DisasterScenario,
    *,
    scenario_index: int,
    seed: int,
    strategy: str,
    physical: bool,
) -> dict[str, object]:
    definition = _scenario_json(scenario)
    return {
        "scenario_id": _scenario_id(scenario_index),
        "scenario": scenario.name,
        "scenario_index": scenario_index,
        "run_seed": seed,
        "scenario_sha256": hashlib.sha256(definition.encode("utf-8")).hexdigest(),
        "scenario_definition": definition,
        "fault_count": len(scenario.failed_branch_ids),
        "failed_branch_ids": json.dumps(list(scenario.failed_branch_ids)),
        "repair_hours": json.dumps(list(scenario.repair_hours)),
        "pv_derating": scenario.pv_derating,
        "grid_carbon_multiplier": scenario.grid_carbon_multiplier,
        "crew_distance_km": scenario.crew_distance_km,
        "ambient_temperature_c": scenario.ambient_temperature_c,
        "strategy": strategy,
        "physical_requested": physical,
        "solve_success": False,
        "failure_phase": pd.NA,
        "failure_reason": pd.NA,
        **{metric: pd.NA for metric in RESULT_METRICS + PHYSICAL_METRICS},
    }


def _complete_row(
    row: dict[str, object],
    result: StrategyResult,
    validation: Any | None,
) -> dict[str, object]:
    row.update(asdict(result.metrics))
    row["solve_success"] = True
    if validation is not None:
        hourly = validation.hourly
        row.update(
            {
                "physical_feasible_hours": int(hourly["is_feasible"].fillna(False).sum()),
                "max_branch_loading_pct": float(hourly["max_branch_loading_pct"].max()),
                "min_voltage_pu": float(hourly["min_voltage_pu"].min()),
                "source_adjustment_max_kw": float(hourly["source_adjustment_kw"].abs().max()),
            }
        )
    return row


def _failed_row(row: dict[str, object], error: Exception, phase: str) -> dict[str, object]:
    row["failure_phase"] = phase
    row["failure_reason"] = _failure_reason(error)
    return row


def run_single_scenario(
    scenario: DisasterScenario,
    *,
    scenario_index: int = 1,
    seed: int = 20260822,
    physical: bool = True,
) -> pd.DataFrame:
    """Run every strategy for one scenario without leaking exceptions to a batch.

    The physical path intentionally executes the existing coupled pipeline as a
    unit.  If it fails, every strategy receives a failed row with the exact
    scenario definition and a pipeline-level reason; subsequent scenarios still
    run.  The dispatch-only path is isolated per strategy, which additionally
    records a failure in one strategy without discarding its peers.
    """

    rows = [
        _base_row(
            scenario,
            scenario_index=scenario_index,
            seed=seed,
            strategy=strategy,
            physical=physical,
        )
        for strategy in STRATEGIES
    ]

    if physical:
        try:
            pipeline = run_scenario(scenario)
        except Exception as error:
            return pd.DataFrame([_failed_row(row, error, "physical_pipeline") for row in rows])

        completed: list[dict[str, object]] = []
        for row in rows:
            try:
                strategy = str(row["strategy"])
                completed_row = _complete_row(row, pipeline.strategies[strategy], pipeline.validations[strategy])
                completed_row["feedback_converged"] = bool(pipeline.feedbacks[strategy].converged)
                completed_row["physical_pass"] = bool(pipeline.validations[strategy].hourly["is_feasible"].all())
                care = evaluate_care_tasks(default_care_tasks(), pipeline.strategies[strategy], pipeline.validations[strategy])
                completed_row["care_pass"] = bool(care["task_complete"].all())
                completed_row["recommendation_eligible"] = bool(completed_row["feedback_converged"] and completed_row["physical_pass"] and completed_row["care_pass"])
                completed.append(completed_row)
            except Exception as error:
                completed.append(_failed_row(row, error, "physical_result_extraction"))
        return pd.DataFrame(completed)

    try:
        model = build_ieee33()
    except Exception as error:
        return pd.DataFrame([_failed_row(row, error, "model_build") for row in rows])

    completed = []
    for row in rows:
        try:
            completed.append(_complete_row(row, simulate_strategy(model, scenario, str(row["strategy"])), None))
        except Exception as error:
            completed.append(_failed_row(row, error, "strategy_simulation"))
    return pd.DataFrame(completed)


def run_monte_carlo(count: int = 30, seed: int = 20260822, *, physical: bool = True) -> pd.DataFrame:
    """Run a fault batch with row-level failure accounting and replay metadata."""

    batches = [
        run_single_scenario(scenario, scenario_index=index, seed=seed, physical=physical)
        for index, scenario in enumerate(sample_fault_scenarios(count, seed), start=1)
    ]
    if not batches:  # Defensive: sample_fault_scenarios currently rejects zero.
        return pd.DataFrame()
    # ``concat`` emits a pandas FutureWarning when an early failed batch has
    # metric columns that are entirely NA and a later batch succeeds.  Building
    # records directly preserves the fixed row schema without warning noise in
    # long unattended experiment runs.
    records = [row for batch in batches for row in batch.to_dict(orient="records")]
    return pd.DataFrame.from_records(records).round(5)


def _bootstrap_mean_interval(
    values: np.ndarray,
    *,
    confidence: float,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan")
    if len(values) == 1:
        value = float(values[0])
        return value, value
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(samples, len(values)), replace=True).mean(axis=1)
    alpha = (1.0 - confidence) / 2.0
    lower, upper = np.quantile(means, [alpha, 1.0 - alpha])
    return float(lower), float(upper)


def _wilson_interval(successes: int, attempts: int, confidence: float) -> tuple[float, float]:
    if attempts == 0:
        return float("nan"), float("nan")
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    proportion = successes / attempts
    denominator = 1.0 + z * z / attempts
    centre = (proportion + z * z / (2.0 * attempts)) / denominator
    spread = z * np.sqrt((proportion * (1.0 - proportion) + z * z / (4.0 * attempts)) / attempts) / denominator
    return float(max(0.0, centre - spread)), float(min(1.0, centre + spread))


def summarize(
    results: pd.DataFrame,
    *,
    confidence: float = 0.95,
    bootstrap_samples: int = 2_000,
    seed: int = 20260822,
) -> pd.DataFrame:
    """Summarize solved runs and attach deterministic bootstrap confidence intervals.

    Failed runs contribute to the attempt/failure counts and the solve-success
    confidence interval, but never masquerade as zero-valued reliability data.
    """

    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    if results.empty:
        return pd.DataFrame()

    summary_rows: list[dict[str, object]] = []
    metric_columns = RESULT_METRICS + PHYSICAL_METRICS
    for strategy, group in results.groupby("strategy", sort=True, dropna=False):
        success_mask = group["solve_success"].fillna(False).astype(bool)
        solved = group.loc[success_mask]
        attempts = len(group)
        successes = int(success_mask.sum())
        lower_rate, upper_rate = _wilson_interval(successes, attempts, confidence)
        row: dict[str, object] = {
            "strategy": strategy,
            "scenario_count": int(group["scenario_id"].nunique()) if "scenario_id" in group else attempts,
            "attempt_count": attempts,
            "solved_count": successes,
            "failed_count": attempts - successes,
            "solve_success_rate": successes / attempts if attempts else float("nan"),
            "solve_success_rate_ci_lower": lower_rate,
            "solve_success_rate_ci_upper": upper_rate,
        }
        for metric in metric_columns:
            values = pd.to_numeric(solved[metric], errors="coerce").dropna().to_numpy(dtype=float)
            finite = values[np.isfinite(values)]
            metric_seed = seed + int.from_bytes(
                hashlib.sha256(f"{strategy}|{metric}".encode("utf-8")).digest()[:4], "big"
            )
            ci_lower, ci_upper = _bootstrap_mean_interval(
                finite,
                confidence=confidence,
                samples=bootstrap_samples,
                seed=metric_seed,
            )
            row.update(
                {
                    f"{metric}_n": len(finite),
                    f"{metric}_mean": float(np.mean(finite)) if len(finite) else float("nan"),
                    f"{metric}_median": float(np.median(finite)) if len(finite) else float("nan"),
                    f"{metric}_std": float(np.std(finite, ddof=1)) if len(finite) > 1 else 0.0 if len(finite) else float("nan"),
                    f"{metric}_max": float(np.max(finite)) if len(finite) else float("nan"),
                    f"{metric}_ci_lower": ci_lower,
                    f"{metric}_ci_upper": ci_upper,
                }
            )
        summary_rows.append(row)
    return pd.DataFrame(summary_rows).round(5)


def build_failure_manifest(results: pd.DataFrame) -> dict[str, object]:
    """Extract unique failed scenario definitions and their strategy failures."""

    required = {"scenario_id", "scenario_definition", "solve_success", "strategy", "failure_reason"}
    missing = required.difference(results.columns)
    if missing:
        raise ValueError(f"results missing replay columns: {sorted(missing)}")

    failures = results.loc[~results["solve_success"].fillna(False).astype(bool)]
    failed_scenarios: list[dict[str, object]] = []
    for scenario_id, group in failures.groupby("scenario_id", sort=True):
        first = group.iloc[0]
        failed_scenarios.append(
            {
                "scenario_id": str(scenario_id),
                "scenario_index": int(first["scenario_index"]),
                "run_seed": int(first["run_seed"]),
                "physical_requested": bool(first["physical_requested"]),
                "scenario_sha256": str(first["scenario_sha256"]),
                "scenario": json.loads(str(first["scenario_definition"])),
                "failures": [
                    {
                        "strategy": str(row.strategy),
                        "phase": None if pd.isna(row.failure_phase) else str(row.failure_phase),
                        "reason": None if pd.isna(row.failure_reason) else str(row.failure_reason),
                    }
                    for row in group.itertuples(index=False)
                ],
            }
        )
    return {"schema_version": REPLAY_SCHEMA_VERSION, "failed_scenarios": failed_scenarios}


def write_failure_manifest(results: pd.DataFrame, path: str | Path) -> Path:
    """Write replay-ready JSON for failed scenarios, including zero-failure batches."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_failure_manifest(results), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def replay_failure_manifest(
    path: str | Path,
    *,
    scenario_id: str | None = None,
    physical: bool | None = None,
) -> pd.DataFrame:
    """Replay one or all cases from ``write_failure_manifest`` output."""

    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != REPLAY_SCHEMA_VERSION:
        raise ValueError(f"unsupported replay manifest schema: {manifest.get('schema_version')!r}")
    cases = list(manifest.get("failed_scenarios", []))
    if scenario_id is not None:
        cases = [case for case in cases if case.get("scenario_id") == scenario_id]
    if not cases:
        selector = f" {scenario_id!r}" if scenario_id is not None else ""
        raise ValueError(f"no failed scenario found for selector{selector}")
    batches = [
        run_single_scenario(
            scenario_from_dict(case["scenario"]),
            scenario_index=int(case["scenario_index"]),
            seed=int(case["run_seed"]),
            physical=bool(case["physical_requested"]) if physical is None else physical,
        )
        for case in cases
    ]
    records = [row for batch in batches for row in batch.to_dict(orient="records")]
    return pd.DataFrame.from_records(records).round(5)


def main() -> None:
    parser = argparse.ArgumentParser(description="GridRescue fault-tolerant Monte Carlo experiment")
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260822)
    parser.add_argument("--output", default="artifacts")
    parser.add_argument("--no-physical", action="store_true", help="skip iterative P/Q feasibility feedback")
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--replay", help="failure manifest created by a previous batch")
    parser.add_argument("--scenario-id", help="replay only one scenario_id from --replay")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.replay:
        results = replay_failure_manifest(
            args.replay,
            scenario_id=args.scenario_id,
            physical=False if args.no_physical else None,
        )
    else:
        results = run_monte_carlo(args.count, args.seed, physical=not args.no_physical)
    summary = summarize(
        results,
        confidence=args.confidence,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    results.to_csv(output / "monte_carlo_results.csv", index=False)
    summary.to_csv(output / "monte_carlo_summary.csv", index=False)
    manifest_path = write_failure_manifest(results, output / "monte_carlo_failures.json")
    print(summary.to_string(index=False))
    print(f"\nFailure replay manifest: {manifest_path.resolve()}")


if __name__ == "__main__":
    main()
