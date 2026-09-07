# Wave 7：GridRescue 动作级 MRV 代码审计（仅审计）

**审计范围：** `src/gridrescue/carbon.py`、`report.py`、`restoration.py`、`cli.py`、`artifacts/flood_v05/`、`research_wave/wave6_mrv_schema.md`；为核对数据来源，额外只读查看 `dispatch.py`、`metrics.py`、`pipeline.py`、`scenarios.py` 与现有测试。未修改生产代码、测试、既有 artifact。

## 结论

Wave 6 定义的 MRV contract 尚未落地：当前 v05 是一组可复现的**策略仿真导出**，但没有 run bundle、因子快照、活动账、排放清单、动作 hash chain、G0–G4 gate、seal 或 verify CLI。最小实施应以“导出适配层”接在当前 `cli.py` 的三策略导出之后，保留既有求解与 CSV，避免改动恢复/潮流算法。

当前 `flood_v05` 在固定 `1 h` 步长上，`strategy_comparison.csv.total_carbon_kg` 与 `calculate_carbon()` 可复算一致（误差为写盘四舍五入）：

| strategy slug | grid kgCO2 | diesel kgCO2 | crew kgCO2 | total kgCO2 |
|---|---:|---:|---:|---:|
| traditional | 30667.547122 | 7660.801901 | 10.580000 | 38338.929023 |
| eens | 42923.934978 | 0.000007 | 10.580000 | 42934.514986 |
| carbon_resilient | 41168.015906 | 0.000173 | 10.580000 | 41178.596079 |

`crew = 46 km × 0.23 kgCO2/km`。三个 dispatch 均有 24 行、`hour=0..23`，且逐时功率平衡残差约 `2e-5 kW` 或更小；这说明旧口径在 1 小时演示中自洽，但不等于已满足 MRV 证据链要求。

## 1. 现状与 Wave 6 contract 的缺口

| Wave 6 必需物 | 现有位置 | 审计结果 | 最小落地点 |
|---|---|---|---|
| `inputs/{scenario,network_snapshot,config,factor_snapshot}` | `scenarios.py`、`network_manifest.json`、隐含 dataclass 默认值 | 仅 network manifest 被导出；scenario/config/factor 均未冻结为 run 输入。 | 新 `mrv.py` / `mrv_schema.py` 生成 `inputs/*`。 |
| 正式 `outputs/actions.csv` | `RestorationPlan.actions`、`actions_<slug>.csv` | 只有 `hour,action` 展示列。 | `restoration.py` 提供结构化 action export；MRV writer 加序号/hash。 |
| `activity_energy_hourly.csv` | `dispatch_<slug>.csv` | 含 kW 列但缺 `time_step_h`、flow 行、source ref、record hash。 | `carbon.py` 或新 `mrv.py` 转换。 |
| `emission_inventory_hourly.csv` | `calculate_carbon()` | 只输出总额 dataclass，未保存逐条 factor/activity evidence。 | `carbon.py` 新 inventory builder。 |
| G0–G4 + `service_equivalence.json` | `pipeline.py`、powerflow CSV、comparison CSV | 有物理可行列和 EENS 指标，但无比较合同/claim status。 | `mrv.py` gate evaluator。 |
| action attribution | 无 | 无 leave-one-action-out 或 interaction residual。 | Day 2 新 `attribution.py`（或 `mrv.py`）。 |
| evidence index / seal / `verify-run` | 无 | 无不可变封签。 | `evidence.py` + `cli.py` 子命令。 |
| report claim gating | `report.py` + `cli.py` report append | 总排放直接展示，未区分 inventory 与可比较减排 claim。 | report API 接收 MRV status/claim。 |

## 2. 当前字段映射

### 2.1 计划与动作

