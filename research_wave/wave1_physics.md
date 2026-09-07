# Wave 1：P/Q 物理模型升级独立审计与实施设计

> 边界：本轮只审计、设计和写报告；未改动 `src/`、`tests/`、`data/` 或应用代码。
>
> 审计对象：`src/gridrescue/{network,dispatch,powerflow,restoration,pipeline,faults}.py`、`app.py`、`tests/test_core.py`，并复核 `research_wave/case33_powerflow_audit.md`、`research_wave/microgrid_islanding.md`。重点：DER `P²+Q²≤S²`、GFM 孤岛、过电压闭环、支路热限额。

## 结论先行

现有仓库已经具备三项可复用基础：

1. `case33bw` 的逐节点 `P/Q`、逐支路 `R/X`、10 MVA / 12.66 kV 基值已经进入 `network.py`；基础 BFS 也复现了约 `202.68 kW` 网损和 `0.91309 pu` 最低电压。
2. 调度已节点化，`dispatch_resources_spatial()` 会按连通分区列 P 平衡；无本地资源的孤岛会被置为失供。
3. `validate_dispatch()` 已运行 P/Q BFS，并把后验损耗回灌给调度。

但这还不是闭环的 DER-配网物理模型。**下一步必须先把“资源额定能力、成网资格、Q 出力、热额定”的数据和决策变量实体化，再把电压/热越界转换成正确的 P/Q 控制动作。** 当前模型的几个关键缺口会造成“数值可行、工程不可执行”的假阳性：

- DER 只有 `kW` 容量，调度不含 `q_der`，`0.60 × GFM kW` 被当成统一无功能力；没有逆变器 `S` 圆约束。
- 非根孤岛把 `diesel + storage` 容量最大的节点任选为 slack，不验证该设备的 `gfm`、可用状态、启动状态、SOC 余量或该设备自身 P/Q/S 余量。
- 物理反馈仅对过载和**低电压**缩小 `served_load`；它完全没有处理 `Vmax`，而且削负荷会恶化 PV 反送导致的过电压。根网还被固定在 `1.05 pu`，恰好等于允许上限。
- 支路目前使用项目内硬编码 `capacity_kva`，仅校验发送端 `|S|`；没有持续/应急额定、温度降额、两端反向潮流校验、也没有电流口径。

因此实施顺序应为：**P0 数据和求解结果契约 → P0 GFM/DER capability gate → P1 SOCP/PQ 调度与线性化潮流约束 → P1 双向电压反馈与热限额 → UI/报告/回归。** 在该闭环落地前，界面和报告应称现有结果为“后验 P/Q 筛查”，不应称为已联合优化的物理可执行计划。

---

## 1. 当前实现的可核实事实与问题定位

| 主题 | 现状证据 | 物理/产品后果 | 风险 |
|---|---|---|---|
| DER P/Q/S | `network.py:60-84` 只存 PV、储能、柴油 `kW/kWh`；`dispatch.py:230-250` 只有 P、SOC、充放电约束；`powerflow.py:74` 将 `net_reactive_kvar` 固定为已供负荷 Q。 | PV/BESS/diesel 的 Q=0，却又在孤岛上用经验比例“提供”Q；高 P 时仍可凭空输出 Q。 | **P0-严重** |
| 孤岛 GFM | `_component_slack()` (`powerflow.py:123-129`) 用组件内 `diesel_capacity_kw + storage_power_kw` 最大的节点选 slack。 | 设备是否 GFM、是否开机、是否可黑启动、SOC 是否够、P/Q/S 是否够均未进入选择。 | **P0-严重** |
| 孤岛 Q | `dispatch.py:259-291` 将岛的 Q 上限写为 `0.60 × Σ(diesel kW + storage kW)`。 | kW 与 kvar 的固定换算不对应任意 inverter/柴油机 capability curve；也没有把 Q 分给具体设备。 | **P0-严重** |
| 孤岛有功 | `powerflow.py:384-440` 以选出的单个 slack 的 P 容量比对需求，却以组件总 GFM 容量计算 Q。 | P 与 Q 可用能力来自不同集合，且不满足同一设备的 `P²+Q²≤S²`。 | **P0-严重** |
| 电压控制 | `pipeline.py:100-114` 只在 `max_loading>100` 或 `min_voltage<0.95` 时给 `component_served_caps_kw`；完全未读 `max_voltage_pu`。 | PV 反送/轻载过电压不受控；削减负荷还会提高电压。 | **P0-严重** |
| 根网设定值 | `powerflow.py:406` 根组件 BFS 的 `slack_voltage_pu=1.05`；默认上限也是 1.05。 | 头端被钉在限值上，压缩上游过电压裕量并掩盖调压问题。 | **P0-高** |
| 支路热约束 | `network.py:32-43` 由支路编号生成假设 `capacity_kva`；`powerflow.py:193-211` 仅报发送端 `apparent_flow_kva`。 | 无温度/持续时间/来源，反向潮流及接收端损耗后的最大 S 未被严谨检查。 | **P0-高** |
| 反馈方向 | `pipeline.py:103-113` 把物理违约统一转换为“减少服务负荷”的标量上限。 | 对低压/过载可保守缓解；对过压、局部无功、局部热瓶颈不正确，也丢掉节点位置。 | **P0-高** |
| UI 带电状态 | `FaultState.energized_nodes` (`faults.py:29-34`) 仅为 root component；`app.py:106-109` 用它染色。 | 即使未来孤岛由 GFM 成功供电，界面仍会画成失电；评委会看到调度/拓扑矛盾。 | **P1-高** |
| 结果可追溯 | CLI 已导出 `hourly/branches/nodes/components`，但缺 asset P/Q/S、GFM 状态、两端 S/电流、限额来源和控制动作。 | 无法说明“谁在供无功、哪条线为何越限、为何弃光/削负荷”。 | **P1-中** |

