# Wave 2：同服务 epsilon-constraint Pareto 扫描落地设计

> **范围**：设计说明；本轮只新增本文件，不修改应用代码。目标是在三个既有计划族（传统顺序恢复、最小失供恢复、碳韧协同恢复）上，对每个固定灾害场景做**医院/关键服务硬锁**后的碳—普通负荷失供 Pareto 扫描。调度仍复用 CVXPY 连续 LP，候选仍经过当前 P/Q 潮流反馈闭环；求解失败、不可行和物理校验失败都保留为可下载的结果，而非静默丢弃。

## 1. 已核对的现状与落地点

| 现有对象 | 已有能力 | Pareto 实现怎样复用 |
|---|---|---|
| `restoration.make_plan()` | 三个固定恢复计划；碳韧与最小失供使用相同修复序列/联络线，避免隐藏拓扑优势 | 每个 `strategy` 先生成一个固定 `RestorationPlan`，扫描只改变资源调度与显式服务/碳约束 |
| `dispatch.dispatch_resources_spatial()` | 节点×24h CVXPY LP；PV、柴油、BESS、并网、SOC、分岛能量平衡、无成网源孤岛、无功支撑、组件供电上限 | 提取共享的 LP 构建器；只替换 objective 和追加 epsilon constraints，不复制物理约束 |
| `pipeline._simulate_with_loss_feedback()` | `dispatch -> validate_dispatch -> P/Q 线损/无功损失/组件功率上限 -> dispatch`，最多 8 次迭代 | 每个候选使用同一反馈协议；扫描版严禁释放用户指定的普通负荷上限 |
| `powerflow.validate_dispatch()` | 后验支路热限、电压、功率平衡、无源孤岛检查 | 成为 Pareto 点资格判定的一部分；失败点写入 CSV/JSON |
| `carbon.calculate_carbon()` | 电网、柴油、抢修车辆排放分解 | 以 `total_operational_kg` 作为碳预算/目标，仍保留分量 |
| `experiments.py` | 行级失败记录、统计结果、失败情景 replay manifest | 沿用“每个尝试一行”的模式，扩展 `run_id / epsilon / cap / failure_phase` |
| `app.py` | 三策略对照、能流、潮流、MRV；`st.cache_data` | 新增按按钮触发的 Pareto 页签，绝不让首次打开页面自动跑 27 个物理闭环 |

当前 `dispatch.py` 已有 `max_critical_unserved_kwh` 和 `max_normal_unserved_kwh`，但空间调度层只区分“全部关键/全部普通”。医院服务需要保留节点类别，才能避免“医院少供、另一个关键节点多供”在总关键 EENS 上被掩盖。

另外，现有 `_simulate_with_loss_feedback()` 在普通负荷预算导致求解异常时会把 `effective_normal_limit` 置空后重试。这个容错对当前演示有用，但对 epsilon 扫描会把一个本应记录为不可行的点伪装成可行点；扫描路径必须显式关闭该回退。

## 2. 服务合同：先锁医院与关键服务，再扫普通负荷/碳

### 2.1 节点服务分类

在 `build_node_demand_frame()` 为每一行增加稳定字段，而不是在优化器里用中文名称字符串判断：

```python
service_class: Literal["hospital", "emergency", "critical", "normal"]
is_hospital: bool
is_essential: bool  # hospital + emergency + other critical
```

初始映射从现有 `GridModel.nodes` 的 `node_type` 和 `critical_level` 派生：医院/应急节点归 `hospital`，通信/应急归 `emergency`，其余 `critical_level >= 2` 归 `critical`，其余归 `normal`。case33 当前医院/应急节点位于 `node_id=2,17`；该编号只是当前数据事实，代码以服务标签为准。

### 2.2 分层词典序锚点

对每个 **(scenario, strategy)** 的固定计划，先在与候选相同的 P/Q 反馈条件下计算服务锚点：

1. `U_h* = min hospital_unserved_kwh`；
2. 加 `U_h <= U_h* + tau_h`，求 `U_e* = min other_essential_unserved_kwh`；
3. 加前两条锁，求 `U_n* = min normal_unserved_kwh`；
4. 记录锚点总供电 `H*`、各类别负荷、潮流反馈快照及 solve status。