| Wave 6 正式字段 | 当前来源 | 映射/处理 |
|---|---|---|
| `strategy_id` | 中文 `strategy` | 用稳定 slug：`traditional`、`eens`、`carbon_resilient`；中文名称只作 display。 |
| `plan_id` | 无 | 对冻结 scenario/network/config/action intent 的 canonical JSON 取 hash 前缀。 |
| `sequence_no` | action dataframe 行序 | 以生成顺序从 1 递增，禁止由展示文本排序。 |
| `action_id` | 无 | `act-0001`…；禁止从“闭合…”文本反推身份。 |
| `hour` | `RestorationPlan.actions.hour` | 可直接映射；应校验 `0 <= hour < horizon_h`。 |
| `action_type` | `action` 字符串 | 当前可从 `闭合联络开关 T<n>`→`close_tie`、`修复支路 L<n>`→`repair_branch` 解析；更稳妥是 `make_plan()` 直接结构化生成。 |
| `target_id` | `T<n>` / `L<n>` | 分别取 tie/branch ID；需保留 `target_type=branch`。 |
| `before/requested/after_state_json` | 无 | 对 tie 写 `open→closed`；repair 写 `failed→repaired/closed`，状态字典须与 `state_at_hour()` 结果一致。 |
| `status`, `reason_code`, `physical_gate_status`, `evidence_ref` | 无 | 至少已应用、被拒、候选三态；G1/潮流 CSV 给 evidence link。 |

**关键观察：** `make_plan()` 先把所有 `tie_ids` 写入展示 action（`restoration.py:82–88`），但实际状态每个 hour 又经过 `_safe_ties()`（`92–100`）筛选。正式账本必须记录最终是否 `simulated_applied`；只导出计划文本会把被安全筛掉的 tie 误标为已执行。

### 2.2 能源活动与排放清单

| Wave 6 `energy_flow` / inventory | 当前 dispatch 列 | 换算与边界 |
|---|---|---|
| `grid_import` | `grid_import_kw` | `energy_kwh = grid_import_kw × time_step_h`；进入 `grid_scope2_location` inventory。含用于供电、充电与网络损耗的上级电量。 |
| `diesel_generation` | `diesel_generation_kw` | 同上；进入 `diesel_scope1` inventory。 |
| `pv_available` | `pv_available_kw` | 活动记录；**不**写 inventory。实际 PV 消纳可由 `pv_available_kw - renewable_curtailment_kw` 衍生。 |
| `bess_charge` | `battery_charge_kw` | 活动记录；不写 inventory。 |
| `bess_discharge` | `battery_discharge_kw` | 活动记录；不写 inventory，绝不生成负排放。 |
| `renewable_curtailment` | `renewable_curtailment_kw` | 活动记录；不写 avoided-emission inventory。 |
| `unserved_critical` | `unserved_critical_kw` | 服务 gate/活动证据；不写 inventory。 |
| `unserved_normal` | `unserved_normal_kw` | 服务 gate/活动证据；不写 inventory。 |
| crew vehicle | `scenario.crew_distance_km` + `EmissionFactors.crew_vehicle_kg_per_km` | 现有是 run/strategy 常数，须先冻结 distance、单位、因子和来源，再生成 event/crew inventory 行。 |
| grid factor | `grid_carbon_kg_per_kwh` | `hourly_profiles()` 由 `0.5366 × grid_carbon_multiplier × profile` 生成；每小时冻结进 factor snapshot。 |
| diesel factor | `EmissionFactors.diesel_kg_per_kwh=0.72` | 建 registry/snapshot；不能继续把 magic number 分别留在 `carbon.py` 与 `dispatch.py`。 |
| curtailment opportunity factor | `EmissionFactors.curtailed_renewable_opportunity_kg_per_kwh=0.5366` | 仅解释性参数；不得写 inventory/减排/动作贡献。 |

### 2.3 物理与服务 gate 证据

| Gate | 可复用证据 | 缺口 |
|---|---|---|
| G0 同边界 | scenario、model SHA、24 h 固定时域、dispatch config | 当前未输出 scenario/seed/config/factor snapshot hash，且没有 baseline/proposed comparison contract。 |
| G1 物理 | `powerflow_<slug>.csv.is_feasible`，支路/节点/组件 CSV | 可用，但须冻结为相同 run 的 evidence，并在 gate 结论中逐小时检查。 |
| G2 关键服务 | `critical_eens_kwh`、CareTask CSV | 当前 comparison 可做聚合输入；定义应明确基线、epsilon、是否采用 CareTask 额外门槛。 |
| G3 普通服务 | `eens_kwh - critical_eens_kwh` 或 dispatch `unserved_normal_kw` | 当前碳韧策略相对 EENS baseline 的普通失供增加：`4787.6723 - 2223.1143 = 2564.5580 kWh`；在默认预算 0 下应阻断“同服务减排” claim。 |
| G4 数据/完整性 | network SHA、现有 CSV | 没有 factor source hash、input manifest、evidence index 或 seal，当前只能 `conditional/blocked`，不可称已核证。 |

