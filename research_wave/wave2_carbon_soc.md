# Wave 2 设计：Carbon-SOC 与碳因子注册表（10 天比赛最小可实现版本）

> 目标：把 GridRescue 已有的“恢复阶段碳排”升级为**可复算、可解释、可审计**的碳—储能协同层；它服务于调度比较与 MRV，不把储能、光伏或恢复负荷包装成天然“减排”。
>
> 本文是设计稿，不改现有代码。建议后续实现沿用当前 24 个小时步长、`dispatch.frame`、`node_frame`、`artifacts/` 导出结构。

---

## 1. 一句话定义与边界

**Carbon-SOC（碳感知荷电状态）**不是“电池里物理储存了多少碳”，也不是碳信用/绿证账户；它是储能在跨时段充放电时使用的一个**归因账本与决策状态**：

1. `SOC_energy`：电池中可用电能（物理状态，kWh）；
2. `SOC_carbon_ledger`：这部分电能的来源标签、充电时段排放因子、数据质量与未归因份额（会计状态，kgCO2）；
3. `marginal_factor`：调度“多充/多放 1 kWh”可能改变的边际电源排放信号（决策状态，**估算值**）；
4. `accounting_factor`：本轮实际购电排放核算使用的平均/供应商因子（MRV 状态，**报表值**）。

### 1.1 本版强制区分的三类数

| 类别 | 用途 | 可否进“恢复阶段实际排放”总计 | 例子 |
|---|---|---:|---|
| 实际活动数据 | 量化本次运行发生的排放 | 可以 | 电网购电、柴油出力、车辆里程 |
| 归因账本数据 | 解释电池输出来自何时、何种来源 | 不重复加入 | 某 100 kWh SOC 中有 60 kWh 来自电网充电 |
| 反事实/边际数据 | 评估策略相较基线可能避免或增加的排放 | 单列，非实际总排放 | 电池在高边际因子时段放电的潜在替代效应 |

**硬规则：**

- 不把“恢复更多负荷”直接称为减排；它首先是韧性收益。
- 不把电池放电记为零排放；其上游影响已在充电时发生，或处于“初始 SOC 来源未知”。
- 不将电池的“碳账本释放”再次计入运行总排放，防止双重计算。
- 不把 PV 弃电乘某因子后写成已经发生的“避免排放”；它只能叫**弃光替代排放潜力**，且必须给出被替代对象与因子。
- 不把绿证、PPA、市场法因子混进物理调度的边际排放信号。它们属于不同问题，必须分字段、分图层展示。

这与现有 README 中“恢复更多负荷不直接认定为减排、弃电机会损失单列”的表述一致；Carbon-SOC 的作用是把该边界落到数据、公式、报表和 UI 上。

---

## 2. 对当前 GridRescue 的问题定位

当前实现已经有正确的基础：

- `scenarios.hourly_profiles()` 输出逐时 `grid_carbon_kg_per_kwh`；
- `dispatch_resources[_spatial]()` 在目标函数中使用 `grid × grid_carbon_kg_per_kwh + 0.72 × diesel`；
- `carbon.calculate_carbon()` 输出电网、柴油、抢修车辆与弃光机会量；
- `dispatch.frame` 已输出 `battery_charge_kw`、`battery_discharge_kw`、`battery_soc_kwh`、购电/柴油/PV/弃电；空间调度还输出节点级 SOC。

但竞赛答辩会追问四件事：**因子从哪来、是平均还是边际、储能为何此刻充/放、结果怎样复算**。当前原型存在以下需要显式标注的假设：

1. 基准 `0.5366 kgCO2/kWh` 与灾害倍数为合成输入；其来源、适用区域、版本、有效期和不确定性未结构化记录。
2. 同一个 `grid_carbon_kg_per_kwh` 同时承担“实际排放核算”和“优化调度信号”，导致平均因子与边际因子的含义混淆。
3. 电池 SOC 仅记录电能，没有充电来源和碳归因；初始 SOC 的来源也未声明。
4. `avoided_grid_equivalent_kg` 的名字容易被理解为已核证减排；实际它是弃电在指定反事实下的替代排放潜力。
5. 当前 1 小时步长下 `kW` 求和数值上等于 `kWh`；设计与报告必须显式写出 `Δt=1h`，避免未来切换到 15 分钟步长时单位失真。

