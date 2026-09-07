# Wave 6：动作级 MRV、证据封签与数据可信架构

**日期：2026-08-22（北京时间）**  
**范围：** 基于当前 GridRescue 的 `RestorationPlan.actions`、逐时 dispatch、潮流校验、策略结果和 CLI 导出，提出下一版动作级 MRV 与证据封签架构。  
**本轮边界：** 仅形成数据结构、证据链、UI 和十天实施契约；未改动业务代码或重算既有结果。

## 0. 一句话结论

先把“每次推演的输入、因子、动作、物理校验、服务门和输出”封成一个可验证 run，再讨论“哪个动作减了多少碳”。MVP 的可信闭环是：

```text
冻结输入与因子快照
  → 结构化动作账本
  → 调度/潮流/服务门
  → 证据索引与 SHA-256 封签
  → 独立 verify
  → （少量关键动作）反事实重放归因
```

当前项目已有可复用基础：标准网络 SHA、三策略动作表、逐时 dispatch、逐时潮流/节点/支路/孤岛结果、场景 seed 与 Monte Carlo 结果。当前缺口是统一的 `factor_registry`、`run_manifest`、结构化 action ID、输入/输出 hash index、服务等价门、动作反事实重放和 UI 追溯入口。

---

## 1. 当前输出能证明什么，不能证明什么

### 1.1 当前已有的可连接证据

| 当前文件/对象 | 已含字段 | 在证据链中的角色 | 缺口 |
|---|---|---|---|
| `network_manifest.json` | case33 来源 SHA、基值、P/Q 合计、原始开关状态、基准潮流摘要。 | **网络输入证据**。 | 未绑定 run、代码、依赖、情景或因子快照。 |
| `actions_<strategy>.csv` | `hour, action`。 | **恢复动作展示**。 | 缺 `action_id`、target、前后状态、状态机、因果/物理关联。 |
| `dispatch_<strategy>.csv` | 负荷、PV、网电因子、购电、柴油、充放电、弃电、SOC、失供等逐时字段。 | **能量活动数据**。 | 因子值无 `factor_id`/来源/版本；没有输入行 hash。 |
| `powerflow_*.csv`、`powerflow_nodes_*`、`powerflow_branches_*`、`powerflow_components_*` | 可行性、电压、支路负载、损耗、孤岛供需与无功缺口。 | **物理约束证据**。 | 未被统一引用到最终动作和策略声明。 |
| `strategy_comparison.csv` | EENS、关键恢复率、柴油、新能源、总碳等。 | **策略层摘要**。 | 缺服务等价门、因子版本、比较边界 hash。 |
| `monte_carlo_results.csv`、`monte_carlo_failures.json` | scenario SHA、seed、参数、求解状态、失败原因。 | **合成压力测试证据**。 | 不应冒充现场统计；未被 run seal 串联。 |

### 1.2 当前必须保持的结论边界

1. `actions_*.csv` 目前只是计划/仿真动作序列，不是现场操作票、遥控记录或人工点击记录。
2. `grid_carbon_kg_per_kwh` 当前由年度基准值和情景乘子生成；必须作为冻结的合成因子情景，而非实时边际碳因子。
3. `total_carbon_kg` 是原型运行排放估算；只有服务等价与物理门通过后，才可作为策略差额的比较结论。
4. `renewable_curtailment_kwh` 是清洁能源利用指标，不直接乘因子等于“避免排放”。
5. 当前 `actions` 没有记录车辆、燃料实物、资产执行状态，因此动作级排放首先是**仿真归因账本**，不是现场 MRV 凭证。

---

## 2. 目标架构：一个 run、一条账本、一个封签

### 2.1 目录契约

