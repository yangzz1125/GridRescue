# Wave10 技术增强候选（10 天可落地）

本文只列不改变主张边界的工程增强。禁止引入 GNN、RL、实时 SCADA 或大规模 MISOCP；主流程仍为 case33 + LP/CVXPY + P/Q 反馈 + Care/Physics/MRV 三道门。

## 优先级总览

| 优先级 | 增强 | 评委价值 | 实施风险 | 预计工期 |
|---|---|---:|---:|---:|
| P0 | 动作级可解释归因（LODO + OMA） | 高：回答“为什么这样恢复” | 低 | 1.5–2 天 |
| P0 | 风险调整策略选择（CVaR/失败预算） | 高：从平均最优升级为压力下可用 | 中 | 1.5–2 天 |
| P0 | MRV 因子/活动不确定性传播 | 高：避免单点排放数字过度确定 | 低 | 1 天 |
| P1 | Care/服务分层护照 | 中高：防止平均 EENS 掩盖生命线损失 | 低 | 1 天 |
| P1 | 跨灾种留一类外推验证 | 中高：证明策略不是只适配单一灾种 | 中 | 1.5 天 |

## 1. 动作级可解释归因（LODO + OMA）

### 目标
把 `actions_*.csv` 中的 tie-close、repair-complete 变成可审计决策单元，报告每个动作对关键供电、普通 EENS 和碳清单的边际贡献。保留 `NA/PHYSICAL_FAIL`，不把不可行反事实填成 0。

### 文件级改动
- 新建 `src/gridrescue/attribution.py`：
  - `register_decisions(result) -> decision_registry`（稳定 `decision_id`、原始时刻、asset、语义、依赖）。
  - `run_lodo(scenario, strategy, policy_snapshot)`：逐个删除动作，调用 `solve_strategy_with_feedback`。
  - `run_oma(...)`：按原始时间戳前缀逐步加入动作，输出 telescoping 检查。
  - `AttributionResult`、`decision_registry.csv`、`decision_marginal_value.csv`。
- 新建 `scripts/build_action_attribution.py`：默认暴雨/台风/极端高温各 1 个代表场景；`--all` 扩展 36 场景。
- `app.py`：增加“动作贡献”折线/条形图，显示 `critical_served_delta_kwh`、`normal_eens_avoided_kwh`、`carbon_avoided_kg` 和状态标签。
- 新增 `tests/test_attribution.py`；`docs/action_attribution.md` 记录反事实语义与证据边界。

### 实验设计
3 灾种 × 1 强度 × 1 replicate，三策略；每个参考计划做 LODO，OMA 只对候选策略执行。所有候选固定相同 scenario/network/factor/policy hash。

### 验收标准
1. 基线重放指标与已有 `pipeline_cache` 在 1e-5 内一致。
2. OMA `sum(marginal)` 与完整计划−空计划差异 ≤ 1e-5（可行前缀）。
3. 任何反事实失败都有 `candidate_status=PHYSICAL_FAIL` 与 failure reason，指标为 NA。
4. 每一行含 `decision_id`、`parent_set_hash`、`scenario_sha256`、`policy_hash`，可复放。

## 2. 风险调整策略选择（CVaR/失败预算）

### 目标
利用现有 36 场景批结果，在不改底层求解器的前提下增加“压力风险”决策：均值、CVaR95、失败率、Care/Physics 通过率联合排序。

### 文件级改动
- 新建 `src/gridrescue/robust_policy.py`：
  - `compute_tail_metrics(results, alpha=.95)`（对 `eens_kwh`、`critical_eens_kwh`、`total_carbon_kg` 计算分层 CVaR）。
  - `rank_strategies(results, risk_lambda, failure_budget)`。
  - `RobustPolicyScore`，记录 mean、CVaR、Wilson failure interval、eligible count。
- 新建 `scripts/build_robust_policy.py`，输入 `batch36/experiment_runs.csv` 或 strict-contract 结果，输出 `robust_policy_scores.csv`、`robust_policy_manifest.json`、一张 risk frontier 图。
- `app.py`：增加“平均最优/风险最优”切换；展示 tail 场景 ID，不改变 frozen claim。
- 新增 `tests/test_robust_policy.py`、`docs/robust_policy.md`。

### 实验设计
以 36 个 context 为固定样本，按 hazard×severity 分层；`risk_lambda ∈ {0, .25, .5, 1}`，`alpha ∈ {.90,.95}`。主结果只报告 `failure_budget=0` 的 Care/Physics 合格策略；其余标记 diagnostic。

### 验收标准
1. `risk_lambda=0` 排名与当前按均值排序一致。
2. 增大 `risk_lambda` 时，选中策略 CVaR 不上升（允许均值小幅变差）。
3. 失败场景不得当作 EENS=0；failure rate 与 Wilson 区间保留。
4. 评分输入/版本/alpha/lambda/hash 写入 manifest，重复运行 bitwise 稳定。

## 3. MRV 因子与活动不确定性传播

### 目标
把 `factor_registry.csv` 中已有 `uncertainty_pct` 变成区间证据，回答“排放差异对因子假设是否敏感”，不把区间下界包装为减排。

