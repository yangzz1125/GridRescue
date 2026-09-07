# Wave 8：最小不确定性—校准层（10 天竞赛原型）

> **审阅范围**：`src/gridrescue/scenarios.py`、`experiments.py`、`pipeline.py`、现有 `artifacts/mc30_v04` 与 Wave 6/8 研究文档。本文只提出实现协议，**未改动任何代码**。
>
> **一句话结论**：P0 不要伪造“预测模型校准”。先把已有共同随机场景升级为**冻结、分层、可重放的合成压力集**，用服务/物理门控后的**分层配对 bootstrap**报告策略差异，并用 **stress envelope** 显示脆弱区间。可靠性图（reliability diagram）留到有真实的“事前概率预测 + 事后观测标签”之后。

---

## 1. 当前基线：已有的证据与关键缺口

### 已有、可复用

1. `run_monte_carlo()` 先生成一个 `DisasterScenario`，再由 `run_single_scenario()` 把同一场景交给全部三种策略；对同一个 `scenario_id`，三策略共享场景 JSON 与 SHA-256。这已经是 **common random numbers (CRN)** 的雏形。
2. 每行已有 `scenario_id`、`run_seed`、完整 `scenario_definition`、`scenario_sha256`、`solve_success`、失败阶段/原因、物理指标；失败不被填成零。`mc30_v04` 有 30 个共同场景 × 3 策略，且一个物理管线失败场景被保存在 replay manifest。
3. `summarize()` 已分别给 solve-success Wilson 区间和成功样本的 percentile bootstrap 区间。
4. `scenarios.py` 已有三个明确的合成灾种锚点：暴雨内涝、台风、极端高温；PV 降额、修复时长和网侧碳因子会进入实际计算。

### 不能把现有结果叫作“校准”的原因

| 观察 | 含义 |
|---|---|
| `sample_fault_scenarios()` 是 2–5 条故障、3–12 小时修复及若干范围的均匀抽样 | 它是 deterministic smoke test，不是已由历史故障数据拟合的灾害分布。 |
| 抽样场景没有 `hazard_family`、`severity_band`、`stress_id` | 目前无法检查每类压力是否被覆盖，也无法做按层比较。 |
| `ambient_temperature_c` 被保存但当前没有进入负荷、热限或故障计算 | 它当前不构成可校准的不确定性维度。 |
| 高温额外负荷由精确字符串 `scenario.name == "极端高温"` 触发 | **P0 catalog 不得把 `name` 改成带后缀的 ID**；层级标签应放在 catalog 元数据中，否则会意外移除高温负荷机制。 |
| Monte Carlo 行没有 CareTask/同服务合同 pass | 仅凭当前 MC 行，不能形成“同服务低碳”配对主张。 |
| `run_scenario()` 的碳韧协同策略允许普通服务预算让步（当前约为最小失供参考普通负荷的 8%） | 当前 `碳韧协同恢复` vs `最小失供恢复` 只能作为**受控取舍**，不能默认标成严格同服务降碳。 |
| 工程没有输出事前故障概率或预测区间，也没有真实观测标签 | reliability diagram、Brier score、coverage calibration 现在没有可解释的估计对象。 |

所以，P0 的科学表述应为：**“在预注册的合成压力场景集上，策略差异的可重放不确定性证据”**，不是“真实配网故障概率已校准”。

---

## 2. 最小方案：P0-SUC（Stratified Uncertainty Contract）

### 2.1 设计目标

P0 只新增一个证据层，不改写恢复、调度、潮流或 Pareto 优化器：

```text
冻结场景 catalog
  + 每个 catalog 行一次生成、三策略共享（CRN）
  + G0–G4/服务可比门控
  + 分层配对 bootstrap
  + stress envelope 与失败披露
  = 可答辩的合成不确定性层
```

### 2.2 最小主样本：36 个冻结合成场景

主集采用平衡分层而非继续用未标注的 30 个均匀样本：

```text
3 hazard_family × 2 severity_band × 6 scenario_replications = 36 contexts
36 contexts × 3 strategies = 108 strategy rows
```

