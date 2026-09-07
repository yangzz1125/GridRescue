# Wave 3：动作级 MRV 因果账本与 Run Evidence Seal 设计

**目标**：在 10 天内，把 GridRescue 从“能导出策略结果”的原型，推进为“每个模拟动作、碳因子、服务门槛、求解结果和 UI 操作均可追溯、可复算、可审计”的预案级 MRV 闭环。

**边界**：本方案只覆盖当前 `case33bw` 合成/预案推演。账本中的 `simulated_applied` 表示模型已采纳的仿真动作，绝不等同于现场执行或计量凭证。真实现场接入后，另增加 `field_confirmed` 事件与表计/工单证据链接。本方案采用本地、可导出的 SHA-256 证据封条；没有链上节点、代币、共识或“区块链”叙事。

---

## 1. 当前基线与改造原则

仓库已经具备可利用的基础证据：

- `src/gridrescue/restoration.py` 的 `RestorationPlan.actions` 记录了策略动作；当前 CSV 只有 `hour,action`，例如“闭合联络开关 T37”“修复支路 L6”。
- `src/gridrescue/dispatch.py` / `restoration.py` 生成逐时 `dispatch.frame`，其中已有电网进口、柴油、充放电、弃光、SOC、关键/普通失供等数据。
- `src/gridrescue/powerflow.py` 的 `validate_dispatch` 输出逐时、支路、节点、孤岛物理校验；`pipeline.py` 已把物理反馈纳入迭代。
- `src/gridrescue/carbon.py` 已输出电网、柴油、车辆及总运行排放；因子目前仍以 dataclass 默认值和逐时调度列存在，尚未形成可版本化 registry。
- CLI 已导出网络来源 SHA-256、策略结果、动作、调度和潮流表；Streamlit 已展示动作时间线并可下载报告/CSV。

MVP 的关键不是追求“不可篡改神话”，而是建立**可验证篡改痕迹**和**确定性复算**：

1. 一次 run 的输入、因子、动作、输出、软件环境必须各有哈希。
2. 动作由结构化 ID 表示，中文 `action` 保留为展示文本，不能作为计算或归因主键。
3. 减排/归因结论要先过服务等价与物理可行门；未通过时保留结果但锁住“减排/贡献”标签。
4. 任何 UI 点击只是一条交互证据，真正影响模型的动作另记为求解采纳证据；两者通过 `ui_event_id` 关联。
5. 每条账本行线性 hash chain，run 完成时写一个 `seal.json`；本地文件的替换会被复核命令识别。

---

## 2. 目标产物与目录

建议每个 run 使用稳定的 `run_id`：`<UTC时间>-<scenario_slug>-<strategy_slug>-<short_input_hash>`。例如 `20260822T091530Z-flood-carbon-7c19a4b2`。

```text
artifacts/runs/<run_id>/
  run_manifest.json                 # 本次运行环境、输入、门控与最终封条索引
  action_ledger.jsonl               # 每一动作/状态转换一行，按 seq 增长
  causal_attribution.csv            # 仅记录通过门控的边际重放结论
  factor_snapshot.csv               # 本 run 实际引用因子的冻结快照
  service_equivalence.json          # 基线—方案的门控输入和判定
  ui_events.jsonl                   # 有界、脱敏的 UI 点击事件；可不含 PII
  evidence_index.json               # 文件名、bytes、sha256、media_type、role
  seal.json                         # terminal ledger hash、artifact root、校验状态
  inputs/
    scenario.json
    network_manifest.json
    factor_registry.sha256
    config.canonical.json
  outputs/
    actions_*.csv
    dispatch_*.csv
    powerflow_*.csv
    powerflow_nodes_*.csv
    powerflow_branches_*.csv
    powerflow_components_*.csv
    strategy_comparison.csv
    report_*.md
  logs/
    stdout.log
    command.txt
```

全局只维护一份受版本控制的注册表：

```text
data/carbon/factor_registry.csv
data/carbon/factor_registry.schema.json
```

`artifacts/runs/.../factor_snapshot.csv` 是运行期切片，所有结果只引用快照中的 `factor_id` + `factor_record_hash`；因此未来改动 registry 不会重写历史 run 的解释。