```text
artifacts/runs/<run_id>/
  inputs/
    scenario.json
    network_snapshot.json
    config.json
    factor_snapshot.csv
    input_manifest.json
  outputs/
    actions.csv
    action_ledger.jsonl
    dispatch_<strategy>.csv
    powerflow_<strategy>.csv
    powerflow_nodes_<strategy>.csv
    powerflow_branches_<strategy>.csv
    powerflow_components_<strategy>.csv
    strategy_comparison.csv
    service_equivalence.json
    causal_attribution.csv              # 有重放才生成
    report_<strategy>.md
  logs/
    stdout.log
    solver.log
    ui_events.jsonl                     # UI 可选，不参与求解
  evidence/
    evidence_index.json
    seal.json
    verification.json
  run_manifest.json
```

**文件角色分离：** `inputs/` 冻结事实与假设；`outputs/` 是本 run 的派生产物；`logs/` 说明过程；`evidence/` 记录完整性和验证结果。任何图表和 PDF 都应进入 evidence index，而不是仅保留截图。

### 2.2 最小闭环

```text
scenario + network + config + factor snapshot
     ↓  (input_manifest_sha256)
planner / dispatch / powerflow
     ↓
action ledger + outputs
     ↓
G0-G4 gates
     ↓
evidence_index.json → seal.json → verify-run
```

`run_id` 不应只由时间生成。建议：

```text
run_id = YYYYMMDDTHHMMSSZ + "-" + first12(SHA256(network + scenario + config + factors + seed))
```

这使“相同名字、不同输入”的情况可被识别；时间仍用于排序，不作为唯一身份。

---

## 3. Factor Registry：因子不是代码常数

### 3.1 目标

将所有会影响碳结论的数值从散落的常量迁移为可冻结、可引用的 registry。当前至少覆盖电网购电、柴油发电、抢修交通，以及未来 Carbon-SOC 的充电来源强度。

### 3.2 `factor_registry.csv` schema

| 字段 | 示例/规则 |
|---|---|
| `factor_id` | `EF-CN-GRID-2023-LOCATION-V1`；值或适用边界变化必须新 ID/版本。 |
| `factor_version` | `1.0.0`。 |
| `activity` | `grid_import` / `diesel_generation` / `crew_vehicle` / `on_site_pv_operation`。 |
| `value`、`unit` | 必须成对，例如 `0.5306,kgCO2/kWh`；不得把 CO2 与 CO2e 混写。 |
| `gas_basis` | `CO2` / `CO2e` / `not_applicable`。 |
| `geography`、`year`、`temporal_resolution` | 全国/省级/区域；年度/小时；年度因子不可显示为实时。 |
| `method` | `location_based`、`fuel_combustion`、`engineering_prior` 等。 |
| `source_class`、`source_id` | B/C/D 及对应数据卡。 |
| `source_title`、`source_url`、`publication_date` | 资料定位。 |
| `source_file_sha256`、`registry_record_hash` | 原始公告/文献快照与登记行完整性。 |
| `license`、`retrieved_at_bjt` | 使用权与取得时间。 |
| `uncertainty_pct`、`applicability` | 不确定度和生效边界。 |
| `approval_status` | `approved` / `conditional` / `pending` / `retired`。 |

### 3.3 当前常数的迁移纪律

| 当前值 | 当前处理 | MRV 状态 |
|---|---|---|
| `grid_carbon_kg_per_kwh` 的 `0.5366 × multiplier × peak_shape` | 基础因子与情景形状分离；snapshot 中登记 `annual_factor_id`、`scenario_multiplier` 和 `profile_generator_version`。 | 当前属于 D/E，不能称实时、地区权威因子。 |
| `diesel_kg_per_kwh=0.72` | 注册为 `D-EF-DIESEL-PENDING-V1`，待原始来源冻结后再提升 B/C。 | `conditional`，不写 CO2e。 |
| `crew_vehicle_kg_per_km=0.23` | 注册为 `D-EF-VEHICLE-PENDING-V1`，补车型、燃料、路线与方法。 | `conditional`。 |
| `curtailed_renewable_opportunity_kg_per_kwh=0.5366` | 仅作解释性敏感性字段；不进入减排或动作贡献汇总。 | 不作为 Inventory factor。 |