- `hazard_family`：`flood`（暴雨内涝）、`typhoon`（台风）、`heat`（极端高温）。
- `severity_band`：`reference`、`stressed`。
- `scenario_replication`：`01…06`；每个由固定 master seed 和层键派生。
- 六个重复是为了同时满足小型竞赛的运行预算和每个 hazard×severity cell 至少有可见的样本量；它不支持对现实发生概率的估计。
- 36 个 context 是主要结果集；当前 `--count 30` 的未分层随机批保留为 regression/smoke test，不能与主集混合。

### 2.3 分层生成规则（全部基于当前已接入字段）

每个 hazard 从 `SCENARIOS` 取 canonical `DisasterScenario`；catalog 中保存外部标签，`scenario.name` 保持原始中文名称。使用 `master_seed=20260822` 及稳定哈希派生每一 cell/replication 的 generator seed。

| 层 | 故障集合 | 修复时长 | PV derating | grid carbon multiplier | crew distance | 解释 |
|---|---|---|---|---|---|---|
| `reference` | 保留灾种锚点故障支路 | 每条锚点修复时长乘 `U[0.90,1.10]`、向上取整 | 锚点值乘 `U[0.90,1.05]`，截断到 `[0,1]` | 锚点值乘 `U[0.95,1.05]` | 锚点值乘 `U[0.90,1.10]` | 合成的近锚点扰动。 |
| `stressed` | 锚点故障 + 1 条由 catalog 预先记录的非重复 active branch | 原锚点修复时长乘 `U[1.20,1.35]`；新增故障 `U{8,…,12}` 小时 | 锚点值乘 `U[0.60,0.85]`，截断到 `[0,1]` | 锚点值乘 `U[1.10,1.20]` | 锚点值乘 `U[1.15,1.35]` | 合成边界压力，不解释为实际重现期。 |

规则：

- 所有抽样值在创建 catalog 时冻结；运行策略时**禁止重新抽样**。
- `stress` 不是概率意义的“95% worst case”，仅指明更不利、预注册的合成参数带。
- P0 不加入 `LOAD_HIGH`、线路热限乘子或温度驱动故障：当前数据结构/潮流输入尚未把它们实现为版本化可重放参数。
- `EF_HIGH` 在 P0 主集由 `grid_carbon_multiplier` 的压力范围自然覆盖；它是碳核算/调度敏感性，不能被误读成物理供电压力。

### 2.4 CRN 与配对纪律

每条策略结果必须带同一 `context_id`、同一 `scenario_sha256`、同一 `catalog_sha256`。

```text
context c:
  scenario_c = deserialize(catalog[c].scenario_definition)
  result_A(c), result_B(c), result_C(c) = run the same scenario_c
```

配对差以候选 `C` 减参考 `B` 为例：

\[
\Delta^{CO2}_c = CO2_C(c)-CO2_B(c),\quad
\Delta^{crit}_c = EENS^{crit}_C(c)-EENS^{crit}_B(c),\quad
\Delta^{EENS}_c = EENS_C(c)-EENS_B(c).
\]

纪律：

1. A/B/C 不得各自生成不同 seed 或不同故障集。
2. 只在同一 `context_id` 上做差；缺任一对端、SHA 不等、输入 hash 不全时，该 pair 进入 failure/accounting，但不进 effect estimator。
3. “成功”不等于“可比较”：C–B 的严格同服务比较还必须通过相同服务合同门。
4. catalog 的 master seed、policy JSON、生成器版本、网络/Care/factor/code hash 必须写入 run manifest。

---

## 3. 门控与两类比较：避免少供电伪低碳

### 3.1 最小门控

| Gate | 条件 | P0 行为 |
|---|---|---|
| G0 input | catalog、scenario、network、factor、Care/contract、code/config hash 完整 | 缺任一项：`INPUT_INVALID`，不参与统计。 |
| G1 solve | `solve_success=true` | 失败保留，计入 attempted 分母。 |
| G2 physical | `physical_feasible_hours=24` 且 `source_adjustment_max_kw <= 0.10` | 否则 `PHYSICAL_FAIL`。 |
| G3 care | CareTask 必选任务、Tier-1、deadline/duration/voltage 合同全部通过 | P0 新增运行时导出；当前 MC 行尚未具备。 |
| G4 comparable | 两端同一 context；同服务则 service caps 相同且均通过 | 区分严格比较与受控取舍。 |

