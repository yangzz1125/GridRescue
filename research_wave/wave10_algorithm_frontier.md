# GridRescue Wave 10：算法前沿与学术创新路线

**冻结日期：2026-08-22**  
**性质：研究设计报告；未修改生产代码。**

## 结论先行

Wave 8 已正确裁定：GridRescue 的强项不是宣称“发明一个全新恢复算法”，而是服务合同、物理反馈、MRV 证据与主张 gate 的闭环。Wave 10 的正确方向，是把极端天气不确定性和尾部风险纳入这个闭环，而不是在 10 天内强行上 GNN、强化学习或 MISOCP。

**推荐一主一辅一证书：**
1. 主线：嵌套 CVaR 的生命线风险预算恢复（A2）。
2. 辅线：联合天气压力集上的轻量鲁棒服务验证（A1-lite）。
3. 证书：碳因子翻转阈值 / 最小后悔证书（A5）。
4. 保障：风险 MRV gate（A11）。

若只做一项，选 A2。它复用现有 CVXPY、ServiceContract、CareTask、Pareto、Monte Carlo、MRV 路径，且可严谨地说成“冻结合成压力集上的尾部生命线风险比较”。

## 已审阅现状

| 代码/测试 | 已有资产 | Wave 10 含义 |
|---|---|---|
| src/gridrescue/scenarios.py | DisasterScenario 已含故障、修复、PV 降额、碳倍率、抢修距离、温度；可确定性生成 24h profile 和合成多故障样本。 | 缺少概率、相关性、预报误差、非前视阶段。 |
| dispatch.py | CVXPY 节点-小时空间调度，岛屿功率平衡、GFM、SOC、PV/柴油、服务 cap、词典序目标和 ServiceContract。 | 可直接承接有限场景 CVaR、风险预算和鲁棒外层验证。 |
| pipeline.py / powerflow.py | P/Q 后验校验和损耗/组件 cap 回灌；严格合同候选不静默放宽。 | 新风险候选仍必须经过物理门。 |
| pareto.py | 医院→关键→普通负荷词典序锚点，epsilon 预算碳前沿，CareTask/物理失败留档。 | 风险扩展必须保留服务锚点，不可改回简单权重和。 |
| experiments.py | scenario SHA、失败入分母、replay、bootstrap CI。 | 可做 out-of-sample paired tail validation。 |
| mrv.py | 因子、活动账、inventory、hash chain、claim gate、seal、verifier。 | 应把 alpha、catalog、tail set、风险表纳入可重算证据。 |
| test_core.py/test_pareto.py/test_experiments.py | 基准潮流、无源岛、Pareto、失败 epsilon、失败重放已有覆盖。 | 新方向应追加风险算术、catalog、tail、篡改、物理余度测试。 |
| wave8_synthesis.md | 禁止伪概率校准、真实天气 API、Carbon-SOC 结论、MISOCP/MINLP、无标签 AI 宣传。 | 坚持 kgCO2、E 类合成、same_service gate、失败不填零。 |

当前系统实际是单场景、24h、确定性空间凸调度加物理反馈；Monte Carlo 是离线压力测试，不是已实现的随机规划。温度目前主要是元数据；没有真实故障标签或现场概率分布。因此所有概率表述应限定为“冻结合成压力集经验覆盖/尾部统计”。

## 统一正式主张门

任一新算法只有同时满足才可进入正式主张：
1. 风险定义、alpha、场景集、服务 cap、碳边界固定并 hash；
2. 候选经现有潮流/反馈并物理通过；
3. CareTask、医院与关键服务不低于公开合同；
4. 使用与调参集分离的冻结外样本 catalog；
5. 报告样本数、失败数、paired scenario SHA、CI 与尾部样本数；
6. 至少保留一个失败/保守性代价反例；
7. risk config、catalog、tail set、输出表进入 MRV verifier；
8. same_service_pass=false 时不写同服务减排或严格碳优势。

## 20 条候选与裁决