### 3.4 `factor_snapshot.csv`

run 启动时从 registry 选择实际使用的行并复制为不可变快照。典型字段：

```text
run_id,hour,activity,factor_id,factor_version,value,unit,gas_basis,
geography,year,temporal_resolution,source_class,source_file_sha256,
scenario_multiplier,profile_generator_version,record_hash
```

对当前原型，逐时 `grid_carbon_kg_per_kwh` 应可被解释为：

```text
annual factor (factor_id) × scenario multiplier × declared profile function
```

而非伪造一个“本小时官方碳因子”。

---

## 4. Run Manifest：把计算边界冻结为可复算合同

### 4.1 `run_manifest.json` 最小 schema

```json
{
  "schema_version": "1.0",
  "run_id": "20260822T010203Z-xxxxxxxxxxxx",
  "created_at_bjt": "2026-08-22T09:02:03+08:00",
  "status": "sealed",
  "command": "python -m gridrescue.cli run --scenario 台风 --seed 2026 --seal",
  "runtime": {
    "python": "3.11.x",
    "os": "Windows",
    "solver": "CLARABEL:<version>",
    "lockfile_sha256": "sha256:<...>"
  },
  "code": {
    "bundle_sha256": "sha256:<...>",
    "git_commit": null,
    "git_state": "not_available"
  },
  "scenario": {
    "scenario_id": "typhoon_v03",
    "class": "E",
    "seed": 2026,
    "definition_sha256": "sha256:<...>"
  },
  "network": {
    "source_id": "B-NET-001",
    "source_sha256": "sha256:B408...A95D",
    "snapshot_sha256": "sha256:<...>"
  },
  "inputs": {
    "config_sha256": "sha256:<...>",
    "factor_snapshot_sha256": "sha256:<...>",
    "input_manifest_sha256": "sha256:<...>"
  },
  "gates": {
    "physical": "pending",
    "service_equivalence": "pending",
    "data_quality": "conditional"
  },
  "evidence_index_sha256": "sha256:<...>",
  "seal_sha256": "sha256:<...>"
}
```

### 4.2 当前项目的 manifest 特殊规则

- 当前目录无 Git 元数据时，`git_commit` 允许为 `null`，但必须补 `code_bundle_sha256`；不能伪造 commit。
- 运行环境必须固定 Python、CVXPY、solver、依赖锁文件/`pip freeze` 的 hash。优化器版本变化可能造成末位甚至策略变化。
- `scenario_definition`、`network_snapshot` 和 `factor_snapshot` 必须作为独立文件写入，不仅依赖源代码中的常量。
- 每个策略应有 `strategy_id`、`plan_id` 和动作账本终端 hash；不同策略绝不共享未标注的结果。

---

## 5. 动作级账本：从中文动作文本升级到可核验实体

### 5.1 动作状态机

当前 `RestorationPlan.actions` 只有 `hour, action`。下一版每个动作都应有稳定 ID、目标对象和状态机：

```text
proposed
  → evaluated
      → rejected              # 带失败约束证据
      → simulated_applied     # 被最终 plan 采用
      → superseded            # 被后续计划替换
```

**规则：** `simulated_applied` 只表示本次仿真被采用；不可写成现场“已执行”。现场接入后另加 `field_confirmed`，并携带 A 类工单/遥测证据。

### 5.2 `action_ledger.jsonl` schema