### 2.1 比赛版的定位声明（建议放进 README 和答辩页）

> 本原型输出的是“灾害恢复运行的可追溯排放估算”和“碳感知调度对比”，不是碳交易、CCER 核证、产品碳足迹认证或实时电力市场结算。因子数据质量与时间/区域匹配程度会被随结果导出；缺少真实区域级边际数据时，边际结果仅用于策略敏感性分析，不作为对外减排宣称。

---

## 3. 最小科学模型与公式

### 3.1 统一符号、单位和时间

对时段 `t`：

- `Δt`：时段长度（本项目固定为 `1 h`）
- `P_grid,t`、`P_diesel,t`、`P_ch,t`、`P_dis,t`：功率，kW
- `E_pv_curt,t`：弃光电能，kWh
- `EF_acc,t`：实际核算电网因子，kgCO2/kWh
- `EF_marg,t`：边际电力因子，kgCO2/kWh；缺失时为空，不伪造为平均因子
- `EF_diesel`、`EF_vehicle`：柴油与车辆因子，须绑定口径/版本
- `η_c`、`η_d`：充电、放电效率；当前可从总效率 `η_rt=0.94²` 或明确拆分得到
- `S_t`：时段开始储能电量，kWh（电池侧）
- `B_t`：已归因储能碳账本余额，kgCO2
- `U_t`：未归因储能电量，kWh（初始 SOC、数据缺失或混合来源）

### 3.2 物理 SOC（调度硬约束）

当前模型可泛化为：

```text
S_(t+1) = S_t + η_c × P_ch,t × Δt − (P_dis,t × Δt) / η_d
S_min ≤ S_t ≤ S_max
0 ≤ P_ch,t ≤ P_ch,max
0 ≤ P_dis,t ≤ P_dis,max
```

若先保留当前单一效率 `η`，就采用当前逻辑：

```text
S_(t+1) = S_t + η × P_ch,t × Δt − (P_dis,t × Δt) / η
```

`SOC% = 100 × S_t / S_max`。所有导出都应带 `time_step_hours`，当前值为 `1.0`。

### 3.3 实际运行排放（唯一可进主总计的公式）

```text
C_operational
 = Σ_t [P_grid,t × Δt × EF_acc,t]
 + Σ_t [P_diesel,t × Δt × EF_diesel]
 + D_crew × EF_vehicle
```

其中 `EF_acc,t` 可以是区域平均、配电公司供应因子或其他经登记的**核算因子**，但必须在因子注册表中可定位。电池充电带来的电网排放已在第一项中出现；电池放电时不再增记一份排放。

若柴油可获得燃料流量，比赛后续版优先改成：

```text
C_diesel = Σ_t Fuel_t × EF_fuel_litre × (1 + oxidation/CH4/N2O adjustment)
```

在只有出力时，使用 `kWh` 因子仍可行，但需要标注为“机组特定效率未知时的项目假设”。IPCC Energy Volume 2 的 stationary/mobile combustion 指南可作为燃料与车辆因子口径底座。[S3]

### 3.4 电池碳归因账本（解释，不重复核算）

给充电电能加来源标签 `s ∈ {grid, pv, diesel, initial_unknown}`，为每个来源建立 bucket。以电池侧能量计，电网充电 bucket 的入账为：

```text
ΔS_grid,t = η_c × P_ch_grid,t × Δt
ΔB_grid,t = P_ch_grid,t × Δt × EF_acc,t
```

PV 充电：

```text
ΔS_pv,t = η_c × P_ch_pv,t × Δt
ΔB_pv,t = 0  （仅指运行边界内的本地 PV 发电，不等于生命周期为零）
```

柴油充电：

```text
ΔS_diesel,t = η_c × P_ch_diesel,t × Δt
ΔB_diesel,t = P_ch_diesel,t × Δt × EF_diesel
```