### 本轮复跑观察

对当前 `台风` 场景，三策略 `FlowValidation.hourly.is_feasible` 均为 true，最大电压都恰为 `1.05 pu`，最低电压约 `0.972–0.976 pu`，最大支路负载率约 `71.7–74.9%`。这说明现有基准场景没有触发过压测试，而非已经证明高渗透 DER 下的过压控制有效；根节点固定为 `1.05 pu` 也使“最大值恰到上限”缺乏解释力。

`research_wave/microgrid_islanding.md` 的方向是正确的：每个孤岛必须先有 GFM，再做 P/Q/V/S 校验。下面的实施设计将其收敛为可落地的数据结构、约束、接口和测试。

---

## 2. 目标模型：统一符号、资源能力和潮流方程

### 2.1 统一符号与单位

- 所有网络功率在应用边界使用 `kW/kvar/kVA`；BFS/DistFlow 内部统一换为 p.u.，系统基准保持 `S_base=10,000 kVA`、`V_base=12.66 kV`。
- 对节点 (i)，取**负荷为正、DER 向网络注入为正**：

\[
P_i^{net}=P_{i}^{served}+P_i^{charge}-\sum_{a\in i}p_{a}
\]
\[
Q_i^{net}=Q_i^{served}+Q_i^{charge}-\sum_{a\in i}q_{a}
\]

其中 (q_a>0) 表示设备向网络注入无功（抬压），(q_a<0) 表示吸收无功（压低电压）。当前负荷采用恒功率因数缩放：

\[
Q_i^{served}=\frac{Q_{i,base}}{\max(P_{i,base},\epsilon)}P_i^{served}
\]

第一版保留该 PQ 负荷假设；后续 ZIP 负荷是 P2，不与本轮阻塞。

### 2.2 DER P/Q/S 约束（必须进调度器）

给每个物理资源 (a) 建立独立的 AC 并网点变量 ((p_{a,t},q_{a,t}))，并把 `s_available_kva` 当作可用而非铭牌额定：

\[
p_{a,t}^2+q_{a,t}^2\le (S_{a,t}^{available})^2
\]

这是 CVXPY/Clarabel 可直接表示的二阶锥：`cp.SOC(s_available, cp.hstack([p, q]))`。

**PV：**
\[
0\le p_{pv,t}\le \min(P^{weather}_{pv,t}, P^{nameplate}_{pv}),\quad
Q^{min}_{pv}\le q_{pv,t}\le Q^{max}_{pv},\quad p_{pv,t}^2+q_{pv,t}^2\le S_{inv}^2
\]

PV 的 curtailment 必须为 `P_weather - p_pv`；当 (p\) 接近 (S) 时，Q 裕量自动收缩为
\[
|q_{pv}|\le\sqrt{S_{inv}^2-p_{pv}^2}.
\]

**BESS（AC 侧）：**