---

## 3. Action Ledger：动作级因果账本

### 3.1 事件模型

`action_ledger.jsonl` 是 append-only JSONL，而不是一张可任意更新的业务表。每个“计划动作”至少会经历以下状态事件：

```text
ui_intent (可选) → proposed → evaluated → simulated_applied | rejected
                         │
                         └→ superseded (被新的求解结果替代)
```

- `ui_intent`：用户在界面中点击“运行”“策略切换”“查看 T+7”或未来的“尝试闭合 T37”。仅记录控制意图，不改变物理状态。
- `proposed`：策略/求解器提出结构化动作。
- `evaluated`：动作经过径向性、故障隔离、源/孤岛、潮流、设备/碳约束检查。
- `simulated_applied`：该动作进入最终 `RestorationPlan` 并影响结果；这是当前 MVP 的最高状态。
- `rejected`：保留拒绝原因和证据，特别适合证明“未为减碳牺牲关键负荷或违反物理约束”。
- `superseded`：因物理反馈迭代或重新求解导致之前候选动作被替换；不得删除旧行。

### 3.2 结构化 schema

每一行只使用 JSON 原生类型，数值不以中文字符串写入；时间用 ISO-8601 UTC，模拟时刻另用 `sim_hour`。

| 字段 | 示例 / 类型 | 作用 |
|---|---|---|
| `schema_version` | `"1.0"` | 解析兼容性。 |
| `run_id`, `ledger_id`, `seq` | string, UUID, int | run 内唯一、顺序固定。 |
| `event_type`, `status` | `action`, `proposed` | 状态机与事件语义。 |
| `action_id`, `action_type` | `act-0003`, `close_tie` | 动作主键与受控枚举。 |
| `target_type`, `target_id` | `branch`, `37` | 设备目标；可扩展 `repair_task`、`generator`、`bess`。 |
| `sim_hour`, `effective_from_hour` | int | 仿真时间与生效时点。 |
| `before_state`, `after_state` | object | 最小状态差，例如 `tie_closed: false → true`。 |
| `plan_id`, `strategy_id`, `scenario_id` | string | 与策略、灾害绑定。 |
| `origin` | `solver`, `ui`, `replay` | 动作是谁发起。 |
| `ui_event_id`, `request_id` | nullable string | UI 请求和后端处理的关联键。 |
| `solver_step`, `iteration` | string/int | 对应 `pipeline._simulate_with_loss_feedback` 的迭代证据。 |
| `constraint_result` | object | `radial`, `fault_isolated`, `source_feasible`, `powerflow_feasible` 等布尔值和理由。 |
| `input_refs`, `output_refs` | object | 具体文件及 SHA-256；不要只写路径。 |
| `factor_refs` | array | 影响本动作比较的 `factor_id` / record hash。 |
| `causal_group_id` | string | 用于连接同一因果试验的动作与 attribution 行。 |
| `actor_kind` | `system` / `operator` | 当前默认为 `system`；真实部署再加工号的 pseudonymous reference。 |
| `created_utc` | ISO-8601 UTC | 事件写入时间。 |
| `prev_hash`, `record_hash` | hex SHA-256 | 线性链字段。 |

受控 `action_type`：`close_tie`、`open_tie`、`repair_branch`、`energize_island`、`dispatch_grid`、`dispatch_diesel`、`charge_bess`、`discharge_bess`、`curtail_pv`、`shed_normal_load`、`shed_critical_load`。当前已有的文本动作至少映射：

| 当前展示文本 | 新 action_type | target |
|---|---|---|
| `闭合联络开关 T37` | `close_tie` | `branch:37` |
| `修复支路 L6` | `repair_branch` | `branch:6` |

中文展示字段 `display_text` 可以保留，但由结构化字段生成并在导出时校验，以防 `L6/T37` 文本解析歧义。

### 3.3 账本行样例