## 3. 易发生的双算、漏算与单位错误

### P0（上线 MRV 前必须封住）

1. **`kW` 被当成 `kWh`，时间步长隐含为 1。**
   - `carbon.py:39–42`、`metrics.py:29–43` 和 `dispatch.py` 的各 horizon sum 都直接求和；这在 v05 的 1 h step 成立，改为 15/30 min 会按 `1/time_step_h` 夸大 EENS、柴油、PV、弃电和排放。
   - 修复原则：Run config 必带 `time_step_h`，所有 energy/inventory/gate 成本统一乘该步长；dispatch SOC 方程也要相应乘 `time_step_h`。

2. **同一柴油因子存在双真相。**
   - `carbon.py:10` 使用 dataclass `0.72`，`dispatch.py:157/354` 又硬编码 `0.72` 进入优化与 `carbon_cap_kg`。
   - 因子升级或 gas basis 改造后，优化约束和报表清单可能分叉；必须只从 factor snapshot 读取，或把同一 frozen factor 显式传入 dispatch 与 inventory。

3. **`curtailed_renewable_opportunity_kg_per_kwh` 极易被当成“避免排放”。**
   - `carbon.py:49` 输出 `avoided_grid_equivalent_kg`，虽未纳入 `total_operational_kg`，字段名称可在后续 report/UI/attribution 被误用。
   - Wave 6 已规定它不进 inventory、不进比较差额、不归因给动作；正式 MRV API 应将其放到 `sensitivity_metrics`，避免进入 `CarbonBreakdown` 的可汇总字段。

4. **crew 排放可能随策略/反事实双算或失真。**
   - 当前每种 strategy 直接用同一 scenario distance（`restoration.py:307`），因此三策略总碳都加 `10.58 kgCO2`。同边界比较时这会抵消，但若 leave-one-action-out 改变 repair/tie/crew schedule，继续沿用或重复追加固定 distance 都会错误。
   - 第一版需把 `crew_distance_km` 标记为 frozen plan/run input；反事实明确定义为“相同 crew event”或由可证据化的 route model 重算，二者不得混用。

5. **“增量排放”文字没有可比基线。**
   - `report.py:34` 称“比较恢复方案的增量排放”，但 `calculate_carbon()` 输出的是每个策略的 operational total；CLI 也单独输出三份报告，未给 baseline、G0–G4 或差额。
   - v05 的碳韧与 EENS baseline 普通服务不等价（G3 默认失败），报告必须仅称“原型运行排放清单”，差额只能标为未门控的策略差异。

### P1（与 P0 同批做，避免证据错配）

6. **行动展示表没有实际状态、拒绝动作或证据链接。** `actions.csv` 只有文本，无法证明 `RestorationPlan`、`state_at_hour()`、潮流结果三者一致。
7. **没有因子版本/gas basis/source hash。** 当前字段名默认 CO2，但 registry/snapshot 缺失时后续 CO2/CO2e 混合无从阻止。
8. **CSV 格式不满足 canonical MRV。** v05 出现科学计数法（如 `1e-05`、`4e-06`），而 Wave 6 明确禁止；float 也没有统一最多六位、无 NaN/Infinity 的写盘器。
9. **输出不是单一 bundle。** 当前 `--output` 可直接覆写目录，文件无 `run_id`、no logs、no immutable snapshots；跨次运行/strategy 结果可混放。
10. **运行时默认参数未冻结。** `ResourceConfig`、`DispatchWeights`、scenario seed、solver/version，以及 `pipeline.py` 的 normal allowance 8% 都影响结果，却未导出到 evidence。

## 4. 最小可实施的代码/API/文件清单

不改求解算法；按 P0/P1 增加导出、验证、门控。建议以低耦合新模块完成。

### P0：Day 1，可封存、可复算

