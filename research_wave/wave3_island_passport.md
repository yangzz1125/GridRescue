# Wave 3：微网成岛能力护照与韧性安全裕度热图

## 1. 决策摘要

本波把现有“孤岛数量 + 潮流是否可行”的结果升级为**每一个非根网连通分量、每一个小时都可审计的成岛能力护照**。它回答评委、调度员和抢修人员最关心的八个问题：

1. 这个岛是否有成网（GFM）电源，证据来自哪里？
2. 它能否黑启动，启动还缺哪些前置条件？
3. 此刻 P、Q 各剩多少安全裕度？
4. 电池 SOC、柴油燃料分别还能撑多久？
5. 最低电压、最大热负载率在哪个节点/支路？
6. 当前计划下能稳定维持多长时间？
7. 一旦失败，最先击穿的是哪条约束？
8. 哪些岛已经“可供电”，哪些只是“拓扑上孤立、尚未可成岛”？

**MVP 的核心原则**：不把“有 PV”“有 BESS”自动解释为可成岛；不把聚合功率平衡自动解释为黑启动能力；缺失的设备能力、燃料和启动数据必须显示为 `unknown`，而不是填成绿色。现有模型中的 GFM 是由柴油/BESS容量**推断**出来的工程假设，护照必须把该证据等级直接展示出来。

本波只产出设计，不修改任何代码。建议实现目标为 10 天 MVP，复用现有 `dispatch`、`FlowValidation.components/nodes/branches/hourly` 与 `network_nodes` 导出，不重写当前潮流或恢复求解器。

---

## 2. 当前仓库基线：已经有什么、还缺什么

### 2.1 已有可直接复用的物理证据

| 层 | 现有对象/文件 | 已能回答的问题 |
|---|---|---|
| 拓扑与DER台账 | `GridModel.nodes`、`network_nodes.csv` | 节点、关键等级、PV、储能功率/能量、柴油容量、节点类型。 |
| 支路台账 | `GridModel.branches`、`network_branches.csv` | 线路端点、联络线、R/X、热额定 `capacity_kva`、容量假设来源。 |
| 拓扑时序 | `restoration.state_at_hour()`、`build_node_demand_frame()` | 每小时连通分量、`component_key`、是否根网分量。 |
| 节点调度 | `DispatchResult.node_frame` | 每小时每节点已供负荷、PV、柴油、充/放电、SOC、损耗。 |
| 物理校验 | `FlowValidation.components/nodes/branches/hourly` | 成分量 P/Q、局部 slack、源可行性、电压、热负载、损耗、收敛、整体可行。 |
| 页面 | `app.py` 的“恢复数字孪生 / 潮流校验” | 场景、策略、小时游标、拓扑和既有潮流结果。 |

当前 `validate_dispatch()` 对每个连通分量已有清晰的硬边界：根网外无 local GFM 候选时，分量只要存在供电/出力需求就判为不可行；PV 本身不会单独被当作成网源。空间调度也会把“无 GFM 的非根岛”全部去供电并弃掉其 PV。这是能力护照最重要的真实基础。

### 2.2 当前 GFM 判定的准确表述

`powerflow._component_slack()` 的当前口径为：根分量的 slack 是上级电网；非根分量从节点中选择 `diesel_capacity_kw + storage_power_kw` 最大且大于零的节点作为 slack。`dispatch_resources_spatial()` 也使用岛内柴油容量 + 储能功率大于零作为“可有成网能力”的必要条件。

这意味着当前数据支持：

```text
GFM_INFERRED = (diesel_capacity_kw + storage_power_kw) > 0
```

但它尚未支持“设备已验证具备 GFM 控制、黑启动、同期、并网/离网切换、保护定值及可用通信”的现场事实。因此 MVP 必须把 GFM 证据分层：

| 状态 | 含义 | 当前可得性 |
|---|---|---|
| `verified` | 台账/试验记录明确设备具备 GFM 并处于可用态 | 缺数据，后续资产台账补齐。 |
| `assumed_from_model` | 由柴油/BESS容量推断为可成网 | 当前可计算，默认状态。 |
| `grid_following_only` | 只有 PV 或只有无 GFM 标记资源 | 当前可从节点容量推断。 |
| `none` | 没有候选本地源 | 当前可计算。 |
| `unknown` | 设备或可用性数据缺失 | 新增显式状态，绝不涂绿。 |

### 2.3 当前缺口及 MVP 补法