### 文件级改动
- 新建 `src/gridrescue/mrv_sensitivity.py`：
  - `sample_factor_scenarios(registry, n=500, seed=20260823, method="lhs")`。
  - `propagate_inventory(bundle, draws)`；输出每策略 `inventory_p05/p50/p95`、paired delta 区间、sign-stability。
  - 缺失/非有限因子直接 `DATA_MISSING`。
- 新建 `scripts/build_mrv_sensitivity.py`：默认 500 次确定性 LHS；输入冻结 MRV bundle，输出 `mrv_sensitivity_draws.csv`、`mrv_sensitivity_summary.csv`、manifest。
- `app.py` 的 MRV 面板增加区间和“符号稳定性”标识；same-service gate 仍取原 gate。
- 新增 `tests/test_mrv_sensitivity.py`、`docs/mrv_sensitivity.md`。

### 实验设计
对 grid/diesel/crew 三类因子按 registry `uncertainty_pct` 扰动；活动量按 ±5% 测量误差做第二层 draw（可选）。500 draws，固定 seed；同时做 OAT ±20% 灵敏度排名。

### 验收标准
1. 零不确定性时 p05=p50=p95，且与 `verify_mrv_bundle` 基线一致（≤1e-6 kgCO2）。
2. 所有 draw 保留 factor snapshot hash；不可行/缺失 draw 明确标记，不填零。
3. 区间只影响敏感性报告，不改变原 `claim_status` 或 `same_service_pass`。
4. summary 可重放，seed/hash/config 写入 manifest。

## 4. Care/服务分层护照

### 目标
将现有 CareTask 和 node `service_class` 统一为服务分层护照，分别报告 Tier-1/Tier-2 任务、hospital/essential/critical/normal 能量服务，避免 aggregate EENS 掩盖关键小负荷。

### 文件级改动
- 新建 `src/gridrescue/cohorts.py`：定义 E 类 synthetic cohort schema、选择器、能量分区校验、`build_service_passport(result, validation, tasks)`。
- 新建 `data/resilience_service_cohorts_v1.json`；只包含服务合同，不包含个人或人口属性。
- `scripts/build_service_passport.py` 输出 `service_passport.csv/json`；写入 cohort definition SHA。
- `app.py` 增加 cohort heatmap；`tests/test_cohorts.py`、`docs/service_passport.md`。

### 实验设计
36 contexts × 3 strategies，按 cohort 计算 demand/served/EENS/served_fraction/pass；Tier-1 为硬门，Tier-2/energy cohort 做监测。

### 验收标准
1. energy cohort 选择器严格分区且无重复/漏项；分区和等于 node_frame 总需求（≤1e-6）。
2. Tier-1 任务任一失败即 `care_contract_pass=false`；缺失证据为 `DATA_MISSING`。
3. 输出含 `data_class=E_synthetic_service_cohort_template` 和 definition SHA。
4. 与现有 `evaluate_care_tasks` 结果逐任务一致。

## 5. 跨灾种留一类外推验证

### 目标
检查策略权重是否只在某一灾种上有效：在两类灾种上选择 risk policy，在留出灾种上验证；仍是合成压力实验，不宣称真实气候预测。

### 文件级改动
- `src/gridrescue/scenarios.py`：为 catalog 行增加 `hazard_family`、`severity_band`、`replicate_id` 元数据（不改变现有 scenario hash）。
- 新建 `scripts/run_transfer_eval.py`：LOHO（leave-one-hazard-out）训练/选择/测试，输出 `transfer_matrix.csv`、failure manifest。
- 新建 `src/gridrescue/transfer.py`（按 hazard family 分组、固定策略评分、汇总 Wilson/CVaR）。
- `app.py` 增加“跨灾种迁移矩阵”只读图；`docs/transfer_eval.md`、`tests/test_transfer.py`。

### 实验设计
3 folds：leave-flood-out、leave-typhoon-out、leave-heat-out；每 fold 用 2 hazard × 2 severity × 4 reps 选策略，留出 1 hazard 的 12 contexts 测试。只允许使用冻结 policy，不在测试集调参。

### 验收标准
1. 训练/测试 scenario SHA 不重叠。
2. 输出每 fold 的 mean/CVaR95/EENS/critical-EENS/carbon、Care/Physics pass、failure count。
3. `risk_lambda=0` 等价现有均值基线；测试结果只作 robustness/transfer 证据，不改 strict-eligible=0 事实。
4. 运行 10 分钟内完成（复用 pipeline cache），结果可重放。

## 推荐 10 天节奏

| 日程 | 交付 |
|---|---|
| D1 | attribution registry + LODO/OMA 单场景 |
| D2 | attribution 三灾种 + UI + tests |
| D3 | robust_policy tail metrics + batch36 report |
| D4 | robust policy UI + manifest + tests |
| D5 | MRV sensitivity engine + 500 draws |
| D6 | MRV UI + report + tests |
| D7 | service passport + cohort schema |
| D8 | transfer eval + figures |
| D9 | docs/video/申报书更新；只保留稳定增强 |
| D10 | 全量回归、zip、manifest/hash、答辩演练 |

## 砍项规则

若 D4 仍未通过 57-test 回归，冻结 P1/P2；最终提交至少保留 P0 的 attribution、risk policy、MRV sensitivity 三项。任何增强都不得将 `strict_eligible=0` 改写为严格减排。