### 3.2 严格比较与受控取舍必须分表

| `comparison_mode` | 候选资格 | 可以说什么 |
|---|---|---|
| `strict_same_service` | B/C 均 G0–G4；C 使用 Pareto `epsilon=0` 或与 B 完全相同的公开服务 caps | “在本冻结合成压力集及该服务合同下，候选运行排放较低/未见关键服务平均恶化。” |
| `controlled_tradeoff` | B/C 均 G0–G3；C 公开 normal-service epsilon，且 metrics 含 `delta_normal_eens_kwh` | “在关键服务不降级、普通服务公开让步下的碳—服务取舍。” |
| `diagnostic_only` | SHA 不同、某端失败或未过 G0–G3 | 仅失败/诊断图；不进入策略优越性结论。 |

这条区分对当前项目是硬要求：现有 `碳韧协同恢复` 常规管线不是自动的 `strict_same_service` 对照。

---

## 4. 统计协议：分层配对 percentile bootstrap

### 主估计量

- 每个指标的总体点估计：36 个 context 的等权平均配对差；平衡设计使每个 hazard×severity cell 同权。
- 同时报告：mean、median、IQR、`win/tie/loss`、eligible pair 数、总尝试数、每个 cell 的 pair 数。
- 主要终点最多三个：`total_carbon_kg`、`critical_eens_kwh`、`eens_kwh`；不为每个附属指标制造显著性结论。

### Bootstrap 算法

1. 固定 `analysis_seed=20260822`，`B=5000` 次。统计开销相对潮流运行可忽略。
2. 对每个 `hazard_family × severity_band` cell，带放回抽取该 cell 的 eligible `context_id`，抽样数保持该 cell 的原 eligible n。
3. 合并六个重抽后的 cell，计算均值配对差。
4. 取 2.5%/97.5% 分位数为 percentile 95% interval。
5. 对每个 `comparison_mode` 独立做分析；禁止把 strict 与 controlled pairs 混在一次 bootstrap 中。
6. 所有 B 次抽样使用同一输入行顺序、analysis seed、bootstrap version，以便结果位级重放（允许浮点输出显示容差）。

不要用“两条未配对均值 CI 相减”代替上面的 interval；它丢掉了 CRN 产生的协方差，也没有处理 pair 完整性。

### 结果解释规则

| 结论级别 | 必须条件 |
|---|---|
| `eligible` | 总 eligible paired n ≥ 24，且六个 cell 每个至少 4 个 eligible pair；否则仅 exploratory。 |
| `lower carbon under strict contract` | strict mode；`CI_upper(mean ΔCO2) < 0`；并且 `CI_upper(mean Δcritical_EENS) <= 0`；每个 eligibility/failure count 公开。 |
| `no evidence of critical-service degradation` | strict mode；critical EENS 差的 95% CI 上界不高于预注册的 `0.001 kWh` 合同容差。 |
| `controlled carbon-service trade-off` | controlled mode；公开 epsilon、Δnormal EENS、critical/Care 门、CI；严禁命名为 same-service result。 |
| `heterogeneous / fragile` | 任一 cell 的点估计符号反转、或者 6 个 cell 中少于 5 个显示同方向时，用分层图展示，不汇成“全局优势”。 |

失败/物理通过率另用 Wilson 95% interval；一项原型可靠性候选门槛为：`physical+care pass lower Wilson bound >= 0.80`。低于该值依旧输出结果和失败 manifest，但不标“运行稳健”。这个门槛是竞赛原型的透明发布阈值，不是供电可靠性认证阈值。

---

## 5. P0 图：stress envelope，而不是伪可靠性图

### Fig U1 — 分层覆盖与失败矩阵（必做）

- 行：hazard；列：severity。
- 每个格：`attempted / solved / G2 pass / G3 pass / strict-eligible`。
- 旁列：失败 `context_id`、failure gate、replay ref。
- 通过门：三策略在每个 context 的 `scenario_sha256` 一致率必须为 **100%**。

