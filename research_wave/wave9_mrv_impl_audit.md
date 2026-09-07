# Wave 9：MRV 实现审计（P0，只读）

**审计日期：2026-08-22**  
**范围**：`mrv.py`、`carbon.py`、`dispatch.py`、`pipeline.py`、`cli.py`、`data/factor_registry.csv`；为核对 `_safe_ties` 与账本的一致性，额外只读检查了 `restoration.py`。  
**操作**：只读检查与本地复算；**未改动任何文件**。

## 0. 结论与 P0 优先级

| P0 | 发现 | 风险 | 最小修复目标 |
|---|---|---|---|
| P0-1 | `factor_registry.csv` 的 `record_hash` 是占位符；运行时 registry 哈希 CSV 往返后也不可重算 | 因子记录不可审计，`verify_mrv_bundle()` 仍会报 verified | 单一、类型规范化的 factor registry loader；写入前/验证时逐行复算 hash。 |
| P0-2 | 柴油 `0.72` 仍在 carbon 默认值、MRV 默认 registry 和数据 CSV 各自定义；调度使用 carbon 默认值而非 registry | 优化、核算和导出可能悄然分叉 | registry 是唯一事实源；同一 `EmissionFactors` 实例贯穿 dispatch、carbon、MRV。 |
| P0-3 | `time_step_h=1.0` 只在 MRV 导出层声明；电池 SOC、EENS、碳项、服务 caps 都隐式假定 1h | 当前 1h 可算对，未来任何非 1h 参数都将错误 | P0 固定并 assert 1h；P1 才端到端传递 `dt`。 |
| P0-4 | `_safe_ties()` 按小时静默移除不再安全的联络线；MRV action ledger 只记录初始 close，不记录 automatic open | “after_state=closed / simulated_applied”与实际网络最终状态冲突 | 用实际 state transition 生成 ledger，补 `open_tie` 动作，并在 verify 回放/比较状态。 |
| P0-5 | verifier 只校验 action 行 hash/链及若干代数式；遗漏 factor/activity/inventory record hash、manifest terminal hash、输入 manifest linkage、evidence ref | `verified=true` 的含义强于实际检查内容 | 补全哈希链、引用解析、动作末端 hash 和跨表外键/方程检查。 |

**现状不应称为完整 MRV 防篡改验证**。它当前验证“文件索引未被普通改动破坏 + 少数算式成立”；其 seal 本身没有私钥/外部时间戳，代码也已明确标注为 file-integrity only。

---

## 1. `record_hash`：当前状态与精确问题

### 1.1 当前实现

- `mrv.py:43–44`：`_record_hash()` 对移除 `record_hash` 字段后的 JSON 做 SHA-256。
- `mrv.py:47–112`：`default_factor_registry()` 在内存中构造三条记录，并在 `mrv.py:110–111` 当场填入 hash。
- `mrv.py:455,473`：MRV bundle 写的是上述运行时生成 registry；**没有读取** `data/factor_registry.csv`。
- `data/factor_registry.csv:2–4`：三行 `record_hash` 都是文字 `generated-at-runtime`，不是真正 hash。

本地复算结果（2026-08-22）：

| 行 | data CSV record_hash | 以当前 `_record_hash()` 复算 | 结果 |
|---|---|---|---|
| grid-base-demo | `generated-at-runtime` | `sha256:9d334c5d…37b5fa` | 不匹配 |
| diesel-demo | `generated-at-runtime` | `sha256:5c217ab9…c39f75` | 不匹配 |
| crew-vehicle-demo | `generated-at-runtime` | `sha256:b0014fa9…2fcb40` | 不匹配 |

已有 MRV artifact 的 `inputs/factor_registry.csv` 虽保存了 runtime hash，但**重新由 CSV 读入再 hash 仍不匹配**。直接原因：运行时 `factor_version` 是字符串 `"1.0"`，`pandas.read_csv()` 后变成浮点数 `1.0`；当前 canonical JSON 把这两者编码成不同字节。`verify_mrv_bundle()` 从未校验 factor-record hash，因此旧 bundle 仍返回 `verified=true`。

### 1.2 P0 修改建议