```json
{
  "schema_version": "1.0",
  "run_id": "20260822T091530Z-flood-carbon-7c19a4b2",
  "ledger_id": "b3a6e04c-4e61-4a36-b0ad-d02f061ef263",
  "seq": 7,
  "event_type": "action",
  "status": "simulated_applied",
  "action_id": "act-0003",
  "action_type": "close_tie",
  "target_type": "branch",
  "target_id": 37,
  "display_text": "闭合联络开关 T37",
  "sim_hour": 0,
  "effective_from_hour": 0,
  "before_state": {"tie_closed": false},
  "after_state": {"tie_closed": true},
  "strategy_id": "carbon_resilient",
  "scenario_id": "flood_v03",
  "origin": "solver",
  "actor_kind": "system",
  "solver_step": "restoration_plan",
  "iteration": 2,
  "constraint_result": {
    "fault_isolated": true,
    "radial": true,
    "source_feasible": true,
    "powerflow_feasible": true
  },
  "input_refs": {"network_manifest": "sha256:...", "scenario": "sha256:..."},
  "output_refs": {"dispatch": "sha256:...", "powerflow_hourly": "sha256:..."},
  "factor_refs": [{"factor_id": "GRID-CN-2023-LB", "record_hash": "sha256:..."}],
  "causal_group_id": "cg-20260822-0003",
  "created_utc": "2026-08-22T09:15:42Z",
  "prev_hash": "sha256:...",
  "record_hash": "sha256:..."
}
```

### 3.4 账本不承担的职责

- 不把批次级 `total_carbon_kg` 粘到每个动作上；那会把同一结果重复归因。
- 不记录无法验证的“现场已执行”；当前只有模拟事实。
- 不存 token、cookie、浏览器指纹、姓名或 IP。UI 追溯采用随机 `browser_session_id`，run 完成或 24h 后清理原始交互日志。

---

## 4. Factor Registry：让排放因子可定位、可冻结

### 4.1 CSV 最小 schema

`data/carbon/factor_registry.csv` 每一行是不可变版本。更新数值时新增 `factor_id` 或 `version`，不可原地覆盖已发布记录。

| 字段 | 示例 | 必填 |
|---|---|---:|
| `factor_id` | `GRID-CN-2023-LB-V1` | 是 |
| `factor_family` | `grid_import` / `diesel_generation` / `crew_vehicle` / `pv_operational` | 是 |
| `value` | `0.5306` | 是 |
| `unit` | `kgCO2/kWh`、`kgCO2/L`、`kgCO2/km` | 是 |
| `geography`, `year`, `temporal_resolution` | `CN`, `2023`, `annual` | 是 |
| `accounting_method` | `location_based` / `residual_mix` / `direct_combustion` | 是 |
| `source_title`, `source_url`, `source_published_date`, `retrieved_utc` | 来源元数据 | 是 |
| `source_sha256` | 原始文件或页面存档哈希 | 是 |
| `uncertainty_pct`, `evidence_level` | `10`, `A/B/C` | 是 |
| `assumption`, `approved_by`, `approval_status` | `false`, `team`, `approved` | 是 |
| `valid_from`, `valid_to`, `supersedes_factor_id` | 版本链 | 建议 |
| `record_hash` | canonical row SHA-256 | 是 |

**落地约束**：当前 `EmissionFactors` 的默认常数应转为 registry 引用；`hourly_profiles` 生成的 `grid_carbon_kg_per_kwh` 也须在 manifest 中声明“由哪个 annual factor、何种情景 multiplier 生成”。`grid_carbon_multiplier` 是情景参数，不得伪装成独立官方因子。

### 4.2 Factor Snapshot

启动 run 时，按实际策略、场景、计算期选取 registry 行并写入 `factor_snapshot.csv`。每个调度行增加：

```text
hour,grid_factor_id,grid_factor_record_hash,diesel_factor_id,vehicle_factor_id,
source_type,temporal_resolution,scenario_multiplier
```

这样可以解释“该小时的排放数值来自 annual 因子 × 场景 multiplier”，而不会伪称有实时边际碳强度。

---

## 5. 服务等价门控：先保服务，再显示因果/减排结论

### 5.1 Gate 的输入与判定

比较基线 `B` 与方案 `P`，同 run 下固定：网络、故障、需求曲线、DER 容量、天气/PV、因子快照、时窗、求解器配置和 seed。`service_equivalence.json` 至少写：