| 缺口 | 影响 | MVP 补法 |
|---|---|---|
| `gfm`、`black_start`、逆变器模式没有显式字段 | BESS/PV 是否真可成岛不可审计 | 新增 sidecar 资产台账；没有记录时护照显示 `unknown` / `assumed_from_model`。 |
| 柴油燃料、油耗曲线、启动时间、爬坡率未建模 | 无法给出工程保证的持续时长 | V1 用 SOC 约束 + `fuel_unknown` 标识；V1.1 增加燃料和起机参数。 |
| `components` 有最大负载率、最低电压，但无最弱节点/支路 ID | 热图无法精确定位瓶颈 | 由 `powerflow_nodes` / `powerflow_branches` 反向聚合得到。 |
| `component_key` 是成员节点串，会随并岛/切网改变 | 一个物理岛跨时段的护照不稳定 | 用 `island_episode_id` 表示“同一拓扑片段内的岛”；合并/拆分时开启新 episode 并保留父子关系。 |
| 当前 `source_capacity_kw` 是选定 slack 节点的 P 能力 | 不能把它直接误称为全岛全部 DER 的并联额定能力 | 护照同时列出 `validator_slack_capacity_kw` 与 `installed_island_der_kw`，两者不混写。 |

---

## 3. 能力护照：对象、状态机与最小数据模型

### 3.1 对象边界

护照对象不是“整条配电网”，而是：

```text
Passport = (run_id, scenario, strategy, island_episode_id, hour, component_key)
```

- 仅对 `is_root_component=false` 的连通分量生成**成岛护照**；根网分量生成“根网运行卡”，避免把上级电网误叫作孤岛。
- 每小时生成一张快照；同一 `component_key` 在拓扑未变化的连续时段可聚合为一张 episode 护照。
- 以 `component_key`（排序节点 ID 串）为本时刻精确成员证据；以 `island_episode_id` 做 UI/报告主键。

建议状态机：

```text
topology_isolated
  → candidate_gfm
  → black_start_ready
  → energized
  → constrained / degraded
  → deenergized / infeasible
```

其中 `energized` 必须同时满足径向、GFM、P/Q、V、热、收敛和可用性门；`candidate_gfm` 只表示发现候选设备，绝不等价于已带电。

### 3.2 核心门控（Gate）

| Gate | 判定 | 当前数据来源 | 护照结果 |
|---|---|---|---|
| G0 拓扑 | 非根分量、故障隔离、闭合联络后仍径向 | `state_at_hour`、`graph_from_state`、`is_radial` | `topology_status` |
| G1 GFM | 至少一个真实/推断的 GFM 资源，且可用 | 节点 DER + sidecar | `gfm_status` |
| G2 黑启动 | 黑启动标记、启动完成、站控/通信/同期前置条件均满足 | sidecar、动作/事件账本 | `black_start_status` |
| G3 有功 | P 供给、P reserve、SOC/燃料门满足 | `components` + `node_frame` | `p_status` |
| G4 无功 | Q 需求不超过 Q 能力，且留出无功备用 | `components` | `q_status` |
| G5 电压 | `V_min >= V_limit` 且 `V_max <= V_limit` | `components` + `nodes` | `voltage_status` |
| G6 热稳定 | `max_loading_pct <= 100%` | `components` + `branches` | `thermal_status` |
| G7 持续性 | 资源持续时长不短于承诺服务时长 | SOC / 燃料 / 时间线 | `duration_status` |

成岛能力最终状态：

```text
READY       : G0–G7 全通过，且关键证据不是 unknown
CONDITIONAL : 物理量通过，但黑启动/GFM/燃料存在 assumption 或 unknown
DEGRADED    : 仍带电但任一软裕度低于黄线
BLOCKED     : 任一硬门失败，禁止显示为“已恢复成岛”
```

### 3.3 `island_passport_hourly` 字段（MVP 主表）

建议导出 `island_passport_hourly_<strategy>.csv`；每一行对应一个 hour × component。字段以四类组织，避免 UI 从几十张 CSV 临时猜语义。

#### A. 身份、拓扑和证据

| 字段 | 单位/示例 | 来源/计算 |
|---|---|---|
| `run_id`、`scenario_id`、`strategy_id` | 字符串 | run metadata。 |
| `hour`、`timestamp` | h / ISO-8601 | 推演时钟。 |
| `island_episode_id` | `isl-<hash>-h03` | 连续同构 component 的 episode ID。 |
| `component_id`、`component_key` | `2` / `18-19-20-21` | `validation.components`。 |
| `node_count`、`node_ids` | `4` / JSON array | `components` / `component_key`。 |
| `is_root_component` | bool | `components`。 |
| `topology_radial`、`fault_isolated` | bool | 新增 topology analyzer；现有 state/graph 可推导。 |
| `passport_status`、`blocked_reason_codes` | `READY` / JSON list | Gate 汇总。 |
| `data_confidence` | `observed/assumed/mixed/unknown` | 各字段 evidence 的最弱等级。 |