| 位置 | 建议 |
|---|---|
| `mrv.py:27–44` | 增加 `canonicalize_factor_record()`：字段集合固定；`factor_version` 永远 string；`year` int；`value/uncertainty_pct` float；空文本保持 `""`；拒绝 `NaN`/未知字段。只对 canonicalized dict 计算 `record_hash`。 |
| `mrv.py:47–112` | 以 `load_factor_registry(path)` 替代硬编码的 `default_factor_registry()`；使用 `pd.read_csv(..., dtype=str, keep_default_na=False)` 后再按 schema 转型，并逐行验证 `record_hash`。若保留 demo fallback，也由同一 canonical row builder 输出。 |
| `data/factor_registry.csv:2–4` | 写入实际 canonical hash，删除 `generated-at-runtime`。该文件成为运行时 registry 的唯一来源，或明确删除该文件以免形成第二事实源。 |
| `mrv.py:455,473` | 写入已验证 source registry（连同 source-file SHA）；manifest 应保存 registry file SHA 与每项 `record_hash`。 |
| `verify_mrv_bundle():574+` | 读取 registry/snapshot 时执行 schema canonicalization 和每行 hash 校验；snapshot 的 `registry_record_hash` 必须能指回 registry 中同 activity 的有效 hash。 |

### 1.3 验收断言

```text
for every factor row:
    actual_record_hash == _record_hash(canonicalize_factor_record(row))

load(data/factor_registry.csv).to_csv(...).read_back(...)
    -> factor IDs, typed canonical payloads and hashes unchanged

mutate factor value but keep original record_hash
    -> verify_mrv_bundle(...).verified is False
```

---

## 2. 柴油系数 0.72：重复位置与单一来源改法

### 2.1 2026-08-22 当前重复位置

| 位置 | 值/用途 | 当前关系 |
|---|---|---|
| `carbon.py:11` | `EmissionFactors.diesel_kg_per_kwh = 0.72` | `calculate_carbon()` 的默认实绩核算值（`carbon.py:44`）。 |
| `mrv.py:70–88`，尤其 `:74` | `diesel-demo` registry value `0.72` | MRV factor snapshot/inventory 的值（`mrv.py:142–164`）。 |
| `data/factor_registry.csv:3` | `0.72` | 文件层 registry 值；当前运行时未读。 |
| `dispatch.py:84,209` | 默认 `DEFAULT_EMISSION_FACTORS` 参数 | 调度中的柴油碳项已通过 `emission_factors.diesel_kg_per_kwh` 使用默认对象（`dispatch.py:160–163`、`:361–364`），不再是独立字面量。 |
| `restoration.py:295–307`、`:307` | 未传入 factor instance | spatial dispatch 与 `calculate_carbon()` 都回落到默认 factors。 |

因此，**裸字面量在 dispatch 已消除，但“运行 registry / carbon default / 数据 CSV”仍是三套权威来源**。只要用户改 CSV 的 0.72，优化器、`calculate_carbon()` 和 MRV 都不会随之改变。

### 2.2 P0 修改建议

1. 用已验证 registry 构造唯一 `EmissionFactors`（grid base、diesel、crew）；同时保存三个 factor IDs/hashes。
2. 从 `run_pipeline()` / `run_scenario()` 向 `_simulate_with_loss_feedback()`、`simulate_strategy()`、`dispatch_resources_spatial()` 与 `calculate_carbon()` 显式传入同一 immutable `EmissionFactors`。
3. `mrv._factor_snapshot()` 接收同一 registry/factors，而不是自行 `default_factor_registry()`。
4. `ServiceContract.carbon_cap_kg`、dispatch `carbon_term`、inventory、reconciliation 全部使用这个同一 instance。
5. 审计字段新增：`diesel_factor_id`、`diesel_factor_record_hash`、`diesel_kg_per_kwh`。

### 2.3 验收断言

- 以测试 factor `diesel=0.81` 跑最小 scenario：dispatch objective carbon component、`calculate_carbon().diesel_kg`、MRV diesel factor snapshot、inventory diesel rows 全部等于 `0.81 × diesel_energy_kwh`（给定同一 `dt`）。
- bundle 中任意 strategy 的 `carbon_reconciliation.difference_kgCO2` 绝对值 ≤ `1e-5`。
- 对一个 bundle，`factor_registry.csv`、`factor_snapshot.csv`、inventory 内的 `diesel_factor_id/record_hash` 一致。

---

## 3. `time_step_h`：流转缺口

### 3.1 已声明的位置

