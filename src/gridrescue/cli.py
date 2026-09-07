from __future__ import annotations

import argparse
import json
from pathlib import Path

from .care import default_care_tasks, evaluate_care_tasks, write_care_tasks
from .islands import build_island_passports, write_island_passports
from .mrv import write_mrv_bundle
from .pipeline import run_pipeline
from .powerflow import solve_base_case, validate_dispatch
from .scenarios import SCENARIOS


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GridRescue restoration simulation")
    parser.add_argument("--scenario", choices=list(SCENARIOS), default="暴雨内涝")
    parser.add_argument("--output", default="artifacts")
    parser.add_argument(
        "--created-at",
        default=None,
        help="optional ISO-8601 evidence timestamp with UTC offset",
    )
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    result = run_pipeline(args.scenario)
    result.model.nodes.to_csv(output / "network_nodes.csv", index_label="node_id")
    result.model.branches.to_csv(output / "network_branches.csv", index=False)
    base_flow = solve_base_case(result.model)
    base_flow.nodes.to_csv(output / "base_powerflow_nodes.csv", index=False)
    base_flow.branches.to_csv(output / "base_powerflow_branches.csv", index=False)
    (output / "network_manifest.json").write_text(
        json.dumps(
            {
                "source_name": result.model.source_name,
                "source_sha256": result.model.source_sha256,
                "base_mva": result.model.base_mva,
                "base_kv": result.model.base_kv,
                "active_load_kw": float(result.model.nodes["base_load_kw"].sum()),
                "reactive_load_kvar": float(result.model.nodes["reactive_load_kvar"].sum()),
                "normally_closed_branches": len(result.model.base_branch_ids),
                "normally_open_ties": len(result.model.tie_branch_ids),
                "capacity_assumption": result.model.capacity_assumption,
                "base_powerflow": {
                    "converged": base_flow.converged,
                    "iterations": base_flow.iterations,
                    "minimum_voltage_pu": base_flow.min_voltage_pu,
                    "active_loss_kw": base_flow.p_loss_kw,
                    "reactive_loss_kvar": base_flow.q_loss_kvar,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    result.comparison.to_csv(output / "strategy_comparison.csv", index=False)
    care_tasks = default_care_tasks()
    for strategy, strategy_result in result.strategies.items():
        slug = {"传统顺序恢复": "traditional", "最小失供恢复": "eens", "碳韧协同恢复": "carbon_resilient"}[strategy]
        strategy_result.dispatch.frame.to_csv(output / f"dispatch_{slug}.csv", index_label="hour")
        strategy_result.plan.actions.to_csv(output / f"actions_{slug}.csv", index=False)
        validation = result.validations[strategy]
        validation.hourly.to_csv(output / f"powerflow_{slug}.csv", index_label="hour")
        validation.branches.to_csv(output / f"powerflow_branches_{slug}.csv", index=False)
        validation.nodes.to_csv(output / f"powerflow_nodes_{slug}.csv", index=False)
        validation.components.to_csv(output / f"powerflow_components_{slug}.csv", index=False)
        passports = build_island_passports(
            result.model,
            result.scenario,
            strategy_result,
            validation,
        )
        write_island_passports(passports, output, slug)
        care_evaluation = evaluate_care_tasks(care_tasks, strategy_result, validation)
        write_care_tasks(care_tasks, care_evaluation, output, slug)
        infeasible_hours = int((~validation.hourly["is_feasible"]).sum())
        blocked_island_hours = (
            int((passports.hourly["passport_status"] == "BLOCKED").sum())
            if not passports.hourly.empty
            else 0
        )
        validation_summary = f"""

## P/Q潮流与孤岛硬校验

- 网络数据：{result.model.source_name}
- 原始文件SHA-256：`{result.model.source_sha256}`
- 物理不可行小时：{infeasible_hours} / 24
- 最大支路负载率：{validation.hourly['max_branch_loading_pct'].max():.2f}%
- 最低节点电压：{validation.hourly['min_voltage_pu'].min():.4f} pu
- 孤岛未覆盖功率缺口：{validation.hourly['unserved_balance_kw'].sum():.2f} kWh
- 非根孤岛episode：{len(passports.episodes)}
- 护照BLOCKED小时：{blocked_island_hours}
- GFM/黑启动证据：当前由柴油/BESS模型容量推断，未冒充现场验证
- 生命线任务完成：{int(care_evaluation['task_complete'].sum())} / {len(care_evaluation)}
- 一级生命线任务完成：{int(care_evaluation.loc[care_evaluation['tier'] == 1, 'task_complete'].sum())} / {int((care_evaluation['tier'] == 1).sum())}
- CareTask数据边界：E类合成赛事模板，不是医院实测或临床标准
- 支路热限额口径：{result.model.capacity_assumption}
"""
        (output / f"report_{slug}.md").write_text(
            strategy_result.report + validation_summary,
            encoding="utf-8",
        )
    mrv = write_mrv_bundle(
        result,
        output / "mrv",
        project_root=Path(__file__).resolve().parents[2],
        created_at=args.created_at,
    )
    print(result.comparison.to_string(index=False))
    print(
        f"\nMRV bundle={mrv['bundle'].resolve()} "
        f"verified={mrv['verification']['verified']}"
    )
    print(f"\nArtifacts written to {output.resolve()}")


if __name__ == "__main__":
    main()
