# Wave 7：Carbon-SOC 最小可实现代码设计（审计结论）

> 范围：只审计；本文件不修改 `dispatch.py`、`scenarios.py`、`carbon.py`、CareTask 或 Pareto 代码。
>
> 结论：Carbon-SOC 应实现为**可选的空间调度附加策略层**，而不是替换当前三策略、重写碳核算、或改动 CareTask/Pareto 的默认入口。最小闭环为：同一服务合同下生成 A/B/C 三个候选，B 加保护底仓 `R`，C 在 B 的约束上增加低权重目标 SOC `T`；所有候选仍走现有 P/Q 反馈与 `validate_dispatch`。

## 1. 已核对的当前边界

### 1.1 已有能力，可直接复用

| 位置 | 已有事实 | Carbon-SOC 接法 |
|---|---|---|
| `dispatch.py:273-293` | 节点级 `charge`、`discharge`、`soc[t,node]`，已有 SOC 状态方程、最小/最大 SOC 和功率约束 | 在既有 `soc` 上附加逐时逐储能节点的保护下界；绝不另建一套电池状态。 |
| `dispatch.py:296-339` | 按 `(hour, component_key)` 做有功平衡；root 才有 `grid`，无 GFM 的孤岛强制去供电 | `R/F/T` 必须使用每小时的 `component_key` 聚合/分配；不跨 component 汇总。 |
| `dispatch.py:346-410` | 服务合同包含医院、其他关键、普通负荷、碳上限与 CareTask 的硬最小功率窗 | A/B/C 均传入同一个 `ServiceContract` 和 `task_requirements`，以此作为同服务门。 |
| `dispatch.py:428-459` | `min_hospital_eens` 等词典序入口，以及 `min_carbon` 目标 | A/B/C 的最终候选都可用 `DispatchObjective("min_carbon")`，服务由合同先锁死；C 仅加极小的目标偏差项。 |
| `scenarios.py:68-91` | 固定 24 个一小时点，已有合成 `grid_carbon_kg_per_kwh` | MVP 固定 `dt=1.0h`，将该列同时标记为 decision-factor proxy，不把它宣称为真实边际因子。 |
| `carbon.py:39-49` | 运行碳仅计网购、柴油、抢修车辆；BESS 充放不单列排放 | 保持总账原样。SOC 是时移解释层，严禁对电池放电再加“零碳”或避排进总排放。 |
| `pipeline.py:69-138` | 每次 dispatch 后均跑损耗/无功/容量反馈，再验潮流 | Carbon-SOC 比较器必须复用 `solve_strategy_with_feedback` 或同等闭环；首轮 envelope 使用当轮 component/cap 输入，反馈迭代后重算。 |

### 1.2 现有约束决定的实现红线

1. `battery_soc_kwh` 在 aggregate 表中是所有节点的和；Carbon-SOC 真实判断必须依赖 `node_frame` 的单节点 SOC，不能从 aggregate 倒推分岛底仓。
2. `node_frame` 的 SOC 行是 **该小时动作后的 `soc[t+1]`**（`dispatch.py:497`）。新导出必须同时给出 `soc_start_kwh=soc[t]` 和 `soc_end_kwh=soc[t+1]`，避免拿错边界。
3. `component_key` 随抢修/联络开关变化。底仓在每小时按当前拓扑计算；后续小时并网后才允许同 component 的资源共同计入，分裂时不得“带着总 SOC”越岛。
4. 当前 `calculate_carbon()` 隐含 `dt=1h`（对 kW 列直接求和）。本轮不引入 0.5h 通用步长；否则碳账和 EENS 需一起改为显式乘 `dt`。
5. 当前 SOC 变量含不具备 storage 的节点（其 `Emax=0`）。envelope 只生成 `storage_energy_kwh > 0` 的节点；其余位置填零并不增加约束。
6. 现有 `min_carbon` 已带极小失供/吞吐次级项。C 的 target 项须只在显式启用时加入，且量级明显低于服务合同和运行碳，否则会把“追 T”变成伪硬约束。

## 2. 推荐的最小代码形状

### 2.1 新文件，隔离新增概念

新增 `src/gridrescue/carbon_soc.py`，不把 Carbon-SOC 数学塞进 `carbon.py`。建议只放四类纯数据/纯计算对象：