#### B. GFM / 黑启动 / 资源资格

| 字段 | 单位/示例 | 说明 |
|---|---|---|
| `gfm_candidate_count` | 个 | 岛内候选 GFM 数。 |
| `gfm_primary_node`、`gfm_primary_asset_id` | node 29 / `BESS-N30` | 首选成网源。 |
| `gfm_status` | `verified/assumed_from_model/grid_following_only/none/unknown` | 见 2.2。 |
| `gfm_available_kw` | kW | 可用且具 GFM 资格的 P 能力；与总 DER 分列。 |
| `gfm_available_kvar`、`gfm_available_kva` | kvar/kVA | 明确 Q/S 能力。 |
| `black_start_status` | `ready/pending/failed/unknown/not_required` | 非根岛一般要求 `ready`。 |
| `black_start_start_delay_min` | min | 黑启动/并离网前置时长。 |
| `black_start_preconditions` | JSON | 站控、通信、保护、同期、开关状态。 |
| `gfm_evidence_level`、`black_start_evidence_ref` | `assumption_v1` / hash | 能力证据而非口头说明。 |
| `pv_grid_following_kw`、`pv_gfm_kw` | kW | 防止把普通 PV 当成黑启动源。 |

#### C. P/Q、SOC、燃料、时长

| 字段 | 单位 | 来源/公式 |
|---|---:|---|
| `required_source_kw` | kW | `components.required_source_kw`。 |
| `validator_slack_capacity_kw` | kW | `components.source_capacity_kw`；仅当前 validator 的 slack 能力。 |
| `installed_island_der_kw` | kW | 岛内节点 `diesel_capacity_kw + storage_power_kw + pv_capacity_kw` 聚合。 |
| `p_reserve_kw` | kW | `validator_slack_capacity_kw - required_source_kw`；负数即硬失败。 |
| `p_reserve_pct` | % | `100 × p_reserve_kw / max(required_source_kw, ε)`。 |
| `required_reactive_kvar` | kvar | `components.required_reactive_kvar`。 |
| `reactive_capacity_kvar` | kvar | `components.reactive_capacity_kvar`。 |
| `q_reserve_kvar` / `q_reserve_pct` | kvar / % | `Qcap - Qreq` 及归一化。 |
| `reactive_shortfall_kvar` | kvar | `components.reactive_shortfall_kvar`。 |
| `soc_kwh`、`soc_pct` | kWh / % | 岛内 `node_frame.battery_soc_kwh` 与静态 `storage_energy_kwh`。 |
| `usable_bess_energy_kwh` | kWh | `Σ max(SOC - min_soc×E_cap, 0)`；`min_soc` 必须来自运行配置。 |
| `bess_discharge_kw` / `bess_charge_kw` | kW | `node_frame` 聚合。 |
| `diesel_generation_kw` | kW | `node_frame` 聚合。 |
| `fuel_available_l`、`fuel_reserve_l` | L | 资产/现场输入；缺失为 NULL。 |
| `fuel_burn_lph` | L/h | 发电机曲线或输出估计；缺失为 NULL。 |
| `fuel_duration_h` | h | `(fuel_available_l-fuel_reserve_l)/fuel_burn_lph`，未知保持 NULL。 |
| `bess_duration_h` | h | `usable_bess_energy_kwh / max(bess_net_support_kw, ε)`；仅 BESS 实际承担正净支撑时有意义。 |
| `committed_duration_h` | h | 运维/关键负荷 SLA 所需维持时长。 |
| `safe_duration_h` | h | `min(remaining_topology_window, bess_duration_h, fuel_duration_h)`，忽略 NULL 但记录原因；若全未知则 NULL。 |
| `duration_confidence` | `calculated/partial/unknown` | 必须与 fuel/SOC 数据一致。 |

**持续时长的特别规则**：当前项目只有 24h 调度窗口，且没有燃料库存和柴油油耗。因此 V1 的 `safe_duration_h` 是“在当前计划、当前拓扑 episode 下的资源边界估计”，不是现场承诺。若 fuel 数据缺失，页面显示“柴油持续时长未知”，绝不以柴油容量除负荷冒充真实小时数。

#### D. V、热限、最弱约束与安全裕度

