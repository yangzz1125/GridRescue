# GridRescue 动作级 MRV：最小可实施数据契约（Wave 6）

**范围：** 竞赛原型的仿真运行（不是现场操作票）。本规范只定义下一版最小 MRV bundle；它兼容现有 `actions_<strategy>.csv`、`dispatch_<strategy>.csv`、`powerflow_*.csv`、`strategy_comparison.csv` 和 `network_manifest.json`，但把它们置于一个可复算、可验签的 run 下。

## 1. 设计决定

1. **一轮 run 先冻结输入，再产生计划、逐时能源流、物理校验和策略结果。**
2. **动作、活动量、排放清单、反事实归因分四层保存。** 开关/修复不是直接乘排放因子；能源流才进入 inventory，离散动作的碳贡献只来自重放反事实。
3. **当前结果只可称“原型运行排放清单”。** 只有 G0–G4 同时通过，才显示“同服务边界下的排放差额”；`sealed` 仅代表文件完整性，不代表现场实测或第三方核证。
4. **当前碳口径默认 `CO2`，不伪称 `CO2e`。** 若后续引入 CO2e 因子，必须单独 factor snapshot / comparison boundary，禁止在同一汇总中混加。
5. **MVP 不做 Shapley。** 关键离散动作使用 deterministic leave-one-action-out；多动作非线性交互进入未分配余量。

目录（唯一 bundle 边界）：

```text
artifacts/runs/<run_id>/
  inputs/{scenario.json,network_snapshot.json,config.json,factor_snapshot.csv}
  outputs/{actions.csv,activity_energy_hourly.csv,emission_inventory_hourly.csv,
           service_equivalence.json,strategy_comparison.csv,powerflow_*.csv,
           dispatch_*.csv,action_attribution.csv?}
  logs/{solver.log,stdout.log}
  evidence/{evidence_index.json,seal.json,verification.json}
  run_manifest.json
```

`action_attribution.csv` 只在执行反事实重放后生成。没有该文件时 UI 必须显示 **“归因未计算”**，而不是显示零贡献。

---

## 2. 固定单位、数值和标识规则

| 项 | 规范 |
|---|---|
| 时间 | `hour` 为整数 `0..horizon_h-1`；`time_step_h` 为正数，当前固定 `1.0`。时间戳为 RFC3339、带 `+08:00` 或 `Z`。 |
| 功率 | `*_kw`，单位 kW；能量 `*_kwh`，单位 kWh；活动记录必须显式含 `time_step_h`。 |
| 因子 | `kgCO2/kWh` 或 `kgCO2/kWh`，与 `gas_basis=CO2/CO2e` 精确匹配。 |
| 排放 | `kgCO2` 或 `kgCO2`，与因子 `gas_basis` 匹配；比较的两边必须完全一致。 |
| 浮点写盘 | CSV 使用十进制、最多 6 位小数；进入 hash 前按相同精度量化。禁止 `NaN`、`Infinity`、科学计数法。 |
| ID | 小写 ASCII + `-`/`_`；`run_id`、`strategy_id`、`plan_id`、`action_id`、`factor_id` 都不可在其作用域重复。 |
| hash | 小写 `sha256:<64 hex>`；所有 JSON/JSONL 用 UTF-8、LF、排序键、紧凑分隔符 canonical JSON。 |

### 必须执行的单位检查

```text
energy_kwh == power_kw * time_step_h              (abs error <= 1e-6)
emission_value == activity_value * factor_value   (abs error <= 1e-6)
activity_unit == "kWh"
factor_unit == "kg<gas_basis>/kWh"
emission_unit == "kg<gas_basis>"
```

- `grid_import`、`diesel_generation`、`pv_available`、`curtailment`、`unserved_*` 均不得为负。
- `battery_charge`、`battery_discharge` 是能量流；**电池放电不得生成负排放或“避免排放” inventory 行**。
- `renewable_curtailment` 是资源利用指标；不得乘电网因子写成 `avoided_emission`。
- 当前 `dispatch` 的 kW 列，在 `time_step_h=1` 下数值等于单小时 kWh；新表仍保留两者，杜绝未来改变步长后误算。

---

## 3. 最小 CSV：factor registry 和 run snapshot

### 3.1 全局 `data/factor_registry.csv`

这是受控登记表，不随 run 修改；`factor_id + factor_version` 唯一。