```python
@dataclass(frozen=True)
class CarbonSocPolicy:
    policy_id: str = "CSWC-V1"
    time_step_hours: float = 1.0
    reserve_horizon_h: int = 3
    carbon_horizon_h: int = 6
    high_factor_quantile: float = 0.70
    shift_margin_kg_per_kwh: float = 0.02
    target_shortfall_weight: float = 1e-3
    throughput_weight: float = 1e-6
    factor_quality: str = "synthetic_d"
    allow_grid_precharge: bool = True

@dataclass(frozen=True)
class CarbonSocEnvelope:
    # shape=(n_hours, n_nodes), each row constrains soc[t+1]
    reserve_end_kwh: np.ndarray
    target_end_kwh: np.ndarray
    replacement_factor: np.ndarray
    shift_gain: np.ndarray
    window_flag: np.ndarray
    reserve_feasible: np.ndarray
    critical_deficit_forecast_kwh: np.ndarray
    node_ids: tuple[int, ...]
    policy: CarbonSocPolicy

@dataclass(frozen=True)
class CarbonSocMode:
    # "off" = A, "reserve" = B, "window" = C
    name: str
    apply_reserve: bool
    apply_target: bool

@dataclass(frozen=True)
class CarbonSocComparison:
    summary: pd.DataFrame
    hourly: pd.DataFrame
    policy_snapshot: dict[str, object]
```

`carbon.py` 保持为**核算账本**；`carbon_soc.py` 是**调度决策信号和解释账本**。两者只共享因子数值，不共享或重复总量计算。

### 2.2 `dispatch_resources_spatial` 的唯一必要扩展

建议新增两个关键字参数，默认 `None`，确保所有旧调用字节级行为等价：

```python
carbon_soc: CarbonSocEnvelope | None = None,
carbon_soc_mode: CarbonSocMode | None = None,
```

在 `dispatch.py` 现有 SOC 约束之后插入：

```python
if carbon_soc_mode and carbon_soc_mode.apply_reserve:
    constraints.append(soc[1:, :] >= carbon_soc.reserve_end_kwh - 1e-4)

if carbon_soc_mode and carbon_soc_mode.apply_target:
    target_shortfall = cp.Variable((n_t, n_n), nonneg=True)
    constraints.append(target_shortfall >= carbon_soc.target_end_kwh - soc[1:, :])
```

最终 objective 只在 `apply_target=True` 时增加：

```python
+ policy.target_shortfall_weight * cp.sum(target_shortfall)
+ policy.throughput_weight * cp.sum(charge + discharge)
```

实现检查：

- envelope 的 `node_ids` 必须精确等于空间 dispatch 的 sorted `nodes`；shape 必须是 `(n_t, n_n)`，否则 `ValueError`。
- `reserve_end_kwh >= min_soc * storage_energy_bus`、`target_end_kwh >= reserve_end_kwh`、`target_end_kwh <= storage_energy_bus` 应在 envelope builder 固化。
- **A (`off`) 不创建 `target_shortfall`，不增加一条约束，也不改变 objective。** 这是回归隔离的核心。
- `R` 是硬约束；`T` 只产生缺口罚项。不要把 `soc >= T` 写成硬约束，也不要为凑 T 临时打破服务/潮流门。

### 2.3 保护底仓 `R` 的最小可审计算法

对每个小时、当前 component、储能节点集合构建。这是预测性保护下界，不是碳信用账。

```text
critical_need[k,c] = sum(node critical_load_kw in c)
firm_grid[k,c]    = grid_capacity_kw[k] only if c is root
firm_diesel[k,c]  = sum(diesel_capacity_kw in c)
firm_pv[k,c]      = sum(pv_available_kw in c), only if root or diesel exists
Dcrit[k,c]        = max(0, critical_need - firm_grid - firm_diesel - firm_pv)

reserve_required = Emin_sum + sum(Dcrit[k,c] for k in [t, t+Hr)) / eta
Rcomp[t,c]        = min(Emax_sum, reserve_required)
reserve_feasible  = reserve_required <= Emax_sum + eps
```

最小实现的保守选择：PV 只在 root 或本 component 有柴油 GFM 时计为 `firm_pv`；不把同一块待保护 BESS 的放电当作非 BESS firm supply。反馈产生的 `component_served_caps_kw` 可在 `critical_need` 上额外做上界或作为 envelope 输入版本字段，但不可绕过服务合同。

分配给同 component 中各个 BESS：

```text
share_i = (Emax_i - Emin_i) / sum_j(Emax_j - Emin_j)
R[t,i]  = Emin_i + (Rcomp[t,c] - Emin_sum) * share_i
```

零可用容量 component 直接填 `Emin`。当 `reserve_feasible=False`，仍把 `R` 截到 `Emax` 以保证求解器可解，同时导出红色失败标记；比较器不得把它标记为“服务/底仓通过”。

### 2.4 碳目标 `T` 的最小可审计算法

