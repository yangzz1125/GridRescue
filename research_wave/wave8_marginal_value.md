# Wave 8：恢复调度决策的轻量边际价值归因设计

> 范围：研究设计，不修改运行代码。本方案为 `GridRescue` 的既有恢复计划、空间调度、P/Q 反馈和碳账本增加一个**模型内反事实归因**视角：量化某个已排定动作缺失或按顺序加入时，三个结果如何变化。
>
> 三个主结果统一使用当前 24 个 `1 h` 时段的存量口径：
>
> 1. `critical_served_kwh`：关键负荷已供电量；
> 2. `normal_unserved_kwh`：普通负荷未供电量；
> 3. `operational_carbon_kg`：运行碳清单，等于购电、柴油和车辆项之和。
>
> **措辞边界**：本文所称“决策贡献”“边际价值”“归因”均指在固定输入、固定模型结构、固定求解规则和所定义反事实下的**模型归因**。它不是对真实电网、抢修行为、患者结果或排放系统作出的现实世界因果证明。特别地，当前 DER、热限额、故障/修复情景与部分排放因子含工程或合成假设；结论必须随 scenario、factor registry、代码版本和 policy snapshot 一起报告。

## 1. 已核对的接入边界

当前恢复计划在 `src/gridrescue/restoration.py` 的 `make_plan()` 中形成：

- `initial_tie_ids`：0 时刻闭合的联络开关；
- `repair_order` 与 `repair_completed_at`：故障支路的修复完成时刻；
- `actions`：可直接用于决策注册表的事件表。

以现有 `artifacts/flood_v08/actions_carbon_resilient.csv` 为例，参考计划含 6 个事件：T37、T33、T34（hour 0），L6（hour 7），L27（hour 13），L13（hour 23）。这正适合做首轮轻量归因，而不是把每个连续 CVXPY 变量都误说成一项“人工调度决策”。

每个候选仍应走既有闭环：

```text
masked / prefix RestorationPlan
  -> simulate_strategy / spatial dispatch
  -> validate_dispatch
  -> loss + reactive-loss + component-cap feedback
  -> convergence and 24-hour physical feasibility gate
  -> calculate_metrics + calculate_carbon
```

`calculate_metrics()` 已提供总 EENS、critical EENS、关键恢复率等；本研究额外从 dispatch 直接计算：

```text
critical_served_kwh = sum(served_critical_kw) * dt
normal_unserved_kwh = sum(unserved_normal_kw) * dt
operational_carbon_kg = carbon.total_operational_kg
```

当前 `dt=1 h`，所以数值上是逐小时 kW 列求和；导出字段仍显式写 `kWh`，避免以后改步长时产生单位误读。

### 1.1 碳账本的可解释范围

`src/gridrescue/carbon.py` 将运行碳拆为：

```text
total_operational_kg = grid_kg + diesel_kg + crew_kg
```

本轮候选使用同一灾害情景的 `crew_distance_km`。因此单个开关/修复事件的候选间 `crew_kg` 通常恒定；可归因差异主要来自 `grid_kg` 与 `diesel_kg`。输出必须同时保留三项，不把“少供电”“电池放电”或“弃绿变化”写成自动减排。

## 2. 推荐方法：LODO 为主，时间顺序边际为辅

采用两种互补、计算量都很低的指标：

1. **Leave-one-decision-out（LODO）**：回答“在该参考计划其余动作仍保留时，这个动作在模型中有多必要？”
2. **Ordered marginal analysis（OMA）**：回答“按这份排程的执行顺序，加入该动作时系统指标发生了什么变化？”

默认先交付 LODO 排名；当答辩需要讲恢复过程时，再展示 OMA 瀑布图。两者不应混成一个“真实因果分数”。

### 2.1 决策单元与反事实语义

把一个 `actions` 行映射为一个稳定的 `decision_id`：

| 类别 | 例子 | 反事实操作 |
|---|---|---|
| `tie_close` | `tie:T37@h0` | 从 `initial_tie_ids` 移除该 tie；其他 ties 和修复完成时刻保持原样。 |
| `repair_complete` | `repair:L6@h7` | 从 `repair_completed_at` 移除该支路，使其在整个 24 h 研究窗内保持 failed；不把剩余修复动作提前。 |