| 字段 | 单位 | 来源/公式 |
|---|---:|---|
| `min_voltage_pu`、`max_voltage_pu` | pu | `components`。 |
| `min_voltage_node_id` | node | `nodes` 按 `(hour, component_id)` 求 `voltage_pu` 最小值。 |
| `voltage_margin_pu` | pu | `min_voltage_pu - voltage_min_limit_pu`。 |
| `voltage_margin_pct_band` | % | `100×(Vmin−Vlow)/(Vhigh−Vlow)`；低于 0 为硬失败。 |
| `max_loading_pct` | % | `components`。 |
| `worst_branch_id` | branch | `branches` 按 `(hour, component_id)` 最大 `loading_pct`。 |
| `thermal_headroom_pct` | percentage point | `100 - max_loading_pct`。 |
| `thermal_headroom_kva` | kVA | `branch.capacity_kva - branch.apparent_flow_kva`。 |
| `powerflow_converged`、`iterations` | bool / 次 | `components`。 |
| `service_load_kw` | kW | 岛内 `node_frame.served_load_kw`。 |
| `critical_service_kw`、`critical_service_pct` | kW / % | 岛内已供关键负荷 / 需求。 |
| `weakest_constraint` | enum | 见 4.3。 |
| `weakest_margin_pct` | % | 所有可比较 margin 的最小值。 |
| `heat_class` | `green/yellow/orange/red/gray` | 映射规则。 |

### 3.4 Sidecar 资产台账（现有节点表不硬塞未经验证的字段）

建议新数据源为 `data/island_assets.csv`，一个 `asset_id` 一行：

```text
asset_id,node_id,asset_type,enabled,gfm_capable,black_start_capable,
pmax_kw,qmax_kvar,smax_kva,ramp_kw_per_min,start_delay_min,
fuel_capacity_l,fuel_available_l,fuel_reserve_l,fuel_curve_id,
min_soc_pct,communication_ready,protection_ready,sync_ready,
evidence_level,evidence_ref,valid_from,valid_to
```

最小可用填法：先为 N14/N30 的 BESS、N18/N30 的柴油建立资产记录；若没有现场确认，把 `gfm_capable`、`black_start_capable` 保持 `unknown`，同时用现有模型产生 `assumed_from_model` 标签。此设计保留模型可跑性，但禁止“模型里有储能”变成“现场已经黑启动验证”。

---

## 4. 韧性安全裕度热图：计算口径与可解释规则

### 4.1 不做黑箱分数，先做可追溯 margin 向量

每个 island-hour 先产出下面的**原始裕度**，所有颜色、排序和“最弱约束”都从它们来：

```text
M_P   = P_capacity_validator - P_required
M_Q   = Q_capacity - Q_required
M_V   = V_min - V_low
M_TH  = 100 - branch_loading_max_pct
M_SOC = usable_bess_energy / required_island_support_power
M_FUEL= (fuel_available - fuel_reserve) / fuel_burn
M_DUR = safe_duration_h - committed_duration_h
```

其中 `M_P/M_Q/M_V/M_TH` 由现有校验数据直接得到；`M_SOC` 可由现有 SOC 和配置得到；`M_FUEL/M_DUR` 需要新资产台账。任意未知值保持 `NULL`，而不是 0 或满分。

### 4.2 用无量纲版本统一排序，但保留原始值

为了把 kW、kvar、pu、百分比、小时放进同一热图，计算以下归一化裕度；表格和 hover 仍须显示原值及公式：

```text
m_P  = M_P  / max(P_required, ε)
m_Q  = M_Q  / max(Q_required, ε)
m_V  = (V_min - V_low) / (V_high - V_low)
m_TH = (100 - loading_pct) / 100
m_DUR= M_DUR / max(committed_duration_h, ε)
```

建议阈值：

| 热色 | 条件 | 含义 |
|---|---|---|
| `red` | 任一硬门失败，或任意归一化 margin `< 0` | 已越界/不可成岛。 |
| `orange` | 最小已知 margin `0–10%` | 临界，下一动作必须优先处理。 |
| `yellow` | 最小已知 margin `10–25%` | 有条件运行，禁止大阶跃加负荷。 |
| `green` | 最小已知 margin `≥25%` 且 GFM/黑启动证据合格 | 有较稳安全余量。 |
| `gray` | 关键能力为 unknown（尤其 GFM、黑启动、燃料） | 物理数值也许通过，但不可作“准备就绪”结论。 |

电压建议沿用当前 validator 的 `0.95–1.05 pu`；热限沿用 `loading_pct <= 100%`。UI 可以额外显示橙色预警线（如 0.97 pu、90% loading），但预警线不能改写物理硬约束。

### 4.3 最薄弱约束（`weakest_constraint`）

`weakest_constraint` 不是“发生过什么”而是“若保持当前岛状态，最先需要处理什么”。算法：