不需要先做复杂 MISOCP。MVP 以当前因子、容量和未来替代机会生成软目标：

```text
replace_factor[k,c] = max(
    EF_grid[k] if c is root and grid capacity is positive else 0,
    EF_diesel if diesel capacity in c is positive else 0,
)
replaceable_kw[k,c] = min(
    sum(Pdis_max of stores in c),
    max(0, firm_grid[k,c] + firm_diesel[k,c]),
)
shift_gain[t,k,c] = eta * eta * replace_factor[k,c] - EF_grid[t]
```

在 `[t, t+Hc)` 选 `replaceable_kw>eps` 的点，取 replacement factor 的 70% 分位数为门槛；只累计满足门槛、且至少存在一个正的 `shift_gain > margin` 的未来槽：

```text
Eopp = sum(min(replaceable_kw, Pdis_sum) / eta for eligible slots)
Tcomp = clip(Rcomp + Eopp, Rcomp, Emax_sum)
```

同样按可用容量比例分配到节点。若因子恒定/反转、没有可替代网电或柴油、因子质量不是可用状态，则 `T=R`，C 退化为 B，而不是制造“预充”动作。

## 3. A/B/C：同服务、同动作、同物理闭环

不要将 A/B/C 加进全局 `STRATEGIES`。`tests/test_core.py` 和 Monte Carlo 断言当前策略集合恰为三个固定中文名；扩容会破坏既有结果与 UI 对照语义。

新建独立入口，例如 `run_carbon_soc_comparison(...)`：

| 候选 | 传入空间调度的 mode | 服务/物理条件 |
|---|---|---|
| A `existing_carbon_resilient` | `off` | 固定 `make_plan(..., "碳韧协同恢复")` 的恢复动作；同一个 ServiceContract；同一 feedback seed。 |
| B `reserve_only` | `reserve` | 与 A 完全相同的合同、因子、资源、P/Q 迭代参数；新增 `soc >= R`。 |
| C `carbon_soc_window` | `window` | 与 B 相同，另加 `T` 的软缺口项及理由码。 |

推荐执行序列：

1. 先用现有 Pareto/CareTask 方式得到本次对照的服务合同：医院、其他关键、普通 EENS cap、CareTask requirements、可选 carbon cap；合同连同 policy 做 snapshot/hash。
2. 固定 `strategy="碳韧协同恢复"` 的 `RestorationPlan`，保证修复顺序和联络开关动作相同。
3. A 用 `DispatchObjective("min_carbon")` + 合同求解并完成现有物理反馈。
4. B/C 在每次 feedback iteration 开始时，基于该轮的 node demand、component key、grid factor 和 component caps 重建 envelope，再进空间 dispatch。
5. 对每个候选调用已有 `evaluate_care_tasks()` 与 `validate_dispatch()`；只有 `care_task_complete`、各 EENS cap、反馈收敛、`24/24 is_feasible` 都通过时，才在 summary 中写 `comparison_eligible=True`。
6. 仅在 `A/B/C` 都 eligible 时展示 `C_minus_A_operational_kg`；任一失败则差异填 `NA` 并保留 failure reason。

这比复用 `run_pipeline()` 的三个“策略权重”更严谨：当前“碳韧协同恢复”在无合同路径会放宽普通负荷（最多附加 8% EENS，`restoration.py:261-294`），不是 Carbon-SOC A/B/C 的同服务基线。

## 4. 数据输出与理由码：只扩展，不污染旧 schema

`DispatchResult` 继续返回现有 `frame` 和 `node_frame`。Carbon-SOC 比较器单独产生：

- `carbon_soc_policy.json`：policy、因子质量、`dt=1.0`、factor snapshot hash、service contract hash、scenario 与 plan hash；
- `carbon_soc_hourly_strategy.csv`：每行 `(run_id, variant, hour, node_id)`；
- `carbon_soc_comparison.csv`：A/B/C 的 EENS、CareTask、physical、carbon、reserve 状态、可比性；
- `carbon_soc_manifest.json`：输入/版本/hashes/eligible 状态。

建议小时表至少有：

```text
run_id,variant,hour,node_id,component_key,is_root_component,
soc_start_kwh,soc_end_kwh,reserve_kwh,flexible_soc_kwh,target_soc_kwh,
charge_kw,discharge_kw,critical_deficit_forecast_kwh,
grid_decision_factor_kgco2e_per_kwh,replacement_factor_kgco2e_per_kwh,
shift_gain_kgco2e_per_kwh,window_flag,reserve_feasible,
action,reason_code,factor_quality,component_isolation_flag
```