| 字段 | 含义 |
|---|---|
| `schema_version, run_id, sequence_no, action_id` | 账本身份与严格顺序。 |
| `strategy_id, plan_id, hour, effective_from_hour` | 所属方案与时间。 |
| `action_type` | `close_tie` / `open_branch` / `repair_branch` / `dispatch_diesel` / `charge_bess` / `discharge_bess` / `shed_load`。 |
| `target_type, target_id` | `branch/T37`、`branch/L24`、`asset/BESS-01`、`load_group/critical` 等。 |
| `before_state, requested_state, after_state` | 结构化前后状态；展示中文 text 仅为附属。 |
| `origin` | `strategy_rule` / `optimizer` / `operator_simulation` / `replay`。 |
| `status, reason_code` | 状态机和值域；拒绝时须写约束名。 |
| `input_refs` | scenario/network/factor/config hash 引用。 |
| `evidence_refs` | 对应 dispatch 行范围、powerflow component/branch 行、约束/日志 hash。 |
| `physical_gate_status, service_gate_status` | 最终门控。 |
| `parent_action_ids, counterfactual_of` | 描述依赖与反事实关系。 |
| `created_at_bjt, prev_hash, record_hash` | hash chain。 |

示例：

```json
{
  "schema_version": "1.0",
  "run_id": "<RUN_ID>",
  "sequence_no": 3,
  "action_id": "act-0003",
  "strategy_id": "carbon_resilient",
  "plan_id": "plan-<HASH12>",
  "hour": 0,
  "action_type": "close_tie",
  "target_type": "branch",
  "target_id": "T37",
  "before_state": {"normally_closed": false, "energized": false},
  "requested_state": {"switch": "closed"},
  "after_state": {"switch": "closed"},
  "origin": "strategy_rule",
  "status": "simulated_applied",
  "reason_code": "restoration_connectivity_candidate",
  "input_refs": {"scenario_sha256": "sha256:<...>", "network_sha256": "sha256:<...>"},
  "evidence_refs": {"powerflow_hours": [0, 23], "branch_ids": [37]},
  "physical_gate_status": "pass",
  "service_gate_status": "not_applicable",
  "prev_hash": "GENESIS:<RUN_ID>",
  "record_hash": "sha256:<...>"
}
```

### 5.3 动作与现有输出的映射

| 现有动作文本 | 新 `action_type` | target | 关联证据 |
|---|---|---|---|
| `闭合联络开关 T<n>` | `close_tie` | `branch/T<n>` | network snapshot、每小时 topology、支路潮流、径向校验。 |
| `修复支路 L<n>` | `repair_branch` | `branch/L<n>` | scenario repair duration、故障状态变化、恢复后 dispatch/潮流。 |
| 调度器的柴油/储能/削负荷决策 | `dispatch_diesel`、`charge_bess`、`discharge_bess`、`shed_load` | asset 或 load group | `dispatch` 对应小时行、SOC、功率平衡、因子快照。 |
| 不安全联络候选 | `close_tie` | `branch/T<n>` | `status=rejected`；`reason_code=non_radial|infeasible_island|thermal_violation`。 |

**建议：** 恢复层的开关/修复是“离散主动作”；逐时电源出力是“连续活动记录”。答辩演示先展示离散主动作，MRV 表内再把相关小时的连续能源流链接进来。

---

## 6. 动作级碳核算表：流量、因子、归因分开

### 6.1 三张表，而非一张大表

1. **`activity_energy_hourly.csv`**：每小时的实物流/服务量；从 dispatch 派生。
2. **`emission_inventory_hourly.csv`**：活动数据 × factor snapshot；形成 Inventory。
3. **`action_attribution.csv`**：关键动作的确定性反事实差额；仅在门控通过时形成“比较贡献”。

这样可以避免“一个开关动作直接乘一个因子就称减排”的错误。

### 6.2 `activity_energy_hourly.csv`

| 字段 | 说明 |
|---|---|
| `run_id,strategy_id,hour,activity_id` | 主键。 |
| `action_id` | 关联最近/主导离散动作；无单一归属时为空并写 `allocation_method=none`。 |
| `energy_flow` | `grid_import`、`diesel_generation`、`pv_direct`、`pv_to_bess`、`bess_charge`、`bess_discharge`、`curtailment`、`unserved_critical`、`unserved_normal`。 |
| `value,unit,time_step_h` | kW/kWh 必须明确；当前 1h 时 `kW × 1h = kWh`。 |
| `source_class, data_mode` | B/D/E 及 `synthetic_demo` 等。 |
| `dispatch_row_hash, record_hash` | 可回到 dispatch。 |