\[
p_{b,t}=p_{dis,t}-p_{ch,t},\quad p_{ch},p_{dis}\ge0
\]
\[
E_{t+1}=E_t+\eta_c p_{ch,t}\Delta t-\frac{p_{dis,t}\Delta t}{\eta_d}
\]
\[
E^{min}\le E_t\le E^{max},\quad
p_{b,t}^2+q_{b,t}^2\le S_{b,inv}^2.
\]

MVP 使用 `p_ch + p_dis <= Pmax`、严格正的 throughput cost，并以测试断言禁止数值同时充放电；若需要“数学上绝对互斥”，升级到 MISOCP 或先把模式作为外部状态机确定，别在无二进制求解器下伪装成严格互斥。

**柴油机：**

\[
P^{min}_{d,t}\le p_{d,t}\le P^{max}_{d,t},\quad
Q^{min}_{d,t}\le q_{d,t}\le Q^{max}_{d,t},\quad
p_{d,t}^2+q_{d,t}^2\le S_{d}^{2}.
\]

启动/最小出力由运行状态机给出；第一阶段先把其 `available/started` 当成给定参数，避免在物理升级中同时引入机组组合复杂度。

**上级电网：**根节点 slack 的 (p_{grid},q_{grid}) 是 BFS 求出的平衡量，必须同时校验合同/变电站能力：

\[
0\le p_{grid}\le P_{grid}^{max},\qquad
p_{grid}^2+q_{grid}^2\le S_{grid}^{max,2}.
\]

默认根电压应为 `1.00 pu`，只有明确的 OLTC/tap 控制才允许在预先定义的离散/连续区间内调节，例如 (0.98\le V_{slack}\le1.02)，绝不把 1.05 当常数。

### 2.3 径向 BFS / DistFlow

现有 `_bfs_power_flow()` 可保留为数值内核，但输出需要扩展。对定向支路 (i\to j)：

\[
I_{load,j}=\overline{\frac{S_{net,j}}{V_j}},\qquad
I_{ij}=I_{load,j}+\sum_{k\in children(j)}I_{jk}
\]
\[
V_j=V_i-(r_{ij}+jx_{ij})I_{ij}.
\]

迭代收敛后，两端功率为：

\[
S_{ij}^{from}=V_i\overline{I_{ij}}S_{base},\qquad
S_{ij}^{to}=V_j\overline{I_{ij}}S_{base}.
\]

损耗：

\[
P_{loss,ij}=|I_{ij}|^2r_{ij}S_{base},\qquad
Q_{loss,ij}=|I_{ij}|^2x_{ij}S_{base}.
\]

需要同时输出 `p/q_from`、`p/q_to`、`s_from/s_to`、`s_max_kva`、`current_a`、`ampacity_a`、`loading_pct`。对有反向潮流的支路，热检查取两端最大：

\[
S_{ij}^{max} = \max(|S_{ij}^{from}|,|S_{ij}^{to}|),\qquad
I_{ij}=|I_{ij}^{pu}|I_{base}.
\]

### 2.4 支路热限额与温度降额

不要用 `capacity_kw = capacity_kva × 0.95` 做物理约束。为每条线定义一份单独的工程假设表；若有 ampacity，优先用电流约束：

\[
I_{base}=\frac{S_{base}}{\sqrt3V_{base}},\quad
I_{max,\ell,t}=I_{ref,\ell}\, f_T(T_{amb,t})\, f_{emg,t}.
\]

MVP 的温度函数可作为**显式工程假设**：

\[
f_T(T)=\operatorname{clip}\left(
\sqrt{\frac{T_{cond,max}-T}{T_{cond,max}-T_{ref}}}, f_{min}, f_{max}\right),
\]

并把 `T_cond_max/T_ref/f_min/f_max` 连同来源写入数据表。若只有 S 额定，则使用

\[
S_{max,\ell,t}=S_{cont,\ell}\,f_T(T_{amb,t})
\]

并将其标记为 `provisional_engineering_assumption`。所有报警必须区分 `continuous` 与 `emergency`，持续时间不得被静默混用。

### 2.5 GFM 孤岛门槛和 P/Q 平衡

每个非根连通分量先执行 `IslandAssessment`，再允许其服务任何负荷。候选设备 (a) 必须同时满足：