放电时先从 bucket 中按 **FIFO（比赛 MVP 推荐）** 或“按能量比例混合（可选）”扣除电池侧能量：

```text
E_withdraw,t = P_dis,t × Δt / η_d
B_out,t = Σ_s [E_withdraw_from_s,t × I_s,t]
I_s,t = B_s,t / S_s,t   （bucket 的归因强度）
```

`B_out,t` 只用于说明“本次放电携带的上游归因强度”；**它不加入 `C_operational`**。bucket 的守恒检查：

```text
Σ_s S_s,t = S_t
Σ_s B_s,t = B_t
S_s,t+1 = S_s,t + charge_bucket − discharge_bucket
```

### 3.5 初始 SOC 的诚实处理

灾后场景常从 `initial_soc=72%` 开始。其来源如果未知，碳账本不允许私自设为 0：

```text
S_initial_unknown = initial_soc × S_max
B_initial_unknown = NULL
source = initial_unknown
```

比赛 MVP 的处理：

- 主运行排放：照常统计本次电网/柴油/车辆活动；
- Carbon-SOC：显示“初始 SOC：`x kWh`，来源未归因”；
- 决策敏感性：给出 `initial_soc_factor_low/base/high` 三档，或只在 `initial SOC 的来源` 已登记时参与跨时段碳迁移解释；
- 禁止用“电池已有电，所以本次零碳”叙事。

### 3.6 边际电力碳因子与储能的耦合

#### 两个因子，不合并

| 字段 | 回答的问题 | 可用于 |
|---|---|---|
| `EF_acc,t`（accounting / average） | 本时段已经购入的电量在报表中计多少排放？ | MRV 主总计 |
| `EF_marg,t`（marginal） | 如果调度多从电网取或少取 1 kWh，边际上可能改变谁的出力？ | 调度信号、敏感性与反事实对比 |

平均因子用于 location-based 电力核算的思想与 GHG Protocol Scope 2 Guidance 一致；市场法合同因子和物理运行信号须分开。 [S1]

对一次“电网充电于 `t_c`、放电替代电网于 `t_d`”的局部边际判断：

```text
Potential_shift_benefit
≈ EF_marg,t_d × P_dis,t_d × Δt
 − EF_marg,t_c × P_ch,t_c × Δt
```

又因 `P_dis × Δt ≈ η_c × η_d × P_ch × Δt`，有：

```text
应优先跨时段移能的必要条件（只看碳）：
EF_marg,t_d × η_c × η_d > EF_marg,t_c
```

实际优化还须与关键负荷失供、孤岛成网约束、节点/支路容量、柴油替代、寿命吞吐成本共同求解。因此比赛中的推荐优先级是：

```text
关键负荷安全约束 > 岛屿可行性/潮流约束 > EENS > 碳信号 > 吞吐损耗
```

**重要限制：**

- `EF_marg` 只有在有区域、时段、系统边界、推导方法和不确定性时才可以填值；没有就为 `NULL`。
- 禁止把历史平均因子改名为“边际因子”。若用平均因子作 proxy，字段必须写 `marginal_proxy_from_average=true`，UI 显示“近似，不用于减排声明”。
- 电网因子只代表给定系统边界。跨区潮流、网损、弃风弃光、机组启停、需求响应等会改变真实边际结果，比赛版不应假装全都建模。

### 3.7 弃光的正确展示

```text
E_pv_curt = Σ_t P_pv_curt,t × Δt
Potential_displacement = Σ_t E_pv_curt,t × EF_counterfactual,t
```

第二式只能放在“情景潜力/反事实”卡片，且输出 `counterfactual_description`：例如“假设同一节点的弃光可无约束替代根节点购电”。存在网络孤岛、储能满电或负荷已恢复时，该假设往往不成立。故主报告字段建议从 `avoided_grid_equivalent_kg` 重命名为：

```text
curtailed_pv_displacement_potential_kgco2e
```

---

## 4. 碳因子注册表：最小可实现数据模型

### 4.1 注册表原则