动作判定以求解结果为准：`RESERVE_LOCKED`、`LOW_FACTOR_PRECHARGE`、`HIGH_FACTOR_GRID_DISPLACEMENT`、`HIGH_FACTOR_DIESEL_DISPLACEMENT`、`NO_REPLACEABLE_LOAD`、`FACTOR_FLAT_OR_UNCERTAIN`、`NEUTRAL`。理由码是**解释输出**，不参与优化约束。

## 5. 对 CareTask/Pareto 的零破坏接法

### 不要改的内容

- 不修改 `default_care_tasks()`、`care_task_requirements()`、`evaluate_care_tasks()`。
- 不修改 `ParetoScanSpec` 的默认字段、`ParetoScanResult`、manifest `schema_version=2`、默认 artifacts 集合。
- 不向 `STRATEGIES` 加 A/B/C，也不改变 `strategy_weights()` 的既有三条路径。
- 不修改 `CarbonBreakdown` 的字段/总量定义。

### 新路径必须复用的内容

```python
contract = ServiceContract(
    hospital_unserved_cap_kwh=...,
    other_essential_unserved_cap_kwh=...,
    normal_unserved_cap_kwh=...,
    carbon_cap_kg=...,                 # 若对照使用则三者相同
    crew_emissions_kg=...,             # 与 calculate_carbon 同边界
    task_requirements=care_task_requirements(default_care_tasks()),
)
```

随后对 A/B/C 各自：

```python
evaluation = evaluate_care_tasks(tasks, result, validation)
physical_pass = feedback.converged and validation.hourly["is_feasible"].all()
care_pass = evaluation["task_complete"].all()
```

这样 CareTask 的重叠功率需求、电压门和 deadline/duration 仍由现有测试覆盖；Carbon-SOC 没有机会把“aggregate 看起来够”误当作医院任务完成。

## 6. 最小测试清单（新增，不改旧断言）

1. **off 回归**：不传 `carbon_soc` 时，`dispatch_resources_spatial` 的 aggregate/node 数值与当前基准在容差内一致；这是最重要的保护测试。
2. **R 下界**：所有 storage node、所有 hour 断言 `soc_end + eps >= reserve_end`。
3. **reserve infeasible**：构造 critical forecast 超容量的两小时 fixture；结果导出 `reserve_feasible=False`，comparison 失败可审计，不伪造成功。
4. **平坦因子**：24 小时 factor 相同，`T==R`，C 的 grid precharge 不增加，C 相对 B 无额外“窗口”动作。
5. **低—高玩具窗口**：低因子早时段 + 高因子可替代网电晚时段，C 允许充/留电；放电后仍大于 R。
6. **柴油替代**：孤岛有柴油与 storage 时，C 的窗口 discharge 对应正柴油出力并给 `HIGH_FACTOR_DIESEL_DISPLACEMENT`。
7. **component separation**：同小时拆成两个 component 的 fixture，验证 R/T 分别计算；一个 island 的高因子不提高另一个岛的 target。
8. **CareTask 回归**：运行现有 `tests/test_care.py`，再在 Carbon-SOC runner 中断言四个任务全部完成才可比较。
9. **Pareto 回归**：运行现有 `tests/test_pareto.py`；标准 `scan_pareto()` 输出列、行数、schema 和 care artifacts 均不变。
10. **三灾害集成**：暴雨内涝、台风、极端高温各 A/B/C，所有可比较候选需 24/24 physical feasible；失败必须落在 comparison failures，而非删除。

## 7. 实施顺序（最小风险）

1. 新建纯 envelope builder + 单元玩具 case，不接 dispatch。
2. 给 `dispatch_resources_spatial` 加完全可选 envelope/mode，先写 off 回归。
3. 用独立 `run_carbon_soc_comparison` 组织 A/B/C；不碰 `run_pipeline` 默认行为。
4. 接 CareTask/physical eligibility 和 CSV/manifest。
5. 最后再接 UI；UI 只读新增 artifacts，不能反向改变 policy。

## 8. 审计结论

最小可实现版本的创新点应是：**按小时、按电气 component 锁住可复算的保供底仓 R；把 `SOC-R` 输出为可调电量 F；只把未来真实能替代网电/柴油的窗口转成软目标 T；A/B/C 在完全相同的 CareTask 服务合同、修复动作、因子版本和物理反馈下比较。**

实现上最关键的隔离策略是：Carbon-SOC 作为 opt-in 数据对象和独立比较 runner 存在，默认 dispatch、既有三策略、CareTask 和 Pareto API/schema 均保持原样。这能给出新证据，同时避免把现有绿色回归基线打碎。
