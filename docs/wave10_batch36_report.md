# Wave10 36场景配对实验报告

**生成日期：2026-08-23**  
**catalog冻结日期：2026-08-22**  
**数据等级：E类合成压力场景**

## 设计

- 3个灾种：暴雨内涝、台风、极端高温。
- 3档强度：low、medium、high。
- 每个分层4个固定复本，共36个scenario_id。
- 三种策略使用相同scenario_id和输入hash；每个策略36/36物理批处理成功。
- 统计使用逐场景配对差和确定性bootstrap，失败场景不填零。

## 碳韧协同恢复相对最小失供恢复

| 指标 | 配对均值差（候选−参考） | 95% bootstrap区间 | 解释 |
|---|---:|---:|---|
| EENS (kWh) | +3192.85 | [3046.78, 3324.06] | 普通服务让步带来更高总失供 |
| critical EENS (kWh) | −15.05 | [−22.74, −7.99] | 关键服务侧配对差更低 |
| 关键负荷恢复率 | +0.0466个百分点 | [0.0247, 0.0704] | 关键服务侧略高 |
| 运行清单 (kgCO2) | −2331.35 | [−2447.95, −2203.79] | 受控服务预算下的清单差异 |

## 主张边界

这不是严格同服务减排结论。V08正式claim gate仍为：

```text
same_service_pass=false
claim_status=controlled_service_budget_inventory_difference
```

因此正式表述只能是：**在固定E类合成压力集上，碳韧协同策略相对最小失供参考策略呈现受控服务预算下的运行碳清单差异，同时普通服务EENS增加。**

完整机器可读证据：

- `artifacts/wave10/batch36/experiment_runs.csv`
- `artifacts/wave10/batch36/validation_summary.csv`
- `artifacts/wave10/batch36/paired_deltas.csv`
- `artifacts/wave10/batch36/paired_report.json`
- `artifacts/wave10/batch36/failure_manifest.json`

## C0/C4分轨

已将同一36条scenario_id拆成两条审计臂：

- C0：最小失供恢复，reference service anchor；
- C4：碳韧协同恢复，controlled-budget candidate。

当前 `strict_eligible=0`、`controlled_eligible=36`，这表示分轨已完成，但严格同服务比较仍被证据门拦截；不能把C4的清单差异升级成严格减排结论。
