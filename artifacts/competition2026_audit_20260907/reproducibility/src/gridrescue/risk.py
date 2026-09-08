"""Risk-adjusted strategy ranking for replayed GridRescue scenarios.

The module deliberately keeps failed runs visible.  A strategy is only marked
eligible when its failure rate is within the caller-supplied budget; no failed
run is converted to a zero-valued outcome.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import math
from typing import Iterable, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class RiskSummary:
    strategy: str
    metric: str
    total: int
    successes: int
    failures: int
    failure_rate: float
    mean: float | None
    p95: float | None
    cvar95: float | None
    risk_score: float | None
    eligible: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _finite(values: Iterable[float]) -> np.ndarray:
    out = np.asarray([float(v) for v in values if math.isfinite(float(v))], dtype=float)
    return out


def cvar(values: Sequence[float], *, alpha: float = 0.95) -> float | None:
    """Return empirical upper-tail CVaR for a loss metric."""
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    arr = np.sort(_finite(values))
    if arr.size == 0:
        return None
    boundary = alpha * arr.size
    start = int(math.floor(boundary))
    tail_sum = float(arr[start]) * (1 - (boundary - start)) + float(arr[start + 1:].sum())
    return tail_sum / (arr.size - boundary)


def _row_success(row: Mapping[str, object]) -> bool:
    truthy = {"1", "true", "yes", "pass", "optimal"}
    if str(row.get("solve_success", "True")).strip().lower() not in truthy:
        return False
    for field in ("physical_pass", "care_pass", "feedback_converged", "recommendation_eligible"):
        if field in row and str(row[field]).strip().lower() not in truthy:
            return False
    if "physical_feasible_hours" in row:
        try:
            return float(row["physical_feasible_hours"]) == 24
        except (ValueError, TypeError):
            return False
    return True


def summarize_risk(
    rows: Iterable[Mapping[str, object]],
    *,
    metric: str = "eens_kwh",
    alpha: float = 0.95,
    cvar_weight: float = 0.5,
    failure_budget: float = 0.0,
) -> list[RiskSummary]:
    """Aggregate loss-tail risk by strategy.

    ``risk_score = mean + cvar_weight * (CVaR - mean)``.  Lower is better.
    Failure eligibility is reported separately and never hidden in the score.
    """
    if cvar_weight < 0:
        raise ValueError("cvar_weight must be non-negative")
    if not 0 <= failure_budget <= 1:
        raise ValueError("failure_budget must be in [0, 1]")
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if metric not in row:
            raise KeyError(f"missing metric column: {metric}")
        grouped[str(row.get("strategy", "UNKNOWN"))].append(row)

    summaries: list[RiskSummary] = []
    for strategy, items in sorted(grouped.items()):
        successes = [float(item[metric]) for item in items if _row_success(item) and str(item[metric]).strip() not in {"", "None", "nan"}]
        values = _finite(successes)
        total = len(items)
        success_count = len(values)
        failures = total - success_count
        failure_rate = failures / total if total else 1.0
        mean = float(values.mean()) if values.size else None
        p95 = float(np.quantile(values, 0.95)) if values.size else None
        tail = cvar(values, alpha=alpha)
        score = None if mean is None or tail is None else float(mean + cvar_weight * (tail - mean))
        summaries.append(
            RiskSummary(
                strategy=strategy,
                metric=metric,
                total=total,
                successes=success_count,
                failures=failures,
                failure_rate=failure_rate,
                mean=mean,
                p95=p95,
                cvar95=tail,
                risk_score=score,
                eligible=bool(values.size and failure_rate <= failure_budget),
            )
        )
    return summaries


def choose_strategy(summaries: Sequence[RiskSummary]) -> RiskSummary | None:
    """Choose the lowest risk score among eligible summaries."""
    eligible = [item for item in summaries if item.eligible and item.risk_score is not None]
    return min(eligible, key=lambda item: float(item.risk_score)) if eligible else None