1. 先判断硬失败：`NO_GFM`、`BLACK_START_NOT_READY`、`P_SHORTFALL`、`Q_SHORTFALL`、`VOLTAGE_LOW/HIGH`、`THERMAL_OVERLOAD`、`NONCONVERGED`、`DURATION_SHORT`。
2. 无硬失败时，对 `m_P/m_Q/m_V/m_TH/m_DUR` 取最小的已知值。
3. 任何关键输入 unknown 时，若其会改变是否可以成岛，优先标 `GFM_EVIDENCE_UNKNOWN`、`BLACK_START_UNKNOWN` 或 `FUEL_ENDURANCE_UNKNOWN`；不要用漂亮的电压值掩盖它。
4. 平局时按安全优先序：GFM/黑启动 → P/Q → V → 热 → 持续时长。

建议受控枚举：

```text
NO_GFM, GFM_EVIDENCE_UNKNOWN, BLACK_START_NOT_READY,
BLACK_START_UNKNOWN, P_RESERVE, Q_RESERVE, VOLTAGE,
THERMAL, SOC_ENDURANCE, FUEL_ENDURANCE, TOPOLOGY_RADIAL,
POWERFLOW_CONVERGENCE, SERVICE_DEADLINE, NONE
```

### 4.4 热图形态

建议同时提供两张图，避免单一颜色掩盖物理原因：

1. **岛×时间安全裕度热图**：行=`island_episode_id`，列=T+0…T+23，色=`heat_class` 或 `weakest_margin_pct`。单元格文本：`最弱约束 / margin / Vmin / loading`。
2. **约束×时间热图**：选择一个岛后，行=`GFM、Black Start、P、Q、SOC、Fuel、V、Thermal、Duration`，列=小时，色=该约束的 status/margin。它回答“为什么这个格是黄/红”。

推荐 tooltip：

```text
岛：isl-17-18-... / T+6 h
状态：CONDITIONAL（GFM=assumed_from_model）
最弱约束：THERMAL，余量 7.2 pp
最低电压：0.961 pu @ N24
最大负载率：92.8% @ L17
P/Q 余量：42.0 kW / 88.1 kvar
SOC：348 kWh（可用 271 kWh）
柴油持续时长：未知（缺 fuel_available_l）
```

示例数字仅说明展示格式，绝不作为现有运行结果声明。

---

## 5. 从现有 validation / components 导出的确定性数据流

### 5.1 现有导出到护照字段的映射

| 护照字段组 | 优先输入 | 现有列 | 转换 |
|---|---|---|---|
| 分量身份 | `powerflow_components_*.csv` | `hour,component_id,component_key,is_root_component,node_count,slack_node` | 非根分量进入护照。 |
| GFM 初筛 | `network_nodes.csv` + components | `diesel_capacity_kw,storage_power_kw,slack_node` | 岛内容量>0 为 `assumed_from_model`；`slack_node=-1` 为 `none`。 |
| P 约束 | components | `required_source_kw,source_capacity_kw,source_adjustment_kw,unserved_balance_kw,source_feasible` | `p_reserve_kw=source_capacity-required`；保留 slack 语义。 |
| Q 约束 | components | `required_reactive_kvar,reactive_capacity_kvar,reactive_shortfall_kvar` | `q_reserve=capacity-required`。 |
| 电压 | components + nodes | `min_voltage_pu,max_voltage_pu`; nodes 的 `voltage_pu` | nodes groupby 找 `min_voltage_node_id`。 |
| 热稳定 | components + branches + network branches | `max_loading_pct`; branches 的 `loading_pct,apparent_flow_kva`; `capacity_kva` | branches groupby 找最差支路并算 kVA headroom。 |
| SOC/出力 | `dispatch.node_frame` | `battery_soc_kwh,battery_charge_kw,battery_discharge_kw,diesel_generation_kw,served_load_kw` | 按 `(hour, component_key)` 聚合；需将 node_frame 与 `build_node_demand_frame` 的组件标签相连。 |
| 关键服务 | node demand + node frame | `critical_load_kw,served_critical_kw` | 岛内求和与 SLA 对照。 |
| 整体可行 | `powerflow_*.csv` | `is_feasible,thermal_violation,voltage_violation,balance_violation` | 用作页面全局 badge，分量细节仍以 components 为准。 |

### 5.2 建议的变换顺序

```text
run_pipeline(scenario)
  ├─ StrategyResult.dispatch.frame
  ├─ StrategyResult.dispatch.node_frame
  ├─ FlowValidation.hourly / components / nodes / branches
  ├─ state_at_hour + build_node_demand_frame
  └─ network_nodes / network_branches + island_assets sidecar
        ↓
normalize_component_membership()
        ↓
aggregate_component_resources()
        ↓
join_voltage_and_thermal_bottlenecks()
        ↓
evaluate_island_gates()
        ↓
compute_margin_vector_and_weakest_constraint()
        ↓
island_passport_hourly.csv + island_passport_episode.csv + island_margin_heatmap.csv
```