### Fig U2 — C–B 配对碳—关键服务散点（必做）

- x：`Δcritical_eens_kwh`；y：`Δtotal_carbon_kg`。
- 颜色：hazard；形状：severity；灰色空心：diagnostic-only pair。
- 加 0 轴、每个象限的样本数、总体 paired n 与服务合同模式。
- 不截断坐标轴；strict 与 controlled 分面，不同图或不同 panel。

### Fig U3 — 分层 paired-effect forest（必做）

- 行：3 hazard、2 severity、overall。
- 两个 panel：mean `ΔCO2` 及 95% CI；mean `Δcritical EENS` 及 95% CI。
- 每行写 `n_eligible/N_context`，overall 只在 cell coverage 达标时展示。

### Fig U4 — Stress envelope（必做）

- x：severity (`reference` → `stressed`)；每个 hazard 分面；每策略一条线。
- y：分别为 `total_carbon_kg`、`critical_eens_kwh`、`min_voltage_pu`/`max_branch_loading_pct`。
- 每个点/带展示 cell 内 **P10 / P50 / P90**（n=6 时同时显示原始点，分位带仅作描述）。
- 同时画 G2/G3 pass proportion，不把失败填成 0 或省略。

**为什么这比 reliability diagram 合适：**当前项目没有“预测概率 `p`”，只有预注册的合成输入和一次求解结果。U4 描述的是策略面对输入应力的响应范围（stress envelope）；它不会暗示模型已被真实故障频率校准。

### 暂不画的图：reliability diagram

P0/P1 不画“预测故障概率 vs 实际频率”。如果用生成器自己造的 synthetic label 再画，图只验证生成器自洽，不能验证真实性；这会误导评委。

---

## 6. 产物与 CSV schema（建议目录）

```text
artifacts/uncertainty_v1/
  uncertainty_policy.json
  scenario_catalog.csv
  scenario_catalog.json                 # 包含完整 scenario_definition
  uncertainty_runs.csv
  paired_deltas.csv
  uncertainty_summary.csv
  stress_envelope.csv
  uncertainty_failures.json
  charts/U1_coverage_matrix.{png,svg}
  charts/U2_paired_carbon_service.{png,svg}
  charts/U3_paired_forest.{png,svg}
  charts/U4_stress_envelope.{png,svg}
  run_manifest.json
```

### `scenario_catalog.csv`（一行 = context）

```csv
catalog_id,context_id,hazard_family,hazard_name,severity_band,scenario_replication,
master_seed,generator_seed,stress_id,scenario_sha256,scenario_definition_ref,
fault_count,failed_branch_ids_json,repair_hours_json,pv_derating,
grid_carbon_multiplier,crew_distance_km,ambient_temperature_c,
network_sha256,factor_snapshot_sha256,policy_sha256,generator_version
```

约束：`context_id` 唯一；36 行恰好 `3×2×6`；JSON 内容的 SHA 与 `scenario_sha256` 一致；`scenario_definition_ref` 指向 JSON 中的完整 immutable payload。

### `uncertainty_runs.csv`（一行 = context × strategy）

```csv
run_id,catalog_id,context_id,hazard_family,severity_band,stress_id,
strategy_id,strategy_name,scenario_sha256,network_sha256,care_definition_sha256,
factor_snapshot_sha256,config_sha256,code_sha256,run_seed,solver_seed,
solve_success,physical_pass,care_contract_pass,service_contract_pass,
comparison_mode,claim_eligible,failure_gate,failure_phase,failure_reason,
eens_kwh,critical_eens_kwh,normal_eens_kwh,total_carbon_kg,
diesel_energy_kwh,renewable_consumed_kwh,physical_feasible_hours,
min_voltage_pu,max_branch_loading_pct,source_adjustment_max_kw,
wall_time_s,artifact_dir,replay_ref
```

约束：失败行的性能/结果指标为 empty/NA，非零；`attempted` 由行数而非非空 KPI 计数；`physical_pass` 采用 G2 的确定义。

### `paired_deltas.csv`（一行 = context × candidate/reference）