1. `gfm=True`、`black_start=True` 或已由上级网同步并网；
2. `availability[t]=True` 且已经过 `start_delay_h`；
3. BESS 有足够 SOC：
\[
E_{a,t}\ge E_{min}+\frac{P_{reserve}\Delta t}{\eta_d};
\]
4. 设备本身在求得 (p,q) 下满足 S 圆和 Q 上下限；
5. 预留频率/扰动裕量：
\[
P_{reserve}\ge\max(P_{largest\ step},P_{largest\ DER\ loss}),
\]
  第一版将它作为可审计 proxy，不把它冒充完整动态频率仿真。

MVP 选择一台明确的 `reference_gfm_asset_id` 作电压/相角参考；其他 GFM 先按给定 P/Q 或可选 participation factor 分担。BFS 求出的该参考机 P/Q 必须回写并做同一台设备的能力检查：

\[
\left|\sum_a p_a-\sum_iP_i^{served}-P_{loss}\right|\le\epsilon_P,
\]
\[
\left|\sum_a q_a-\sum_iQ_i^{served}-Q_{loss}\right|\le\epsilon_Q.
\]

任何一项不满足，岛状态只能是 `deenergized` 或 `infeasible`，并给出原因代码；禁止用 `source_adjustment` 填平。

---

## 3. 可直接实施的文件级改造方案

### 3.1 新增数据与类型（P0，先做）

| 文件 | 改造 | 必需字段/验收 |
|---|---|---|
| **新增** `data/der_assets.csv` | 将硬编码的 PV/BESS/diesel 从基准网络剥离为资源清单。每行一个物理 AC 设备，不把同一节点的柴油和 BESS 混成一个“容量”。 | `asset_id,bus_id,kind,p_min_kw,p_max_kw,q_min_kvar,q_max_kvar,s_rated_kva,availability_profile,gfm,black_start,start_delay_h,ramp_kw_per_h,energy_kwh,soc_min,initial_soc,eta_charge,eta_discharge,reserve_kw,source,assumption_class`。PV 还需 `p_weather_profile` / `dc_capacity_kw`；柴油可预留 `fuel_kwh`。 |
| **新增** `data/engineering_limits.csv` | 显式取代 `_thermal_limit_kva()` 的按编号猜测。 | `branch_id,ampacity_cont_a,ampacity_emergency_a,s_cont_kva,s_emergency_kva,temp_ref_c,conductor_max_c,source,assumption_class,valid_from,notes`。允许 ampacity 或 S 至少一个存在；缺失应是“未配置”，不是 0。 |
| **新增** `src/gridrescue/assets.py` | 定义 `DERAsset`、`DERFleet`、`BranchLimit`、`IslandAssessment`、`PhysicalEnvelope` dataclass；集中校验单位、唯一 ID、bus ID、`s_rated≥|p|max`（若有）。 | `validate_asset_table()`、`validate_limit_table()` 输出可读错误；所有输入保留 `source/assumption_class`。 |
| `src/gridrescue/network.py` | `GridModel` 增加 `der_assets` 与 `branch_limits` DataFrame；`build_ieee33()` 从 CSV 载入。节点表保留聚合展示字段，但不再是优化真源。保留 `capacity_kva` 一版兼容别名，新增 `thermal_configured`，下一版删除 `capacity_kw/power_factor_assumption`。 | `graph_from_state()` 继续只传 R/X/branch ID；不要把限额写死到图边。 |

**数据迁移原则：**现有节点 13、29 的储能和 17、29 的柴油只是默认情景的初始资源位置。`gfm/black_start/S_rated/Q_limit` 均须在新表明确赋值；在未获得设备规格前用 `engineering_assumption_v1` 标记，界面和报告暴露该假设。

### 3.2 岛屿状态机（P0）