### 6.3 `emission_inventory_hourly.csv`

| 字段 | 说明 |
|---|---|
| `inventory_id,run_id,strategy_id,hour` | 主键。 |
| `activity_id, activity_value, activity_unit` | 活动数据。 |
| `factor_id, factor_version, factor_value, factor_unit` | 使用的冻结因子。 |
| `calculation_formula` | 如 `kWh × kgCO2/kWh`。 |
| `emission_value, emission_unit, gas_basis` | 结果与口径。 |
| `boundary_module` | `grid_scope2_location`、`diesel_scope1`、`vehicle_scope1_or_3`。 |
| `source_class, uncertainty_pct` | 数据质量。 |
| `activity_record_hash, factor_record_hash, record_hash` | 双向证据。 |

**强制规则：**

- 电池充电从来源进入 Inventory；放电只记录能量转移及 Carbon-SOC，不生成负排放。
- 现场 PV 的运行期排放和环境属性单列；环境属性不清晰时不能标零碳。
- 弃绿只进入 `curtailment` 活动表，不直接生成 `avoided_emission` 行。
- 当前没有真实车辆路线/油耗时，车辆排放只能由 D 类工程参数生成，不能归为现场证据。

### 6.4 `action_attribution.csv`

| 字段 | 说明 |
|---|---|
| `attribution_id,run_id,action_id,method` | `leave_one_action_out` 等方法。 |
| `counterfactual_run_id,counterfactual_definition` | 例如 `do(close_tie:T37=false)`。 |
| `outcome_name,observed_value,counterfactual_value,delta_value,unit` | `inventory_kg`、`diesel_kg`、EENS、服务量等。 |
| `physical_gate_status,service_gate_status,claim_status` | 只有均 pass 时可为 `accepted`。 |
| `interaction_residual_kg` | 多动作非线性余量，不硬摊给单个动作。 |
| `factor_snapshot_hash,input_manifest_hash,output_evidence_hash` | 反事实与原 run 的证据绑定。 |
| `confidence_note,record_hash` | 明确“固定反事实设定下的边际差异”。 |

**归因主方法（MVP）：** 固定其余动作和相同输入，撤销一个动作后重放：

```text
marginal(action a) = outcome(final plan) - outcome(final plan with do(a=off))
```

它是**模型内、确定性反事实**，不是现场统计因果。若撤销后物理不可行或服务门失败，则 `claim_status=blocked`：可显示“该动作是服务必要条件”，但不写“该动作减排 X kg”。

### 6.5 多动作交互的处理

```text
interaction_residual = strategy_delta - Σ accepted_action_marginal
```

出现交互余量时归为 `unallocated_interaction`。MVP 不平均分摊；后续若需要公平分配才引入有限采样 Shapley，并把运行次数、采样误差与稳定性一并报告。

---

## 7. G0–G4 门控：先服务、先物理，后谈减排

策略基线 B 和提案 P 只有在同一比较边界下才可展示 ΔInventory。

| Gate | 判定 | 不通过时的 UI/报告行为 |
|---|---|---|
| **G0 同边界** | 相同网络、情景、负荷、资源容量、时钟、因子快照、seed、solver 配置。 | 禁止比较；显示“输入边界不一致”。 |
| **G1 物理** | 全时段拓扑、孤岛、功率平衡、潮流、电压和热限额均通过。 | 仅显示不可行诊断；禁止推荐/减排。 |
| **G2 关键服务** | `served_critical(P) >= served_critical(B)-ε`。 | 禁止“低碳”结论；展示关键 EENS。 |
| **G3 普通服务** | 普通失供不超过预注册预算；预算须写入 manifest。 | 禁止写“同服务减排”；可写权衡候选。 |
| **G4 数据质量** | 关键因子、网络、场景和结果均有数据卡/许可证/哈希；D/E 输入完整披露。 | 可运行但为 `conditional`；不得写“权威核证”。 |