每一个被计算器使用的因子必须回答：**数值、单位、空间、时间、边界、方法、来源、版本、质量、审批、哈希**。不需要区块链；一个带哈希的不可变导出、版本化 CSV/JSON 和审批字段已足以支撑比赛可信度。

### 4.2 表一：`carbon_factor_registry`（因子定义表）

| 字段 | 类型/示例 | 说明 |
|---|---|---|
| `factor_id` | `CF-GRID-CN-REGIONA-2026-AVG-V1` | 不可变业务 ID |
| `version` | `1.0.0` | 修改数值/方法即升版 |
| `factor_family` | `grid_average` / `grid_marginal` / `diesel_generation` / `vehicle_distance` | 物理对象 |
| `accounting_role` | `accounting` / `decision` / `counterfactual_only` | 防止误用 |
| `value` | `0.5366` | 数值 |
| `unit` | `kgCO2/kWh` | 强制单位字典 |
| `gas_scope` | `CO2` / `CO2e` | 不允许混填 |
| `lifecycle_boundary` | `operational_combustion` / `generation_output` / `well_to_wheel` | 明确边界 |
| `geography_type/value` | `balancing_area: X` | 区域/电网范围 |
| `asset_or_fuel` | `grid` / `diesel_genset` / `repair_van` | 适用对象 |
| `temporal_granularity` | `annual` / `hourly` | 分辨率 |
| `valid_from`, `valid_to` | ISO 时间 | 有效期 |
| `methodology_id` | `METH-EGRID-OUTPUT-2025` | 计算/发布方法 |
| `source_org`, `source_title`, `source_url` | 文本 | 原始来源 |
| `source_published_at`, `retrieved_at` | ISO 时间 | 溯源 |
| `source_sha256` | 64 hex | 文件/响应证据哈希 |
| `quality_tier` | `A/B/C/D` | 见 4.5 |
| `uncertainty_pct` | `12.0` 或 `NULL` | 有依据时填写 |
| `status` | `draft/reviewed/approved/retired` | 只允许 approved 用于正式导出 |
| `approved_by`, `approved_at` | 用户/时间 | 轻量审批 |
| `notes` | 文本 | 限制说明 |

### 4.3 表二：`carbon_factor_observation`（逐时/区域值）

只在因子为时序值时需要。

| 字段 | 说明 |
|---|---|
| `observation_id` | 主键 |
| `factor_id`, `factor_version` | 外键式引用 |
| `timestamp_start`, `timestamp_end`, `timezone` | 必须显式时区 |
| `area_code` | 与注册表区域一致 |
| `value`, `unit` | 实际时段因子 |
| `data_status` | `measured / published / estimated / proxy / missing` |
| `source_record_id`, `source_sha256` | 原始记录证据 |
| `quality_flag` | `ok / delayed / gap_filled / outlier` |

### 4.4 表三：`carbon_factor_assignment`（本次运行到底用了哪个因子）

| 字段 | 说明 |
|---|---|
| `run_id` | 运行 ID |
| `hour`, `node_id`（可空） | 调度粒度；电网根节点可只填 hour |
| `purpose` | `actual_accounting / optimization_signal / counterfactual` |
| `factor_id`, `factor_version`, `observation_id` | 精确引用 |
| `value_used` | 进入公式的值 |
| `fallback_reason` | 例如 `hourly data gap -> annual average` |
| `is_proxy` | 布尔值 |
| `assignment_hash` | 防串改 |

### 4.5 数据质量分级（无需假装“实时”）

| 等级 | 描述 | 可用于 |
|---|---|---|
| A | 目标区域、目标时段、权威/计量来源、方法与不确定性齐全 | 实际核算；边际决策 |
| B | 目标区域匹配，时段为日/月/年平均或经透明插值 | 实际核算；调度 sensitivity |
| C | 相邻区域/公开基准 proxy，有明确限制 | 原型对比；不得作对外减排结论 |
| D | 合成、教学或未验证参数 | 仅仿真演示，UI 红色标注 |

当前 `0.5366 × disaster_multiplier` 应注册为 `quality_tier=D`、`data_status=synthetic`。这不是缺点；透明说明比伪造“真实低碳调度”更容易拿评委信任。