`component_key` 必须来自和本次 validation 相同的拓扑时刻；不要用某个小时的岛成员去 join 另一个小时的节点出力。实现时建议以 `(hour, node_id)` 为主键先接入 component 信息，再聚合。

### 5.3 新增导出物（不破坏现有 CSV）

```text
artifacts/<scenario_or_run>/
  island_passport_hourly_<strategy>.csv       # 一行 = hour × component
  island_passport_episode_<strategy>.csv      # 连续岛 episode 摘要
  island_margin_heatmap_<strategy>.csv        # 宽表或 tidy 表，供 UI 直接画图
  island_bottlenecks_<strategy>.csv           # 最弱节点、支路、约束及证据链接
  island_asset_snapshot.csv                   # 本次 run 冻结的 GFM/黑启动/燃料台账
  island_passport_schema.json                 # 版本、单位、门控、阈值
```

最小 `island_margin_heatmap` tidy schema：

```text
hour,island_episode_id,component_key,metric_name,
margin_value,margin_unit,normalized_margin,status,
heat_class,weakest_constraint,evidence_ref
```

### 5.4 需要明确写进导出 manifest 的假设

1. `gfm_status=assumed_from_model` 的推断规则与版本；
2. 电压阈值、热负载阈值、无功支持比例（当前 validator 默认 `0.60`）；
3. `min_soc`、储能效率和时间步长；
4. 热额定来源目前为 `GridRescue engineering thermal limits v0.2`，不是 MATPOWER case33bw 原始 rateA/B/C；
5. 燃料 / 黑启动字段缺失时的 unknown 处理；
6. `source_capacity_kw` 是当前 validator slack 的 P 能力，不是未经证明的全岛聚合成网容量。

---

## 6. UI：90 秒讲清“这个岛到底能不能撑住”

### 6.1 页面落点

保留现有五个 tab，不推倒主界面；新增第六个 tab：**“成岛护照”**。同时在既有页面做最小联动：

| 现有位置 | 新增内容 |
|---|---|
| 顶部 KPI | `可成岛 READY/CONDITIONAL/BLOCKED` 数、当前最弱约束、最小安全裕度。 |
| 恢复数字孪生 | 选中非根岛时，右侧显示护照摘要；节点/边 hover 增加 `island_episode_id`、最弱约束。 |
| 潮流校验 | 在逐时线图下添加“最差岛/最差支路/最差节点”表，点击跳转护照。 |
| 成岛护照（新增） | 热图、单岛卡片、资源/SOC/燃料/电压/热限证据抽屉。 |
| MRV报告 | 下载护照 CSV、资产快照、schema、阈值/证据说明。 |

### 6.2 新 tab 的版面

```text
┌───────────────────────────────────────────────────────────────────┐
│ 当前小时 T+06 | READY 1 | CONDITIONAL 2 | BLOCKED 1 | 最弱：THERMAL │
├─────────────────────────────┬─────────────────────────────────────┤
│ 岛×时间裕度热图              │ 选中岛的能力护照                    │
│ rows: island episode         │ 状态 / GFM证据 / 黑启动 / 成员节点  │
│ cols: T+0...T+23             │ P/Q reserve, SOC, Fuel, duration    │
│ color: weakest margin         │ Vmin@node, loading@branch             │
├─────────────────────────────┴─────────────────────────────────────┤
│ 约束×时间明细热图 + 最弱约束时间线 + 资产/潮流证据抽屉              │
└───────────────────────────────────────────────────────────────────┘
```

卡片固定显示如下字段，评委无需读 CSV：

```text
岛 episode / T+hour / 成员节点 / 服务的关键负荷
状态：READY | CONDITIONAL | DEGRADED | BLOCKED
GFM：asset_id @ node，verified / assumed / unknown
黑启动：ready / pending / unknown，缺失前置条件
P/Q：required、capacity、reserve
SOC：当前、可用能量、放电功率、估计 BESS 时长
Fuel：库存、预留、油耗、预计时长；未接入时明确“unknown”
V/热：最低 pu @ node、最大 % @ branch
最薄弱约束：枚举 + 原始 margin + 推荐动作
```

### 6.3 颜色和交互禁忌

- **灰色优先于绿色**：GFM 或黑启动关键证据 unknown 时，即使潮流可行，也显示灰色 `CONDITIONAL`，而不是绿色“安全”。
- **红色绝不美化**：`source_feasible=false`、`reactive_shortfall>0`、`V<0.95`、`loading>100`、非收敛、无 GFM 任一命中，网络图的岛边界和护照标题必须红色。
- **热图可钻取**：点击单元格同时更新网络至同一小时、highlight 最差节点/支路、显示 `components/nodes/branches` 的行级证据。
- **显示建议但不伪装自动控制**：如“先削减普通负荷 45 kW”“延后冷负荷”“起柴油并确认燃料”，应标 `recommended_next_action`，不标“已执行”。