| 文件 | 改造 | 关键实现点 |
|---|---|---|
| **新增** `src/gridrescue/islanding.py` | 实现 `assess_islands(model, topology, fleet_state, hour)`。 | 每岛返回 `island_id,nodes,root_connected,status,reason_code,reference_gfm_asset_id,stage,p_reserve_kw,q_reserve_kvar,soc_margin_kwh`。原因代码至少：`NO_GFM`,`GFM_UNAVAILABLE`,`START_DELAY`,`SOC_RESERVE`,`P_LIMIT`,`Q_LIMIT`,`S_LIMIT`,`BLACK_START_SEQUENCE`,`NON_RADIAL`,`SYNC_REQUIRED`。 |
| `src/gridrescue/faults.py` | `FaultState` 不再把 root component 等同于“全部带电”；保留 `root_energized_nodes`，新增岛候选元数据或由 `islanding.py` 填写 `energization_status_by_component`。 | 拓扑层只回答“可连通”；运行层回答“是否实际带电”。避免 `energized_nodes` 语义混淆。 |
| `src/gridrescue/restoration.py` | `state_at_hour()` 保持拓扑纯函数；在 `build_node_demand_frame()` 之后/调度之前评估每个岛。开关动作添加 `preconditions/result/reason_code`，要求 `radial + GFM + sync + remote_ok`。 | 失去 GFM 的岛：全量负荷失供、PV 按 grid-following 限制弃电；合格岛才进入 P/Q 调度。 |
| `app.py`、`report.py` | 网络图按实际状态区分 `root_energized / island_gfm / deenergized / infeasible`；动作时间线显示 GFM、黑启动阶段、失败原因。 | 不能再用 `state.energized_nodes` 的 root-only 集合给孤岛染色。 |

### 3.3 调度器：从 P-only 到节点/资产 P/Q SOCP（P0→P1）

| 文件 | 改造 | 关键实现点 |
|---|---|---|
| `src/gridrescue/dispatch.py` | 把 `ResourceConfig` 从全局聚合备用配置缩减为求解参数；主输入改为 `DERFleet + node_demand + IslandAssessment + PhysicalEnvelope`。 | 增加 `p_der[asset,t], q_der[asset,t]`，BESS 的 SOC、PV curtailment、每岛 P/Q 平衡、每资产 S 圆、Q 上下限、GFM reserve。 `served_reactive_kvar` 保留；新增 `pv_q_kvar,bess_q_kvar,diesel_q_kvar,der_p_kw,der_q_kvar,der_s_kva,q_headroom_kvar`。 |
| `src/gridrescue/restoration.py` | `build_node_demand_frame()` 增加 `base_p_kw/base_q_kvar` 与 `component_key`；不要只把 `reactive_ratio` 当作 Q 的唯一表示。 | 负荷优先级仍由 `critical_level` 处理；按节点保留 P/Q，方便物理反馈进行局部约束。 |
| `src/gridrescue/powerflow.py` | `_node_dispatch()` 从 node_frame 接收明确的 `der_p/q` 聚合，构造准确 `net_load_kw/net_reactive_kvar`。 | 移除“Q 等于负荷且所有 DER Q=0”的隐式规则。对非根岛，由 `reference_gfm_asset_id` 做 slack；解后回写该设备所需 P/Q 并校验其 circle。 |

**推荐求解分层：**

1. 固定开关拓扑、固定 GFM 候选和上一轮工作点；
2. 以 LinDistFlow / branch-flow SOCP 给 dispatch 施加节点电压和支路 S 约束；
3. 用现有 BFS 作真值验证；
4. 若超容差，生成局部 `PhysicalEnvelope` 后重解；最多 6–8 轮，若无单调改善返回 `infeasible` + 失败代码，而非伪收敛。

### 3.4 潮流与热限额（P0→P1）

| 文件 | 改造 | 关键实现点 |
|---|---|---|
| `src/gridrescue/powerflow.py` | 扩充 `_bfs_power_flow()` 返回两端 P/Q/S、`current_pu/current_a`、`rating_*`、`thermal_margin`；支持从资产清单而非节点总量获得 Q。 | 根电压默认 1.0。`SnapshotFlow` / `FlowValidation` 加 `root_p_kw/root_q_kvar/root_s_kva`、`max_current_loading_pct`、`max_s_loading_pct`、`min_q_headroom_kvar`、`overvoltage_node_count`。 |
| `src/gridrescue/powerflow.py` | 新增 `build_linearized_constraints(...)`，为每个固定径向分区建立 P/Q→V 和 P/Q→branch-flow 的局部线性/SOCP包络。 | 用 (w=|V|^2)：`w_j≈w_i−2(rP+xQ)`；热约束用 `SOC(Smax,[P,Q])`。BFS 保持唯一最终裁判。 |
| `src/gridrescue/pipeline.py` | 将当前标量 `component_served_caps_kw` 替换为 `PhysicalEnvelope`。 | Envelope 至少分开：`service_cap_by_node`、`pv_p_upper_by_asset`、`q_min/q_max_by_asset`、`branch_flow_margin`、`reason_codes`；不得把所有问题压成总服务上限。 |

### 3.5 双向电压/热反馈（P1）

当前反馈规则只知道“供电少一点”。新规则按违约类型选择控制杠杆：