后者很重要：LODO 测的是“该支路按原定完成时刻被修复”的必要性，不是“重排班组后最优修复顺序”的价值。这样不会把一个动作的贡献和一次完整重优化混在一起。

每个候选必须保留相同的 scenario、资源配置、时间轴、初始 SOC、碳因子、热限额、求解器、反馈容差和最大反馈次数。对于同一小时的事件，参考顺序固定为：`tie_close` 先于 `repair_complete`，再按 asset id 升序；此排序只为可重复性，不声称其为唯一的物理执行顺序。

### 2.2 LODO 定义与符号

令 `D` 为参考计划的完整决策集合，`D\{j}` 为仅移除事件 `j` 的候选；令

```text
Y(P) = [C(P), U(P), K(P)]
C = critical_served_kwh
U = normal_unserved_kwh
K = operational_carbon_kg
```

将三个结果统一转为“正数=该动作带来改善”的 LODO benefit：

```text
Bcritical_j = C(D) - C(D\{j})
Bnormal_j   = U(D\{j}) - U(D)
Bcarbon_j   = K(D\{j}) - K(D)
```

解释规则：

- `Bcritical_j > 0`：该动作在参考模型内增加关键供电；
- `Bnormal_j > 0`：该动作减少普通失供；
- `Bcarbon_j > 0`：该动作降低运行碳清单；
- 负值是允许且有信息量的模型结果，常见于拓扑、资源和时序相互作用；不得强行裁成 0。

如果候选未收敛、潮流不可行或同一策略快照下求解无解，数值 benefit 填 `NA`，而不是用 0 伪装。可附标签：`essential_for_reference_feasibility`。

### 2.3 Ordered marginal 定义

按参考事件的时间顺序构造前缀集合：

```text
P0 = empty plan
Pj = {d1, d2, ..., dj},  j = 1...m
```

每个 `Pj` 保留事件自身在原计划中的 timestamp；例如加入 `repair:L27@h13` 不会把它提前到 hour 0。对统一收益向量

```text
Q(P) = [C(P), -U(P), -K(P)]
```

定义：

```text
Mordered_j = Q(Pj) - Q(Pj-1)
```

此路径满足逐维 telescoping identity：

```text
sum_j Mordered_j = Q(Pm) - Q(P0)
```

前提是每个前缀均有确定的数值解。与 LODO 不同，OMA 明确依赖顺序；因此它展示的是**该计划路径上的**边际变化，而不是顺序无关贡献。

### 2.4 交互与排序敏感性

配电网恢复存在强互补性：一个 tie 的价值可能只在某条支路修复之后出现。因此：

- **不得**要求 `sum(LODO_j)` 等于完整计划相对空计划的总改善；不相等正是交互存在的正常表现。
- 首版只用一个固定的时间顺序，保持轻量。
- 对进入前三、或 LODO 与 OMA 排名冲突的决策，补跑 10 个带固定 seed 的合法随机顺序，报告中位数、P10/P90 和 rank range。此项是敏感性分析，不必上完整 Shapley 枚举。

## 3. 关键实施规则：冻结 policy snapshot，杜绝候选内自重标定

当前 `碳韧协同恢复` 的无合同路径会先根据**当前候选的网络状态**求最小失供基准，再允许最多 8% 的普通负荷额外失供。若对每一个 LODO 候选直接调用这条默认路径，候选会自行更改比较门槛，归因会混入“候选重新定义了自己的服务预算”。

因此设计实现时必须持久化并复用一个 `policy_snapshot`：

```text
scenario hash + plan hash + ResourceConfig + DispatchWeights
+ initial SOC + grid-factor hash + feedback tolerance/max-iterations
+ fixed critical/normal service bounds (if used) + solver/version
```

推荐两层运行：