建议输出 `service_equivalence.json`：

```json
{
  "baseline_run_id": "<B>",
  "proposed_run_id": "<P>",
  "comparison_boundary_hash": "sha256:<...>",
  "criteria": {
    "same_scenario": true,
    "same_network": true,
    "same_demand": true,
    "same_der_capacity": true,
    "same_factor_snapshot": true,
    "physical_pass": true,
    "critical_service_pass": true,
    "normal_service_budget_pass": false
  },
  "gate_status": "blocked",
  "failed_reasons": ["G3 normal service budget exceeded"],
  "comparative_claim_status": "blocked"
}
```

当前“碳韧协同恢复”允许普通负荷延迟时，必须把这一预算显式固化在 G3；不能只比较关键负荷恢复率后就称全面减排。

---

## 8. 证据封签：Artifact Hash Chain

### 8.1 Canonicalization

同一内容跨设备写法不同会产生不同 hash，因此先规定：

- JSON 使用 UTF-8、键排序、紧凑分隔符、禁止 `NaN/Infinity`。
- 表格固定 UTF-8、LF、列顺序、行排序、数值精度；kW/kWh 等按声明精度量化后再封存。
- `record_hash` 不包含自身字段；路径使用 run 内相对路径。
- 二进制原始文件按原字节 hash，任何重保存都生成新版本。

### 8.2 账本链

```text
record_hash(i) = SHA256(
  "gridrescue-action-ledger-v1\n" + canonical_json(record_i_without_record_hash)
)
prev_hash(i) = record_hash(i-1)
prev_hash(0) = "GENESIS:<run_id>"
```

这可检测篡改、删除或重排动作记录。它不是区块链，也不保证拥有主机管理员权限的人无法重写全部历史；它提供的是**run 内可验证完整性**。

### 8.3 `evidence_index.json`

对所有输入、输出、日志和关键 UI 导出，按相对路径排序记录：

```json
{
  "schema_version": "1.0",
  "run_id": "<RUN_ID>",
  "files": [
    {
      "path": "inputs/factor_snapshot.csv",
      "role": "factor_snapshot",
      "bytes": 1234,
      "sha256": "sha256:<...>",
      "media_type": "text/csv"
    }
  ]
}
```

`artifact_root_hash = SHA256(canonical_json(evidence_index))`。索引角色建议固定为 `input`、`factor_snapshot`、`configuration`、`action_ledger`、`dispatch`、`powerflow`、`report`、`gate`、`log`、`ui_trace`。

### 8.4 `seal.json`

```json
{
  "schema_version": "1.0",
  "run_id": "<RUN_ID>",
  "seal_status": "sealed",
  "run_manifest_sha256": "sha256:<...>",
  "factor_snapshot_sha256": "sha256:<...>",
  "action_ledger_terminal_hash": "sha256:<...>",
  "artifact_root_hash": "sha256:<...>",
  "verifier_version": "1.0",
  "created_at_bjt": "2026-08-22T...+08:00",
  "seal_sha256": "sha256:<...>"
}
```

状态只允许：

| 状态 | 含义 |
|---|---|
| `draft` | 尚在运行或文件未齐。 |
| `sealed` | 必需文件、hash chain 与 manifest 已齐。 |
| `verified` | 独立验证器已复核通过。 |
| `invalid` | 缺文件、文件篡改、链断裂、manifest 不匹配或门控不满足。 |

发布 ZIP 时，ZIP hash 只证明分发包字节一致；真正的证据根仍是解压后的 `seal.json + evidence_index.json`。

---

## 9. UI 可信度徽章与动作追溯

### 9.1 顶部徽章