```csv
catalog_id,context_id,hazard_family,severity_band,candidate_strategy,
reference_strategy,comparison_mode,scenario_sha256,candidate_run_id,
reference_run_id,pair_complete,physical_pair_pass,care_pair_pass,
service_pair_pass,eligible_pair,epsilon,metric_name,candidate_value,
reference_value,delta_abs,delta_pct,exclusion_reason
```

- 对 `CO2`、critical EENS、total EENS、normal EENS 至少各生成一行。
- `scenario_sha256` 不一致时 `pair_complete=false` 并写入 `exclusion_reason=SCENARIO_MISMATCH`，这是 CI 阻断错误而不是普通缺失。

### `uncertainty_summary.csv`（一行 = comparison × stratum × metric）

```csv
analysis_id,catalog_id,comparison_mode,candidate_strategy,reference_strategy,
hazard_family,severity_band,metric_name,unit,attempted_contexts,
complete_pairs,eligible_pairs,mean_delta,median_delta,iqr_delta,
win_count,tie_count,loss_count,bootstrap_method,bootstrap_samples,
analysis_seed,ci_level,ci_lower,ci_upper,claim_status,claim_reason
```

`hazard_family=ALL,severity_band=ALL` 的 overall 行只在 balanced cells 有足够 eligible n 时输出。

### `stress_envelope.csv`（一行 = strategy × cell × metric）

```csv
catalog_id,hazard_family,severity_band,strategy_id,metric_name,unit,
attempted_contexts,solved_contexts,physical_care_passes,p10,p50,p90,
mean,min,max,pass_rate,pass_ci_lower,pass_ci_upper
```

### `uncertainty_policy.json`（必须冻结）

至少包含 `catalog_id`、master/analysis seed、catalog dimensions、抽样范围、canonical hazard definitions、eligible active branch rule、G0–G4、service tolerance、bootstrap 方法/次数、图版本、依赖版本、hashes、创建命令和禁止的结论用语。

---

## 7. 运行协议与预算

### P0：必须完成（最小有意义层）

1. 生成并 review 36 行 catalog，先检查 hash、分层和边界，**再跑求解**。
2. 每个 context 用同一 payload 完整运行 A/B/C，写 108 行 run results。
3. 导出 CareTask/服务合同状态到 run-level row；保留现有 replay/失败记录。
4. 建 `strict_same_service` C–B（Pareto epsilon=0）和 `controlled_tradeoff` C–B（常规碳韧）两张 paired 表。
5. 跑 fixed-seed 分层 paired bootstrap (B=5000)，产出 U1–U4 及原始 CSV。
6. 指定一个成功和一个失败 `context_id` 现场 replay；比对 scenario SHA 与 gate/result 状态。

**预算**：对一台提交演示机，目标 `P50 ≤ 5 min`、`P95 ≤ 10 min` 完成 36 contexts（108 strategy results）及导出；bootstrap/作图目标 `<10 s`。若实际运行超过 10 分钟：先保留 36 contexts，减少图重绘/重复 MRV 打包，不削减 CRN、分层或失败记录。记录 CPU、Python、solver、wall-time per context。

**P0 验收**：

- [ ] 36 contexts、108 行 A/B/C 结果；每 cell 正好 6 context。
- [ ] 每个 context 三策略 `scenario_sha256` 相同；一致率 100%。
- [ ] `scenario_catalog.json` 可独立重建每一个输入；抽样范围、seed、policy hash 完整。
- [ ] 失败行、失败 reason、replay ref 全保留；KPI 不是零填充。
- [ ] strict/controlled 统计、CSV、图完全分开。
- [ ] C–B CI 只取 eligible pairs；summary 同时显示 `n_eligible/N_total`。
- [ ] `physical+care pass` 的 Wilson 95% lower bound ≥ 0.80 才可贴“prototype robustness evidence”标签；否则仅作诊断/改进结论。
- [ ] 若 strict `n<24` 或任一 cell `<4`，overall conclusion 标 `EXPLORATORY`，不得写稳健优势。

### P1：有余力时做（压力包络与 seed 外部复核）