| 文件/模块 | 最小新增 API | 职责 |
|---|---|---|
| **新增** `src/gridrescue/mrv_schema.py` | `MRV_SCHEMA_VERSION`、`RunContext`、`FactorRecord`、`required_bundle_paths()`、`canonical_json_bytes()`、`sha256_prefixed()`、`write_canonical_csv()` | schema 常量、ID/单位校验、canonical JSON/CSV/hash；禁止散落实现。 |
| **新增** `src/gridrescue/mrv.py` | `build_factor_snapshot(...)`、`build_activity_energy(...)`、`build_emission_inventory(...)`、`export_action_ledger(...)`、`write_run_bundle(...)` | 将已有 `StrategyResult`、validation、scenario/model/config 转成 Wave 6 inputs/outputs。 |
| `carbon.py` | `EmissionFactors` 加 `gas_basis` / stable factor IDs（或由 `FactorSnapshot` 注入）；新增 `build_inventory_from_activity()` | 继续保留 `calculate_carbon()` 作为 legacy summary，但 summary 必须由 inventory 聚合复算。 |
| `restoration.py` | `RestorationAction`（或 `RestorationPlan.action_events`）和 `structured_actions(plan, ...)` | 直接输出 `close_tie/repair_branch`、target、requested state，而非解析中文 display text；保留 `actions` 展示 dataframe 以兼容 UI。 |
| `cli.py` | `run --seal`（兼容旧 `--scenario/--output`）或 subcommand `run`；传入 output run dir | 写 `artifacts/runs/<run_id>/inputs`、`outputs`、`logs`、`evidence`；旧 v05 平铺 CSV 可继续输出。 |
| **新增** `src/gridrescue/evidence.py` | `build_evidence_index()`、`seal_bundle()`、`verify_run()` | 生成 `run_manifest.json`、index、seal、verification。 |
| **新增** `data/factor_registry.csv` | registry 文件 | 初始三项：grid、diesel、crew；均标记 conditional D/E 并留 source/source-file hash 字段。 |

**建议 API 边界：**

```python
run_dir = write_run_bundle(
    root=Path("artifacts/runs"),
    model=result.model,
    scenario=result.scenario,
    strategies=result.strategies,
    validations=result.validations,
    config=FrozenRunConfig(...),
    seal=True,
)
verification = verify_run(run_dir)
```

`write_run_bundle()` 内部先冻结所有 inputs，再对每个 strategy 写 action/activity/inventory/powerflow/dispatch；不要让 `report.py` 直接参与数值核算。

### P1：Day 2，比较 claim 与动作归因

| 文件/模块 | 最小新增 API | 职责 |
|---|---|---|
| `mrv.py` 或 **新增** `mrv_gates.py` | `evaluate_service_equivalence(baseline, proposed, boundary) -> ServiceGateResult` | 实现 G0–G4，写 `service_equivalence.json`。 |
| **新增** `attribution.py` | `leave_one_action_out(...)`、`write_action_attribution(...)` | 固定输入和其余 action，重放 restore→dispatch→powerflow→inventory；写 `blocked/accepted/informational` 与 interaction residual。 |
| `report.py` | `markdown_report(..., mrv: MRVReportStatus | None = None)` | 默认显示“原型运行排放清单”；只有全 gate pass 才显示比较排放差额和 accepted attribution。 |
| `cli.py` | `verify-run <dir>`、`attribution <run-dir> --strategy ...` | 退出码非零表示 invalid；归因只处理最多 10 个 applied actions。 |
| **新增测试** `tests/test_mrv.py` | 见下一节 | MRV 独立于现有 core tests，防止算法测试掩盖证据链缺失。 |

## 5. 现有报告/API 的最小变更规则

1. **`CarbonBreakdown` 保持兼容，但降级为派生摘要。** `grid_kg/diesel_kg/crew_kg/total_operational_kg` 必须由 inventory 聚合；`avoided_grid_equivalent_kg` 改名/隔离为解释性指标。
2. **`markdown_report()` 不应自行推导或批准 claim。** 将 `claim_status`、gate 失败原因、inventory reference 由 MRV 层传入；没有 MRV status 时报告用明确的“未封签原型输出”状态。
3. **`RestorationPlan.actions` 不可作为正式 ledger。** 可继续供 CLI/UI 显示；正式 ledger 另有 stable `action_id` 与 hash chain。
4. **避免 report 被 seal 后再次拼接。** 当前 `cli.py:97–100` 先生成文本再 append validation summary。MRV 下先构造最终报告，再纳入 evidence index；verification 文件自身排除于 seal，避免循环。
5. **保持 legacy CLI 文件兼容。** 新 bundle 是唯一 claim/evidence boundary；旧 `actions_<slug>.csv` 等可继续生成但不能被当作 sealed evidence。

## 6. 必须测试（按 P0/P1）

