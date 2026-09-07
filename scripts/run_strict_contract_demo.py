from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gridrescue.pareto import ParetoScanSpec, scan_pareto
from gridrescue.scenario_catalog import build_catalog


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "wave10" / "strict_contract_demo"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/wave10/strict_contract_9")
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    # Replicate 1 for each disaster x intensity stratum. This is a strict-
    # contract stratified batch, not a replacement for the full 36-scenario
    # C0/C4 study.
    catalog = build_catalog()
    selected = [catalog[index] for index in (0, 4, 8, 12, 16, 20, 24, 28, 32)]
    rows: list[pd.DataFrame] = []
    anchors: list[pd.DataFrame] = []
    manifests: list[dict[str, object]] = []
    for record in selected:
        result = scan_pareto(
            record.to_disaster_scenario(),
            ParetoScanSpec(
                strategies=("碳韧协同恢复",),
                normal_allowance_fractions=(0.0, 0.04),
                max_feedback_iterations=8,
                output_dir=None,
            ),
        )
        point = result.points.copy()
        point["catalog_scenario_id"] = record.scenario_id
        point["catalog_payload_sha256"] = record.payload_sha256
        rows.append(point)
        anchor = result.anchors.copy()
        anchor["catalog_scenario_id"] = record.scenario_id
        anchors.append(anchor)
        manifests.append(
            {
                "scenario_id": record.scenario_id,
                "payload_sha256": record.payload_sha256,
                "points": len(result.points),
                "frontier_eligible": int(result.points["frontier_eligible"].fillna(False).sum()),
                "failures": len(result.failures),
            }
        )
    points = pd.concat(rows, ignore_index=True)
    anchor_table = pd.concat(anchors, ignore_index=True)
    points.to_csv(output / "strict_contract_points.csv", index=False)
    anchor_table.to_csv(output / "strict_contract_anchors.csv", index=False)
    manifest = {
        "schema_version": "gridrescue-wave10-strict-contract-demo-1.0",
        "generated_at": "2026-08-23",
        "freeze_date": "2026-08-22",
        "scenario_count": len(selected),
        "allowance_fractions": [0.0, 0.04],
        "strategy": "碳韧协同恢复",
        "strict_contract": True,
        "scenarios": manifests,
        "claim_boundary": "representative strict-contract feasibility demo; not a 36-scenario generalization",
    }
    (output / "strict_contract_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