```json
{
  "baseline_run_id": "...",
  "proposed_run_id": "...",
  "comparison_boundary_hash": "sha256:...",
  "epsilon_critical_kwh": 0.001,
  "epsilon_normal_kwh": 0.08,
  "criteria": {
    "same_scenario": true,
    "same_network": true,
    "same_demand": true,
    "same_der_capacity": true,
    "same_factor_snapshot": true,
    "baseline_physical_feasible": true,
    "proposed_physical_feasible": true,
    "critical_service_equivalent": true,
    "normal_service_budget_met": true
  },
  "gate_status": "pass",
  "failed_reasons": []
}
```

推荐门控：

```text
G0 同边界：scenario/network/demand/resources/factors/clock 一致
G1 物理：两方案所有小时 powerflow is_feasible=true
G2 关键服务：served_critical(P) >= served_critical(B) - εcritical
G3 普通服务：unserved_normal(P) <= unserved_normal(B) + approved_normal_budget
G4 禁止代偿：critical shed=0，或双方处于同一批准的紧急豁免条件
```

只有 `G0..G4=pass` 时，页面和报告展示：

```text
ΔInventory = Inventory(B) - Inventory(P)
```

任一失败时，`delta_inventory_kg` 仍可计算为数值，但标记 `comparative_claim_status=blocked`，UI 只显示“服务不等价/物理校验未过；不形成减排结论”，同时展示两边 EENS、关键服务与排放清单。这里防住了“少供电所以更低碳”的伪贡献。

### 5.2 当前项目的关键调整

当前 `碳韧协同恢复` 允许普通负荷延迟且 README 已有“关键负荷一致、普通负荷预算”的叙述。Gate 要显式纳入普通负荷预算，不能只比较 `critical_recovery_pct`。`strategy_comparison.csv` 应增加：

```text
served_critical_kwh,served_normal_kwh,critical_eens_kwh,normal_eens_kwh,
physical_feasible_hours,service_gate_status,comparative_claim_status
```

并把当前报告中“total_carbon_kg 更低”严格表述为**运行排放清单差异**；是否称“减排”由 gate 决定。

---

## 6. Causal Attribution：动作对结果的可复算因果归因

### 6.1 归因口径

行动归因不是从优化器目标权重中“读出来”。采用小规模、确定性的**动作级干预重放**：在固定的同一 run 输入与所有其他被采纳动作下，撤销或替换单一动作，重新运行恢复—调度—潮流校验。该操作对应：

```text
Δ(action a) = Outcome(final plan) - Outcome(plan with do(a = off/replaced))
```

结果仅称为“该固定反事实设定下的边际差异（marginal effect）”，不宣称现场统计因果。每次反事实必须使用新的 `counterfactual_run_id` 并再次过物理和服务门。

### 6.2 归因类型与何时使用

| attribution_method | 适用对象 | 输出解释 |
|---|---|---|
| `direct_flow` | 调度能源流 | 如某小时柴油减少、电网进口变化；直接从能量流和 factor snapshot 得到。 |
| `leave_one_action_out` | 开关、修复、BESS/柴油策略动作 | 固定其他动作，撤销一个动作后重算。MVP 主方法。 |
| `paired_plan_delta` | B0 vs P1 总体 | 仅用于策略总体，不分配到动作。 |
| `allocation_only` | 多动作强交互，MVP 先不精确拆解 | 报 `unallocated_interaction_kg`，禁止硬摊。 |

MVP 先覆盖最多 10 个“改变拓扑、修复顺序或调度源”的关键动作。动作组合有明显非线性时：

```text
interaction_residual = plan_delta - sum(accepted_action_marginals)
```

将余量列为 `unallocated_interaction`，不把它平均涂给每个动作。后续需要更公平的联合贡献才做 Shapley 近似；那是 V2，不应阻塞十天交付。

### 6.3 causal_attribution.csv schema