| ID | 思路 | 类别 | 最小实现 | 验证指标 | 文件 | 正式主张 |
|---|---|---|---|---|---|---|
| A1 | 联合天气压力集的 WDRO-lite | 真创新 | 为 load、PV、碳因子、修复时长、热限建立 9-15 个相关有限压力场景；名义候选逐场景复验。 | worst EENS、worst carbon、Care/physical pass rate、regret。 | 新 weather_risk.py；改 scenarios.py、experiments.py、mrv.py。 | 条件可进；称“合成联合压力集鲁棒性”。 |
| A2 | 嵌套 CVaR 生命线风险预算 | 真创新，首选 | 新 risk.py 计算 LifeLineLoss 的 mean/VaR/CVaR；先对候选外层评估，再做有限场景 CVXPY 扩展。 | CVaR 0.8/0.9/0.95、tail Care 完成率、tail RRT、mean 碳代价。 | 新 risk.py/test_risk.py；改 pareto.py、experiments.py、mrv.py。 | 可进。 |
| A3 | 两阶段非前视预案 | 真创新 | 枚举初始 SOC reserve、tie policy、repair order；灾后观察后再用当前 dispatch。 | perfect-information gap、CVaR、预案 regret。 | 新 two_stage.py；改 restoration.py、experiments.py。 | 条件可进；不可称全局随机规划最优。 |
| A4 | CVaR-RRT 修复尾部时间 | 真创新 | 修复时长生成上尾样本；care.py 导出 task 首次连续完成时刻。 | Care deadline miss、CVaR-RRT、平均 RRT、碳/EENS 代价。 | 改 scenarios.py/care.py；新 test_repair_tail.py。 | 条件可进。 |
| A5 | 碳因子翻转阈值/最小后悔证书 | 真创新 | 从固定 activity 求候选在 grid/diesel factor 改变下的交叉阈值；输出 certificate CSV/JSON。 | 阈值两侧符号重算、稳定区间、max regret。 | 新 robustness.py/test_factor_certificate.py；改 mrv.py。 | 可进；仅固定活动/因子敏感性。 |
| A6 | 服务预算-碳-CVaR 三维 Pareto | 真创新 | 在既有 epsilon points 上补 out-of-sample risk 列，三维非支配、二维投影。 | 非支配数、tail risk 降幅、normal EENS 代价。 | 改 pareto.py/app.py；新 test_risk_pareto.py。 | 条件可进，依赖 A2。 |
| A7 | CareTask 机会约束 | 真创新 | tier-1 严格，tier-2 在有限样本至少 S-k 个通过；首版只做报告 gate。 | task completion rate、deadline miss、Wilson CI。 | 改 care.py/experiments.py；新 test_care_chance.py。 | 条件可进；仅经验覆盖率。 |
| A8 | 物理反馈裕度 envelope | 真创新 | 将 Vmin 和 loading 由 pass/fail 改为明确安全余度；后续再收紧 component cap。 | voltage/loading margin、stress pass、EENS/carbon conservatism。 | 改 powerflow.py/pipeline.py；新 test_physical_margin.py。 | 可进。 |
| A9 | PV-负荷-故障-修复联合机制 catalog | 真创新 | 暴雨、台风、高温三 regime，使用规则化相关采样而非独立随机。 | 参数相关矩阵、regime 覆盖、排序稳定性。 | 改 scenarios.py/experiments.py；新 test_weather_catalog.py。 | 条件可进；合成机制。 |
| A10 | 对抗式场景搜索 | 真创新 | 在 A9 的受限空间内用 beam/coordinate search 寻找最差 Care/physical 案例。 | worst loss 提升、query budget、replay 一致性。 | 新 adversary.py/test_adversary.py。 | 条件可进；称“约束压力测试”。 |
| A11 | Risk-of-Claim MRV gate | 包装创新但工程价值高 | claim_gates 加 catalog hash、alpha、tail count、OOS、risk recomputation。 | 改 alpha/loss/weight/catalog 后 verifier 失败。 | 改 mrv.py/test_mrv.py；新 test_risk_mrv.py。 | 可作系统创新，不单称算法首创。 |
| A12 | 动作 LODO 风险归因 | 弱真创新 | 单暴雨、6 动作、逐个移除后重跑，输出模型内 risk delta。 | replay、physics/care pass、delta。 | 新 attribution.py；改 restoration.py。 | 仅“模型反事实边际贡献”。 |
| B1 | GNN-free 图结构筛选 | 包装创新/过渡 | 图割、岛容量、GFM、关键覆盖、PV/load 特征的规则或线性排序。 | recall@k、false negative、vs 随机。 | 新 graph_screen.py。 | 仅辅助筛选。 |
| B2 | 物理约束 GNN surrogate | 高风险 | 若探索，先做 tree/MLP，按 topology 留出，不取代潮流。 | OOD recall/FNR、节省调用、误筛代价。 | 研究 notebook，不加 release 依赖。 | 不进正式主张。 |
| B3 | GNN warm-start/策略学习 | 高风险 | 需大量图-策略标签和统一 imitation target。 | optimality gap、violations、OOD。 | 未来 learning_policy.py。 | CUT。 |
| B4 | 图对比学习场景检索 | 包装创新 | 先用 hand-crafted feature cosine nearest-neighbor，展示相似案例。 | 检索稳定性、指标距离。 | scenario_retrieval.py。 | 仅解释/UI。 |
| C1 | SCM：天气→故障→修复→服务/碳 | 真创新但边界强 | 写 structural equations；在固定 exogenous seed 下做 do(PV/repair) 干预。 | intervention reproducibility、相关对照、合法调整变量反例。 | 新 causal.py/test_causal.py/causal_assumption_register.md。 | 条件可进，仅合成机制因果。 |
| C2 | 双重稳健因果评价抢修动作 | 高风险 | 需要真实 OMS/工单/天气/动作日志与治理。 | propensity/outcome balance/ATE。 | 未来数据工程。 | CUT。 |
| C3 | 安全 RL/GNN-RL | 高风险 | 混合动作、约束、训练成本高；与冻结证据链冲突。 | violation rate、OOD、sample cost。 | 未来。 | CUT。 |
| C4 | MISOCP/AC-OPF 联合恢复 | 高风险 | 需重写现有稳定反馈流程和求解器依赖。 | feasible optimum gap/runtime。 | 未来。 | CUT。 |

