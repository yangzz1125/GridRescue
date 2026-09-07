# GridRescue Wave 3：医院生命线临床任务链 MVP 设计

> **范围**：将当前“关键负荷恢复率”升级为可解释的医院生命线任务链：任务、依赖、最迟启动/完成时限、最小持续时间、供电电压带和冷负荷启动共同决定“临床可用性”。
>
> **本文件只定义产品与模型设计，不改动当前代码。** 现有网络仍为 MATPOWER `case33bw`；医院标签、DER 布置、临床任务参数和情景结果均须按**合成原型**表述。

---

## 1. 为什么要从“关键负荷”走到“临床任务”

当前仓库把 `critical_level >= 2` 的节点负荷统一汇总为 `critical_load_kw`，并以 `critical_recovery_pct`、`critical_eens_kwh` 评价恢复。这个口径适合第一版配网恢复，但会掩盖三个答辩漏洞：

1. **同样是 90 kW 已供电，临床状态不同。** 先恢复通信/控制，再启动 ICU 支撑、急诊分诊、冷链，和随机给一个连续 90 kW 是不同的恢复计划。
2. **任务有时序与前置条件。** 一个冷链负荷有保冷余量、压缩机启动冲击与供电质量要求；它不是“某小时累计多给几度电”即可等价替代。
3. **当前关键负荷百分比并未约束电压、启动峰值和任务完成时间。** 这会造成“关键恢复率 100%，但关键任务仍错过时限”的叙事风险。

可靠供电支撑医疗设备、照明、通信、清洁供水与紧急处置是卫生设施韧性的基础；医院也应按应急计划配置并测试应急/备用电力。该 MVP 借此把“保供”表述为**通用设施运行任务的仿真指标**，不把它表述为真实临床决策或患者级处置。资料见文末来源。 

**MVP 的判断单位**：不是病人、病历或医疗指令，而是 `CareTask`（一项匿名化的设施/科室运行任务）。输出是“任务在仿真中是否按条件完成”，不是医疗建议。

---

## 2. 设计目标、非目标与验收口径

### 2.1 目标

- 以 24 h 恢复窗口为单位，把 N03、N18 的医院/应急负荷拆为有限个可解释任务；
- 使每个任务同时受 **拓扑带电、可用功率、依赖、deadline、min_duration、设备电压带、启动冲击** 约束；
- 复用现有 `RestorationPlan → node_demand → spatial dispatch → powerflow` 主线，不把“临床评分”伪装成电气约束已内嵌；
- 输出任务级 KPI、事件日志和 UI 解释，使评委能看到策略为什么先恢复某一项；
- 默认使用可复现的合成任务库，并清楚声明数据边界。

### 2.2 非目标（MVP 不宣称）

- 不模拟患者生理、设备内部控制、药品/疫苗真实温控曲线或医院真实应急预案；
- 不把 N03/N18 解释为任何真实医院或真实馈线；
- 不以目前的后验潮流检查替代现场保护、同期、短路容量、ATS、隔离开关和设备铭牌校核；
- 不向现场下发开关、发电机或医疗设备控制命令。

### 2.3 MVP 验收口径

一项任务仅在下列条件同时满足时记为 `completed_on_time`：

1. 任务所在节点/孤岛在对应时间段有可用电源；
2. 已供功率覆盖该任务运行功率与启动事件需要；
3. 前置任务已经完成；
4. 任务连续运行达到 `min_duration_h`；
5. 任务启动和运行时的节点电压均处于该任务配置的带内；
6. 启动时刻不晚于 `latest_start_h`，且如配置了完成期限，完成时刻不晚于 `deadline_h`。

任何条件缺失，UI 需显示**具体阻塞原因**：`deenergized`、`power_shortfall`、`dependency_pending`、`deadline_missed`、`voltage_out_of_band` 或 `cold_start_headroom_shortfall`。

---

## 3. `CareTask` 数据模型

