# Wave11 可落地创新方向（10天冲刺备选）

> 基于现有 `network`、`scenarios`、`restoration`、`dispatch`、`care`、`pareto`、`experiments`、`paired_stats`、`mrv` 和 Streamlit 工作台整理。所有方向保持当前主张边界：`controlled_service_budget_inventory_difference`；36 场景 `strict_eligible=0` 不包装为严格同服务减排。

| 优先级 | 方向 | 核心问题 | 创新点 | 最小交付物 | 主要指标 | 风险 |
|---|---|---|---|---|---|---|
| S | CVaR 极端风险鲁棒推荐 | 均值最优方案可能在台风/热浪尾部失效 | 将 MC/重放结果转为 P95 EENS、CVaR95、Gate 失败概率并参与推荐 | `src/gridrescue/risk.py`、风险卡、JSON 报告 | mean/CVaR95 EENS、最差10%关键EENS、PASS概率、bootstrap CI | 极低 |
| S | 韧性-碳自适应策略路由器 | 固定策略无法随灾种、强度和 GFM 条件切换 | 用现有 36 场景 paired deltas 训练可解释规则/决策树，输出策略、置信度、拒绝理由 | `scripts/build_policy_router.py`、留一灾种验证 | oracle regret、策略准确率、Gate-pass率、推理延迟 | 低 |
| S | MRV 证据图谱与篡改挑战 | 评委难直观看 activity→factor→inventory→claim 的证据关系 | 证据图可视化 + 自动注入删行、换因子、改 hash、断外键等 mutation | `mrv_graph.py`、Streamlit 页、mutation tests | 篡改召回率、误报率、链覆盖率、验证耗时 | 极低 |
| S | Pareto 膝点与排名稳定性 | Pareto 点太多，评委难选推荐点 | 自动 knee-point + 因子/故障扰动下 rank bootstrap，解释“为何不是最低碳点” | `knee.py`、推荐卡、rank report | 膝点稳定率、排名翻转率、双目标 regret、Gate 通过率 | 极低 |
| A | 反事实边界压力测试 | 36 固定场景无法显示策略何时反转或失败 | 围绕 NO_GFM/BLOCKED 和失败点搜索最小故障组合，生成边界证据 | `search_failure_boundary.py`、boundary CSV/图 | 最小故障数、边界误差、失败阶段分布、策略反转率 | 低 |
| A | 生命线任务依赖 DAG + 公平服务 | 普通负荷聚合损失分配不透明 | 任务依赖、deadline、连续时长和居民/公共服务公平指标纳入合同 | `care.py`/`ServiceContract` 扩展、分组指标 | 任务成功率、deadline违约、Gini/max-min、关键EENS、碳增量 | 低 |
| A | 修复队伍路径-碳联合优化 | `crew_emissions` 目前是固定项，修复顺序未体现车辆路径 | 简化道路距离/天气通行时间，联合修复优先级与车程碳 | `crew.py`、3种启发式、MRV动作账 | 医院恢复时间、EENS、crew km/碳、总碳 | 低-中 |
| A | 电池寿命/隐含碳耦合 | throughput 仅作为权重，未计入寿命损耗 | SOC 轨迹→throughput/rainflow 近似→寿命折算碳，防止“减运行碳、增寿命碳” | `dispatch` degradation cost、MRV 字段 | 运行碳、寿命折算碳、柴油替代量、SOC/热限、膝点变化 | 低-中 |
| B | 公开气象回放适配器 | 当前灾害是 E 类合成压力场景 | 武汉天气回放→可解释故障概率/强度映射，保留 synthetic fallback | `weather_replay.py`、3日缓存、输入 hash | 映射校准、可复现率、数据缺失率、策略变化 | 中（数据与证据等级） |
| B | 柔性负荷/需求响应 | 普通负荷仅能供/失供，未体现移峰潜力 | 可移峰负荷、舒适度/服务预算与小时碳强度联动 | `dispatch` 增加 flex load 守恒约束与指标 | 峰值削减、EENS、柴油/弃光、碳、舒适度违约 | 中 |

## 10天组合建议

1. **证据最稳组合**：CVaR → 策略路由器 → MRV 图谱 → Pareto 膝点。
2. **叙事最强组合**：上述四项 + 修复队伍路径-碳。
3. **模型增强组合**：上述四项 + 电池寿命；只在已有测试全绿后实施。
4. 气象回放和柔性负荷属于候补，不得影响 Wave10 冻结包；外部数据/新约束单独编号并标记 E 类。

## 共同验收规则

- 新增结果必须有独立 manifest、失败分母和可重放命令。
- 不得把受控服务预算差异写成严格同服务减排；`same_service_pass=false` 保持显式。
- 优先复用 36 场景 catalog、`paired_stats`、现有 `mrv verifier` 与 Streamlit FROZEN/LIVE 隔离。

## 快速排序（创新×证据×10天可交付）

| 方向 | 一等奖叙事 | 代码复用 | 证据可复核 | 10天完成度 | 综合判断 |
|---|---:|---:|---:|---:|---|
| CVaR 风险推荐 | 4 | 5 | 5 | 5 | 首选 |
| 自适应策略路由 | 5 | 5 | 4 | 4 | 首选 |
| MRV 证据图谱 | 4 | 5 | 5 | 5 | 首选 |
| Pareto 膝点稳定性 | 4 | 5 | 5 | 5 | 首选 |
| 反事实边界搜索 | 5 | 4 | 5 | 4 | 次选 |
| 修复队伍路径-碳 | 5 | 4 | 3 | 3 | 次选 |
| 电池寿命隐含碳 | 4 | 4 | 3 | 3 | 次选 |
| 任务 DAG/公平 | 4 | 4 | 4 | 4 | 次选 |
| 气象回放 | 5 | 3 | 2 | 2 | 候补 |
| 柔性负荷 | 4 | 3 | 3 | 2 | 候补 |