### P0 必测

1. `test_activity_unit_equation_non_hourly_step`：2 小时、`time_step_h=0.25`；验证每条 `energy_kwh == power_kw * step`，carbon/metrics/gates 不再把 kW 直接相加。
2. `test_inventory_equation_and_basis`：grid/diesel 的 `activity × factor == emission`；CO2/CO2e、unit、负值、NaN/Infinity 均拒绝；BESS/PV/curtailment 不生成 inventory。
3. `test_factor_snapshot_immutable_and_shared_with_dispatch`：变 live registry 后旧 run 不变；柴油优化 carbon cap 与 inventory 使用同一 snapshot value，而非两个 `0.72`。
4. `test_plan_action_ledger_consistency`：`simulated_applied` 的 target/hour 与最终 `state_at_hour()`/plan 一致；被 `_safe_ties()` 排除的 tie 必须是 rejected/superseded 而非 applied。
5. `test_action_chain_tamper_delete_reorder`：改行、删行、调换、改 sequence、改 state JSON 均使 verify invalid。
6. `test_seal_detects_dispatch_and_report_tamper`：改 `grid_import_kw` 一格、改 report、一份 required file 缺失、evidence index 引用错误均 invalid。
7. `test_powerflow_evidence_gate`：任一 `is_feasible=False` 时 G1 false；同 run 能找到对应 CSV evidence。
8. `test_report_does_not_claim_comparative_reduction_without_gate`：没有 MRV 或 G3 fail 时，不出现“同服务减排/动作减排”数值。

### P1 必测

9. `test_g0_boundary_mismatch_blocks`：factor snapshot、seed、network SHA、horizon、step、solver config 任一不同即 blocked。
10. `test_g2_g3_blocks_current_flood_like_case`：critical 相等但 proposed normal EENS 超 baseline+0 budget，G3 false；本例可使用 v05 EENS/EENS+carbon-resilient fixture。
11. `test_leave_one_action_out_is_deterministic`：同冻结输入重放两次，counterfactual output evidence hash 相同。
12. `test_blocked_counterfactual_has_no_carbon_contribution_label`：反事实 G1/G2/G3 失败时仅写 service necessity/blocked，无 kg contribution。
13. `test_interaction_residual_is_unallocated`：accepted marginal 之和不等于 strategy delta 时，差额只在 `unallocated_interaction`。
14. `test_cli_run_seal_verify_exit_codes`：run--seal 后 verify 为 valid；篡改后 verify 返回非零并写 verification.json（该文件不进入 seal）。

## 7. 文档与 artifact 一致性问题

1. **Wave 6 第 9 节的具体数值已过时。** `wave6_mrv_schema.md:315` 写的是 `eens_kwh=2294.2657` 与 `0.0`、以及 `37406.4066` 与 `38922.1370`；当前审计对象 `flood_v05/strategy_comparison.csv` 是 `4787.6723`、`2223.1143`、`41178.5961`、`42934.5150`。规范应保留“G3 因普通负荷差异可能失败”的规则，但不应把旧 artifact 数值作为当前直接影响。
2. **Wave 6 说 CSV 禁科学计数法（第 2 节），v05 dispatch/powerflow 仍含 `1e-05`/`4e-06`。** canonical writer 是 P0 基础设施，不可只写文档。
3. **当前 v05 不具备 schema 所列的正式 required files。** 因此它可留作 legacy/demo baseline，不能被重命名为 `sealed` 或用于最终可比较减排 claim。
4. **现有 pytest 主要覆盖物理/策略/Pareto/Care；未覆盖 carbon factor snapshot、MRV units、seal、action ledger 或 report gate。** `artifacts/pytest_review_latest.log` 记录的既有一次运行是 `9 passed in 51.86s`，这并不验证 Wave 6 MRV contract。

## 实施优先级

- **P0（先做）：** canonical schema/hash、frozen inputs/factor snapshot、structured action ledger、activity+inventory、bundle+seal+verify、report 仅显示 inventory 状态。
- **P1（后做）：** G0–G4 comparison contract、claim gating、leave-one-action-out、interaction residual、CLI attribution。
- **避免重构：** 不必先改 CVXPY 模型、恢复排序、潮流求解或 CareTask 逻辑；MRV 适配应围绕已存在 `StrategyResult`/`FlowValidation` 读取并输出证据。