```text
[ E 合成推演 ] [ 因子：D 条件可用 ] [ 物理门：通过 ]
[ 服务门：受限/通过 ] [ 证据：sealed · 8d4c…91af ]
```

- A/B/C/D/E 来源等级与 `sealed/verified` 完整性状态必须分开显示。
- `sealed` 不等于“真实”或“权威”；它只表示本 run 的文件链可验。
- 因子为 D/E 时，用黄/橙标签写清“工程假设/合成”，而不是绿色“可信”。

### 9.2 MRV 证据抽屉（最小实现）

| 位置 | 显示内容 | 点击后追溯 |
|---|---|---|
| 顶部 KPI | run_id、短 hash、seal 状态、G0–G4。 | 完整 manifest 与复算命令。 |
| 恢复动作表 | `action_id`、T+hour、类型、目标、状态、物理状态、归因状态。 | before/after 状态、关联 dispatch 小时、潮流 branch/component 行、ledger hash。 |
| 能源与碳流 | 每小时活动量、factor ID、年/地区/时间分辨率、计算式。 | factor snapshot 原行与来源卡。 |
| 三策略对照 | G0–G4 矩阵和比较边界 hash。 | 若 blocked，显示服务或物理失败原因；不展示“减排”。 |
| 下载区 | `report`、manifest、seal、evidence index、ledger、factor snapshot。 | 下载事件记录到 UI trace。 |

### 9.3 UI trace（只记录交互，不冒充操作）

建议 `ui_events.jsonl`：

```text
ui_event_id,run_id,browser_session_id,event_type,page,widget_key,
safe_value_or_hash,created_at_bjt,prev_hash,record_hash
```

事件包括 `run_requested`、`scenario_selected`、`strategy_selected`、`hour_viewed`、`ledger_action_opened`、`download_requested`。若未来允许界面提出动作，则用 `action_proposed_by_ui`；只有后端账本写出 `simulated_applied` 后，UI 才能显示为已采纳的仿真动作。不得将浏览查看或点击误写成现场控制证据。

---

## 10. 推荐文件与接口切片（设计，不在本轮实现）

| 模块 | 建议位置 | 核心职责 |
|---|---|---|
| canonical/hash | `src/gridrescue/evidence.py` | canonical JSON、文件 hash、evidence index、verify。 |
| factor registry | `src/gridrescue/factors.py` | schema 校验、snapshot、因子选择。 |
| ledger | `src/gridrescue/ledger.py` | action/event 写入、链校验、状态机。 |
| MRV gate | `src/gridrescue/mrv.py` | G0–G4、Inventory、服务等价 JSON。 |
| attribution | `src/gridrescue/attribution.py` | leave-one-out replay、交互余量。 |
| bundle | `src/gridrescue/bundle.py` | run 目录、manifest、seal、验证报告。 |
| CLI | `src/gridrescue/cli.py` | `run --seal`、`verify-run`、`reproduce`、`replay-action`。 |
| UI | `app.py` | seal badge、MRV evidence tab、action drill-down、UI trace。 |

建议 CLI 契约：

```powershell
$env:PYTHONPATH="$PWD\src"
python -m gridrescue.cli run --scenario "暴雨内涝" --seed 2026 --output artifacts/runs --seal
python -m gridrescue.cli verify-run --run artifacts/runs/<run_id>
python -m gridrescue.cli reproduce --manifest artifacts/runs/<run_id>/run_manifest.json
python -m gridrescue.cli replay-action --run artifacts/runs/<run_id> --action-id act-0003 --mode remove
```

上述命令是实施验收接口，当前版本尚未实现。

---

## 11. 自动测试契约