### 4.6 因子选择算法（MVP）

```text
输入：run_time, area, factor_family, purpose
1. 查 approved 且 valid_from ≤ run_time < valid_to 的同区域逐时 observation。
2. 若无：查 approved 同区域年/月平均 factor；记录 fallback_reason。
3. 若 purpose=optimization_signal 且没有可信 marginal：返回 NULL，或仅在显式开启 proxy 模式时返回 average proxy。
4. 若 purpose=actual_accounting：允许 average fallback，但在 MRV 中标 DQ。
5. 输出 factor_id/version/observation_id/value/quality/is_proxy/source_hash。
```

---

## 5. 与现有恢复调度的耦合设计

### 5.1 保持当前模型能跑的 MVP 接口

不改变现有核心变量名称的前提下，调度输入新增概念列：

| 现有/新增列 | MVP 含义 |
|---|---|
| `grid_carbon_kg_per_kwh` | 保留兼容；等同本轮 `grid_accounting_kgco2e_per_kwh` |
| `grid_marginal_kgco2e_per_kwh` | 新增；允许空值 |
| `grid_factor_quality_tier` | A-D |
| `grid_factor_id` / `grid_factor_version` | 实际核算因子引用 |
| `grid_marginal_factor_id` | 决策因子引用 |
| `time_step_hours` | 固定 `1.0` |
| `battery_initial_soc_source` | `unknown / grid / pv / mixed` |
| `battery_initial_soc_factor_id` | 若可归因则填 |

实现顺序建议：

1. **核算不变**：`C_operational` 仍用 `grid_accounting` + 柴油 + 车辆；
2. **调度可配置**：策略“碳韧协同恢复”可在 `carbon_objective_mode` 中选择 `accounting_average`、`marginal_if_available`、`no_carbon_signal`；
3. **缺边际时不强行填充**：退回核算平均因子，但在结果中标注 `marginal_mode=proxy_average`；
4. **储能账本后处理**：先作为 dispatch 后处理，从 `grid/PV/diesel/charge/discharge` 生成 `storage_soc_ledger`；
5. **第 2 阶段再进优化**：如需细分充电来源，将聚合 `battery_charge_kw` 拆为 `charge_from_grid/pv/diesel`；若不拆，MVP 仅记录“充电时段电网混合因子归因”，并显示该简化。

### 5.2 推荐的调度目标（词典序优先于任意加权“碳分”）

当前 `DispatchWeights` 是加权和。比赛版建议把 UI 和报告描述为“近似的多目标加权优化”，不要声称全球最优的碳韧调度。可进一步采用以下词典序/ε-约束模型：

```text
Stage A: 先最小化关键负荷失供 EENS_critical
Stage B: 在 Stage A 最优值 + ε 内，最小化总 EENS
Stage C: 在 A/B 可接受集合中，最小化 C_operational 或 marginal decision cost
Stage D: 最小化柴油使用、储能吞吐、开关动作
```

这使“为了少几 kg CO2e 故意牺牲医院负荷”的伪科学叙事失效，也更符合灾害恢复情境。

### 5.3 节点/孤岛耦合

空间调度已有 `node_frame` 与成网约束。Carbon-SOC 不能只看系统总 SOC；应至少包含：

```text
(hour, node_id, component_key, is_root_component,
 storage_soc_kwh, storage_charge_kw, storage_discharge_kw,
 factor_area, accounting_factor_id, marginal_factor_id)
```

原因：孤岛内储能放电可能避免柴油，而根节点储能放电可能减少上级购电；两者对应的边际对象不同。若 island 无柴油/储能 GFM 能力导致本就不可供电，不能凭“低碳 PV”宣称恢复或减排。

---

## 6. MRV 证据链与可复算导出

### 6.1 最小证据链

```text
原始输入（场景/网络/资源/因子源）
  └─ SHA-256 + 获取时间 + 责任人
       ↓
已审批因子版本 + 本运行 assignment
       ↓
运行配置（代码版本、solver、随机种子、Δt、策略权重）
       ↓
逐时 dispatch / node dispatch / SOC ledger
       ↓
排放计算明细与断言结果
       ↓
MRV 报告 + manifest.json + 全部输出哈希
```