- `mrv.py:191,195`：activity 行硬写 `time_step_h=1.0`、`energy_kwh=power`。
- `mrv.py:449–450`：config 声明 `horizon_h=24`、`time_step_h=1.0`。
- `mrv.py:597–600`：仅校验 activity 内部 `energy=power×time_step`。

### 3.2 实际计算仍隐式按 1h

| 文件/行 | 1h 假设 |
|---|---|
| `carbon.py:43–46` | 直接对 `kW × kg/kWh` 和 `kW` 求和，未乘 `dt`。 |
| `dispatch.py:140`、`:298` | SOC 递推把 kW 直接加/减到 kWh。 |
| `dispatch.py:150–156`、`:348–351` | `max_*_unserved_kwh` 对 kW 逐时求和。 |
| `dispatch.py:160–171`、`:361–364` | 碳和能量型目标对 kW 直接求和。 |
| `dispatch.py:358–360` | hospital/essential/normal EENS 均对 kW 直接求和。 |
| `pipeline.py:185–188` | `critical_limit`、`normal_limit` 从逐小时 kW 直接求和后当 kWh 使用。 |
| `mrv.py:204–269` | inventory 采用 activity 的 energy；若上游 `dt != 1`，MRV 可自洽而模型/Carbon 已错。 |

### 3.3 P0 与 P1 的正确切分

**P0（推荐，低风险）**：当前模型只支持 24 个等间隔 1h step。把这个约束变成单一常量/断言：

- 定义单一 `TIME_STEP_H = 1.0`；配置、MRV activity 和 horizon manifest 都引用它。
- 在 dispatch/pipeline 输入端 assert `time_step_h == 1.0`；不暴露可配置时间步。
- 声明所有 `sum(hourly_kw)` 在该 P0 不变量下才是 kWh。

**P1（若要支持非 1h）**：将 `time_step_h` 沿 `run_pipeline → run_scenario → _simulate_with_loss_feedback → simulate_strategy → dispatch_* → calculate_carbon → metrics → write_mrv_bundle` 传递；至少执行：

```text
SOC[t+1] = SOC[t] + η*charge_kw[t]*dt - discharge_kw[t]/η*dt
EENS = sum(unserved_kw[t]*dt)
CO2 = sum(grid_kw[t]*grid_factor[t]*dt) + diesel_factor*sum(diesel_kw[t]*dt)
energy_kwh = power_kw*dt
```

同时把所有 service cap、Pareto cap、metrics 中的 energy/throughput/curtailment 聚合改为乘 `dt`。这是涉及 `metrics.py` 的后续修改；P0 不应伪装成已支持。

### 3.4 验收断言

- **P0**：尝试 `time_step_h=0.5` 必须 fail-fast，不能静默产出结果。
- **P1**：同一恒功率 24h scenario 分别以 24×1h 和 48×0.5h 离散，EENS、SOC terminal、grid/diesel CO2 在容差内相等；activity 每行严格通过 `energy=power×dt`。

---

## 4. `_safe_ties` 的最终状态与动作账本不一致

### 4.1 代码路径

- `restoration.py:50–89`：`make_plan()` 将 `close_ties_greedily()` 结果写入 `plan.initial_tie_ids`，并只生成 `close_tie` + `repair_branch` 的计划动作。
- `restoration.py:92–100`：`_safe_ties()` 在每个小时尝试候选 tie；`evaluate_state()` 抛 `ValueError` 时直接跳过该 tie。
- `restoration.py:103–115`：`state_at_hour()` 每小时从同一 `initial_tie_ids` 重新调用 `_safe_ties()`；这意味着 tie 可在修复后因环网安全被**隐式打开**。
- `mrv.py:272–317`：`_action_rows()` 只从 `plan.initial_tie_ids` 建 `close_tie`，将 `after_state_json={"switch":"closed"}`、`status=simulated_applied` 写入账本；无 `open_tie`。

### 4.2 实测反例：暴雨内涝 / 最小失供与碳韧策略

只读运行 `run_pipeline("暴雨内涝")` 后：

```text
initial_tie_ids = (37, 33, 34)
hour 0–6  : {33, 34, 37}
hour 7–12 : {34, 37}       # repair L6 后 T33 已被 _safe_ties 移除
hour 13–22: {34}           # repair L27 后 T37 被移除
hour 23   : {}             # repair L13 后 T34 被移除；最终无联络线闭合
```

现有 `actions.csv` 的 `eens` ledger 却只有：