1. **OAT stress envelope**：仅在三个 canonical anchor 上，以 `PV ∈ {0.8,1.0,1.2}`、`repair ∈ {0.8,1.0,1.3}`、`EF ∈ {0.85,1.0,1.15}` 逐因子扫描；其他量固定。只使用当前已接入字段。
2. 每条曲线仍使用 A/B/C 同一 context；展示 rank flip、G2/G3 fail、P10/P50/P90，而非单点最优。
3. 执行一个外部 catalog (`master_seed=20260823`) 作为 confirmatory replicate；不删除主 seed 的坏结果，也不拿第二 seed 替换主结果。
4. 若 P0 已通过，再将 6 repeats 升到 10（60 contexts）以缩窄合成实验的估计不确定性。

**P1 接受阈值**：

- strict 结论在 confirmatory catalog 保持相同效应方向，且 3 个 hazard 中至少 2 个保持 `ΔCO2<0` 点估计；否则写“hazard-dependent”。
- 任一 OAT 曲线出现 G2/G3 失败、服务翻转或碳排序反转，必须在 U4/附表展示并停止“uniformly better”话术。
- P1 运行目标：canonical OAT ≤20 min；第二个 36-context catalog ≤10 min。超预算先减少 OAT levels，不减少成功/失败审计。

### P2：真实数据到位后的真实校准（未来）

P2 的对象不是策略指标，而是 **天气/资产/状态 → 未来故障概率或修复时间分布**。最低数据合同：

```text
asset_id, feeder_id, asset_type, location_or_zone,
observed_start_utc, observed_end_utc, outage_or_trip_flag,
failure_cause, repair_duration_h, planned_or_forced,
weather_timestamp, rain, wind, gust, temperature,
load, DER_availability, data_quality_flag
```

所需工作：

1. 以滚动时间窗或按 feeder 分组的 held-out split 验证；禁止把同一风暴/同一资产的相邻小时随机分到 train/test。
2. 预测层输出 `p(failure in horizon | x)` 或显式的 repair-time predictive distribution，并在训练期之外保存事前预测。
3. reliability diagram：10 个 **equal-count** probability bins，画 bin mean prediction vs observed event rate，附 binomial/Wilson 区间和每 bin `n`。
4. 同时报 Brier score、相对 climatology 的 Brier skill、calibration-in-the-large、calibration slope；罕见故障还应报 PR-AUC / event recall at operational alert budget。
5. 仅当 held-out 集至少约有 **100 个正事件**、每个可靠性 bin 至少 30 个 exposure，且完整性/数据漂移检查通过时，才把 reliability diagram 作为正式定量证据。低于此规模可画探索图，但不能据此校准概率。
6. 对 EENS、CO2 等连续结果的 prediction intervals，用 held-out empirical coverage：目标 nominal 90% interval 的覆盖率 85%–95%，并按灾种/feeder 分层。当前项目没有这一类预测区间，因此暂不评价 coverage calibration。

这些是模型改进的诊断门槛，不是配网运行许可、可靠性认证或真实减排核证阈值。

---

## 8. 现有合成场景能做什么，未来真实数据才可做什么

| 能力 | 现在（synthetic） | 需要未来真实数据 |
|---|---|---|
| CRN 公平策略比较 | **可做**；现有架构已接近，只需显式 catalog/metadata。 | 不依赖真实数据。 |
| 分层压力覆盖 | **可做**；以三灾种锚点和当前已接入字段构造，明确它是合成。 | 可用历史天气/故障联合分布替换先验范围。 |
| paired bootstrap CI | **可做**；对同一 context 的策略差并按层重采样。 | 可用历史情景做 out-of-sample effect validation。 |
| solve/physical/Care pass 可靠性 | **可做**；是原型执行可靠性，不是现实故障率。 | 可用现场运行/回放验证工程可靠性。 |
| stress envelope | **可做**；显示输入压力下的性能范围与失败面。 | 可用历史事件/预报集合提供有经验依据的输入分布。 |
| 预测故障概率 reliability diagram | **不可解释地做**；当前无预测概率和真实标签。 | **需要**带时间和资产映射的故障/工单、天气、网络资产数据。 |
| repair-duration distribution calibration | **不可解释地做**；修复时间是合成输入。 | 需要工单开始/结束、资源可达性、原因/资产类别。 |
| 碳因子误差校准 | **仅做假设敏感性**；registry 当前是 synthetic demo。 | 需要可信/版本化的区域时变因子与核算边界。 |
| 外推到真实武汉馈线 | **不可做**；case33、DER/Care 参数均是工程/赛事假设。 | 需要实际 feeder、DER、关键负荷、设备状态及事件历史。 |