```text
factor_id,factor_version,activity,gas_basis,value,unit,geography,year,
temporal_resolution,method,source_class,source_id,source_title,source_url,
source_file_sha256,uncertainty_pct,applicability,approval_status,record_hash
```

**值域：**

- `activity`: `grid_import|diesel_generation|crew_vehicle`
- `gas_basis`: `CO2|CO2e`
- `temporal_resolution`: `annual|hourly|event`
- `method`: `location_based|fuel_combustion|engineering_prior`
- `source_class`: `A|B|C|D|E`（当前合成假设用 `D` 或 `E`）
- `approval_status`: `approved|conditional|retired`
- `unit`: `kgCO2/kWh`、`kgCO2/kWh`，车辆因子则 `kgCO2/km` 或 `kgCO2/km`。

**当前常量映射：**

| 当前代码/数据 | registry 记录 | 状态 |
|---|---|---|
| `grid_carbon_kg_per_kwh = 0.5366 × multiplier × profile` | 一条年度 grid factor；hourly 变化由 snapshot 中 `scenario_multiplier` + `profile_generator_version` 声明。 | `conditional`, `D/E`，不可显示为实时官方小时因子。 |
| `diesel_kg_per_kwh = 0.72` | `activity=diesel_generation`。 | `conditional`，补来源后再升级。 |
| `crew_vehicle_kg_per_km = 0.23` | `activity=crew_vehicle`。 | `conditional`；目前仅在 `crew_distance_km` 真实/冻结时写 inventory。 |
| `curtailed_renewable_opportunity_kg_per_kwh` | 不进 registry 的 inventory 口径；仅可做解释性敏感性参数。 | 不可参与排放差额或动作贡献。 |

### 3.2 每轮 `inputs/factor_snapshot.csv`

run 使用的因子从 registry 复制而来；旧 run 永远只读自己的 snapshot。

```text
run_id,hour,activity,factor_id,factor_version,value,unit,gas_basis,geography,
year,temporal_resolution,method,source_class,source_file_sha256,
scenario_multiplier,profile_generator_version,registry_record_hash,record_hash
```

- `hour`：年度/事件因子也展开至每个计算小时，保证任何 inventory 行只需引用一个 snapshot 行。
- `scenario_multiplier=1`、`profile_generator_version=none` 适用于不随小时变化的 diesel/vehicle 记录。
- `record_hash` 是整行（不含自身）的 canonical record hash；不得从 live registry 动态取值。

---

## 4. 最小动作账本：`outputs/actions.csv`

保留现有 `hour,action` 仅作展示列；以下为唯一正式动作表。当前恢复层只需生成离散动作 `close_tie`、`repair_branch`。逐时调度不伪装成人工/开关动作，而留给 activity 表。

```text
run_id,sequence_no,action_id,strategy_id,plan_id,hour,action_type,target_type,
target_id,before_state_json,requested_state_json,after_state_json,origin,status,
reason_code,physical_gate_status,evidence_ref,prev_hash,record_hash,display_text
```

**枚举：**

- `action_type`: `close_tie|open_branch|repair_branch`
- `target_type`: `branch`
- `origin`: `strategy_rule|optimizer|replay`
- `status`: `proposed|evaluated|rejected|simulated_applied|superseded`
- `physical_gate_status`: `pass|fail|pending|not_applicable`

**最小约束：**

1. `sequence_no` 从 1 连续递增；`action_id=act-0001` 这类稳定 ID，不能按展示文本匹配。
2. `simulated_applied` 的 `target_id/hour` 必须与最终 `RestorationPlan` 一致。
3. `rejected` 必须有非空 `reason_code` 与 `evidence_ref`；可用 `non_radial|thermal_violation|voltage_violation|infeasible_island`。
4. `before/requested/after_state_json` 均为对象 JSON。例如闭合 T37：`{"switch":"open"}` → `{"switch":"closed"}` → `{"switch":"closed"}`。
5. `evidence_ref` 使用 run 内相对 JSON，如 `{"powerflow_branch":"outputs/powerflow_branches_carbon_resilient.csv#hour=0&branch_id=37"}`。
6. `prev_hash` 首行固定 `GENESIS:<run_id>`；之后引用前一行 `record_hash`。

---

## 5. 能源活动和排放清单：两个 CSV

### 5.1 `outputs/activity_energy_hourly.csv`

