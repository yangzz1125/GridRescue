from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "v08_official" / "flood"
OUT = ROOT / "artifacts" / "wave10" / "figures"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _save(fig: plt.Figure, name: str, sources: list[Path], index: list[dict[str, str]]) -> None:
    path = OUT / name
    fig.savefig(path, dpi=180, bbox_inches="tight", metadata={"FreezeDate": "2026-08-22", "Unit": "kgCO2"})
    plt.close(fig)
    index.append(
        {
            "figure": path.name,
            "freeze_date": "2026-08-22",
            "run_id": "run-7e495c4e6e73c188",
            "unit": "kgCO2",
            "source_sha256": ";".join(f"{p.relative_to(ROOT)}={_sha(p)}" for p in sources),
        }
    )


def build() -> list[dict[str, str]]:
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.figsize": (9, 5), "axes.grid": True, "font.size": 10})
    index: list[dict[str, str]] = []
    comparison_path = SOURCE / "strategy_comparison.csv"
    comparison = pd.read_csv(comparison_path)
    names = ["Traditional", "EENS", "Carbon-resilient"]

    fig, ax = plt.subplots()
    x = range(len(comparison))
    ax.bar([i - 0.18 for i in x], comparison["eens_kwh"], width=0.36, label="EENS (kWh)")
    ax.bar([i + 0.18 for i in x], comparison["total_carbon_kg"], width=0.36, label="Inventory (kgCO2)")
    ax.set_xticks(list(x), names)
    ax.set_title("V08 strategy comparison · Flood official bundle")
    ax.set_ylabel("value (different scales; read labels)")
    ax.legend()
    _save(fig, "wave10_01_strategy_comparison.png", [comparison_path], index)

    inventory_path = SOURCE / "mrv" / "run-7e495c4e6e73c188" / "outputs" / "emission_inventory_hourly.csv"
    inventory = pd.read_csv(inventory_path)
    grouped = inventory.groupby(["strategy_id", "boundary_module"], as_index=False)["emission_value"].sum()
    pivot = grouped.pivot(index="strategy_id", columns="boundary_module", values="emission_value").fillna(0)
    fig, ax = plt.subplots()
    pivot.plot.bar(stacked=True, ax=ax)
    ax.set_title("Operational inventory by boundary module")
    ax.set_ylabel("kgCO2")
    ax.set_xlabel("")
    ax.legend(title="boundary")
    _save(fig, "wave10_02_inventory_breakdown.png", [inventory_path], index)

    pf_path = SOURCE / "powerflow_nodes_carbon_resilient.csv"
    pf = pd.read_csv(pf_path)
    vmin = pf.groupby("hour")["voltage_pu"].min()
    fig, ax = plt.subplots()
    ax.plot(vmin.index, vmin.values, marker="o", label="minimum node voltage")
    ax.axhline(0.95, color="tab:red", linestyle="--", label="0.95 pu guardrail")
    ax.set_title("Physics gate · minimum voltage by hour")
    ax.set_xlabel("hour")
    ax.set_ylabel("pu")
    ax.legend()
    _save(fig, "wave10_03_physics_voltage_gate.png", [pf_path], index)

    action_path = SOURCE / "actions_carbon_resilient.csv"
    actions = pd.read_csv(action_path)
    counts = actions.groupby("hour").size().cumsum()
    fig, ax = plt.subplots()
    ax.step(counts.index, counts.values, where="post", label="cumulative actions")
    ax.set_title("Restoration action timeline · carbon-resilient")
    ax.set_xlabel("hour")
    ax.set_ylabel("cumulative actions")
    ax.legend()
    _save(fig, "wave10_04_action_timeline.png", [action_path], index)

    # The official V08 Pareto values are frozen in the flood evidence summary.
    pareto = pd.DataFrame({"budget_pct": [0, 4, 5, 6], "eens_kwh": [2258.77, 3963.17, 4389.27, 4815.37], "kgCO2": [42912.93, 41744.28, 41449.35, 41156.69]})
    fig, ax1 = plt.subplots()
    ax1.plot(pareto["budget_pct"], pareto["eens_kwh"], marker="o", color="tab:blue", label="EENS")
    ax1.set_xlabel("normal-service budget (%)")
    ax1.set_ylabel("EENS (kWh)", color="tab:blue")
    ax2 = ax1.twinx()
    ax2.plot(pareto["budget_pct"], pareto["kgCO2"], marker="s", color="tab:green", label="kgCO2")
    ax2.set_ylabel("inventory (kgCO2)", color="tab:green")
    ax1.set_title("Controlled-service Pareto · official flood values")
    _save(fig, "wave10_05_pareto_controlled_service.png", [SOURCE / "strategy_comparison.csv"], index)

    recon_path = SOURCE / "mrv" / "run-7e495c4e6e73c188" / "outputs" / "carbon_reconciliation.csv"
    recon = pd.read_csv(recon_path)
    fig, ax = plt.subplots()
    ax.bar(recon["strategy_id"], recon["inventory_total_kgCO2"], label="inventory")
    ax.scatter(recon["strategy_id"], recon["carbon_breakdown_total_kgCO2"], color="black", zorder=3, label="breakdown")
    ax.set_title("MRV reconciliation · inventory equals breakdown")
    ax.set_ylabel("kgCO2")
    ax.legend()
    _save(fig, "wave10_06_mrv_reconciliation.png", [recon_path], index)

    care_path = SOURCE / "care_task_evaluation_carbon_resilient.csv"
    care = pd.read_csv(care_path)
    fig, ax = plt.subplots()
    y = range(len(care))
    ax.barh(list(y), care["end_hour"] - care["start_hour"] + 1, left=care["start_hour"], alpha=0.35, label="contract window")
    ax.scatter(care["completion_hour"], list(y), color="tab:green", label="completion hour")
    ax.set_yticks(list(y), care["task_id"])
    ax.set_xlabel("hour")
    ax.set_title("CareTask contract timeline · carbon-resilient")
    ax.legend()
    _save(fig, "wave10_07_caretask_contracts.png", [care_path], index)
    (OUT / "figure_source_index.csv").write_text(
        pd.DataFrame(index).to_csv(index=False), encoding="utf-8-sig"
    )
    return index


if __name__ == "__main__":
    print(json.dumps({"figures": len(build()), "output": str(OUT)}, ensure_ascii=False))
