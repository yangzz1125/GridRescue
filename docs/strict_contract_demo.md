# 严格服务合同实验 Demo

**生成日期：2026-08-23**  
**冻结catalog日期：2026-08-22**

## 实验目的

用现有Pareto求解器真正执行CareTask、医院/关键服务和普通服务合同，验证C0端点与C4受控预算点是否能在同一场景下通过物理反馈，而不是只按标签做C0/C4分轨。

## 范围

本轮选择3个代表场景，每个场景运行普通服务预算`0%`和`4%`两个点：

- `W10-01-01-01`：暴雨内涝 / low；C0和C4均通过；
- `W10-02-01-02`：台风 / low；关键服务锚点失败，两个点均保留为失败；
- `W10-03-03-04`：极端高温 / high；C0和C4均通过。

结果：6个点中4个frontier eligible，2个在`essential_anchor`阶段失败。失败没有填零，均写入points表和failure字段。

## 代表结果

| 场景 | 预算 | contract | physical | frontier | normal EENS | kgCO2 |
|---|---:|---|---|---|---:|---:|
| 暴雨low | 0% | PASS | PASS | PASS | 0.001 | 43693.15 |
| 暴雨low | 4% | PASS | PASS | PASS | 1704.396 | 42504.70 |
| 台风low | 0% | FAIL | FAIL | FAIL | — | — |
| 台风low | 4% | FAIL | FAIL | FAIL | — | — |
| 高温high | 0% | PASS | PASS | PASS | 0.001 | 47491.60 |
| 高温high | 4% | PASS | PASS | PASS | 1726.681 | 46178.00 |

## 解释边界

这个Demo证明“严格合同求解链可运行并会保留失败”，不代表36场景总体严格同服务结论。完整36场景批仍保留`strict_eligible=0`的保守主张口径；后续若扩展严格合同批次，必须继续报告失败分母、场景hash和OOS边界。

机器证据：

```text
artifacts/wave10/strict_contract_demo/strict_contract_points.csv
artifacts/wave10/strict_contract_demo/strict_contract_anchors.csv
artifacts/wave10/strict_contract_demo/strict_contract_manifest.json
```
