from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from gridrescue.paired_stats import bootstrap_mean_delta, summarize_pairs


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "artifacts" / "wave10" / "batch36"


def main() -> int:
    runs = pd.read_csv(BATCH / "experiment_runs.csv")
    candidate = runs[runs["strategy"] == "碳韧协同恢复"].copy()
    reference = runs[runs["strategy"] == "最小失供恢复"].copy()
    merged = candidate.merge(reference, on="scenario_id", suffixes=("_candidate", "_reference"))
    eligible = merged["solve_success_candidate"].astype(bool) & merged["solve_success_reference"].astype(bool)
    rows: list[dict[str, object]] = []
    for metric in ("eens_kwh", "critical_eens_kwh", "critical_recovery_pct", "total_carbon_kg"):
        summary = summarize_pairs(
            merged[f"{metric}_reference"].tolist(),
            merged[f"{metric}_candidate"].tolist(),
            eligible.tolist(),
        )
        deltas = (
            merged.loc[eligible, f"{metric}_candidate"].astype(float).to_numpy()
            - merged.loc[eligible, f"{metric}_reference"].astype(float).to_numpy()
        )
        boot = bootstrap_mean_delta(deltas, n_resamples=2000, seed=20260822)
        rows.append({"metric": metric, **summary.__dict__, "bootstrap": json.dumps(boot, ensure_ascii=False)})
    pd.DataFrame(rows).to_csv(BATCH / "paired_deltas.csv", index=False)
    report = {
        "schema_version": "gridrescue-wave10-paired-report-1.0",
        "generated_at": "2026-08-23",
        "freeze_date": "2026-08-22",
        "catalog": "36 synthetic scenarios; same scenario_id paired across strategies",
        "candidate": "碳韧协同恢复",
        "reference": "最小失供恢复",
        "rows": rows,
        "claim_boundary": "descriptive paired experiment; same_service_pass remains false in official V08 claim gate",
    }
    (BATCH / "paired_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pairs": len(merged), "eligible": int(eligible.sum()), "output": str(BATCH)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