```text
activity_id,run_id,strategy_id,hour,time_step_h,primary_action_id,energy_flow,
power_kw,energy_kwh,data_mode,dispatch_ref,record_hash
```

- `energy_flow`: `grid_import|diesel_generation|pv_available|bess_charge|bess_discharge|renewable_curtailment|unserved_critical|unserved_normal`。
- `primary_action_id`：只有明确由某离散动作切换的段才可填写；否则为空。它**不是**碳归因。
- `data_mode`: 当前原型固定 `synthetic_demo`；未来现场可以是 `telemetry|metered|estimated`。
- `dispatch_ref`: 固定为如 `outputs/dispatch_carbon_resilient.csv#hour=7`。

### 5.2 `outputs/emission_inventory_hourly.csv`

仅 `grid_import`、`diesel_generation`，以及有真实/冻结里程时的 `crew_vehicle` 生成此表。

```text
inventory_id,run_id,strategy_id,hour,activity_id,activity_value,activity_unit,
factor_id,factor_version,factor_value,factor_unit,gas_basis,emission_value,
emission_unit,boundary_module,activity_record_hash,factor_record_hash,record_hash
```

- `boundary_module`: `grid_scope2_location|diesel_scope1|crew_estimated`。
- 计算式：`activity_value[kWh] × factor_value[kg<gas>/kWh]`。
- 所有 inventory 行的 `gas_basis` 及 `emission_unit` 必须与同 run 的 comparison boundary 一致。
- 现有 `CarbonBreakdown` 仍可由本表按 `boundary_module` 聚合复算；`total_operational_kg` 不再是唯一证据源。

---

## 6. 反事实归因：`outputs/action_attribution.csv`

只对最多 10 个关键 `simulated_applied` 离散动作计算。固定输入、冻结其余最终计划，撤销动作 `a` 后全链路重放：恢复 → dispatch → powerflow → inventory → gates。

```text
attribution_id,run_id,action_id,method,counterfactual_run_id,
counterfactual_definition,outcome_name,observed_value,counterfactual_value,
delta_value,unit,physical_gate_status,service_gate_status,claim_status,
interaction_residual_value,interaction_residual_unit,input_manifest_hash,
factor_snapshot_hash,output_evidence_hash,record_hash
```

**固定定义：**

```text
method = leave_one_action_out
counterfactual_definition = do(<action_id>=off)
delta_value = observed_value - counterfactual_value
```

因此对于 `outcome_name=inventory_emission`，`delta_value < 0` 代表撤销后排放更高、该动作在此固定反事实下有较低排放的边际贡献。报告渲染时使用清晰语言，避免正负号混乱：

```text
marginal_inventory_change_if_removed_kg = counterfactual - observed
```

**claim status：**

- `accepted`：反事实和原 run 均通过物理/服务 gate，且边界相同。
- `blocked`：反事实不物理可行或服务不等价；可写“服务必要条件”，不写碳贡献值。
- `informational`：只用于不进入减排结论的观察指标。

多动作交互：

```text
interaction_residual = strategy_inventory_delta - sum(accepted marginals)
```

余量写入一条 `action_id=unallocated_interaction` 记录，绝不平均摊给动作。

---

## 7. `run_manifest.json`：比较合同

以下字段全部必填；`git_commit` 允许 `null`，但 `code_bundle_sha256` 不允许为空。

```json
{
  "schema_version": "gridrescue-mrv-1.0",
  "run_id": "20260822T010203Z-a1b2c3d4e5f6",
  "created_at": "2026-08-22T09:02:03+08:00",
  "status": "sealed",
  "command": "python -m gridrescue.cli run ... --seal",
  "runtime": {
    "python": "3.11.x",
    "os": "Windows",
    "solver": "<name>:<version>",
    "dependency_lock_sha256": "sha256:<...>"
  },
  "code": {"git_commit": null, "code_bundle_sha256": "sha256:<...>"},
  "boundary": {
    "horizon_h": 24,
    "time_step_h": 1.0,
    "gas_basis": "CO2",
    "normal_service_budget_kwh": 0.0
  },
  "scenario": {"scenario_id": "...", "seed": 2026, "sha256": "sha256:<...>"},
  "network": {"source_id": "case33bw", "source_sha256": "sha256:<...>", "snapshot_sha256": "sha256:<...>"},
  "config_sha256": "sha256:<...>",
  "factor_snapshot_sha256": "sha256:<...>",
  "input_manifest_sha256": "sha256:<...>",
  "strategies": [{"strategy_id": "carbon_resilient", "plan_id": "plan-<12hex>", "action_ledger_terminal_hash": "sha256:<...>"}],
  "gates": {"physical": "pending", "service_equivalence": "pending", "data_quality": "conditional"}
}
```