### 6.4 面向答辩的标准讲法

> 这个岛不是因为有光伏就被标为恢复。系统先检查它有没有成网源和黑启动证据，再检查 P/Q 备用、电压和线路热稳定，最后把 SOC 与燃料换算成持续时长。热图红色格能一键定位到具体支路或节点；灰色格不是安全，而是现场能力资料尚未闭环。

---

## 7. 测试与验收矩阵

### 7.1 单元测试

| 测试名（建议） | Fixture | 关键断言 |
|---|---|---|
| `test_passport_emits_nonroot_components_only` | 根网 + 非根岛 | 根网不进入 island passport；非根岛有一行/小时。 |
| `test_source_free_island_is_blocked` | 现有支路18断开 fixture | `gfm_status=none`、`passport_status=BLOCKED`，无“已恢复”标签。 |
| `test_gfm_inference_is_not_verified` | 仅现有 nodes 容量 | `diesel/BESS>0` 只产生 `assumed_from_model`，不产生 `verified`。 |
| `test_black_start_unknown_is_gray` | 无 sidecar | 物理可行时仍为 `CONDITIONAL/gray`，`black_start_status=unknown`。 |
| `test_p_q_margin_formula` | 固定 components 行 | P/Q reserve、百分比与 shortfall 符号正确。 |
| `test_voltage_bottleneck_join` | 两节点不同 pu | 最小节点 ID 与 `voltage_margin_pu` 正确。 |
| `test_thermal_bottleneck_join` | 两支路不同 loading | 最差 branch ID、百分比和 kVA headroom 正确。 |
| `test_soc_usable_energy_respects_minimum` | 固定 SOC/capacity/min_soc | 可用能量不为负，单位随 `Δt` 一致。 |
| `test_fuel_endurance_unknown_not_zero` | fuel 缺失 | `fuel_duration_h=NULL`，状态 `unknown`，不被当作 0h 硬失败。 |
| `test_duration_gate_blocks_short_commitment` | SOC/fuel 低于 SLA | `DURATION_SHORT` 成为最弱约束。 |
| `test_unknown_priority_in_weakest_constraint` | 物理 margin 很高 + GFM unknown | 最弱约束是 `GFM_EVIDENCE_UNKNOWN`。 |
| `test_margin_heat_class_thresholds` | 边界值 | red/orange/yellow/green/gray 映射稳定。 |

### 7.2 集成与回归测试

1. **三场景 × 三策略回归**：暴雨内涝、台风、极端高温各跑 3 策略；护照行数与每小时非根分量数量一致，已有 `validation.hourly.is_feasible` 行为不改变。
2. **组件一致性**：任意护照行的 `required_source_kw`、`required_reactive_kvar`、`min_voltage_pu`、`max_loading_pct` 必须与源 `powerflow_components` 同键相等（允许写入精度容差）。
3. **节点/支路证据一致性**：护照标的 `min_voltage_node_id` 必须等于 `powerflow_nodes` 对应分量的 argmin；`worst_branch_id` 必须等于 `powerflow_branches` 的 argmax。
4. **拓扑切换 episode**：开/合联络线造成 component 成员变化时，旧 episode 在切换小时前结束，新 episode 从切换小时开始，二者不可被错误拼接。
5. **无 GFM PV 岛**：PV 存在、柴油/BESS 都为零，结果仍 `BLOCKED`，展示 `grid_following_only`。
6. **Q 限制**：构造 `reactive_shortfall_kvar>0` 的 fixture，护照必须红色且最弱约束 `Q_RESERVE`，不能只报 P 足够。
7. **热/压极限**：验证低压和过载分别成为最弱约束，并可定位到节点/线路。
8. **明确能力台账**：加入 verified GFM、black start、fuel 的 fixture 后，由 `CONDITIONAL` 正确升级 `READY`。
9. **导出稳定性**：固定输入、固定 seed/solver 条件下，护照 CSV、schema 与 heatmap 规范化哈希一致。
10. **UI smoke**：切换场景、策略、小时，热图、选中岛卡片、网络 highlight 同步；当无非根岛时显示空态而不是异常。

### 7.3 演示验收脚本（90 秒）

```text
1. 选择“暴雨内涝 / 碳韧协同恢复 / T+当前成岛时刻”。
2. 在拓扑图点击一个非根岛：右侧出现护照摘要和状态。
3. 打开热图：指出黄/红/灰格的 weakest_constraint。
4. 点击该格：网络高亮 Vmin 节点与最热支路，显示 P/Q/SOC/Fuel 原始证据。
5. 切换到无 GFM fixture：岛立即显示 BLOCKED，不显示“关键负荷已恢复”。
6. 下载 island_passport_hourly.csv 和 island_asset_snapshot.csv，展示字段与 run/hash 信息。
```