| BFS 发现 | 首选控制 | 次选 | 最后手段 | 禁止动作 |
|---|---|---|---|---|
| `V < Vmin` | 就地 DER 注入 Q（正 q）且保持 S 圆 | 减少该下游服务负荷；调整根 tap（若配置） | 拓扑重构/延迟冷负荷 | 用上游/远端虚拟 Q 填平 |
| `V > Vmax` | 就地 PV/BESS 吸收 Q（负 q） | BESS 充电 | 限该 PV 的 P/弃光、重构 | 仅削减负荷；这通常会更高压 |
| `S/I > limit` 且正向 | 降下游服务/移供 | 本地 P/Q 重分配、闭合有效 tie | 限发/弃光 | 只看 P 而忽略 Q |
| `S/I > limit` 且反向 | 吸收 Q、BESS 充电 | 限相邻 DER P/弃光 | 拓扑重构 | 用容量为 kW 的阈值判合格 |
| GFM P/Q/S 或 reserve 失败 | 先在该岛削低优先级负荷 | 换合格 GFM/延迟启动 | 该岛 deenergize | 将缺口记成 slack adjustment |

局部灵敏度可由每轮 BFS 做数值差分或从线性化 branch-flow 提取：

\[
\Delta w \approx J_P\Delta p^{inj}+J_Q\Delta q^{inj}.
\]

反馈产生的约束要包含 `asset_id/node_id/hour/cause/target_margin`；最终 CSV 能回答“第 12 小时 N30 的 PV 为何弃了 34 kW、BESS 吸收了多少 kvar”。

---

## 4. 实施次序、接口契约与回滚点

### Milestone A — 可审计能力数据与 GFM gate（答辩前 P0）

1. 新增两个 CSV 与 `assets.py`，`GridModel` 加载、校验并导出；保留旧节点聚合字段用于 UI 兼容。
2. 实现 `islanding.py`，将 source-free、PV-only、SOC reserve、GFM false、启动未完成全部硬判为不带电。
3. `powerflow.py` 改根电压为 `1.00 pu`，明确产生/消费 Q；BFS 输出两端 S/电流。
4. 所有接口先追加字段，不删除现有 `dispatch.frame` 列；旧报告读取字段不受影响。

**验收门槛：**`NO_GFM`、`SOC_RESERVE`、`S_LIMIT` 任一触发时，`is_feasible=False`、岛内 `energized=False`、报告有原因代码；没有 `source_adjustment` 被视为电源。

### Milestone B — P/Q/S SOCP 调度与约束反馈（P1）

1. `dispatch_resources_spatial()` 引入 asset P/Q variables 和 SOC circle，输出 asset_frame；每岛 P/Q 平衡进入优化器。
2. `build_linearized_constraints()` 对固定拓扑加入 (V^2) 与 branch S SOC 约束。
3. `PhysicalEnvelope` 取代 `component_served_caps_kw`，实现过压/过载的方向正确控制。
4. 先完成单一根网、单一孤岛、单时段，再接回 24h、三策略、碳约束。

**验收门槛：**BFS 后所有电压、两端 S/电流、每 asset P/Q/S、每岛 P/Q 残差均在容差内；若反馈失败，状态为 `infeasible` 而不是仅修改展示数字。

### Milestone C — 运行可解释性（P1）

1. CLI 额外输出 `der_dispatch_*.csv`、`islands_*.csv`、`constraint_events_*.csv`、`engineering_limits_used.csv`。
2. UI 增加 `max voltage`、`max S/I loading`、`Q headroom`、GFM 名称/SOC/reserve、过压控制动作；图上显示实际岛状态。
3. 报告把“工程假设/限额来源/温度降额”和“不可行原因”写入 MRV 附录。

### Milestone D — P2（不阻塞 P0/P1）

- 多 GFM droop/下垂共享、同步合闸过程、柴油燃料与最小开停机、ZIP 负荷、三相不平衡、完整动态频率、N-1 和气象线路动态热额定。

---

## 5. 必须新增的回归测试

建议拆为 `tests/test_assets.py`、`tests/test_islanding.py`、`tests/test_powerflow_constraints.py`、`tests/test_physical_feedback.py`；保留 `test_core.py` 的 case33 基准 smoke test。