默认数值容差：

```text
tau_h = max(1e-4 kWh, 1e-6 * hospital_demand_kwh)
tau_e = max(1e-4 kWh, 1e-6 * essential_demand_kwh)
tau_feas = 1e-4 kWh
```

候选的硬约束始终为：

```text
U_h <= U_h* + tau_h
U_e <= U_e* + tau_e
```

这不是“医院必须 100% 供电”的虚假承诺：如果医院因物理孤岛、资源不足或网络上限而不可完全供电，`U_h*` 会如实大于零；后续所有点都被锁在这个物理最优服务水平附近。对当前能完全供电的情景，该约束自然退化为医院 EENS 近零的硬锁。

普通负荷有两种对称扫描方式：

**A. 普通 EENS epsilon 扫描（默认展示方式）**

\[
\min C\quad
\text{s.t. } U_h\le U_h^*+\tau_h,\;U_e\le U_e^*+\tau_e,\;
U_n\le U_n^*+\epsilon_n.
\]

其中 `epsilon_n = rho_normal * normal_demand_kwh`，首版取
`rho_normal = (0, 0.01, 0.04, 0.08)`；需要更细曲线时改为九点 `(0, .005, .01, .02, .04, .06, .08, .10, .12)`。

**B. 碳预算 epsilon 扫描（镜像方式）**

先解服务锁下的 `C_min`，再解 `U_n` 最小端得到 `C_at_normal_min`，然后：

\[
\min U_n\quad
\text{s.t. hard service locks},\quad C\le \bar C_j,
\]

\[
\bar C_j=C_{min}+\lambda_j(C_{at\_normal\_min}-C_{min}),\quad
\lambda_j\in\{0,.125,.25,.375,.5,.625,.75,.875,1\}.
\]

扫描 A 直接回答“额外允许多少普通 EENS 可换来多少 kgCO2”；扫描 B 直接回答“碳上限压到此处时，最低普通 EENS 是多少”。两种模式同场景、同计划、同硬服务合同，端点应在容差内相互复现。

### 2.3 服务等价与对外叙述规则

- `rho_normal=0`：医院、其他关键、普通负荷均对齐各自锚点，可称为**严格服务等价的低碳点**。
- `rho_normal>0`：只可称为**受控普通负荷让步的服务—碳权衡点**；展示绝对碳时必须同时展示普通 EENS、已供电量、服务层。
- 任一点若 `served_kwh < H* - epsilon_n - tau_h - tau_e` 或硬锁超限，标记 `contract_pass=False`，保留但不进入前沿/推荐。
- 不将电池放电、弃光减少或少供电直接称为减排；碳指标仍为当前 `calculate_carbon()` 的电网+柴油+抢修车辆运行清单。

## 3. 建议 API 与数据结构

### 3.1 调度层：最小重构、最大复用

建议把 `dispatch_resources_spatial()` 的变量与物理约束提取到私有 `_build_spatial_dispatch_problem(...)`，返回变量、constraints、数据矩阵及可重建结果的 metadata。公开入口保留兼容，新增参数化入口：

```python
@dataclass(frozen=True)
class ServiceContract:
    hospital_unserved_cap_kwh: float | None = None
    other_essential_unserved_cap_kwh: float | None = None
    normal_unserved_cap_kwh: float | None = None
    carbon_cap_kg: float | None = None
    tolerance_kwh: float = 1e-4

@dataclass(frozen=True)
class DispatchObjective:
    kind: Literal[
        "min_hospital_eens", "min_essential_eens", "min_normal_eens",
        "min_carbon"
    ]
    secondary_weight: float = 1e-7

def dispatch_resources_spatial_constrained(
    demand: pd.DataFrame,
    node_demand: pd.DataFrame,
    grid_capacity_kw: np.ndarray | pd.Series,
    *,
    config: ResourceConfig = ResourceConfig(),
    contract: ServiceContract = ServiceContract(),
    objective: DispatchObjective = DispatchObjective("min_normal_eens"),
    node_loss_kw: pd.Series | None = None,
    node_q_loss_kvar: pd.Series | None = None,
    component_served_caps_kw: dict[tuple[int, str], float] | None = None,
    solver: str = "auto",
) -> DispatchResult:
    ...
```