| 字段 | 说明 |
|---|---|
| `attribution_id`, `run_id`, `action_id`, `causal_group_id` | 主键和关联。 |
| `method`, `counterfactual_definition` | 如 `leave_one_action_out`、`do(close_tie:T37=false)`。 |
| `baseline_ref`, `counterfactual_run_id`, `replay_command_hash` | 可复算定位。 |
| `outcome_name`, `observed_value`, `counterfactual_value`, `delta_value`, `unit` | 核心差值。 |
| `service_gate_status`, `physical_gate_status`, `claim_status` | `accepted` / `blocked` / `informational`。 |
| `factor_snapshot_hash`, `input_manifest_hash`, `output_evidence_hash` | 证据绑定。 |
| `interaction_residual_kg`, `confidence_note` | 解释交互和确定性局限。 |
| `created_utc`, `record_hash` | 审计链。 |

输出优先顺序：`inventory_kg`, `diesel_kg`, `grid_kg`, `crew_kg`, `served_critical_kwh`, `normal_eens_kwh`, `renewable_curtailment_kwh`, `switch_operations`。`avoided_grid_equivalent_kg`、弃光机会损失和 Carbon-SOC 强度只能作为解释性指标，不能直接作为动作减排相加。

### 6.4 一个合格的归因结论

```text
动作 act-0003 / close_tie T37：在同一暴雨场景、同一因子快照、其余最终计划锁定下，
撤销 T37 后 24h Inventory 从 41,178.6 kg 上升到 41,760.2 kg；两次潮流均可行且
关键服务等价，故记录边际贡献 +581.6 kgCO2 avoided。若撤销导致关键负荷服务失败，
记录为 `claim_status=blocked`，只保留“动作对服务的必要性”而不写减排贡献。
```

注意上述数字只是展示 schema 的例子，真实结果必须由 replay 生成。

---

## 7. Run Manifest 与 Evidence Seal

### 7.1 run_manifest.json

```json
{
  "schema_version": "1.0",
  "run_id": "...",
  "status": "sealed",
  "created_utc": "...",
  "completed_utc": "...",
  "command": "python -m gridrescue.cli --scenario 暴雨内涝 --output artifacts/runs/<run_id>",
  "git": {"commit": "<sha|dirty>", "dirty": false},
  "runtime": {"python": "3.11.x", "os": "Windows", "platform": "..."},
  "dependencies": {"lockfile_sha256": "sha256:...", "solver": "cvxpy:<version>"},
  "scenario": {"id": "...", "sha256": "sha256:...", "seed": 2026},
  "network": {"source_name": "MATPOWER case33bw", "source_sha256": "sha256:..."},
  "configuration": {"canonical_json_sha256": "sha256:...", "time_step_h": 1, "horizon_h": 24},
  "factor_snapshot": {"path": "factor_snapshot.csv", "sha256": "sha256:..."},
  "strategies": [{"strategy_id": "carbon_resilient", "plan_id": "...", "action_ledger_terminal_hash": "sha256:..."}],
  "gates": {"service_equivalence": "pass", "physical": "pass"},
  "evidence_index_sha256": "sha256:...",
  "seal_sha256": "sha256:..."
}
```

禁止把 `run_id` 仅取当前时间；它必须也绑定 input/config hash，避免“同名不同输入”。当前 CLI 生成的 `network_manifest.json` 可直接成为 manifest 的 `network` 证据来源。

### 7.2 Canonicalization 与哈希链

为了跨机器复算，hash 输入使用 UTF-8 JSON canonical form：键名排序、紧凑分隔符、禁止 NaN/Infinity、浮点在写入前按业务精度量化（例如 kWh/kw 到 6 位小数；因子按 registry 原值）。

对每条 ledger JSON：

```text
payload = record 去除 record_hash 字段
record_hash = SHA256("gridrescue-ledger-v1\n" + canonical_json(payload))
prev_hash = 前一行 record_hash；首行固定 "GENESIS:<run_id>"
```

对 run 输出：

1. `evidence_index.json` 按相对路径排序，记录每份输入/输出/log 的 SHA-256、bytes、media type、role。
2. `artifact_root_hash = SHA256(canonical_json(evidence_index))`。
3. `seal.json` 绑定 `run_manifest` hash、账本 terminal hash、factor snapshot hash、artifact root hash、创建时间和 verifier 版本。
4. 可选导出固定排序 ZIP；ZIP 自身 hash 是分发完整性证据，**不是**权威来源。解压后仍以 `seal.json` 为准。