### 3.1 核心对象

建议任务记录采用 YAML/CSV 维护、Pydantic/dataclass 读取。字段分四层：身份、运行、时序、可审计来源。

| 字段 | 类型 / 单位 | 含义 |
|---|---|---|
| `task_id` | string | 全局稳定 ID，如 `N18-ICU-SUSTAIN` |
| `facility_id` / `facility_label` | string | 合成医院园区 ID / 展示名称 |
| `node_id` | int | case33 的 0-based 节点 ID；UI 同时显示 Nxx |
| `service_group` | enum | `core_power`、`acute_care`、`cold_chain`、`water_air`、`it_comms` 等设施任务分组 |
| `priority` | 1..5 | 仅用于资源不足时的排序；不替代 deadline |
| `nominal_kw` | kW | 稳态运行有功功率 |
| `power_factor` | 0..1 | MVP 的无功近似；由 `nominal_kw*tan(arccos(pf))` 生成 kvar |
| `min_kw` | kW | 达到“已运行”判定的最小供电功率；通常等于或略小于 `nominal_kw` |
| `voltage_min_pu` / `voltage_max_pu` | pu | 稳态节点电压带，作为任务可用性门槛 |
| `latest_start_h` | h from incident | 最迟启动时刻 |
| `deadline_h` | h from incident, nullable | 最迟完成时刻；为空表示只检查最迟启动 |
| `min_duration_h` | h | 连续最小运行时间；完成后可进入 `sustained` 或允许停机 |
| `dependencies` | `task_id[]` | 必须先完成的 DAG 前置任务 |
| `preemptible` | bool | 是否可在已完成最小时长后被降载/停止 |
| `restart_limit` | int | 窗口内允许重新启动次数 |
| `cold_start` | object / null | 启动峰值、持续分钟数、最小关机时间、启动电压门槛 |
| `thermal_holdover_h` | h, nullable | 适用于冷链类的合成保冷余量；超过即为业务 SLA 违约 |
| `source_class` | enum | 固定为 `synthetic_mvp_v1`，防止误读为医院台账 |
| `assumption_note` | string | 参数由何种演示假设产生、未来由谁确认 |

推荐的 `cold_start` 子结构：

```yaml
cold_start:
  start_kw: 18.0                 # 启动瞬时/15 min 峰值，不是额外 1 h 稳态负荷
  start_duration_min: 10
  startup_voltage_min_pu: 0.92
  min_off_h: 0.25
  max_parallel_starts_at_node: 1
```

### 3.2 状态机

```text
pending
  ├─[节点带电 + 依赖完成 + 启动容量/电压足够]→ starting
  ├─[超过 latest_start_h]→ missed
starting
  ├─[启动窗口通过]→ running
  └─[功率或启动电压不够]→ blocked_cold_start → pending
running
  ├─[连续达到 min_duration_h]→ completed_on_time / completed_late
  ├─[供电或运行电压失效]→ interrupted
  └─[可抢占且完成最小时长]→ standby
interrupted
  ├─[restart_limit 未耗尽]→ pending
  └─[超过重启限制或期限]→ missed
```

`completed_on_time` 代表一次仿真内的服务 SLA，而不是临床安全或患者结果。任务状态转换必须落入 append-only 事件表，不能只保留最终颜色。

### 3.3 时间分辨率与冷负荷处理

现有调度/潮流链是 1 h 步长。MVP 保持这个主步长，同时把冷启动作为该小时内的一个 15 min 事件：

- **能量入账**：
  \[
  E_{start}=P_{start}\times duration_{min}/60
  \]
- **容量/电压门槛**：在启动子时段按 `P_start` 而不是小时均值进行功率与电压校验；
- **同节点并发**：默认 `max_parallel_starts_at_node=1`，避免多个电机/冷机在一个 15 min 窗口同时冲击；
- **降级原则**：若暂时没有 15 min 潮流子算例，启动当小时用 `P_start` 做保守 peak gate，并在结果中写 `startup_voltage_check=conservative_hourly_proxy`。不得把平均功率通过而峰值未检验称作已通过。

