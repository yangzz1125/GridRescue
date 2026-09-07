"""Small, dependency-light paired statistics helpers.

These functions keep failed/ineligible runs visible rather than silently
turning them into zero-valued outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class PairedSummary:
    total_pairs: int
    eligible_pairs: int
    failed_pairs: int
    mean_delta: float | None
    median_delta: float | None
    wins: int
    ties: int
    losses: int


def paired_deltas(
    reference: Sequence[float | None], candidate: Sequence[float | None], eligible: Sequence[bool] | None = None
) -> np.ndarray:
    if len(reference) != len(candidate):
        raise ValueError("reference and candidate lengths must match")
    if eligible is not None and len(eligible) != len(reference):
        raise ValueError("eligible length must match values")
    values: list[float] = []
    for idx, (ref, cand) in enumerate(zip(reference, candidate)):
        if eligible is not None and not eligible[idx]:
            continue
        if ref is None or cand is None or not math.isfinite(float(ref)) or not math.isfinite(float(cand)):
            continue
        values.append(float(cand) - float(ref))
    return np.asarray(values, dtype=float)


def summarize_pairs(
    reference: Sequence[float | None], candidate: Sequence[float | None], eligible: Sequence[bool] | None = None
) -> PairedSummary:
    n = len(reference)
    if len(candidate) != n:
        raise ValueError("reference and candidate lengths must match")
    deltas = paired_deltas(reference, candidate, eligible)
    eligible_count = int(len(deltas))
    failed = n - eligible_count
    wins = int(np.sum(deltas < 0))
    ties = int(np.sum(np.isclose(deltas, 0.0)))
    losses = int(np.sum(deltas > 0))
    return PairedSummary(
        total_pairs=n,
        eligible_pairs=eligible_count,
        failed_pairs=failed,
        mean_delta=float(np.mean(deltas)) if eligible_count else None,
        median_delta=float(np.median(deltas)) if eligible_count else None,
        wins=wins,
        ties=ties,
        losses=losses,
    )


def bootstrap_mean_delta(
    deltas: Sequence[float], *, n_resamples: int = 2000, seed: int = 20260822, confidence: float = 0.95
) -> dict[str, float | int | None]:
    values = np.asarray(list(deltas), dtype=float)
    if values.size == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None, "confidence": confidence, "seed": seed}
    if n_resamples < 100:
        raise ValueError("n_resamples must be >= 100")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(n_resamples, values.size), replace=True).mean(axis=1)
    alpha = (1 - confidence) / 2
    lo, hi = np.quantile(draws, [alpha, 1 - alpha])
    return {
        "n": int(values.size),
        "mean": float(values.mean()),
        "lo": float(lo),
        "hi": float(hi),
        "confidence": confidence,
        "seed": seed,
        "n_resamples": n_resamples,
    }


def wilson_interval(successes: int, trials: int, *, confidence: float = 0.95) -> tuple[float, float]:
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("successes/trials out of range")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    # 1.96 is deliberate: no scipy dependency in the base project.
    z = 1.959963984540054
    p = successes / trials
    den = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / den
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / den
    return max(0.0, center - half), min(1.0, center + half)