1. **主归因（fixed-policy）**：所有候选使用相同权重和同一套已冻结约束；不在候选内部重新计算 service anchor 或普通负荷 allowance。
2. **仅对主归因无解的诊断（relaxed diagnostic）**：解除被冻结的普通服务上限，其他输入不变，得到一个“服务退化量”诊断。该行必须标成 `diagnostic_relaxed`，不得与主排名混排。

对于不需要碳韧策略特有 8% allowance 的研究，可优先从 `最小失供恢复` 的固定策略快照开始，作为最小 MVP。之后分别对三类既有 strategy 生成各自的独立归因表；不同 strategy 的决策 value 不可在没有共同服务合同的情况下直接横向比较。

## 4. 算法（伪代码）

```python
reference = build_reference_plan(scenario, strategy)
registry = register_actions(reference.actions, reference)
policy = freeze_policy_snapshot(reference, strategy, resources, factors, solver)

base = solve_closed_loop(reference, policy)
assert usable(base)  # converged + all 24 h physically feasible
save_metrics("baseline_full", base)

# LODO: one physical action absent; all other actions retain original timestamps.
for d in registry:
    candidate_plan = mask_one_decision(reference, d)
    result = solve_closed_loop(candidate_plan, policy)
    save_attribution(
        mode="lodo",
        decision=d,
        metrics=metrics_or_na(result),
        benefits={
          "critical_served": base.C - result.C,
          "normal_unserved_avoided": result.U - base.U,
          "operational_carbon_avoided": result.K - base.K,
        },
        status=status(result),
    )

# OMA: prefixes keep original event timestamps.
previous = solve_closed_loop(empty_plan_like(reference), policy)
for ordinal, d in enumerate(registry.ordered(), start=1):
    prefix_plan = prefix_with_original_times(reference, ordinal)
    current = solve_closed_loop(prefix_plan, policy)
    save_attribution(
        mode="ordered",
        decision=d,
        metrics=metrics_or_na(current),
        benefits={
          "critical_served": current.C - previous.C,
          "normal_unserved_avoided": previous.U - current.U,
          "operational_carbon_avoided": previous.K - current.K,
        },
        status=status(current),
    )
    previous = current
```

`solve_closed_loop` 指的是现有 `solve_strategy_with_feedback()` 所代表的“调度—P/Q 验证—损耗/容量反馈”闭环，不是只跑一次 LP。候选的 `RestorationPlan` 与 `actions` 导出必须同时变化，避免 UI 文本与实际 topology mask 不一致。

## 5. 建议导出表

### 5.1 `decision_registry.csv`

一行一个可归因计划事件：

| 字段 | 含义 |
|---|---|
| `run_id`, `scenario_id`, `strategy`, `plan_hash`, `policy_hash` | 可复现身份与固定比较口径。 |
| `decision_id`, `decision_type`, `asset_id`, `action_label` | 例如 `tie:T37@h0`, `tie_close`, `37`, `闭合联络开关 T37`。 |
| `scheduled_hour`, `ordinal` | 原计划时刻和确定性顺序。 |
| `counterfactual_semantics` | `omit_tie` 或 `unrepaired_through_horizon`。 |
| `dependencies`, `notes` | 依赖/安全 tie 筛选、拓扑解释。 |

### 5.2 `decision_marginal_value.csv`

一行对应一个 `mode × decision_id`；baseline/empty-plan 作为特殊行保留：

| 字段 | 含义 |
|---|---|
| `run_id`, `mode`, `decision_id`, `ordinal`, `parent_set_hash` | 运行身份和所比较的 decision set。 |
| `candidate_status`, `solver_status`, `feedback_converged`, `feedback_iterations`, `physical_feasible` | 数值与物理门。 |
| `critical_served_kwh`, `normal_unserved_kwh`, `operational_carbon_kg` | 三个原始结果；永远保留。 |
| `grid_kg`, `diesel_kg`, `crew_kg` | 碳清单可审计分解。 |
| `delta_critical_served_kwh`, `delta_normal_unserved_avoided_kwh`, `delta_operational_carbon_avoided_kg` | 对应 LODO 或 OMA 的正向收益定义。 |
| `critical_eens_kwh`, `total_eens_kwh`, `served_total_kwh`, `critical_recovery_pct` | 防止仅看三个 headline 指标。 |
| `max_loading_pct`, `min_voltage_pu`, `max_residual_kw`, `infeasibility_reason` | 物理边界与失败原因。 |
| `policy_hash`, `factor_registry_hash`, `code_revision`, `random_order_seed` | 比较完整性。 |
| `attribution_statement` | 固定文本：`model_based_counterfactual_attribution_not_real_world_causal_effect`。 |