约束的 `carbon_cap_kg` 必须用与 `calculate_carbon()` 完全相同的运行变量表达式：

```python
carbon_expr = sum(grid * grid_carbon_kg_per_kwh) + 0.72 * sum(diesel) + crew_kg
```

其中 `crew_kg` 是固定的计划/情景常数；没有它会造成 LP 目标和导出的 MRV 碳值口径不一致。医院、其他关键、普通 EENS 都从 `node_demand.service_class` 形成 mask 后按节点/时段求和。当前步长为 1h；实现中应显式乘 `dt_hours`，为后续 15 分钟时段留出口。

`DispatchWeights` 和既有 `dispatch_resources_spatial()` 保持不变，供当前三策略回归；Pareto 不以旧的加权和冒充 epsilon 目标。`min_carbon` 可附加极小、固定且记录在 manifest 中的二级项（例如 BESS 吞吐）以消除多解，但该项不得改变首要目标排序。

### 3.2 Pareto 服务 API

```python
@dataclass(frozen=True)
class ParetoScanSpec:
    strategies: tuple[str, ...] = STRATEGIES
    scan_axis: Literal["normal_eens", "carbon_budget"] = "normal_eens"
    normal_allowance_fractions: tuple[float, ...] = (0.0, 0.01, 0.04, 0.08)
    carbon_lambdas: tuple[float, ...] = (0.0, .125, .25, .375, .5, .625, .75, .875, 1.0)
    max_feedback_iterations: int = 8
    feedback_tolerance_kw: float = 0.10
    solver: str = "auto"
    output_dir: Path | None = None
    keep_optimal_inaccurate: bool = True

@dataclass(frozen=True)
class ServiceAnchor:
    scenario: str
    strategy: str
    hospital_eens_star_kwh: float
    essential_eens_star_kwh: float
    normal_eens_star_kwh: float
    served_star_kwh: float
    feedback: PhysicalFeedback
    status: str

@dataclass(frozen=True)
class ParetoPoint:
    run_id: str
    scenario: str
    strategy: str
    scan_axis: str
    epsilon_normal_kwh: float | None
    normal_allowance_fraction: float | None
    carbon_cap_kg: float | None
    total_carbon_kg: float | None
    hospital_eens_kwh: float | None
    essential_eens_kwh: float | None
    normal_eens_kwh: float | None
    served_kwh: float | None
    solver_status: str
    contract_pass: bool
    physical_pass: bool
    frontier_eligible: bool
    nondominated: bool | None
    solve_seconds: float
    feedback_iterations: int | None
    failure_phase: str | None
    failure_reason: str | None
    dispatch: DispatchResult | None = None  # 内存对象；CSV 不序列化

@dataclass(frozen=True)
class ParetoScanResult:
    spec: ParetoScanSpec
    anchors: pd.DataFrame
    points: pd.DataFrame
    frontier: pd.DataFrame
    failures: pd.DataFrame
    artifacts: dict[str, Path]

def scan_pareto(
    scenario: str | DisasterScenario,
    spec: ParetoScanSpec = ParetoScanSpec(),
) -> ParetoScanResult:
    ...
```

建议模块位置为 `src/gridrescue/pareto.py`；`pipeline.py` 只暴露共享的“固定计划+P/Q 反馈”求解包装，不让 `app.py` 拼 CVXPY 约束。

### 3.3 P/Q 反馈包装

新增一个严格模式，而非改变现有默认行为：

```python
def solve_candidate_with_feedback(
    model: GridModel,
    scenario: DisasterScenario,
    plan: RestorationPlan,
    objective: DispatchObjective,
    contract: ServiceContract,
    *,
    initial_feedback: PhysicalFeedback | None = None,
    strict_contract: bool = True,
) -> CandidateSolve:
    ...
```