```text
h0 close T37, close T33, close T34
h7 repair L6
h13 repair L27
h23 repair L13
```

没有 `open T33/T37/T34`；三条 close 记录仍声称 `after_state=closed`。因此 action hash chain 可以正确、`verify_mrv_bundle()` 可以返回 true，但**账本不描述实际状态演化**。

### 4.3 P0 修改建议

| 位置 | 建议 |
|---|---|
| `restoration.py:50–115` | 区分 *plan intent* 与 *executed topology ledger*。新增 deterministic transition builder：逐小时比较 `state_at_hour(h-1).closed_tie_ids` 与 `state_at_hour(h).closed_tie_ids`。 |
| 过渡顺序 | 当前语义下，每个修复完成小时先写 `repair_branch`，再重新评估 ties，最后写所需 `open_tie`；h0 写实际可闭合的 `close_tie`。把同小时次序写成 `within_hour_sequence`。 |
| ledger 记录 | 对自动移除的 tie 写 `action_type=open_tie`、`origin=automatic_topology_safety`、`reason_code=RADIALITY_OR_STATE_SAFETY`、真实 `before/requested/after_state`、`physical_gate_status=topology_validated`。 |
| `mrv.py:272–317` | 不从 `initial_tie_ids` 重建账本；消费该 executed ledger 或以同一 deterministic transition builder 重放。action `after_state` 只能写实际执行状态。 |
| verifier | 从 scenario/plan/action 逐小时回放，检查 ledger 状态集合与 `state_at_hour()` 完全一致；不一致即失败。 |

### 4.4 验收断言

```text
flood/eens and flood/carbon_resilient:
  ledger includes h=7 open_tie(33), h=13 open_tie(37), h=23 open_tie(34)
  replayed closed-tie set equals state_at_hour(...).closed_tie_ids for h=0..23
  final ledger switch state == final FaultState.closed_tie_ids == empty set

for every strategy:
  action sequence is contiguous, deterministic, chronologically ordered
  every after_state is reachable from previous_state + recorded action
```

---

## 5. `verify_mrv_bundle()`：已覆盖项与遗漏

### 5.1 当前已检查

`mrv.py:574–625` 目前检查：

- seal 内 manifest/index 文件 hash；
- evidence index 中列出的文件是否存在、大小/sha 是否匹配；
- activity 的 `energy_kwh = power_kw × time_step_h` 与非负；
- inventory 的 `emission = activity × factor`；
- action `sequence_no/prev_hash/record_hash` 链；
- `carbon_reconciliation.reconciled`。

### 5.2 P0 缺口

| 缺口 | 位置 | 后果 | 最小补法 |
|---|---|---|---|
| factor registry 行 hash 未验 | `mrv.py:597+` 无 registry/snapshot hash 校验 | 当前 placeholder 与 CSV round-trip hash 错仍 verified | canonical loader + per-row hash + snapshot `registry_record_hash` linkage。 |
| activity/inventory 行 hash 未验 | `_record_hash` 仅在写入时存在 | 改行后若重建外层 index，内部 hash 不检查 | 对每行 `_record_hash(row)==record_hash`。 |
| manifest/seal terminal hash 未比较 | manifest `:531–538`、seal `:549`；verify `:610–611` | action CSV 可形成一条自洽新链，但与已声明 terminal 不一致 | 计算每 strategy terminal（空链=GENESIS），同时等于 manifest 与 seal。 |
| 所有策略的空链未验 | `_verify_action_chain()` 仅遍历 group | 无动作 strategy 的 terminal 语义未校验 | 遍历 `STRATEGY_SLUGS` 全集。 |
| schema/run ID 关联未验 | `:577–586` | manifest/index/seal 的 `schema_version`、`run_id` 不一致仍可通过部分路径 | 强制三方 schema/run_id 完全相同。 |
| manifest 输入 hash 未重算 | scenario/network/config/factor snapshot hashes `:523–530` 未在 verify 比 | 输入文件与 manifest 的语义映射未验证 | 重算并与 manifest 比较；network source SHA/registry SHA 也比较。 |
| snapshot ↔ activity/inventory 外键未验 | `:603–609` | factor/activity ID 或单位替换可保持乘法成立 | 检查 factor_id/version/record hash；每条 inventory `activity_id` 唯一存在且单位匹配。 |
| crew inventory 无 activity row | `_inventory_rows():244–268` 使用字符串 `event:scenario.crew_distance_km` | inventory 外键断裂，无法通用验证 | 将 crew distance 也写为标准 activity，带 scenario ref/hash。 |
| `primary_action_id` 始终空 | `_activity_rows():192` | 能源流与操作无法追溯 | 要么定义为非操作性流且 verify 允许空，要么填实/明确 `not_applicable`。 |
| evidence refs 未解析且当前路径失效 | `dispatch_ref :197` / `evidence_ref :310` 写 `../...` | bundle 实际位于 `mrv/run-*`，该相对路径指向 `mrv/dispatch_*`，而 CLI 文件在 output root；链接不可用 | bundle 内复制 dispatch/plan exports，并验证 ref 存在；或改为正确相对路径/manifest artifact URI。 |
| action ledger 与拓扑未验 | 只验 hash，不验状态 | `_safe_ties` 反例不被发现 | 执行 state replay（第 4 节）。 |
| seal 可重建 | `seal.json` 无签名/外部锚定 | 有文件写权者可同步改 index/seal | 保留 “file integrity only” 边界；P1 用签名/对象锁/可信时间戳。 |

