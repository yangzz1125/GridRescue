"""Factor sensitivity over fixed activities, retaining each original factor value."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib

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

    def to_dict(self):
        return asdict(self)


def lhs_uniform(n: int, *, seed: int = 20260823) -> np.ndarray:
    if n < 1:
        raise ValueError("n must be positive")
    rng = np.random.default_rng(seed)
    values = (np.arange(n) + rng.random(n)) / n
    return rng.permutation(values)


def propagate_factor_uncertainty(inventory, registry, *, draws=500, seed=20260823):
    if not {"strategy_id", "activity_value", "factor_id"}.issubset(inventory):
        raise ValueError("inventory missing required columns")
    if not {"factor_id", "value", "uncertainty_pct"}.issubset(registry):
        raise ValueError("registry missing required columns")
    if inventory.empty or registry.empty or draws < 1:
        raise ValueError("inventory, registry and draws must be non-empty/positive")
    keys = ["factor_id"]
    if "factor_version" in registry:
        if "factor_version" not in inventory:
            raise ValueError("inventory missing factor_version")
        keys.append("factor_version")
    registry = registry.copy()
    inventory = inventory.copy()
    for key in keys:
        registry[key] = registry[key].astype(str)
        inventory[key] = inventory[key].astype(str)
    if registry.duplicated(keys).any():
        raise ValueError("duplicate factor keys")
    factors = registry.set_index(keys)
    multipliers = {}
    for key, factor in factors.iterrows():
        uncertainty = float(factor["uncertainty_pct"]) / 100
        if not np.isfinite(uncertainty) or not 0 <= uncertainty <= 1:
            raise ValueError("uncertainty must be finite and in [0, 100]")
        local_seed = seed + int.from_bytes(hashlib.sha256(str(key).encode()).digest()[:4], "big")
        multipliers[key] = 1 + uncertainty * (2 * lhs_uniform(draws, seed=local_seed) - 1)
    rows, totals, baselines = [], {}, {}
    for strategy, group in inventory.groupby("strategy_id", sort=True):
        total = np.zeros(draws)
        baseline = 0.0
        for item in group.to_dict("records"):
            key = tuple(item[k] for k in keys) if len(keys) > 1 else item[keys[0]]
            if key not in factors.index:
                raise ValueError(f"unknown factor: {key}")
            value = float(item.get("factor_value", factors.loc[key, "value"]))
            activity = float(item["activity_value"])
            if not np.isfinite(value) or not np.isfinite(activity) or min(value, activity) < 0:
                raise ValueError("activity and factor must be finite and non-negative")
            base = activity * value
            baseline += base
            total += base * multipliers[key]
        totals[strategy], baselines[strategy] = total, baseline
        rows.extend({"strategy_id": strategy, "draw": i, "total_carbon_kg": float(v)} for i, v in enumerate(total))
    frame = pd.DataFrame(rows)
    matrix = np.stack(list(totals.values()))
    # Split tied minimum ranks, rather than awarding every tie to alphabetic first.
    winning = np.isclose(matrix, matrix.min(axis=0), rtol=1e-10, atol=1e-8)
    credits = winning / winning.sum(axis=0)
    summaries = [SensitivitySummary(strategy, draws, baselines[strategy], float(total.mean()),
                    float(np.quantile(total, .05)), float(np.quantile(total, .95)),
                    float(credits[i].sum()), float(credits[i].mean()))
                 for i, (strategy, total) in enumerate(totals.items())]
    return frame, summaries