循环仍是：`constrained spatial LP -> validate_dispatch -> 更新 node_loss_kw/node_q_loss_kvar/component_served_caps_kw -> 重解`。

严格模式的三条规则：

1. `normal_unserved_cap`、carbon cap、医院/关键 cap 任一导致不可行，直接写 `solver_infeasible`；不移除任何 cap 后重试。
2. P/Q 未收敛、任一小时 `is_feasible=False`、约束重算超限，写为相应失败或 `physical_pass=False`，不加入非支配集合。
3. 可以将锚点的 `PhysicalFeedback` 作为同计划候选的 warm start，减少迭代；每个候选仍独立后验验证，避免把另一个负荷形状的线损/电压上限当成事实。

这保留了当前物理闭环，又保证 epsilon 的语义没有被回退逻辑改变。

## 4. 运行流程

```text
for scenario:
  model = build_ieee33()
  for strategy in selected strategies:
    plan = make_plan(model, scenario, strategy)
    anchor = solve_lexicographic_anchor(plan, P/Q feedback)
    emit anchor row even if it fails

    if scan_axis == "normal_eens":
      for rho in normal_allowance_fractions:
        cap = anchor.normal_eens_star_kwh + rho * normal_demand_kwh
        solve min carbon under hard service locks + normal cap
    else:
      solve C_min and U_n_min endpoints under hard service locks
      for lambda in carbon_lambdas:
        solve min normal EENS under carbon cap

    recompute all KPIs from DispatchResult + CarbonBreakdown + FlowValidation
    emit exactly one point row per attempted endpoint/grid point

  run contract audit -> non-dominated filter -> artifacts/figures/UI payload
```

端点应被缓存到本次 scan 的内存字典 `(scenario_hash, strategy, objective, contract, feedback_hash)`；不要跨不同输入 hash 复用。初版不需要 CVXPY `Parameter`/warm start 才能正确，但提取共享问题后可把 cap 设为 `cp.Parameter(nonneg=True)`，减少连续九点扫描的 canonicalization 成本。

## 5. 非支配过滤与失败保留

### 5.1 资格过滤先于排名

候选只有同时满足下列条件才是 `frontier_eligible=True`：

```text
solver_status in {optimal, optimal_inaccurate}
AND contract_pass
AND physical_pass
AND finite(total_carbon, hospital_eens, essential_eens, normal_eens)
```

`optimal_inaccurate` 可以暂时显示，但必须显著标记并进入复跑队列；若复跑后仍不准确，不能与普通 `optimal` 混为一个推荐点。

### 5.2 两个前沿视图

1. **服务—碳 trade-off frontier**：固定 `scenario`，在医院/关键硬锁已通过的全部候选上，对 `(total_carbon_kg, normal_eens_kwh)` 做二维非支配。该视图回答普通服务与碳之间的交换。
2. **严格服务等价 frontier**：固定 `scenario + normal_allowance_fraction`（或固定 `carbon_cap` 的同一服务预算层），在合格点中按 `(total_carbon_kg, normal_eens_kwh)` 过滤并额外展示 `served_kwh`。`rho=0` 层允许写“同服务低碳”；其他层只写“该服务层下”。

跨计划族允许比较，因为医院/关键合同在每个计划自身物理可达锚点上定义；图表和 CSV 必须始终带 `strategy`，避免把计划差异误解释成调度差异。

### 5.3 容差稳定的实现规则

```python
def dominates(a: pd.Series, b: pd.Series, *, atol: float = 1e-4, rtol: float = 1e-7) -> bool:
    objectives = ("total_carbon_kg", "normal_eens_kwh")
    def tol(x: float, y: float) -> float:
        return atol + rtol * max(1.0, abs(x), abs(y))
    no_worse = all(float(a[k]) <= float(b[k]) + tol(float(a[k]), float(b[k])) for k in objectives)
    strictly_better = any(float(a[k]) < float(b[k]) - tol(float(a[k]), float(b[k])) for k in objectives)
    return no_worse and strictly_better
```