这已能检测“改一行 dispatch、替换一份报告、删除一条 rejected action”三种常见篡改。它不提供外部时间戳或抗主机管理员重写历史的保证；若需要外部存在性证明，可在提交时把 `seal_sha256` 写入学校/项目制品库或签名 release。这个动作是普通发布存证，不引入区块链。

### 7.3 Seal 状态

UI 和报告只显示以下受控状态：

| seal_status | 条件 | 展示 |
|---|---|---|
| `draft` | run 未完成 | 结果为暂存，不可用于比较结论。 |
| `sealed` | 所有 required file、hash chain、门控齐全 | 显示“已封存 / 可复算”。 |
| `verified` | 独立 `verify_run` 通过 | 显示“复核通过”。 |
| `invalid` | 缺文件、hash 不符、链断裂或环境/命令不匹配 | 所有比较/归因标签置灰。 |

---

## 8. UI 点击追溯与呈现

### 8.1 最小 UI trace

在 `app.py` 中引入一个每次页面会话随机生成的 `browser_session_id`（不写 cookie，不采集 PII）。对以下事件写入 `ui_events.jsonl`：

- `run_requested`：点击“推演/重算”（建议由当前自动计算改为显式按钮触发）。
- `scenario_selected`、`strategy_selected`：记录 ID 和前后值。
- `hour_viewed`：记录 T+hour，用于解释用户看到的网络状态，不宣称影响求解。
- `ledger_action_opened`、`attribution_opened`、`download_requested`：记录被查看/下载的 `run_id`、`action_id`、artifact hash。
- 未来允许人为提议开关操作时，`action_proposed_by_ui` 与后台 `proposed/evaluated/simulated_applied` 通过同一 `request_id` 关联。

每条 UI 事件应包含：`ui_event_id, run_id, browser_session_id, event_type, page, widget_key, value_hash_or_safe_value, created_utc, prev_hash, record_hash`。未点击、未提议、仅由自动算法产生的动作不能伪造 UI id。

### 8.2 UI 设计（10 天 MVP）

现有五个 tab 中只需新增一个轻量“MRV 证据”区，不推倒界面：

1. **顶部 seal badge**：`sealed/verified/invalid`、run_id、输入短 hash、可复制复算命令。
2. **恢复数字孪生 tab**：动作表升级显示 `action_id / hour / target / status / 物理校验 / causal status`；点击某条（可用 selectbox 或 dataframe 行选择）侧边显示 before/after、关联的潮流行和 ledger hash。
3. **三策略对照 tab**：明确显示 Service Gate（G0–G4）矩阵。仅 `pass` 显示“服务等价条件下 ΔInventory”；否则显示 blocked 原因。
4. **能源与碳流 tab**：显示 `factor_id`、年/地区/时间分辨率和 “annual factor × scenario multiplier” 标签。
5. **MRV 报告 tab**：下载报告、`run_manifest.json`、`seal.json`、ledger 和一键验证命令。下载事件写 UI trace。

不建议把技术 hash 铺满所有图表；默认以短 hash 和 badge 显示，证据 tab 提供完整值，避免答辩界面变成日志浏览器。

---

## 9. 推荐实现切片（文件与接口，不在本波改代码）

| 组件 | 建议文件 | MVP 接口 |
|---|---|---|
| canonical JSON / SHA-256 | `src/gridrescue/evidence.py` | `canonical_bytes`, `sha256_file`, `build_evidence_index`, `verify_index` |
| ledger writer/verifier | `src/gridrescue/ledger.py` | `Ledger.append(event)`, `Ledger.verify(path)` |
| factor registry | `src/gridrescue/factors.py` | `load_registry`, `snapshot_for_run`, `validate_factor_row` |
| service gate | `src/gridrescue/mrv.py` | `evaluate_service_equivalence(baseline, proposed, validations, boundary)` |
| causal replay | `src/gridrescue/attribution.py` | `replay_without_action(run_manifest, action_id)`, `attribute_action(...)` |
| run bundle orchestration | `src/gridrescue/cli.py` / 新 `bundle.py` | `write_run_bundle(result, output_dir, command_context)` |
| CLI | `src/gridrescue/cli.py` | `--run-id`, `--seed`, `--seal`, `verify-run <dir>`, `replay-action <dir> --action-id` |
| UI trace / evidence tab | `app.py` | `emit_ui_event`, seal badge, action drill-down |
| tests | `tests/test_mrv.py`, `tests/test_evidence.py`, `tests/test_attribution.py` | 见第 11 节 |