---

## 4. case33 映射：从现有“关键负荷”到医院任务池

### 4.1 当前已确认的模型事实

`src/gridrescue/network.py` 当前明确将两个节点标注为 `医院/应急`，且均为 `critical_level=3`：

| case33 ID | UI 标签 | 当前负荷 | Q | 现有资源 | 推荐合成角色 |
|---:|---|---:|---:|---|---|
| `2` | N03 | 90 kW | 40 kvar | 无 PV / 储能 / 柴油 | **H-A：上级电源依赖型急救医院** |
| `17` | N18 | 90 kW | 40 kvar | PV 260 kW、柴油 220 kW | **H-B：具备本地 DER 的应急医疗枢纽** |

现有其他 L3 节点 N06（通信/数据）、N14（综合能源站）、N25（通信/数据）、N30（综合能源站）仍保留为普通“关键基础设施”；本波**只将 N03、N18 拆成 CareTask**。这能让医院任务链与通信、能源站之间形成可展示的跨节点依赖，而不在 MVP 中虚构整座城市医院网络。

### 4.2 功率守恒与避免双计数

N03/N18 的任务运行功率是对现有各自 **90 kW 基线负荷的分解**，不是额外叠加的新负荷：

\[
\sum_{k \in node\ n} P^{nominal}_k = 90\;kW
\]

对每个小时，医院节点的默认 `base_load_kw × load_multiplier` 应被任务池需求**替换**，而不是与任务池相加。任务全启动时的稳态功率不应超过该节点的合成功率预算；冷启动峰值仅在短子时段作为附加启动门槛计入。

N03/N18 以外，当前 `critical_level >= 2` 的聚合逻辑保持不变。这样可保证：

- 原有三策略对照可继续运行；
- 未启用医院任务模式时，基线输出应逐行回归一致；
- 启用后，`critical_recovery_pct` 只作为电力层 KPI，临床层另报 `task_sla_pct`，二者不得互相冒充。

### 4.3 建议的合成任务集（总稳态功率各 90 kW）

以下是**演示参数，不是设备铭牌、临床规程或真实医院负荷曲线**。它们刻意将“先使系统可控、再开高优先任务、最后启动可延后负荷”的因果链做得可见。

| 任务 ID | 节点 | 合成设施任务 | kW / pf | 最迟启动 | 最小持续 | 依赖 | 电压带 | 启动特征 |
|---|---|---|---:|---:|---:|---|---|---|
| `N03-CORE` | N03 | 应急照明、控制、通信底座 | 12 / .95 | 0.25 h | 24 h | — | 0.90–1.10 | 无 |
| `N03-ICU` | N03 | 重症支撑区连续供电 | 30 / .92 | 0.50 h | 24 h | `N03-CORE` | 0.90–1.10 | 无 |
| `N03-ED` | N03 | 急诊分诊与处置区 | 18 / .95 | 1.00 h | 12 h | `N03-CORE` | 0.90–1.10 | 无 |
| `N03-O2-WATER` | N03 | 医用支持公用工程 proxy | 20 / .88 | 2.00 h | 8 h | `N03-CORE` | 0.92–1.08 | 36 kW / 10 min |
| `N03-COLD` | N03 | 药品/样本冷链 proxy | 10 / .86 | 3.00 h | 20 h | `N03-CORE` | 0.92–1.08 | 24 kW / 10 min；holdover 4 h |
| `N18-CORE` | N18 | 应急照明、控制、通信底座 | 12 / .95 | 0.25 h | 24 h | — | 0.90–1.10 | 无 |
| `N18-ICU` | N18 | 重症/隔离支撑区 | 30 / .92 | 0.50 h | 24 h | `N18-CORE` | 0.90–1.10 | 无 |
| `N18-ED` | N18 | 急诊分诊与转运区 | 18 / .95 | 1.00 h | 12 h | `N18-CORE` | 0.90–1.10 | 无 |
| `N18-COLD` | N18 | 冷链 proxy | 12 / .86 | 3.00 h | 20 h | `N18-CORE` | 0.92–1.08 | 28 kW / 10 min；holdover 4 h |
| `N18-WATER-AIR` | N18 | 公用工程/洁净支持 proxy | 18 / .88 | 2.00 h | 8 h | `N18-CORE` | 0.92–1.08 | 32 kW / 10 min |