先以容差 bucket 去重；同一 bucket 选 `physical_pass=True`、`solver_status=optimal`、更少反馈迭代、再按稳定 `run_id` 的点。失败点永远不参与支配判定，仍保留原始位置、cap、异常类型、反馈次数和输入 hash。

### 5.4 结果文件

| 文件 | 作用与关键字段 |
|---|---|
| `pareto_anchors.csv` | `scenario,strategy,U_h*,U_e*,U_n*,served*,solver_status,feedback_iterations,feedback_hash` |
| `pareto_runs.csv` | 每次端点/网格尝试一行；`run_id,scan_axis,rho,epsilon,carbon_cap,objectives,status,solve_seconds,contract_pass,physical_pass,failure_*` |
| `pareto_frontier.csv` | 合格点的 `frontier_scope,nondominated,dominated_by_count,duplicate_of_run_id` |
| `pareto_failures.json` | 完整失败记录、异常类别/消息、可复跑 spec、情景定义、输入与反馈 hash |
| `pareto_manifest.json` | schema、git/input hash、solver、已安装 solver、时步、容差、参数、时间戳、文件 hash |
| `pareto_dispatch/<run_id>.csv`、`pareto_powerflow/<run_id>.csv` | 仅对成功点和被 UI 选中的失败点保留逐时调度/潮流证据 |

`pareto_runs.csv` 是审计主表：即使某策略在某个 epsilon 不可行，行数也应等于预期尝试数；绝不用失败点的零值或 NA 参与均值、前沿或“最低碳”排名。

## 6. UI 交互设计（Streamlit）

新增第六个页签 **“同服务 Pareto”**，默认不运行全扫描。

### 控件

- 场景：复用当前 `scenario_name`。
- 计划族：默认三项全选，可缩为单策略快速检查。
- 扫描轴：`普通负荷 EENS 上限 → 最小碳`（默认）/ `碳预算 → 最小普通 EENS`。
- 普通让步层：快捷 `严格 / 1% / 4% / 8%`；高级模式显示九点列表。
- 运行按钮：`运行物理 Pareto 扫描`；旁边展示当前实测估时范围。
- 资格开关：默认隐藏不合格推荐点；勾选“显示失败/物理未通过点”后以红色叉号/灰色空心点显示并可查看原因。

### 图表和钻取

1. Scatter：x=`total_carbon_kg`，y=`normal_eens_kwh`，颜色=策略，符号=服务层，边框=是否非支配；hover 给出医院/关键 EENS、普通 EENS、已供 kWh、碳分解、solver/PQ 状态、耗时。
2. 服务层小 multiples：每个 `rho` 一张碳—普通 EENS 图；`rho=0` 标明严格服务等价。
3. 选点表：点击或选择 `run_id` 后显示该点的逐时能流、医院/关键 EENS 曲线、潮流校验表以及与同策略锚点的差分。
4. 失败面板：`failure_phase`、`failure_reason`、cap、迭代次数、下载 replay manifest。
5. 下载：`pareto_runs.csv`、frontier、manifest 和所选点的 dispatch/powerflow CSV。

`@st.cache_data` 的 key 必须包含 `scenario_name`、完整不可变 `ParetoScanSpec` 和模型输入 hash；首次页面只计算当前 `run_pipeline()` 的三策略基线，点击按钮才调用 `scan_pareto()`。长运行时用 `st.status`/进度条显示 `strategy × grid point`，避免用户误以为页面卡死。

## 7. 测试计划