---

## 9. 建议的测试清单（实现时）

| Test | 断言 |
|---|---|
| catalog determinism | 相同 policy/master seed 产生相同 36 行、顺序、JSON 和 SHA。 |
| canonical-name preservation | heat catalog 行仍令 `DisasterScenario.name == "极端高温"`，避免丢失现有高温负荷逻辑。 |
| stratification | 恰好 `3×2×6`；每层无重复 context；字段在 policy bound 内。 |
| CRN integrity | 任一 context A/B/C 的 scenario SHA、network/factor hashes 一致。 |
| gate correctness | G2/G3/G4 任一失败均令 strict eligible false；失败 KPI 非零填充。 |
| pair exclusion | 缺一端、SHA mismatch、服务不等的行不会进入 strict bootstrap。 |
| bootstrap determinism | 固定输入、seed、B=5000 输出 CI 一致；交换 candidate/reference，delta 与 CI 端点符号镜像。 |
| all-cell resampling | bootstrap 不跨 cell 破坏 6-cell 平衡。 |
| replay | 任取成功/失败 context 重放后输入 SHA 一致；数值在求解器容差内。 |
| plot/data consistency | 图中 n、pass counts、分位数与 CSV 重新计算值一致。 |

---

## 10. 推荐实施顺序（不做大而全）

### P0 — 先完成

- `scenario_catalog` + immutable policy/hash；保留 canonical names。
- 36 个 stratified CRN contexts。
- run-level Care/service gate、paired deltas、stratified bootstrap。
- U1–U4、failure/replay、strict/controlled 分离。

### P1 — 有余力再扩展

- OAT stress envelope（三个已接入因子）与第二 master seed。
- 60-context 扩容、feature-flag 消融和 runtime profiling。
- 若实际进入 `load_multiplier`/热限参数，先给它们加入 scenario JSON、policy、hash、单测，再纳入正式 OAT。

### P2 — 数据接入后

- 历史天气—资产—工单数据集、时间/馈线外部验证。
- 故障概率/修复时间概率模型的 reliability diagram、Brier/coverage calibration 与 drift monitoring。
- 将真实 weather replay、synthetic stress 和 operational data 分目录、分图、分主张。

---

## 11. 对答辩的准确表述

> “我们没有把合成故障抽样包装成真实世界概率校准。竞赛版本先固定了三类灾害、两档严重度的共同场景集，让所有策略共享完全相同的故障与资源输入；低碳比较必须同时通过潮流、生命线任务和服务可比门。我们报告分层配对置信区间、压力包络和所有失败场景。真实天气—资产—工单数据到位后，下一阶段才对事前故障概率做 reliability diagram 和 held-out calibration。”

---

## 12. 方法参考

- Efron, B. (1979). *Bootstrap Methods: Another Look at the Jackknife*. **The Annals of Statistics**, 7(1), 1–26. DOI: `10.1214/aos/1176344552`.
- Law, A. M. (2015). *Simulation Modeling and Analysis* (5th ed.). Common-random-number comparison design.
- Gneiting, T., & Raftery, A. E. (2007). *Strictly Proper Scoring Rules, Prediction, and Estimation*. **JASA**, 102(477), 359–378. DOI: `10.1198/016214506000001437`.
- Bröcker, J., & Smith, L. A. (2007). *Increasing the reliability of reliability diagrams*. **Weather and Forecasting**, 22(3), 651–661.

**最终建议**：在 10 天窗口内，P0 的“校准”应是输入、比较和不确定性报告的校准纪律；真正的概率校准必须等待独立真实观测。先把 36 个分层 CRN + paired CI + stress envelope 做完整，比增加未校准的天气故障 AI 模型更有科学价值。