### 6.2 表四：`carbon_mrv_run`（一次可复现运行）

| 字段 | 说明 |
|---|---|
| `run_id` | UUID/可读时间戳 |
| `scenario_id`, `strategy`, `run_started_at`, `timezone` | 运行语境 |
| `time_step_hours`, `horizon_hours` | 单位与边界 |
| `code_commit`, `python_version`, `solver`, `solver_version` | 计算环境 |
| `network_input_sha256`, `scenario_input_sha256`, `factor_bundle_sha256` | 输入证据 |
| `carbon_objective_mode`, `marginal_proxy_enabled` | 方法开关 |
| `boundary_statement` | 固化本报告的核算边界 |
| `result_sha256`, `status` | 输出与状态 |

### 6.3 表五：`storage_soc_ledger`（可答辩的储能账本）

| 字段 | 说明 |
|---|---|
| `run_id`, `hour`, `node_id`, `storage_id` | 定位 |
| `soc_start_kwh`, `charge_input_kwh`, `discharge_output_kwh`, `soc_end_kwh` | 物理量 |
| `source_bucket` | `grid/pv/diesel/initial_unknown` |
| `bucket_energy_start/end_kwh` | 能量守恒 |
| `bucket_carbon_start/end_kgco2e` | 归因信息 |
| `charge_factor_id/version`, `charge_factor_value` | 输入因子 |
| `discharge_attributed_intensity` | 解释性字段，非主排放 |
| `allocation_method` | `FIFO` / `proportional` |
| `quality_tier`, `warning_code` | 数据质量 |

### 6.4 可选防篡改链（比赛足够）

对按时间排序的审计事件：

```text
record_hash_i = SHA256(canonical_json(event_i) + record_hash_(i-1))
```

同时导出：`mrv_manifest.json`、`evidence_index.csv`、`factor_bundle.json`、`dispatch.csv`、`storage_soc_ledger.csv`、`calculation_assertions.json`。不需要宣传“区块链上链”；哈希链的价值是复算时能发现文件被替换。

### 6.5 MRV 报告固定章节

1. 核算对象、时段、地域、单位与系统边界；
2. 数据质量卡：A-D 分布、因子版本、缺失/回退次数；
3. 运行排放主表：电网/柴油/车辆/总计；
4. 储能碳账本：充电来源、初始 SOC 未归因比例、放电归因强度；
5. 反事实结果（如启用）：基线、假设、边际因子质量、区间；
6. 弃光：实测弃电量与“替代排放潜力”分开；
7. 可复算清单：run ID、哈希、输入路径、公式版本；
8. 限制与未覆盖项：生命周期排放、跨区潮流、机组组合、天气预报误差等。

---

## 7. UI：评委 90 秒能看懂的指标与交互

### 7.1 首页六张核心卡（推荐）

| 卡片 | 主数值 | 必须附带的小字 |
|---|---|---|
| 关键负荷恢复率 | `%` | 安全优先，非碳换负荷 |
| EENS | `kWh` | 与基线差值 |
| 恢复阶段实际排放 | `kgCO2` | 电网+柴油+车辆；因子质量 `B/C/D` |
| 电池 SOC | `kWh / %` | 初始 SOC 是否未归因 |
| 碳移峰质量 | `kgCO2 potential` 或 `N/A` | 仅边际因子可用时展示；否则“无可信边际数据” |
| 数据可审计度 | `x/y evidence complete` | 因子、输入、运行、输出哈希 |

### 7.2 三个必备图

1. **24h 能源—SOC 图**：PV、购电、柴油、充/放电、负荷、SOC 双轴；把因子曲线画成独立轴或背景带。
2. **因子和调度解释图**：`EF_acc` 实线、`EF_marg` 虚线（或明示 N/A）、电池充/放电柱；鼠标提示显示 factor ID/version/quality。
3. **策略对比 Pareto 图**：x=`EENS`，y=`C_operational`，点颜色=关键负荷恢复率，tooltip=因子质量与 `marginal_proxy` 标志。不要用单一“碳韧指数”掩盖权衡。

