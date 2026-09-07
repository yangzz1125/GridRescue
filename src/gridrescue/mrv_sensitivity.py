"""Deterministic MRV factor-uncertainty propagation.

This is an evidence-layer analysis: dispatch activities stay fixed while
factor uncertainty is propagated.  It never changes the Care/Physics gates.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import math
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SensitivitySummary:
    strategy_id: str
    draws: int
    baseline_kgco2: float
    mean_kgco2: float
    q05_kgco2: float
    q95_kgco2: float
    winner_count: int
    winner_rate: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def lhs_uniform(n: int, *, seed: int = 20260823) -> np.ndarray:
    if n < 1:
        raise ValueError("n must be positive")
    rng = np.random.default_rng(seed)
    lower = np.arange(n, dtype=float) / n
    upper = (np.arange(n, dtype=float) + 1.0) / n
    return lower + rng.random(n) * (upper - lower)


def propagate_factor_uncertainty(
    inventory: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    draws: int = 500,
    seed: int = 20260823,
) -> tuple[pd.DataFrame, list[SensitivitySummary]]:
    required_inventory = {"strategy_id", "activity_value", "factor_id"}
    required_registry = {"factor_id", "value", "uncertainty_pct"}
    if required_inventory.difference(inventory.columns):
        raise ValueError("inventory missing required columns")
    if required_registry.difference(registry.columns):
        raise ValueError("registry missing required columns")
    factors = registry.set_index("factor_id")
    unknown = set(inventory["factor_id"].astype(str)) - set(factors.index.astype(str))
    if unknown:
        raise ValueError(f"unknown factor IDs: {sorted(unknown)}")
    u = lhs_uniform(draws, seed=seed)
    rows: list[dict[str, object]] = []
    totals: dict[str, np.ndarray] = {}
    for strategy, group in inventory.groupby(inventory["strategy_id"].astype(str), sort=True):
        total = np.zeros(draws, dtype=float)
        baseline = 0.0
        for item in group.itertuples(index=False):
            factor = factors.loc[str(item.factor_id)]
            base = float(item.activity_value) * float(factor["value"])
            # Official MEE rows intentionally leave uncertainty_pct blank
            # because the publication provides no interval. Treat blank as
            # zero perturbation unless a study supplies an explicit project
            # uncertainty; never invent a confidence range for the source.
            raw_uncertainty = factor.get("uncertainty_pct", "")
            try:
                uncertainty = max(0.0, float(raw_uncertainty) / 100.0)
            except (TypeError, ValueError):
                uncertainty = 0.0
            baseline += base
            # A separate deterministic permutation per factor avoids all
            # factors moving in lockstep while preserving reproducibility.
            factor_seed = seed + sum(ord(ch) for ch in str(item.factor_id))
            local = lhs_uniform(draws, seed=factor_seed)
            multiplier = (1.0 - uncertainty) + 2.0 * uncertainty * local
            total += base * multiplier
        totals[strategy] = total
        rows.extend({"strategy_id": strategy, "draw": i, "total_carbon_kg": float(value)} for i, value in enumerate(total))

    frame = pd.DataFrame(rows)
    winner = frame.loc[frame.groupby("draw")["total_carbon_kg"].idxmin(), "strategy_id"]
    counts = Counter(winner.astype(str))
    summaries: list[SensitivitySummary] = []
    for strategy, total in totals.items():
        summaries.append(
            SensitivitySummary(
                strategy_id=strategy,
                draws=draws,
                baseline_kgco2=float(sum(float(item.activity_value) * float(factors.loc[str(item.factor_id)]["value"]) for item in inventory[inventory["strategy_id"].astype(str) == strategy].itertuples(index=False))),
                mean_kgco2=float(total.mean()),
                q05_kgco2=float(np.quantile(total, 0.05)),
                q95_kgco2=float(np.quantile(total, 0.95)),
                winner_count=int(counts.get(strategy, 0)),
                winner_rate=float(counts.get(strategy, 0) / draws),
            )
        )
    return frame, summaries