| 优先级 | 测试场景 | 输入构造 | 关键断言 |
|---|---|---|---|
| P0 | DER 圆约束：PV 满发 | `S=100 kVA, p=100 kW` | `abs(q)<=ε`；任意试图 `q!=0` 均令优化收缩 P 或判不可行。 |
| P0 | DER 圆约束：部分 P | `S=100, p=80` | `|q|<=60 kvar`；`p=80,q=60` 可行，`q=60.01` 违约。 |
| P0 | BESS 双向 P/Q | 放电 `+60 kW` 和充电 `-60 kW`，`S=100` | 两个方向均可有 `|q|≤80`；SOC 方程、效率和 S 圆同时满足。 |
| P0 | 高 Q 热过载 | 构造 `P=0.9S,Q=0.6S` 的支路 | `P` 未超过任意旧 kW 上限但 `sqrt(P²+Q²)>S`，必须 `thermal_violation=True`。 |
| P0 | 双端/反向校验 | 高 PV 反送且有损耗 | `max(abs(S_from),abs(S_to))` 被用作负载率；正反向都触发相同热逻辑。 |
| P0 | PV-only 孤岛 | 非根岛仅有 `gfm=False` PV | `status=NO_GFM`，所有岛内服务为 0，PV 弃电，电压不伪造为 1.0。 |
| P0 | BESS-GFM SOC 余量 | 同一岛设置低/高 SOC | 低 SOC 为 `SOC_RESERVE`；高 SOC 且 P/Q/S 合格才 `energized`。 |
| P0 | GFM S 耗尽 | 岛有足够 kW、但功率因数低使所需 Q 大 | 必须 `S_LIMIT` 或削负荷；不可用组件总 `0.6×kW` 通过。 |
| P0 | 启动/黑启动 | diesel `gfm=True,start_delay_h=2`，在 T0/T2 请求服务 | T0 `START_DELAY`，T2 才可进入站用/关键负荷阶段；冷负荷阶跃不得超 reserve。 |
| P0 | 根电压 | 正常工况 | root BFS 电压默认 `1.0`，不是 `1.05`；上下限单独检查。 |
| P1 | 轻载高 PV 过电压 | 下游 PV 可用高、负荷低、BESS 可充 | 初始 BFS `V>1.05`；反馈先 `q_pv<0`/`q_bess<0`，必要时充电/弃光；最终 `V≤1.05`。 |
| P1 | 过压方向性 | 固定高 PV 反送 | 验证“单独削减负荷”不被用作主要缓解动作，且不会被标成成功控制。 |
| P1 | 低压 Q 支撑 | 远端重负荷、PV/BESS 有 Q headroom | 调度给局部 `q_der>0`，BFS 后 V 改善，同时 `P²+Q²≤S²`。 |
| P1 | 温度降额 | 相同潮流，在 `T_ref` 与高温时比较 | 高温 `Imax/Smax` 下降；基准合格、高温可变为热违约；导出来源/参数。 |
| P1 | 反馈收敛/失败 | 分别构造可控和不可控过压 | 可控时在迭代上限内收敛；不可控时返回 `infeasible + OVERVOLTAGE_UNCONTROLLABLE`，不得假设已可行。 |
| P1 | UI/导出语义 | 成功 GFM 岛 + 失败岛各一个 | `islands.csv`、`asset_frame`、UI 节点状态与实际调度一致；根外成功岛显示为带电。 |
| P0 | 全量回归 | 三个既有场景 + base case | case33 基准依旧匹配 golden；三策略不出现无解释的 slack；旧公共列保持兼容。 |

建议对每个 SOCP/BFS 工况增加两个硬断言：

\[
\max_a\left(\sqrt{p_a^2+q_a^2}-S_a\right)\le10^{-4}\ \mathrm{kVA}
\]

\[
\max_c\{|\Delta P_c|,|\Delta Q_c|\}\le10^{-3}\ \mathrm{kW/kvar}
\]

其中 (c) 是根网或已带电孤岛；数值阈值在报告中注明单位和求解容差。

---

## 6. 风险排序与处置

