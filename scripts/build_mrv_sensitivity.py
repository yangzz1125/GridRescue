from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gridrescue.mrv_sensitivity import propagate_factor_uncertainty


def main() -> int:
    parser = argparse.ArgumentParser(description="Propagate MRV factor uncertainty")
    parser.add_argument("--bundle", default="artifacts/v08_official/flood/mrv/run-7e495c4e6e73c188")
    parser.add_argument("--draws", type=int, default=500)
    parser.add_argument("--output", default="artifacts/wave11/mrv_sensitivity")
    args = parser.parse_args()
    bundle = Path(args.bundle)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    inventory = pd.read_csv(bundle / "outputs" / "emission_inventory_hourly.csv")
    registry = pd.read_csv(bundle / "inputs" / "factor_registry.csv")
    draws, summaries = propagate_factor_uncertainty(inventory, registry, draws=args.draws)
    draws.to_csv(output / "factor_draws.csv", index=False)
    payload = {
        "schema_version": "gridrescue-wave11-mrv-sensitivity-1.0",
        "bundle": str(bundle),
        "draws": args.draws,
        "claim_boundary": "factor uncertainty propagation over frozen activity inventory; Care/Physics gates unchanged",
        "summaries": [summary.to_dict() for summary in summaries],
    }
    (output / "sensitivity_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "strategies": len(summaries), "draws": args.draws}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