### 5.3 建议的 verify 顺序

```text
parse required files and schema/run IDs
→ verify evidence-index membership and hashes
→ verify manifest input hashes/config/registry hashes
→ canonicalize + verify every registry/snapshot/activity/inventory/action record hash
→ verify inventory foreign keys, units and equations
→ verify dispatch/activity reconciliation and crew standard activity
→ verify action chain + manifest/seal terminal hashes
→ replay topology/action states hour-by-hour
→ verify carbon reconciliation
```

**重要**：单纯更新 `evidence_index.json` 与 `seal.json` 不构成攻击抵抗；以上逻辑检查能防止内部不一致，外部篡改抵抗仍需要 P1 签名或不可变存储。

---

## 6. 最小 P0 验收测试矩阵

| ID | 操作 | 期望 |
|---|---|---|
| MRV-01 | 加载 source registry | 三行均有真 SHA-256 record hash；canonical recompute 全匹配。 |
| MRV-02 | CSV write/read 再验证 | factor version 的 `"1.0"` 语义不变，hash 全匹配。 |
| MRV-03 | 将 factor value +0.01 且保留旧 hash | verify=false，错误为 factor record hash mismatch。 |
| MRV-04 | 使用 diesel=0.81 构造 bundle | optimizer/carbon/MRV/inventory/reconciliation 均使用 0.81。 |
| MRV-05 | P0 非 1h 输入 | fail-fast；不产生表面有效 bundle。 |
| MRV-06 | flood/eens action ledger | 有三条自动 open；逐小时状态和最终 state 完全匹配。 |
| MRV-07 | 篡改 actions 后重算 action rows/prev chain，但不改 manifest/seal terminal | verify=false，terminal mismatch。 |
| MRV-08 | 删除或错误修改一个 dispatch/action evidence ref | verify=false，reference missing/mismatch。 |
| MRV-09 | 篡改 inventory 的 `activity_id` 至不存在值，保留乘法成立 | verify=false，inventory activity FK mismatch。 |
| MRV-10 | 旧 bundle `flood_v08` | 修复后应因 factor/hash、ledger 或 ref 缺陷而失败，或由迁移版本明确标为 legacy; 不可继续显示为完全验证。 |

---

## 7. 建议提交顺序

1. **先 P0-1**：registry canonicalization + source file 收口；否则所有碳数字的来源链都不稳。
2. **再 P0-2**：将同一 `EmissionFactors` 注入 pipeline/restoration/dispatch/carbon/MRV；加 diesel mutation test。
3. **再 P0-4**：修复 executed topology ledger，确保 MRV 动作与物理 state 一致。
4. **最后 P0-5**：扩展 verifier 和 tamper tests；旧 bundles 做 legacy migration 标记。
5. `time_step_h` 在本赛题先作为 **1.0h fail-fast invariant**（P0）；非 1h 全链改造列入 P1，避免半实现。

## 8. 对答辩的准确口径

> “MRV 当前是合成赛事数据的文件完整性与算式可复算层。P0 固化 factor 记录、优化/核算的单一因子来源、真实拓扑执行动作账本，以及跨表验证；它不替代第三方核证或防止拥有完整写权限者重封存。时间步在当前版本固定为一小时，非一小时仿真将在端到端能量单位传递完成后开放。”
