# GridRescue 十日冲刺执行单

## 项目定位

**GridRescue 碳韧智网**：面向极端天气的配电网故障恢复与低碳保供数字孪生软件。

主投叙事：新型电力系统 / 极端气候韧性电网。核心不是堆 AI，而是把：

```text
Care 生命线服务合同 → Physics P/Q潮流与热限 → MRV可复算碳证据
```

绑定为三道推荐资格门。

## 十日安排

| 天数 | 必做交付 | 验收证据 |
|---|---|---|
| D1 | 冻结赛道、题目、主张边界、素材清单 | `factsheet`、`claim_dictionary` |
| D2 | 跑通36场景批处理与strict-contract-9 | batch manifest、失败分母 |
| D3 | 完成CVaR/失败预算风险卡 | `risk_report.json` |
| D4 | 完成MRV因子不确定性传播 | `sensitivity_report.json` |
| D5 | 工作台首屏与台风BLOCKED演示 | Streamlit health + 录屏片段 |
| D6 | 补Pareto膝点、MRV证据抽屉、下载按钮 | UI smoke + CSV |
| D7 | 盲审：让非本专业同学复述三道门 | 3个高频问题及答案 |
| D8 | 只修阻断问题，重跑全量测试 | `61 passed` |
| D9 | 更新申报书、视频脚本、manifest、ZIP | SHA-256、`testzip=None` |
| D10 | 现场彩排与双备份 | 本地ZIP、录屏、纸面Q&A |

## 180秒答辩节拍

1. 0–15秒：极端天气下“关键服务、物理安全、碳账”互相冲突。
2. 15–45秒：Care→Physics→MRV三门动画。
3. 45–95秒：暴雨或高温场景展示C0/C4、EENS、关键恢复率、kgCO2。
4. 95–120秒：切台风，展示`normal_anchor → BLOCKED`，说明失败不被隐藏。
5. 120–145秒：打开MRV抽屉，展示factor class E、hash、verifier。
6. 145–165秒：展示36场景配对结果、CVaR卡、500次因子敏感性区间。
7. 165–180秒：主动说清`same_service_pass=false`与应用边界。

## 三句固定答辩话术

- **为什么不是只优化碳？** 先满足生命线合同和潮流物理可行，再谈碳清单。
- **为什么不叫严格减排？** 当前C0/C4服务不等价，系统自动降级为受控服务预算下的清单差异。
- **为什么使用合成数据？** 十日原型先验证可复算链路；真实馈线、天气和因子按同一schema替换后重新核验。

## 冻结规则

```text
strict_eligible=0
same_service_pass=false
claim_status=controlled_service_budget_inventory_difference
```

禁止在最后阶段新增GNN、RL、MISOCP、实时SCADA写回或未经证据登记的外部数据。