以当前设计，`RestorationPlan.actions` 可在 `make_plan` 后立即正规化成 `ActionRecord`；`pipeline._simulate_with_loss_feedback` 每次迭代在 ledger 写 `evaluated/superseded`；最终采用的 plan 写 `simulated_applied`。CLI 最后固定顺序：写 inputs → 策略 outputs → ledger → gate → attribution → index → seal。

---

## 10. 可复算命令与操作序列

以下为**拟新增**命令接口；当前仓库尚未实现，实施时需以这些命令作为验收契约。

```powershell
# 1. 锁依赖、生成一个封存 run
$env:PYTHONPATH="$PWD\src"
python -m gridrescue.cli run `
  --scenario "暴雨内涝" `
  --seed 2026 `
  --output artifacts/runs `
  --seal

# 2. 独立验证：所有文件、factor snapshot、ledger 链、根 hash、门控
python -m gridrescue.cli verify-run `
  --run artifacts/runs/<run_id>

# 3. 复算同一 run：比较 evidence_index 与结果，而不是只看终端成功
python -m gridrescue.cli reproduce `
  --manifest artifacts/runs/<run_id>/run_manifest.json `
  --output artifacts/reproduced/<run_id>
python -m gridrescue.cli compare-runs `
  --expected artifacts/runs/<run_id> `
  --actual artifacts/reproduced/<run_id>

# 4. 对单个动作做 deterministic leave-one-out 重放并写 attribution
python -m gridrescue.cli replay-action `
  --run artifacts/runs/<run_id> `
  --action-id act-0003 `
  --mode remove

# 5. 所有自动化回归
pytest -q
```

复算成功的定义：`verify-run` 通过；同一 lockfile/OS 求解器条件下 canonical outputs hash 相等。若求解器/平台导致合法浮点末位差异，`compare-runs` 必须先逐字段按记录在 manifest 中的 tolerances 比较，再创建一个新 seal，绝不能静默覆盖原证据。

---

## 11. 测试矩阵与验收条件

### 必须自动化

| 测试 | 断言 |
|---|---|
| `test_factor_registry_requires_provenance` | 缺 source hash、unit、year、approval 或重复 `factor_id` 即失败。 |
| `test_factor_snapshot_is_immutable` | 同一 run 用 snapshot；随后修改全局 registry 不改变旧 run 复核结果。 |
| `test_action_ledger_chain_validates` | 正常 JSONL 链可验；修改中间 action、删除一行、改 `seq` 均失败。 |
| `test_ledger_action_matches_plan` | `simulated_applied` 动作集合、时间、target 与 `RestorationPlan` 一致；中文 display text 不参与主匹配。 |
| `test_rejected_action_has_constraint_evidence` | rejected 项必须含失败约束名和关联输入/潮流证据 hash。 |
| `test_service_gate_blocks_low_service_claim` | 构造少供关键或超过普通负荷预算的方案，`claim_status=blocked`。 |
| `test_service_gate_requires_physical_feasibility` | 任一 `validation.hourly.is_feasible=False`，即使排放更低也不可出 Δ 结论。 |
| `test_action_replay_deterministic` | 以固定 seed 重放 `act-0003` 两次，counterfactual output hash 相同。 |
| `test_interaction_is_not_double_counted` | 两个相互依赖动作的 marginal 和超出总差时，余量进入 `unallocated_interaction`。 |
| `test_run_seal_detects_dispatch_tamper` | 改一个 `grid_import_kw`，verify 必须 nonzero/invalid。 |
| `test_ui_trace_links_but_does_not_claim_execution` | `ui_intent` 关联 action；没有 `simulated_applied` 时 UI event 不被展示成最终动作。 |
| `test_reproduce_manifest` | 用 fixture manifest 重跑并与 gold evidence index 对比。 |

### 人工演示验收（5 分钟）