### 7.3 两个证据抽屉

- **因子注册表抽屉**：数值、单位、地域、时间、口径、来源、版本、哈希、质量等级；
- **MRV 回放抽屉**：任意小时点击后显示能量平衡、SOC 方程左右两边、碳公式组成、执行过的 factor assignment、证据哈希。

### 7.4 统一警告文案

- `D 级合成因子：用于仿真对比，非真实区域排放声明。`
- `边际因子为空：未展示“碳移峰收益”，实际排放仍按核算因子计算。`
- `初始 SOC 未归因：本轮主排放不将其视为零碳。`
- `弃光替代排放潜力：反事实估算，未计入实际排放总计。`

---

## 8. 测试与验收清单

### 8.1 单元测试（必须）

| 测试 | 给定 | 断言 |
|---|---|---|
| SOC 能量守恒 | 充/放电、效率、Δt | `S_end` 等于公式结果，误差 `<1e-6` |
| SOC 边界 | 满电/最低 SOC | 充放决策不越界 |
| 功率—能量单位 | `Δt=0.25h` 与 `1h` | 排放和 SOC 随 Δt 正确缩放 |
| 运行排放无双算 | 电网充电后电池放电 | 总排放只记录充电时电网活动一次 |
| bucket 守恒 | grid/PV/diesel/unknown 混合 | `Σ bucket energy = SOC` |
| FIFO/比例分配 | 固定样本 | bucket 顺序和归因强度可预期 |
| 初始 SOC 未归因 | 初始 72% | 不默认为 0 kgCO2 |
| 因子有效期 | 过期/未来因子 | 选择失败或标记回退 |
| 因子单位 | kg/MWh、kg/kWh 混入 | 显式转换或硬错误 |
| 因子角色隔离 | market-based 因子被送进 `EF_marg` | 拒绝 assignment |
| 边际缺失 | `EF_marg=NULL` | 不输出避免排放数值 |
| 弃光命名 | 有弃光 | 主报表中不增加“avoid”总计 |

### 8.2 集成测试（必须）

1. **复算测试**：相同输入、相同因子 bundle、相同 seed，`dispatch.csv` 和 `carbon_summary.json` 哈希一致。
2. **因子版本回放**：改注册表中新版本后，旧 `run_id` 仍可用旧版本复算得到原结果。
3. **合成灾害回归**：暴雨、台风、高温各跑一次；结果含因子质量、证据索引和 SOC ledger。
4. **无边际数据降级**：调度仍可完成；报告明确 `marginal=N/A`，没有误导性潜在减排。
5. **孤岛回归**：非根岛储能放电只能服务本岛，账本 `component_key` 与节点数据一致。
6. **篡改探测**：修改一个输入 CSV 或 factor observation 后，manifest 校验失败并给出具体文件。

### 8.3 演示验收脚本（答辩现场）

```text
A. 选择“暴雨内涝” + 碳韧协同策略，运行。
B. 点击 T+19h：展示高负荷/高因子、储能放电、关键负荷与能量平衡。
C. 打开因子抽屉：展示 factor ID、版本、质量 D（合成）和来源说明。
D. 导出 MRV 包：展示 manifest、dispatch、ledger、factor assignments 的 SHA-256。
E. 切换“无可信边际因子”：潜在移峰卡变 N/A，实际排放主表保持可复算。
F. 篡改 factor CSV 的一个数，点击 verify：显示 hash mismatch。
```

---

## 9. 10 天冲一等奖的实施节奏