| 测试 | 必须断言 |
|---|---|
| factor registry 校验 | 缺少 source hash、单位、年份、状态或重复 `factor_id` 时失败。 |
| factor snapshot 不可变 | 更新全局 registry 不改变旧 run 的结果和验证。 |
| action ledger hash chain | 改一条中间动作、删除一条、重排列或改 sequence 后 verify 失败。 |
| action-plan 一致性 | `simulated_applied` 的 target/小时/集合与最终 `RestorationPlan` 一致。 |
| rejected action 证据 | 拒绝动作必须有约束原因和关联 evidence hash。 |
| 服务门锁定 | 关键少供或普通负荷超预算时，`comparative_claim_status=blocked`。 |
| 物理门锁定 | 任何小时 `is_feasible=false` 时，排放再低也不产生减排结论。 |
| 重放确定性 | 固定 seed 对同一 action 连续 replay，反事实 output hash 相同。 |
| 交互不双计 | 单动作 marginal 总和与总差不一致时余量进入 `unallocated_interaction`。 |
| seal 篡改发现 | 修改一格 `grid_import_kw`、替换报告或删除 log 后 verify 变 `invalid`。 |
| UI 证据边界 | `ui_event` 只关联动作/制品，不被解释为现场执行。 |

---

## 12. 最小十天实现顺序

| 天 | 实施重点 | 当日可验收产物 |
|---:|---|---|
| **D1** | 冻结 schema：factor、action、manifest、gate、seal；制作小型 fixture run。 | JSON/CSV schema 文档与样例通过校验。 |
| **D2** | canonical JSON、SHA-256、evidence index。 | 改任一 input/output 都被 verifier 检出。 |
| **D3** | actions 结构化与 action ledger。 | 当前三策略的开关/修复动作都有 ID、target、status 与链 hash。 |
| **D4** | factor registry 与 per-run snapshot。 | 三个现有碳常数都在 registry 留下来源状态，不再裸值运行。 |
| **D5** | G0–G4 服务/物理/数据质量门。 | 少供关键负荷的 fixture 被自动锁定，不生成减排标签。 |
| **D6** | run manifest、seal、`verify-run`。 | 一个完整 run bundle 可以离线验证并可检测篡改。 |
| **D7** | leave-one-out replay，先支持 `close_tie` 与 `repair_branch`。 | 一个关键动作可生成反事实 bundle。 |
| **D8** | `action_attribution.csv` 与交互余量。 | 动作贡献不越过物理/服务门，不双重归因。 |
| **D9** | Streamlit MRV 证据抽屉、徽章、下载 trace。 | 演示可从动作点到因子、潮流、manifest 和 seal。 |
| **D10** | 全量回归、两类灾害 demo、封存包与篡改演示。 | `pytest`、verify、reproduce、篡改失败演示均留档。 |

**降级优先级：** 若反事实重放工作量超期，仍先完成 `factor snapshot + action ledger + G0–G4 + seal/verify`；动作归因标记为 `planned`，不输出任何“某动作减少 X kg”的数字。封签和门控比漂亮的归因数字更重要。

---

## 13. 答辩口径

> GridRescue 的 MRV 不是在报告末尾加一个碳总数。每一轮推演先冻结网络、场景、因子和配置；每个恢复动作都有结构化账本并连接到逐时能量流和潮流校验；只有关键服务、普通服务预算和物理可行性同时满足，系统才展示同边界下的运行排放差额。所有输入、输出与报告由 SHA-256 证据索引封存，并可独立验证或重放。

对“是不是区块链”的回答：

> 不是。我们采用普通的文件哈希、append-only 账本链和可复算 manifest，目标是让竞赛原型的输入、动作和结论可检查，而不是用去中心化概念替代工程证据。

---

## 14. 最终优先级

**P0：** factor snapshot、action ledger、G0–G4、evidence index、seal/verify。  
**P1：** 关键开关/修复动作的 leave-one-out 反事实与交互余量。  
**P2：** 外部时间戳/签名 release、真实现场 A 类凭证接入、Carbon-SOC 全量账本、Shapley 多动作归因。

这套架构使当前 B/D/E 混合原型也能诚实、可复跑地表达“输入从哪里来、动作做了什么、碳如何计算、哪些结论被门控允许”，而不会把合成结果包装为现场实测。
