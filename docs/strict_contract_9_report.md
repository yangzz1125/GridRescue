# 严格同服务合同 9 场景分层实验

**生成日期：2026-08-23**  
**catalog 冻结日期：2026-08-22**

## 结果摘要

- 9 个场景 × 0%/4% 两个预算点 = 18 个 Pareto 点。
- `frontier_eligible=12/18`，失败 `6/18`，严格合同可行率 66.7%。
- 暴雨：6/6 通过；台风：0/6 通过；极端高温：6/6 通过。
- 台风失败点均保留在 points 与 manifest 中，失败阶段为普通服务锚点（`normal_anchor`），没有填零或从分母剔除。

## 分层解释

| 灾种分层 | 场景数 | 严格合同点 | 通过 | 失败 | 解释 |
|---|---:|---:|---:|---:|---|
| 暴雨 | 3 | 6 | 6 | 0 | 在 0%/4% 服务预算下均满足 Care 与 Physics 门 |
| 台风 | 3 | 6 | 0 | 6 | 普通服务锚点资源不可行，系统阻止继续包装成低碳结果 |
| 极端高温 | 3 | 6 | 6 | 0 | 在该代表性强度下两预算点均可行 |

## 口径边界

`strict_contract=true` 表示同一场景、同一 Care 合同、同一物理约束下的可行性筛选。该批次是代表性严格合同机制演示，**不外推为 36 场景总体严格减排结论**。36 场景主报告仍保持：

```text
strict_eligible=0
same_service_pass=false
claim_status=controlled_service_budget_inventory_difference
```

## 机器证据

- `artifacts/wave10/strict_contract_9/strict_contract_points.csv`
- `artifacts/wave10/strict_contract_9/strict_contract_anchors.csv`
- `artifacts/wave10/strict_contract_9/strict_contract_manifest.json`