| 天数 | 交付 | 验收 |
|---:|---|---|
| D1 | 固化边界声明、术语表、单位字典、`Carbon-SOC` 不双算规则 | 评委问“电池是否零碳”有标准回答 |
| D2 | `carbon_factor_registry` + JSON/CSV bundle + 示例 D 级合成因子 | 每个数可查 ID/version/hash |
| D3 | factor selection + `carbon_factor_assignment` | 一次运行能导出全部 assignment |
| D4 | 将排放公式改成显式 `Δt`；主总计与 counterfactual 分层 | 单元测试通过 |
| D5 | `storage_soc_ledger` 后处理（先 aggregate，后 node） | SOC/bucket 守恒 |
| D6 | UI 六卡、三图、因子抽屉、统一警告 | 90 秒 demo 跑通 |
| D7 | MRV manifest、哈希链、导出包、回放脚本 | 可从导出独立复算 |
| D8 | 3 灾害 × 3 策略对比，做敏感性（低/中/高因子） | 无“确定减排”过度表述 |
| D9 | 异常、缺因子、篡改、孤岛回归测试 | 全部测试绿 |
| D10 | 打磨答辩：问题清单、限制页、录屏、结果快照 | 两次彩排可稳定复现 |

### 9.1 绝对不要在 10 天内做的事

- 不承诺“实时全网边际碳因子”；
- 不自建碳交易/代币/区块链；
- 不把合成因子伪装成当地实时数据；
- 不用一个黑箱“碳韧指数”覆盖 EENS、关键负荷和排放的冲突；
- 不给弃光、储能放电、恢复负荷贴自动减排标签；
- 不在没有完整机组组合、跨区潮流和系统运营数据时宣称因果边际减排已被验证。

---

## 10. 建议的输出字段与文件命名

MVP 新增导出，不破坏现有 CSV：

```text
artifacts/<scenario>/
  carbon_factor_registry_snapshot.csv
  carbon_factor_assignments_<strategy>.csv
  storage_soc_ledger_<strategy>.csv
  carbon_hourly_<strategy>.csv
  mrv_manifest_<strategy>.json
  calculation_assertions_<strategy>.json
  report_<strategy>.md
```

`carbon_hourly_<strategy>.csv` 最少包含：

```text
hour,time_step_hours,
grid_import_kwh,grid_accounting_factor_kgco2e_per_kwh,
grid_actual_kgco2e,diesel_generation_kwh,diesel_kgco2e,
vehicle_kgco2e_allocated,battery_charge_kwh,battery_discharge_kwh,
battery_soc_kwh,battery_attributed_intensity_kgco2e_per_kwh,
initial_soc_unknown_kwh,grid_factor_id,grid_factor_version,
marginal_factor_id,marginal_factor_value,marginal_is_proxy,
curtailed_pv_kwh,curtailed_pv_displacement_potential_kgco2e
```

字段命名里显式包含 `actual`、`attributed`、`potential`、`proxy`，能直接降低答辩中的误读风险。

---

## 11. 参考口径（设计依据，不等于自动适用本地法规）

- **[S1] GHG Protocol, Scope 2 Guidance**：购买/获得的电力排放核算，区分 location-based 与 market-based 概念；本设计据此隔离“核算因子”和合同属性，不把它们混为物理边际调度信号。<https://ghgprotocol.org/scope-2-guidance>
- **[S2] U.S. EPA, eGRID**：提供发电侧环境特征、排放率、发电量和资源结构等数据；可作为“因子必须有来源、区域、年份和方法”的登记样板，并非中国配电网因子的默认替代。<https://www.epa.gov/egrid>
- **[S3] IPCC, 2006 Guidelines for National GHG Inventories, Volume 2 Energy；2019 Refinement**：固定燃烧和移动燃烧的燃料活动数据/因子方法学底座。<https://www.ipcc-nggip.iges.or.jp/public/2006gl/vol2.html>
- **[S4] GHG Protocol Corporate Value Chain (Scope 3) Standard**：强调方法选择、数据质量、不确定性、内部/外部审查应被记录；本设计借鉴其 evidence 和 QA 思路。<https://ghgprotocol.org/sites/default/files/standards/Corporate-Value-Chain-Accounting-Reporing-Standard_041613_2.pdf>

### 结论

比赛 MVP 的高分点不在于发明“碳存储”概念，而在于把**能源物理、碳核算、边际决策、反事实潜力和证据链**严格拆开。这样 GridRescue 可以诚实地回答：在不牺牲关键负荷安全的前提下，某个恢复策略实际排放多少、使用了什么质量的因子、储能为何在该时段动作、以及所有数字如何被复算。
