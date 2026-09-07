from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gridrescue.risk import choose_strategy, summarize_risk


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CVaR/failure-budget strategy report")
    parser.add_argument("--input", default="artifacts/wave10/batch36/experiment_runs.csv")
    parser.add_argument("--output", default="artifacts/wave11/risk_report")
    parser.add_argument("--metric", default="eens_kwh")
    parser.add_argument("--alpha", type=float, default=0.95)
    parser.add_argument("--cvar-weight", type=float, default=0.5)
    parser.add_argument("--failure-budget", type=float, default=0.0)
    args = parser.parse_args()

    input_path = Path(args.input)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with input_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    summaries = summarize_risk(
        rows,
        metric=args.metric,
        alpha=args.alpha,
        cvar_weight=args.cvar_weight,
        failure_budget=args.failure_budget,
    )
    chosen = choose_strategy(summaries)
    payload = {
        "schema_version": "gridrescue-wave11-risk-report-1.0",
        "input": str(input_path),
        "rows": len(rows),
        "metric": args.metric,
        "alpha": args.alpha,
        "cvar_weight": args.cvar_weight,
        "failure_budget": args.failure_budget,
        "claim_boundary": "risk-adjusted ranking over replayed synthetic scenarios; not a field forecast",
        "chosen_strategy": chosen.to_dict() if chosen else None,
        "summaries": [item.to_dict() for item in summaries],
    }
    (output / "risk_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "risk_report.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(summaries[0].to_dict()) if summaries else ["strategy"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(item.to_dict() for item in summaries)
    print(json.dumps({"output": str(output), "chosen_strategy": chosen.strategy if chosen else None, "strategies": len(summaries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
