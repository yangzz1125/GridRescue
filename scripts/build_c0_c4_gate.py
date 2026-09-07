from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "artifacts" / "wave10" / "batch36"
OUT = ROOT / "artifacts" / "wave10" / "c0_c4_gate"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    runs = pd.read_csv(BATCH / "experiment_runs.csv")
    reference = runs[runs["strategy"] == "最小失供恢复"].copy()
    candidate = runs[runs["strategy"] == "碳韧协同恢复"].copy()
    reference.insert(0, "arm", "C0")
    candidate.insert(0, "arm", "C4")
    reference["service_contract_status"] = "reference_service_anchor"
    candidate["service_contract_status"] = "controlled_budget_candidate"
    reference["strict_eligible"] = False
    candidate["strict_eligible"] = False
    reference["controlled_eligible"] = reference["solve_success"].astype(bool)
    candidate["controlled_eligible"] = candidate["solve_success"].astype(bool)
    reference.to_csv(OUT / "c0_strict_reference.csv", index=False)
    candidate.to_csv(OUT / "c4_controlled_candidate.csv", index=False)

    paired = reference.merge(candidate, on="scenario_id", suffixes=("_c0", "_c4"))
    gate = pd.DataFrame(
        {
            "scenario_id": paired["scenario_id"],
            "c0_solve_success": paired["solve_success_c0"].astype(bool),
            "c4_solve_success": paired["solve_success_c4"].astype(bool),
            "same_service_pass": False,
            "strict_eligible": False,
            "controlled_eligible": paired["solve_success_c0"].astype(bool)
            & paired["solve_success_c4"].astype(bool),
            "claim_status": "controlled_service_budget_inventory_difference",
            "normal_eens_delta_c4_minus_c0": paired["eens_kwh_c4"] - paired["eens_kwh_c0"],
            "carbon_delta_kgCO2_c4_minus_c0": paired["total_carbon_kg_c4"] - paired["total_carbon_kg_c0"],
        }
    )
    gate.to_csv(OUT / "comparison_gate.csv", index=False)
    manifest = {
        "schema_version": "gridrescue-wave10-c0-c4-gate-1.0",
        "generated_at": "2026-08-23",
        "freeze_date": "2026-08-22",
        "catalog": "artifacts/wave10/batch36",
        "arms": {
            "C0": "最小失供恢复 / reference_service_anchor",
            "C4": "碳韧协同恢复 / controlled_budget_candidate",
        },
        "pairs": len(gate),
        "strict_eligible": int(gate["strict_eligible"].sum()),
        "controlled_eligible": int(gate["controlled_eligible"].sum()),
        "same_service_pass": False,
        "claim_status": "controlled_service_budget_inventory_difference",
        "interpretation": "C0/C4 are separated for audit; strict same-service claim remains blocked until a same-service contract comparison passes.",
    }
    (OUT / "gate_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