| 测试 | 断言 |
|---|---|
| 服务标签映射 | 医院、应急、普通节点在 24×33 `node_demand` 中类别稳定；普通合计与原 `normal_load_kw` 一致 |
| 锚点词典序 | 对每个策略，第二阶段不劣于医院锚点，第三阶段不劣于医院/其他关键锚点；结果满足 P/Q 后验 |
| 严格服务层 | `rho=0` 的每个合格点医院/关键/普通 EENS 均不超过锚点+容差 |
| EENS epsilon 约束 | 每个合格点 `normal_eens <= U_n* + epsilon + tol`；`epsilon=0` 和普通最小端点一致 |
| 碳预算约束 | 成功点 `total_carbon <= cap + tol`；`lambda=0` 接近碳端点，`lambda=1` 接近普通 EENS 端点 |
| 对称端点 | 两种扫描方式的端点在目标容差内匹配 |
| 非支配函数 | 人工数据验证支配、近重复去重、NaN/失败排除、固定排序下结果确定 |
| 失败保留 | monkeypatch solver/调度抛异常时，预期尝试行完整存在、`failure_phase` 正确、frontier 无该点、manifest 可读取 |
| 禁止预算回退 | 构造严格普通 cap 导致 infeasible；结果必须是 `solver_infeasible`，不得被取消 cap 后变为成功 |
| P/Q 回归 | 每个被标记 `physical_pass` 的点 `validation.hourly.is_feasible.all()`，线损回写与潮流估算在现有容差内 |
| 基线回归 | 既有 `run_pipeline()`、三个策略指标和当前测试全部保持通过 |
| UI 纯函数 | 将 Pareto figure/table payload 提成纯函数，检查失败点与合格点的 trace/下载数据存在；不要求端到端浏览器测试作为 MVP 阻塞项 |

建议 CI 分层：PR 跑单场景、单策略、`rho=(0,.04)` 的物理扫描；夜间跑三策略×九点以及命名三灾害。Monte Carlo/Pareto 100 场景留给离线实验，不塞进 Streamlit 交互路径。

## 8. 预计实现与运行耗时

### 实现工作量

| 工作 | 预计 |
|---|---:|
| 抽取空间 LP 构建器、服务类别和显式合同/目标 | 0.75–1.0 天 |
| 词典序锚点、严格 P/Q 反馈包装、两类扫描 | 1.0–1.5 天 |
| 前沿过滤、artifact/manifest、失败 replay | 0.5–0.75 天 |
| 单元/集成测试和回归修正 | 0.75–1.0 天 |
| Streamlit 页签、图表、下载与体验收 | 0.5–0.75 天 |
| **合计** | **约 3.5–5 个工程日** |

### 当前机器实测基线与扫描预算

在本工作区、`CLARABEL`、暴雨内涝、开启当前 P/Q 反馈的实测结果为：

| 现有路径 | 反馈迭代 | 用时 |
|---|---:|---:|
| 传统顺序恢复 | 2 | 2.09 s |
| 最小失供恢复 | 4 | 5.61 s |
| 碳韧协同恢复 | 5 | 8.24 s |
| 当前 `run_pipeline("暴雨内涝")` 全三策略 | — | 12.91 s |

据此给 UI 的保守预算：

- 单策略、4 个普通 EENS 层：约 **30–90 秒**（含锚点和物理反馈）。
- 三策略、4 层：约 **2–5 分钟**。
- 三策略、9 点碳预算：约 **3–7 分钟**；首次版本以串行保障可复现与日志顺序，后续再评估并行。
- 三个命名灾害全量：约 **10–20 分钟**。

实际耗时须写入每个 `ParetoPoint.solve_seconds`，并在 UI 用已完成点的中位数动态更新 ETA。若候选频繁触发 P/Q 组件上限并需要多轮反馈，时间上界会增加；这应作为诊断信息显示，而不是降低迭代次数后假称已经物理收敛。

## 9. 推荐交付顺序

1. 先完成 `rho=(0, .04)`、单场景、三计划族的后端闭环和 artifact 审计；验证严格服务层没有“少供电刷低碳”。
2. 加四层普通 EENS 扫描与二维非支配图，再实现九点碳预算镜像扫描并对端点做对称性测试。
3. 接 UI 的显式运行按钮、失败显示和下载；默认展示已有三策略基线。
4. 最后扩展到三命名场景和共同随机蒙特卡洛；在聚合前先按场景执行合同审计和失败率汇总。

这样第一版的核心主张会是可验证的：**在相同医院/关键服务水平下，展示每个计划族的普通负荷服务—碳排边界；所有物理或求解失败也作为结果的一部分保留。**