### 5.3 `decision_marginal_summary.csv`

便于答辩读取的紧凑表：

```text
strategy,decision_id,action_label,scheduled_hour,mode,
critical_served_benefit_kwh,normal_unserved_avoided_kwh,
operational_carbon_avoided_kg,physical_feasible,candidate_status,
rank_critical,rank_normal,rank_carbon,interaction_flag
```

“kgCO2 inventory”在可视化和表名中统一写为 `operational_carbon_kg` 或 `kgCO2`，并与当前 factor registry 的单位保持一致；不要同时混用 `kgCO2` 和 `kgCO2` 而没有因子定义。

## 6. 运行量与实际估算

已在当前工作区以 `PYTHONPATH=src` 做了只读基线试跑：

- `solve_strategy_with_feedback(build_ieee33(), get_scenario("暴雨内涝"), "碳韧协同恢复")`：约 **9.8 s**，5 次反馈迭代、收敛、24 h 物理可行；
- 完整 `run_pipeline("暴雨内涝")` 的三 strategy 合计约 **17.7 s**（传统/最小失供/碳韧三条路径分别完成反馈）。

这是本机一次观察值，不是性能承诺；CVXPY 版本、CPU、factor/scenario 和反馈次数都会改变它。

对于当前 6 个动作：

| 工作包 | 闭环候选数 | 以 9.8 s/候选的粗估 | 建议 |
|---|---:|---:|---|
| 基线 + LODO | `1 + 6 = 7` | 约 69 s | 默认 MVP。 |
| OMA（空计划 + 6 前缀） | 7 | 约 69 s | 作为恢复路径图。 |
| LODO + OMA（共享 full baseline） | 13 | 约 127 s | 单 scenario 约 2–4 min，含 CSV/I/O 余量。 |
| 前三决策 × 10 个随机顺序 | 约 30 前缀求解 | 约 5 min | 只在互动高或答辩前执行。 |

不建议首版直接做 `3 灾害 × 3 strategy × 30 Monte Carlo × 每动作 LODO`；它会迅速变成数百次闭环求解。十日 MVP 的合理路径是：一个冻结的暴雨基准场景完成全量 6-action LODO + OMA，再在每灾害各挑 1 个代表情景做排名稳定性复核。

## 7. 可视化设计

### 图 A：三结果决策价值散点（主图）

- x：`normal_unserved_avoided_kwh`；
- y：`operational_carbon_avoided_kg`；
- 气泡面积：`critical_served_benefit_kwh`；
- 颜色：`tie_close` / `repair_complete`；
- 标签：`T37@0`、`L6@7` 等；
- 失败候选用空心红叉并显示 `infeasible`，不将其画成零收益。

这张图直观呈现“普通保供、关键保供、碳账”三者是否同向，同时保留负值象限，避免把 trade-off 隐藏掉。

### 图 B：按恢复时间的 OMA 三联瀑布

三个并列 waterfall：关键已供电增量、普通失供避免量、运行碳避免量。横轴是 6 个计划事件；上方叠加 action hour。图下注明“该序列的模型路径边际，不是顺序无关因果贡献”。

### 图 C：动作—小时热图（辅助）

行是决策，列是 0–23 h；色阶是候选相对基线的 `served critical` 或 `unserved normal` 差。其作用是解释为什么一个 hour 23 修复动作可能对总量价值有限，但对最后时窗仍关键。

每张图均应带以下页脚：scenario id、strategy、policy hash、factor registry hash、code revision、`dt=1 h`、`model-based attribution`。

## 8. 验证与拒绝发布规则

归因产物只有同时通过以下检查才可进入主图；失败项进入 failure CSV，不得静默丢弃。