**关键叙事差异**：

- N03 没有本地 DER。若上游不能重新供电，其高优先任务被如实标为 `deenergized`，而非让关键负荷百分比掩盖该事实。
- N18 有 260 kW PV 与 220 kW 柴油这一**现有合成网络假设**。当 L17 断开而该孤岛具备合法 grid-forming 条件时，可展示“先 CORE，再 ICU/ED，再按启动峰值顺序启动 COLD/WATER-AIR”的恢复过程。
- N18 的联络线 L36（N18–N33）仅是候选恢复路径。是否闭合必须继续通过现有的径向拓扑检查及后续电压/热稳定门，不能在 UI 中预置为必然成功。

---

## 5. 任务链如何接入现有求解链

### 5.1 推荐的 MVP：候选任务时序 + 现有调度/潮流筛选

当前 `dispatch_resources_spatial()` 是连续 CVXPY 调度，不能天然表达二元“任务是否开始”。为了不在首版引入未验证的 MIP 求解器，MVP 采用小规模、可枚举的任务状态机：

```text
RestorationPlan（故障、抢修、联络线）
  → 每小时拓扑/孤岛状态
  → CareTask scheduler（依赖 DAG、deadline、冷启动窗口、优先级）
  → node_task_demand[t,node] + startup_peak[t,node]
  → 现有 spatial dispatch / powerflow
  → feasibility gate（功率、节点电压、热稳定、孤岛平衡）
  → 接受任务状态或回退至下一个可行候选
```

任务数固定为 10 个，候选动作只在 deadline、依赖解锁、节点恢复、可启动时刻发生变化；因此可用 beam search / 优先队列在 24 h 内生成有限候选，不需要枚举所有 `2^(10×24)` 排程。

**候选排序**（清晰且可解释）：

1. deadline 余量最小；
2. 任务优先级最高；
3. 下游依赖数最多；
4. 启动峰值较小或当前节点启动裕量较大；
5. 碳韧策略中，在前四项相同的前提下优先 PV 可用、低柴油边际供电的候选。

碳因素永远排在生命线时限与可行性之后，避免把“少柴油”误解为可以牺牲时间敏感任务。

### 5.2 与已有数据帧的接口契约（计划，不是当前实现）

建议新增以下中间表，而非改写原始网络表：

```text
clinical_task_schedule.csv
  scenario_id,strategy,hour,task_id,node_id,state,requested_kw,
  startup_peak_kw,served_kw,voltage_pu,block_reason,started_at_h,
  completed_at_h,sla_status

clinical_node_requirements.csv
  scenario_id,strategy,hour,node_id,task_requested_kw,task_min_kw,
  startup_peak_kw,task_reactive_kvar,task_count_running,
  must_serve_floor_kw
```

对 N03/N18，`build_node_demand_frame()` 的概念性改造为：

```text
existing base demand at node
  └─ replace with task_requested_kw + optional non-clinical residual
node task requirement
  ├─ normal/run power → dispatch demand and service allocation
  └─ start peak        → 15 min gate / conservative hourly peak gate
```

调度完成后，以节点实际 `served_load_kw` 按以下顺序分配给已请求的任务：已连续运行且不可抢占任务 → 即将超时任务 → 解锁下游依赖任务 → 可抢占/可延后任务。某任务不得从多节点“拼凑”功率；其供电必须完全归属其 `node_id` 与当前连通组件。

