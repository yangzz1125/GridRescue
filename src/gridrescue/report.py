from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from .carbon import CarbonBreakdown
from .metrics import RecoveryMetrics
from .scenarios import DisasterScenario


def markdown_report(
    scenario: DisasterScenario,
    strategy: str,
    metrics: RecoveryMetrics,
    carbon: CarbonBreakdown,
    actions: pd.DataFrame,
) -> str:
    action_lines = "\n".join(
        f"- T+{int(row.hour)}h：{row.action}" for row in actions.itertuples()
    ) or "- 无额外开关操作"
    values = asdict(metrics)
    return f"""# GridRescue 恢复与MRV报告

## 场景

- 灾害：{scenario.name}
- 描述：{scenario.description}
- 故障支路：{', '.join(map(str, scenario.failed_branch_ids))}
- 策略：{strategy}

## 核算边界

本报告比较恢复方案的增量排放，仅统计上级电网购电、应急柴油发电和抢修车辆；
新能源弃电作为机会损失单列。恢复更多负荷本身不被直接认定为减排。

## 恢复动作

{action_lines}

## 韧性结果

- EENS：{values['eens_kwh']:.2f} kWh
- 关键负荷EENS：{values['critical_eens_kwh']:.2f} kWh
- 关键负荷恢复率：{values['critical_recovery_pct']:.2f}%
- 恢复时间：{values['restoration_time_h']} h
- 峰值失供功率：{values['peak_unserved_kw']:.2f} kW
- 开关操作：{values['switch_operations']} 次

## 能源与碳结果

- 柴油发电：{values['diesel_energy_kwh']:.2f} kWh
- 新能源消纳：{values['renewable_consumed_kwh']:.2f} kWh
- 新能源弃电：{values['renewable_curtailment_kwh']:.2f} kWh
- 上级电网排放：{carbon.grid_kg:.2f} kgCO₂
- 柴油排放：{carbon.diesel_kg:.2f} kgCO₂
- 抢修车辆排放：{carbon.crew_kg:.2f} kgCO₂
- 恢复阶段总排放：{carbon.total_operational_kg:.2f} kgCO₂

## 可追溯性

逐时负荷、资源出力、失供电量、排放因子及开关动作均随报告导出，可独立复算。
"""