---

## 8. 10 天 MVP 路线

| 天 | 交付 | 退出标准 |
|---:|---|---|
| D1 | 冻结护照 schema、状态机、G0–G7、热图阈值、单位字典 | 字段评审完成；明确 `assumed/unknown` 规则。 |
| D2 | `island_assets.csv` 模板；录入现有两处 BESS、两处柴油的最小台账 | 每项能力都有 evidence_level；未知不填假值。 |
| D3 | 建护照 ETL：components + node_frame + nodes + branches 的 key 对齐 | 能输出 hour×component 原始表。 |
| D4 | 实现 P/Q/V/thermal、最弱节点/支路、margin 向量 | 与现有 validation CSV 对账通过。 |
| D5 | 接入 GFM/黑启动状态与 `island_episode_id` | 无 GFM、推断 GFM、verified GFM 三种 fixture 通过。 |
| D6 | SOC 可用能量、时长代理、fuel unknown/已知双路径 | duration 不会把 NULL 误写成 0 或安全。 |
| D7 | 导出 5 个护照文件、schema、manifest 假设记录 | CLI/批量 run 可生成完整导出包。 |
| D8 | Streamlit 新“成岛护照” tab，热图 + 单岛卡 + drill-down | 场景/策略/小时联动稳定。 |
| D9 | 单元、集成、UI smoke、固定 fixture、回归对账 | `pytest -q` 全绿；三场景九组合跑通。 |
| D10 | 答辩彩排、极端 fixture 截图、下载包与一页解释词 | 90 秒演示可重复，灰/红/绿语义一致。 |

### 8.1 MVP 范围控制

**D10 前必须完成**：护照字段、现有 validation 对账、GFM/黑启动证据等级、P/Q/V/热/SOC裕度、最弱约束、热图、导出、测试。

**可放到 V1.1**：柴油油耗曲线、逐分钟 cold-load pickup、频率/ROCOF、保护配合、同期合闸动态过程、N-1 GFM 丢失仿真、现场 SCADA/EMS 接入。它们很有价值，但不能阻塞“当前模型的能力边界被诚实展示”这一 MVP。

---

## 9. 实施接口建议（下一波编码时使用）

建议新增纯派生层，不改变现有求解主线：

| 组件 | 建议接口 | 责任 |
|---|---|---|
| `islanding.py` | `build_island_passports(model, scenario, strategy_result, validation, assets, config)` | 生成 hourly/episode 表。 |
| `island_assets.py` | `load_island_assets(path)`, `validate_asset_registry()` | 读取 GFM、黑启动、燃料台账。 |
| `island_metrics.py` | `compute_margins(row)`, `select_weakest_constraint(...)` | 计算统一裕度与热色。 |
| `cli.py` | `--island-assets`, `--export-island-passport` | 导出 CSV、schema、snapshot。 |
| `app.py` | `passport_tab(...)` | 热图、护照卡、证据抽屉。 |
| `tests/test_island_passport.py` | fixtures + 对账 | 上述测试矩阵。 |

不建议把护照逻辑塞进 `validate_dispatch()`：validator 的职责仍是物理可行性；护照是对 validation、设备台账、持续时长和证据等级的可解释聚合。两层分离可避免把 UI 语义和工程假设污染潮流求解。

---

## 10. 最终验收定义

一份合格的“微网成岛能力护照”必须做到：

1. 对每个非根 island-hour 明确给出 `READY / CONDITIONAL / DEGRADED / BLOCKED`，并列出理由；
2. GFM、黑启动、燃料等未建模/未证实能力都显式写 `assumed` 或 `unknown`；
3. P/Q、SOC、V、热限、持续时长、最弱节点/支路均可追溯回现有 CSV 行或资产台账；
4. 热图任何一个红/黄/灰格可以 drill-down 到具体公式、输入、约束和建议动作；
5. `source_free` 岛绝不出现在“已恢复”统计里；
6. 现有 33 节点三场景三策略潮流/调度回归保持稳定；
7. 导出包包含字段 schema、阈值/假设、资产快照和 run 证据，不让漂亮颜色脱离数据来源。

一句话答辩版：

> GridRescue 的成岛不是拓扑动画：每个岛都有 GFM 与黑启动证据、P/Q/SOC/燃料/电压/热限的安全裕度、可维持时长和最薄弱约束；任何未知能力都显式标灰，任何越界都能定位到节点、支路和数据行。