### 5.3 可行性门：功率门、物理门、服务门

任务调度候选只有通过全部门控才可进入结果：

| Gate | 判定 | 用现有链路的接点 |
|---|---|---|
| G1 拓扑/带电 | 节点在根网或存在已确认 grid-forming 的可运行孤岛 | `state_at_hour()` / `evaluate_state()` |
| G2 功率 | `served_kw >= min_kw`；启动时有 `P_start` 裕量 | `dispatch.node_frame` |
| G3 电压 | 对每个运行任务：`v_min <= voltage_pu <= v_max`；启动子时段另验 `startup_voltage_min_pu` | `powerflow` 节点结果 + 启动子算例 |
| G4 热/孤岛 | 最大线路负载率不超阈，孤岛无虚构 slack 调整 | 现有 powerflow 验证结果；下一版收紧为优化内约束 |
| G5 服务 | 依赖、deadline、连续时长、重启限制满足 | CareTask state machine |

MVP 需要在报告中诚实写为“**调度后任务可行性筛选**”；只有将 G2–G4 联合写入优化器后，才能称为“任务约束内嵌优化”。

### 5.4 后续一体化 MILP 路线

第二阶段可把开始变量 `u[k,t]`、运行变量 `r[k,t]`、完成变量 `c[k,t]` 写为 binary；用固定任务需求连接现有连续资源调度：

\[
P_{node,t}^{task}=\sum_{k\in node}(P_k^{run}r_{k,t}+P_k^{start}u_{k,t})
\]
\[
r_{k,t} \ge u_{k,\tau},\quad t\in[\tau,\tau+L_k-1]
\]
\[
u_{k,t}\le \sum_{\tau\le t}c_{d,\tau},\quad \forall d\in Dep(k)
\]
\[
\sum_{t\le latestStart_k}u_{k,t}=1\quad \text{for mandatory task}
\]

候选须再受节点电压、支路热限与孤岛电源约束。此为 V2，不应阻塞 V1 先形成可演示、可测试的任务链。

---

## 6. KPI：电力层、任务层与公平比较

### 6.1 保留的电力层 KPI

保留并继续展示：`critical_eens_kwh`、`critical_recovery_pct`、总 EENS、柴油能量、PV 消纳、总碳排、最小电压、最大支路负载率、孤岛数量、修复动作数。

### 6.2 新增临床任务层 KPI

| KPI | 公式 / 定义 | 作用 |
|---|---|---|
| `task_sla_pct` | 按权重计，按时完成任务数 / 必须任务数 | 主 KPI，替代只看关键负荷百分比 |
| `life_line_on_time_pct` | priority ≥ 4 的任务中按时完成比例 | 展示生命线是否守住 |
| `weighted_task_unserved_kwh` | \(\sum w_k\max(0,P_k^{req}-P_k^{served})\Delta t\) | 区分不同任务的失供影响 |
| `deadline_miss_count` / `deadline_miss_h` | 任务错过数量与超时长度 | 直观的时效性指标 |
| `median / max time_to_start_h` | 任务首次有效启动时刻 | 回答“恢复率 100% 但何时恢复” |
| `cold_start_success_pct` | 成功冷启动次数 / 计划冷启动次数 | 验证启动计划不是纸面顺序 |
| `min_task_voltage_margin_pu` | \(V_t-V_{min,k}\) 的最小值 | 将电能质量放进任务解释 |
| `dependency_blocked_task_h` | 因前置条件而阻塞的 task-hours | 解释“有电但还不能做” |
| `clinical_service_equivalent` | 仅在相同任务 SLA 门槛下比较碳/柴油 | 防止用少供电换低碳 |

### 6.3 公平策略比较规则

所有“碳韧协同优于最小失供”的主结论必须满足：

```text
life_line_on_time_pct ≥ baseline
AND weighted_task_unserved_kwh ≤ baseline + epsilon
AND deadline_miss_count ≤ baseline
AND G1–G4 physical gates all pass
```

