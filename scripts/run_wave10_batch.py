from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from gridrescue.experiments import run_single_scenario, summarize, write_failure_manifest
from gridrescue.scenario_catalog import build_catalog, catalog_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen Wave10 36-scenario catalog")
    parser.add_argument("--output", default="artifacts/wave10/batch36")
    parser.add_argument("--no-physical", action="store_true")
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    records = build_catalog()
    batches = []
    for index, record in enumerate(records, start=1):
        print(f"[{index:02d}/{len(records)}] {record.scenario_id}", flush=True)
        batches.append(
            run_single_scenario(
                record.to_disaster_scenario(),
                scenario_index=index,
                seed=record.seed,
                physical=not args.no_physical,
            )
        )
    results = pd.concat(batches, ignore_index=True).round(5)
    summary = summarize(results, bootstrap_samples=args.bootstrap_samples, seed=20260822)
    results.to_csv(output / "experiment_runs.csv", index=False)
    summary.to_csv(output / "validation_summary.csv", index=False)
    write_failure_manifest(results, output / "failure_manifest.json")
    (output / "catalog_manifest.json").write_text(
        json.dumps(catalog_manifest(records), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary.to_string(index=False))
    print(f"output={output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