## A2 的建议定义

令场景 s 的生命线损失为：

L_s = 1000 E_H,s + 100 E_K,s + 500 × CareDeadlineMiss_s + RRT_s。

经验 CVaR：

CVaR_alpha(L) = mean(最大的 ceil((1-alpha)S 个 L_s))。

首版不要把 CVaR 生硬塞进现有所有加权项。正确顺序是：
1. 固定医院/关键服务合同与 CareTask；
2. 在候选/epsilon 集上最小化 CVaR(L)；
3. 在 CVaR 容差内比较 kgCO2 inventory；
4. 所有展示点经物理反馈和 MRV 验证。

建议主指标 alpha=0.80，0.90/0.95 做敏感性。若 S=12，0.90 的 tail 太小；正式展示优先 S>=30，并写明 tail_count。失败 scenario 不填 0：报告 conditional-on-solved CVaR，同时以失败 gate 阻断正式风险比较。

## 10 天执行

### Day 1-2：catalog 与风险算术
- 固定三灾种联合压力 catalog，JSON/SHA/seed/regime 全保存；
- 实现 risk.py、CVaR 单测、失败不填零；
- 对 A/B/C 和 4 个 epsilon 候选生成 risk_results.csv。

### Day 3：Care 尾部恢复
- 从 care.py 输出 task 首次连续完成时间、deadline miss；
- 形成 LifeLineLoss、tail scenario IDs、tier 汇总。

### Day 4：WDRO-lite 与风险 Pareto
- 名义候选在 catalog 上复验；
- 只保留通过 Care/物理门的 representative points；
- 固定一个平均碳低但 tail Care 差的反例。

### Day 5：翻转阈值证书
- 依据 grid/diesel/crew activity 生成因子阈值；
- 对 ±10%、±20% 离散点 sanity rerun；
- 服务不等价候选禁止出“strict”证书。

### Day 6：risk MRV
- manifest 输入 risk spec/catalog；
- verifier 重算 CVaR/tail；
- 篡改 alpha、loss、weight、catalog hash 均失败。

### Day 7：统计
- paired SHA、bootstrap CI、成功/失败计数；
- alpha 和 catalog seed 敏感性。

### Day 8：展示
- 不增加 tab；在现有证据抽屉加入 Risk evidence；
- 三张图：服务-碳-风险、tail Care timeline、factor flip certificate。

### Day 9-10：复跑与冻结
- 清洁目录重跑、测试、MRV verify；
- 固定 RISK-COMP-01；
- 只发布过统一正式主张门的结论。

## 必需新增测试

1. CVaR 已知数组算术与并列 tail。
2. 失败场景不零填充、整体 risk gate 失败。
3. catalog 同 spec 可重放且 SHA 稳定。
4. 三 regime 参数方向和相关性不自相矛盾。
5. 增加 Care deadline miss 后 CVaR-RRT 单调上升。
6. physical fail 点保留但不得进入 risk frontier。
7. 因子阈值两侧策略符号正确。
8. same_service_pass=false 时阻断 strict carbon/risk claim。
9. 篡改 alpha、tail loss、weight、catalog 后 MRV verify=false。
10. tune/test catalog ID 与 SHA 不重合。
11. 加大物理余度不得改善最坏物理裕度的错误性检查。

## 可用/禁用表述

**可用：**
- “冻结合成极端天气压力集上的 CareTask-CVaR 风险敏感恢复比较。”
- “候选同时通过服务合同、P/Q 物理反馈和 MRV 风险证据 gate。”
- “固定活动账和因子假设下的推荐翻转阈值/稳定区间。”
- “E 类合成机制实验，不等同现场概率、真实预测或第三方核证。”

**禁用：**
- “真实天气概率已校准。”
- “GNN 实现可靠故障预测/实时控制。”
- “DRO 保证真实电网最坏情形。”
- “CVaR 证明现实灾害风险降低。”
- 服务不等价时的“同服务减排/严格碳优势”。
- Carbon-SOC 优越性、AC-OPF/MISOCP 全局最优。

## 最终排序

**P0：** A2、A9、A11、A5、A8。  
**P1：** A1-lite、A4、A6、A12（P0 全绿后最多选一项）。  
**CUT：** B2/B3、C2/C3/C4、完整 Wasserstein DRO、真实天气 API、真实概率校准。

最终学术表述应是：

> GridRescue 将极端天气不确定性显式化为可复放联合压力集，将生命线尾部损失显式化为 CVaR 服务合同，并将物理裕度、CareTask、kgCO2 inventory 与风险参数封入可重算的 recommendation evidence package。

这比堆叠 GNN、RL 或大规模 MISOCP 更符合当前代码资产、Wave 8 边界和 10 天交付条件。