只有在这些服务与物理门控通过后，才比较柴油 kWh、`kgCO2`、弃光与抢修车辆碳。否则 UI 仅显示“低碳候选未通过临床/物理门”，禁止标绿。

---

## 7. UI：把“关键负荷”解释成可审查的恢复任务

### 7.1 现有页面上的四个最小增量

1. **医院生命线抽屉**：点击 N03/N18 或“医院任务”标签打开；顶部显示 `任务 SLA / 最紧 deadline / 当前可供 kW / 电压裕量`。
2. **任务泳道时间线**：每行一个任务，显示依赖箭头、deadline 竖线、启动峰值闪电标记、连续运行区间和颜色状态。
3. **节点功率构成图**：将该节点的任务稳态负荷、启动峰值、PV、柴油、储能/上级电源与未供部分堆叠在同一小时游标上。
4. **原因卡片**：选择一个红色/黄色任务时，显示事实链，例如：`L17 fault → N18 islanded → diesel grid-forming available → N18-CORE started at 0.25 h → N18-COLD delayed to 1.25 h because startup headroom`。

### 7.2 颜色与交互规则

| 状态 | 颜色 | UI 文案 |
|---|---|---|
| `completed_on_time` | 绿色 | 已按时完成 |
| `running` / `starting` | 蓝色 | 运行中 / 启动校验中 |
| `pending` | 灰色 | 待启动 |
| `blocked_*` | 琥珀色 | 被具体门控阻塞 |
| `completed_late` | 橙色 | 已完成但错过时限 |
| `missed` | 红色 | 时限违约 |

UI 不能把任务状态伪装为现场 SCADA 回执。页面应固定显示 `仿真建议 / synthetic scenario` 徽章；动作序列是“建议操作票候选”，不是遥控指令。

### 7.3 答辩模式的关键截图

- **截图 A（同为 100% 关键恢复率的反例）**：展示两个策略的通用关键恢复率相同，但一个让 N18-COLD 超时，另一个任务 SLA 为 100%。
- **截图 B（冷启动排序）**：展示 COLD 与 WATER-AIR 不同时启动，避免峰值越过 N18 本地柴油/孤岛功率余量。
- **截图 C（电压门）**：任务虽有足够 kW，但 `voltage_pu < 0.92`，状态为黄色并被拒绝计为完成。
- **截图 D（低碳公平性）**：Pareto 点只有在全部生命线任务按时后才进入绿色可选集合。

---

## 8. 合成数据声明与数据治理

### 8.1 必须在 README、UI、报告三处一致出现的声明

> 本医院生命线任务链基于 MATPOWER IEEE 33 节点标准配电算例和项目自定义的节点类型/DER 假设构建。N03、N18 的“医院/应急”标签、任务功率、功率因数、期限、连续时长、电压带、冷启动峰值及保冷余量均为可复现的合成演示参数，不对应任何真实医院、患者、设备铭牌、医疗流程或电网运行规程。该模块用于恢复预案仿真、算法比较与答辩展示；投入现场前须由配电、应急、医院设施、临床工程和合规团队以真实台账、保护方案和应急预案逐项校核。

### 8.2 数据包与版本留痕

```text
data/clinical_tasks/
  care_tasks_synthetic_v1.yaml
  care_task_schema.json
  clinical_task_assumptions.md

artifacts/<run_id>/
  clinical_task_schedule.csv
  clinical_task_events.csv
  clinical_node_requirements.csv
  clinical_kpis.json
  clinical_assumptions_snapshot.json
```

`clinical_assumptions_snapshot.json` 至少包含任务文件 SHA-256、case33 源哈希、策略名、场景 seed、时步、任务调度器版本、每个电压/启动假设和运行时间。每个图表都应能追溯到该快照。

### 8.3 从合成到试点的替换路径