1. **基线复现**：`full-plan` 重跑的三个主指标与已冻结 baseline 的绝对差均不大于 `1e-3`（或由 solver 精度明确记录的容差）。
2. **掩码精确性**：每个 LODO 候选只少一个 registry action；其他 ties、repair completion times、资源、scenario 和因子 hash 完全一致。
3. **计划—文本一致性**：候选 `actions` CSV、`RestorationPlan` 和 topology state 在每个 hour 一致；禁止只改显示文本。
4. **物理闭环**：`feedback_converged=True`、所有 `validation.hourly.is_feasible=True`；保留 feedback iteration、最大残差、最小电压和最大 loading。
5. **政策一致性**：所有主归因行具有同一 `policy_hash`；发现 candidate-specific service re-anchor 或 normal-load allowance 重算则整批作废。
6. **碳对账**：每行验证 `total_operational_kg ≈ grid_kg + diesel_kg + crew_kg`；同 scenario 下 crew 差异若非零，必须解释是否改变了车辆边界。
7. **单位检查**：输出固定 `time_step_hours=1.0`；从 `_kw` 列构造能量时显式乘 `dt`。
8. **有序恒等式**：所有 OMA 前缀可行时，逐维验证 `sum(ordered marginal) ≈ full - empty`。
9. **非加性不是失败**：LODO 求和与 full-minus-empty 不相等时只标 `interaction_present`，不得强制校正。
10. **排名稳健性**：若补跑随机顺序，top-3 决策的 rank range 大于 3，或 LODO/OMA 正负号相反，标为 `order_sensitive`，答辩中只报告区间/情景依赖。
11. **声明检查**：所有 summary、图脚和导出 metadata 均包含模型归因而非现实因果证明的固定说明。

## 9. 十天优先级（建议从下一个工作日开始）

| 日 | 优先工作 | 可验收产物 |
|---|---|---|
| D1 | 冻结 `flood_v08` 参考 plan、scenario、resources、factor registry、现有策略和 baseline 指标；生成 decision registry。 | `decision_registry.csv` + policy/plan hash。 |
| D2 | 实现或原型化 plan masking；只跑 full plan 和 6 个 LODO 候选，不改既有三策略默认输出。 | 原始候选日志与 `decision_marginal_value.csv`。 |
| D3 | 接入完整 P/Q feedback、物理失败保留和 carbon reconciliation；完成基线重现测试。 | validation/failure CSV + 测试断言。 |
| D4 | 冻结 carbon-resilient 的 policy snapshot，处理候选内服务 re-anchor；主归因与 relaxed diagnostic 分表。 | `policy_snapshot.json` 与可解释 infeasible 行。 |
| D5 | 生成 OMA 前缀运行与 telescoping QA。 | `ordered` 行、恒等式检查、恢复路径数据。 |
| D6 | 做图 A/B/C，加入 scenario/hash/模型归因页脚。 | 三张可导出 SVG/PNG 和 dashboard table。 |
| D7 | 三个灾害各选一个代表情景复跑 LODO；比较 top-3 的符号与排名。 | `cross_scenario_rank_stability.csv`。 |
| D8 | 对冲突最大的三个动作跑 10 个固定 seed 顺序；标记 interaction/order sensitivity。 | rank interval 表、答辩解释句。 |
| D9 | 交叉审阅：电网组核物理门，优化组核 policy freeze，MRV 组核碳边界与措辞。 | 审阅 checklist、修订 manifest。 |
| D10 | 冻结输入、导出复现命令和一页方法卡；主张只引用通过所有门的图表。 | README 段落、manifest、演示材料。 |

## 10. 答辩可直接使用的表述

> 我们没有把单个修复/开关动作宣称为现实世界中的独立因果效应。系统在固定灾害情景、网络参数、资源、排放因子和求解策略下，移除一个计划事件或按原定时序逐步加入事件，并重新完成调度—潮流反馈闭环。报告的关键供电、普通失供和运行碳差异，因此是可复核的模型内反事实归因；它用于解释该计划在该模型中的脆弱点与协同关系，而不是替代现场对照、抢修记录或排放实测。