| 排名 | 风险 | 为什么会伤答辩可信度 | 处置 | 完成定义 |
|---:|---|---|---|---|
| 1 | GFM 被“最大 kW 节点”替代 | 无 GFM/低 SOC/未启动的孤岛仍可能被派发，违反微网基本运行条件。 | `islanding.py` + 资源状态机 + reference GFM capability check。 | 每岛有唯一可追溯 GFM 或明确失电原因。 |
| 2 | DER 无 S 圆/Q 决策 | 报告声称 P/Q 校验，但 Q 并非由任何具体设备供给。 | asset P/Q/S SOCP，输出 per-asset P/Q/S headroom。 | 所有资产 S 圆、Q range、SOC 通过独立测试。 |
| 3 | 过电压未闭环且根置 1.05 | 高 PV 情景极易被评委一改参数就穿帮；现有反馈方向还会相反。 | 根设 1.0；`PhysicalEnvelope` 按 Q 吸收/充电/弃光控制。 | 轻载高 PV 测试从违约到可控或明确不可控。 |
| 4 | 热限额只有硬编码单端 S | 容量来源不透明，高 Q/反送情况下漏报过载。 | `engineering_limits.csv` + 双端 S/I + 温度降额。 | 每条启用约束的 source/assumption 可导出。 |
| 5 | 后验 P-only 标量反馈 | 局部物理违约被全组件削负荷，策略含义失真。 | 先接线性化 P/Q/S 约束，再保留 BFS 终检。 | 控制事件解释到 bus/asset/branch/hour。 |
| 6 | 拓扑“连通”与运行“带电”混淆 | 成功的 GFM 島在 UI 仍红色，或失败岛被视觉上误称恢复。 | 分离 `topology status` 和 `energization status`。 | UI、CSV、报告三者状态一致。 |
| 7 | 物理升级与碳模型耦合返工 | PV 弃光/BESS 充放电改变 MRV 能量流，旧碳账可能不守恒。 | Milestone B 后同步扩展 `carbon.py` / MRV 测试，但不阻塞 P0。 | PV 直供/充电/弃光和 BESS 能量守恒一致。 |
| 8 | 求解性能和可行性震荡 | 24h×33 bus×多策略的重复 BFS/SOCP 可能超出演示时间。 | 固定拓扑热启动、缓存 sensitivity、限制 6–8 轮，失败可解释。 | 典型场景 30–60 秒内完成；迭代次数/残差导出。 |

---

## 7. 建议的首个 PR 切分

**PR-1（P0，数据+状态，不碰策略目标函数）**

- 新增 `data/der_assets.csv`、`data/engineering_limits.csv`、`src/gridrescue/assets.py`、`src/gridrescue/islanding.py`。
- `network.py` 加载并验证，`faults.py` 分离 root 连通与运行带电语义。
- `powerflow.py` 根电压=1.0，输出两端 S/电流，但暂不改变旧 dispatch 的 P 目标。
- 新增数据、GFM、热双端、根电压测试。

**PR-2（P0，资产 P/Q/S + 岛平衡）**

- `dispatch.py` 加 asset P/Q variables、SOC/S 圆、每岛 P/Q balance；`powerflow.py` 从 asset_frame 取 net Q 并核 reference GFM。
- 移除 `island_q_support_ratio` 作为可行性判据（可保留为默认资产参数生成器，不可作为物理约束）。
- 新增 P/Q/S、SOC/GFM/black-start 测试。

**PR-3（P1，联动电压/热与可解释性）**

- `pipeline.py` 用 `PhysicalEnvelope` 和线性化 SOCP 取代 `component_served_caps_kw`；实现过压控制路径。
- `app.py`、`cli.py`、`report.py` 导出并展示 asset/island/constraint event 数据。
- 加高 PV 过压、高 Q 热过载、温度降额、反馈收敛回归。

这个切分使每个 PR 都能独立回归，并避免同时重写网络、调度、MRV 和 UI 造成不可定位的数值错误。

---

## 8. 最小验收看板（建议答辩前冻结）

1. 基准 `case33bw`：与锁定 golden 的 (V,P,Q,loss) 对标通过。
2. 每小时、每个带电分区：P/Q 平衡残差、GFM ID、SOC/reserve、最小/最大电压、最大两端 S/I loading 都可导出。
3. 每个 DER：`p,q,s,q_headroom,availability,gfm` 可导出，且 S 圆逐项通过。
4. 轻载高 PV、重载低压、高 Q 热过载、无 GFM、SOC 低、启动延迟六类异常均有自动化测试。
5. 不可行时：界面显示“不可行 + 原因 + 哪个约束”，不显示“恢复成功”；报告不把不可供的岛计入恢复率。

完成以上五项后，GridRescue 才能把“P/Q、孤岛、热稳校验”从后验展示升级为可复算、可解释、能经受参数扰动的恢复调度物理内核。