| 当前 synthetic 字段 | 真实替换源 | 校验责任 |
|---|---|---|
| `nominal_kw` / `pf` | 分项回路、ATS/UPS、设备铭牌、能管系统曲线 | 医院设施/临床工程 |
| `deadline_h` / `min_duration_h` | 医院 EOP、科室 downtime procedure、演练复盘 | 应急管理/科室负责人 |
| 电压带、启动峰值 | 设备技术资料、启动试验、配电保护协调 | 电气工程/设备厂商 |
| `thermal_holdover_h` | 冷链设备验证记录、环境温度与装载条件 | 药事/实验室/设施团队 |
| 节点/馈线映射 | GIS、单线图、馈线台账、现场核验 | 配电运检/医院工程 |

真实数据接入前，MVP 只能说“合成设施任务的任务 SLA”，不能说“真实 ICU 连续服务时间”或“患者风险降低”。

---

## 9. 测试计划（实现时的 Definition of Done）

### 9.1 数据与模型单测

| 测试 | 断言 |
|---|---|
| schema 完整性 | 每个 `task_id` 唯一；`node_id` 存在；`source_class=synthetic_mvp_v1` |
| 功率分解 | N03、N18 各任务 `nominal_kw` 之和等于节点 90 kW；不与基线再次相加 |
| 依赖图 | 无环；所有 dependency 都存在；前置任务不晚于子任务的理论 deadline |
| 时间字段 | `latest_start_h >= 0`，`deadline_h >= latest_start_h`，`min_duration_h > 0` |
| 电压字段 | `0 < voltage_min_pu < voltage_max_pu`，冷启动门槛不低于配置的最低合理范围 |
| 冷启动计算 | 能量按分钟积分；启动峰值不被小时平均功率掩盖；并发数受限 |
| 无功近似 | `pf` 合法且 `q = p*tan(arccos(pf))` 可复算 |

### 9.2 调度/物理集成测试

| 场景 | 必须观察到的结果 |
|---|---|
| 未开启 clinical mode | 当前 33 节点输出与既有回归基线一致 |
| N03 上游失电、无替代路径 | N03 任务保持 `deenergized`；不出现虚构的任务完成 |
| N18 L17 断开且本地 grid-forming 资源可用 | `N18-CORE` 先启动，依赖项随后启动；事件表有因果链 |
| 两个冷任务抢同一启动窗口 | 仅一个启动；另一个 `blocked_cold_start` 或顺延 |
| 启动峰值功率不足 | 任务不因小时平均能量足够而错误完成 |
| 电压低于任务门槛 | 即使 `served_kw >= min_kw`，任务也不计完成 |
| deadline / 重启 | 中断超过期限或用尽 restart 次数后，正确记 `missed` |
| 物理违反 | 支路过载、孤岛无合法 source 或 voltage violation 的候选被标记不可行 |
| 确定性 | 相同 seed/输入运行两次，任务事件、KPI、CSV hash 一致 |

### 9.3 指标与叙事测试

- `critical_recovery_pct=100%` 不自动推出 `task_sla_pct=100%`；必须有专门回归样例证明差异；
- 当低碳策略牺牲任一 priority ≥ 4 任务时，不能标记为“推荐”；
- 总任务功率、节点供电、未供任务功率和 EENS 可逐小时闭合；
- UI 文案、MRV 报告、导出文件均包含 `synthetic` 与 assumptions snapshot；
- 所有任务级结论能从 `schedule.csv + events.csv + powerflow nodes.csv` 回放。

---

## 10. 5 分钟答辩故事（推荐演示脚本）

**0:00–0:35｜问题**

> 传统恢复把医院作为一个 90 kW “关键负荷”。但同样 90 kW 的恢复，并不说明急诊、连续支撑、公用工程和冷链是否按时具备运行条件。我们把关键负荷改成了可审计的生命线任务链。

**0:35–1:20｜网络与灾情**