1. 选择“暴雨内涝/碳韧协同恢复”，运行后显示 sealed badge 与 run_id。
2. 打开 `act-0003`，现场展示其 `close_tie/T37`、T+0、径向/潮流通过、输入/输出短 hash。
3. 打开策略比较，展示 G0–G4；若全部通过才展示策略 ΔInventory。
4. 点击“重放该动作”，生成一个反事实 run，显示服务和物理 gate；不通过则只显示原因。
5. 下载 seal，运行 `verify-run`；人为改一位 `dispatch` 后再次校验，界面/命令都报 `invalid`。

---

## 12. 十天落地排程（以 2026-08-22 为 Day 1）

| 天 | 交付 | 退出标准 |
|---:|---|---|
| D1 | freeze schema：action、factor、manifest、gate、seal 字段；建立 fixture run | schema 评审通过，字段不再漂移。 |
| D2 | `evidence.py`：canonical JSON、file hash、evidence index；现有 CLI 输出纳入 index | 修改任一输入/输出可被发现。 |
| D3 | `ledger.py` + actions 结构化映射；导出 action ledger | 当前三策略每个 action 都有 target、小时、状态、链 hash。 |
| D4 | factor registry / snapshot；替换 carbon 常数的运行期来源 | factor provenance、snapshot tests 通过。 |
| D5 | service-equivalence gate；CSV/报告/UI 加 gate 状态 | 少供关键负荷 fixture 的 claim 被锁死。 |
| D6 | run manifest、seal、CLI `verify-run` | 全 run bundle 验证通过；篡改 fixture 失败。 |
| D7 | leave-one-out replay，先支持 `close_tie`、`repair_branch` | 一个真实策略动作可产生 counterfactual bundle。 |
| D8 | causal_attribution.csv、interaction residual、报告文本 | 不发生动作归因求和超过总策略差的双计。 |
| D9 | Streamlit evidence tab、UI trace、下载 trace | 点击—request—ledger—artifact 链条可展示。 |
| D10 | 全量 pytest、两个 disaster demo、ZIP 导出和答辩排练 | 交付封存 run、复算记录、篡改演示、5分钟视频。 |

**降级顺序**：若 D7 的动作重放工作量超预期，仍必须交付 seal、factor snapshot、G0–G4 gate 和动作 ledger；把 attribution 标为 `planned`，不生成“动作贡献”的数字。绝不能为了展示贡献而跳过服务/物理门控。

---

## 13. 风险控制与答辩口径

| 风险 | 控制 |
|---|---|
| “这是区块链吗？” | 回答：不是。是普通 SHA-256 文件完整性、append-only hash chain 和可复算 manifest；目标是审计效率，不是去中心化。 |
| 因子精度被质疑 | 报 source、地区、年、时间分辨率、假设 multiplier 与不确定性；年度因子不伪装成实时边际因子。 |
| 低碳来自少供电 | G2/G3 失败直接封锁减排/归因标签；保留 EENS 与供电结果。 |
| 电池被重复算减排 | 充电来源入账、放电只转移 Carbon-SOC；动作归因只看系统 inventory 差。 |
| 多动作耦合导致归因虚高 | 使用 leave-one-out，交互余量不硬分；V2 才做 Shapley。 |
| UI 被误认为现场控制 | 事件标注 `ui_intent`，模型采纳标注 `simulated_applied`，无现场状态字段。 |
| 本地管理员可重写所有文件 | seal 只能证明一组文件内部一致；对外提交时发布 seal hash/签名 release，形成时间上的外部锚点。 |

**一句话答辩版**：

> GridRescue 不把“低碳”写成优化器口号。每个动作都有结构化账本、每个因子有冻结来源、每个减排结论先过服务与物理门、每次推演有可验证的本地证据封条和一键重算命令。

---

## 14. 本波结论

先做 `factor snapshot + action ledger + G0–G4 + seal/verify`，这四件事能在十天内形成可信闭环；动作级反事实归因只覆盖少量关键开关/修复动作并明确交互余量。该路线复用现有 `RestorationPlan.actions`、dispatch、powerflow 和 CLI 导出，不改动当前的物理模型主线，也不靠区块链噱头掩盖证据缺口。