`run_id` = `timestamp + first12(SHA256(canonical({scenario_sha,network_sha,config_sha,factor_snapshot_sha,seed})))`。时间用于排序；内容指纹识别输入不一致。

---

## 8. SHA-256 封签和独立验证

### 写入顺序

1. 冻结 `inputs/*`、生成 manifest（不包含 seal 字段）。
2. 写 outputs、action hash chain、service gate；输出所有文件后写 `evidence_index.json`。
3. 计算 manifest、factor snapshot、ledger terminal 和 evidence index 的 hash，写 `seal.json`。
4. `verify-run` 重新计算并写独立的 `verification.json`；该文件不纳入 seal，避免循环。

### `evidence/evidence_index.json`

```json
{
  "schema_version": "gridrescue-evidence-1.0",
  "run_id": "<RUN_ID>",
  "files": [
    {"path":"inputs/factor_snapshot.csv","role":"factor_snapshot","bytes":123,"media_type":"text/csv","sha256":"sha256:<...>"}
  ]
}
```

按 `path` 升序。索引必须包含 inputs、正式 outputs、logs 和 `run_manifest.json`；必须排除 `evidence/evidence_index.json`、`evidence/seal.json`、`evidence/verification.json`。

### `evidence/seal.json`

```json
{
  "schema_version": "gridrescue-seal-1.0",
  "run_id": "<RUN_ID>",
  "created_at": "2026-08-22T09:10:03+08:00",
  "manifest_sha256": "sha256:<...>",
  "factor_snapshot_sha256": "sha256:<...>",
  "action_ledger_terminal_hash": "sha256:<...>",
  "evidence_index_sha256": "sha256:<...>",
  "verifier_version": "1.0",
  "seal_sha256": "sha256:<hash of this object without seal_sha256>"
}
```

`verify-run <dir>` 必须检查：canonical JSON、每个 evidence file 的 bytes/hash、CSV ledger 行 hash 和 `prev_hash`、manifest 引用、seal 自 hash、所有 required artifact 存在。任意不符即 `invalid`，并禁止比较/归因 claim。

---

## 9. Claim gates（G0–G4）

| Gate | 断言 | 失败后的状态 |
|---|---|---|
| G0 同边界 | 同 scenario/network/demand/DER/horizon/step/factor snapshot/seed/solver config。 | `comparative_claim_status=blocked` |
| G1 物理 | 两侧所有 hour 的潮流、拓扑、孤岛、功率平衡、热限额、电压均通过。 | 仅可展示不可行诊断 |
| G2 关键服务 | `critical_eens(P) <= critical_eens(B) + epsilon_critical_kwh`。 | 禁止低碳/减排 claim |
| G3 普通服务 | `normal_eens(P) <= normal_eens(B) + normal_service_budget_kwh`。 | 仅展示权衡，不称同服务减排 |
| G4 数据与完整性 | factor snapshot/源 hash/required evidence/seal 均有效；低质量 D/E 完整披露。 | `conditional` 或 `blocked`，不可称核证结果 |

`outputs/service_equivalence.json`：

```json
{
  "schema_version":"gridrescue-service-gate-1.0",
  "baseline_run_id":"<B>",
  "proposed_run_id":"<P>",
  "comparison_boundary_hash":"sha256:<...>",
  "epsilon_critical_kwh":0.001,
  "normal_service_budget_kwh":0.0,
  "gates":{"G0":true,"G1":true,"G2":true,"G3":false,"G4":true},
  "failed_reasons":["G3 normal-service budget exceeded"],
  "comparative_claim_status":"blocked"
}
```

**当前数据的直接影响：** `artifacts/strategy_comparison.csv` 中“碳韧协同恢复”有 `eens_kwh=2294.2657`，而“最小失供恢复”为 `0.0`，两者关键 EENS 都为 `0.0`。若把后者作为 baseline 且普通负荷预算为 `0`，G3 必然失败；当前 `37406.4066` 与 `38922.1370` 的差只能显示为策略排放清单差异，不能展示为“同服务减排”。