展示 case33 故障、N03/N18。说明 N03 是无本地 DER 的合成医院节点，N18 是带合成 PV/柴油资源的应急枢纽；此处只演示预案，不宣称真实医院。

**1:20–2:20｜任务与依赖**

打开 N18 抽屉：CORE 必须先完成；ICU/ED 依赖 CORE；COLD 和 WATER-AIR 具有启动峰值，不能同一时刻硬拉起。时间轴展示 deadline，电压/功率卡展示实际门槛。

**2:20–3:10｜一次策略差异**

切换“最小失供”与“碳韧协同”。前者可能在总 EENS 上接近，但因为启动排序不佳造成一个冷任务逾期；后者先锁定生命线 SLA，再在其余可选负荷与柴油之间优化。强调：低碳不是少供电，只有服务与物理 gate 全绿才比较碳。

**3:10–4:00｜物理与证据**

点击任务事件：供电来源、启动峰值、节点电压、支路热稳定、依赖状态均可追溯。显示 `clinical_task_events.csv`、任务文件 hash 和 scenario seed。若电压不足，任务保持黄色而不被“完成率”粉饰。

**4:00–5:00｜边界与路线图**

> 当前是 IEEE-33 上的合成原型；任务参数不替代医院 SOP。下一步用脱敏回路/设备台账、EOP 期限与真实启动测试校准，并将任务离散变量与 LinDistFlow/潮流约束共同放入优化内核。我们的创新不在于把医院图标放到电网图上，而在于把恢复动作、供电质量、临床任务时限和可复算证据连成一条链。

---

## 11. 交付顺序（10 天内的最小可行路线）

| 日程 | 交付物 | 验收点 |
|---|---|---|
| D1 | `CareTask` schema、10 个合成任务、assumptions 声明 | schema/功率守恒/依赖 DAG 测试通过 |
| D2–D3 | 任务状态机与事件表 | CORE→依赖任务→冷启动顺序可回放 |
| D4 | N03/N18 需求替换与现有 dispatch 连接 | 未启用模式基线回归不变 |
| D5 | 启动 peak gate、node power allocation | 平均功率伪通过用例失败 |
| D6 | 后验电压/热稳定 gate | 低电压任务不得计完成 |
| D7 | 任务 KPI 与 CSV/JSON artifact | KPI 可由事件表重算 |
| D8 | Streamlit 医院抽屉、时间线、原因卡 | 三张答辩截图可稳定复现 |
| D9 | 三策略公平性校验、反例场景 | “100%关键恢复≠100%任务 SLA” 可现场展示 |
| D10 | 全量 pytest、演示录制、MRV/合成数据声明核对 | 可复现 run 包与 5 分钟讲稿齐全 |

若时间不足，优先完成 **任务 schema + 状态机 + N03/N18 功率替换 + 事件/KPI 导出**；UI 可以简化，但不得跳过合成声明、功率双计数检查、deadline 与电压 gate。

---

## 12. 资料来源与使用方式

1. World Health Organization, *Electricity in health-care facilities*：说明稳定电力支撑医疗设备、照明、通信、供水与紧急服务；本项目只用作“为什么需要任务化保供”的背景，不从中推导具体 kW、时限或电压设定。  
2. U.S. eCFR, **42 CFR §482.15**：医院应按应急计划实施应急/备用电源并开展检查、测试和维护；本项目借鉴“计划—演练—记录”的治理思路，不宣称符合任何特定司法辖区的工程合规要求。  
3. ASPR TRACIE, *Utility Failures in Health Care Toolkit*：强调在公用设施故障中采用科室/服务过程快速响应指引，以及级联影响；对应本方案的“任务依赖与原因卡”设计。  

**参数来源边界**：上述来源均不为本 MVP 的任务功率、deadline、启动电流、保冷时长或电压带背书；这些值全部受 `synthetic_mvp_v1` 数据版本约束，后续必须由真实台账和跨专业审查替换。