---

## 10. 验收测试（最小）

| 测试 | 必须断言 |
|---|---|
| `test_factor_registry_rejects_bad_unit_or_source` | gas/unit 不匹配、缺 source hash、重复 `factor_id+version`、非 approved/conditional 均失败。 |
| `test_snapshot_is_immutable` | 修改 live registry 后，旧 snapshot 的 hash 与 inventory 结果不变。 |
| `test_activity_unit_equation` | 非 1h fixture 下 `kW × time_step_h = kWh`；篡改任一值失败。 |
| `test_inventory_unit_equation_and_gas_basis` | 活动×因子=排放；CO2 与 CO2e 混用失败；电池放电没有负排放行。 |
| `test_action_ledger_chain_detects_edit_delete_reorder` | 改中间行、删行、换行序、改 `sequence_no` 均 invalid。 |
| `test_plan_to_action_consistency` | `simulated_applied` 集合与现有 `RestorationPlan.actions` 的闭合/修复目标与 hour 相同。 |
| `test_gates_block_false_low_carbon_claim` | 少供关键负荷、普通负荷超预算、或任一 powerflow hour 不可行时，claim 都为 blocked。 |
| `test_evidence_seal_detects_dispatch_or_report_tamper` | 改一格 `grid_import_kw`、替换报告或缺 required file 后 verify invalid。 |
| `test_replay_is_deterministic` | 固定输入/seed 对同一 action 重放两次，counterfactual evidence hash 相同。 |
| `test_interaction_residual_not_allocated` | marginals 之和与策略差不同，差额只在 `unallocated_interaction`。 |

fixture 至少含：1 个 `close_tie`、1 个 `repair_branch`、2 个小时、`time_step_h=0.25`、一条 rejected action、一个 G3 失败案例。

---

## 11. 两天实施顺序（严格 P0 → P1）

### Day 1：先让任何 run 可封存、可复算

1. 新增 schema constants / canonical JSON / SHA-256 工具；建立上述目录和 required-file list。
2. 将现有三项 carbon 常量导入 `factor_registry.csv`，每次 run 输出 `factor_snapshot.csv`；保留当前数值与 `conditional D/E` 标签，不改求解算法。
3. 在已有 `RestorationPlan.actions` 导出点生成正式 `outputs/actions.csv`；由现有“闭合 T<n> / 修复 L<n>”文本解析出目标 ID，给每行建立 hash chain。
4. 从现有 dispatch 生成 `activity_energy_hourly.csv` 与 `emission_inventory_hourly.csv`；从现有潮流输出生成 G1 所需事实。
5. 输出 manifest、evidence index、seal，交付 `verify-run` 及篡改检测测试。

**Day 1 验收：** 给当前任一场景三策略生成一个 sealed bundle；修改 dispatch 一格后 verifier 失败；旧 `actions_*.csv` 仍可保留供 UI 展示。

### Day 2：再让“较低碳”与“动作贡献”受门控

1. 实现 G0–G4 和 `service_equivalence.json`；将 strategy comparison 的 claim 字段接入报告/UI，默认普通服务预算为 `0.0`，只有 manifest 显式修改才放宽。
2. 添加 `leave_one_action_out`，首批只支持 `close_tie` 与 `repair_branch`；每次重放创建独立 `counterfactual_run_id`/bundle，并走同一 seal/verify。
3. 写 `action_attribution.csv`、`unallocated_interaction`，把所有未过 gate 的项目标为 `blocked`。
4. 完成测试矩阵和一个演示：一个可接受归因，另一个因 G3 或 G1 被阻断。

**Day 2 验收：** 报告只在 G0–G4 全 pass 时显示比较排放差额；单动作归因可被同输入重放；不通过服务/物理 gate 的动作没有“减排 X kg”标签。

---

## 12. 答辩句（可直接使用）

> 每轮 GridRescue 推演先冻结网络、灾害、配置和排放因子；恢复开关与修复动作有按序哈希的结构化账本，逐时能源流再独立形成排放清单。只有物理可行、关键服务和普通服务预算都通过同边界门控，系统才展示排放差额。关键动作的贡献来自可重放的反事实，不把开关文本直接当成减排量；所有输入和输出可由 SHA-256 seal 独立复核。
