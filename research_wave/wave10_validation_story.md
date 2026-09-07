# GridRescue 碳韧智网：Wave 10 竞赛级验证与证据叙事

**正式冻结日期：2026-08-22**  
**工作性质：验证设计与证据叙事；本轮未修改生产代码、模型参数、测试或 V08 正式 artifact。**

## 0. 结论先行：V08 已证明什么，尚未证明什么

V08 是一个可复算、可演示的**方法原型冻结包**，不是现场减排核证包。

### 已冻结、可直接引用的证据

| 证据 | V08 冻结事实 | 位置 |
|---|---|---|
| 基准物理回归 | `case33bw`：3715 kW / 2300 kvar；基准潮流损耗 202.67713 kW；最低电压 0.91309048 pu | `artifacts/v08_official/*/network_manifest.json` |
| 固定场景 | 暴雨内涝、台风、极端高温；每场景三策略均为 24/24 h 物理可行 | `artifacts/v08_official/{flood,typhoon,heat}` |
| 软件回归 | `pytest -q`：46 passed，160.60 s | `release_manifest_v08.json`、`outputs/GridRescue_MVP验证报告.md` |
| MRV 完整性 | 3 个正式 bundle、各检查 17 文件、`verified=true` | `artifacts/v08_official/verification_summary.json` |
| 当前主张门 | 三个正式 bundle 都是 `controlled_service_budget_inventory_difference`；均为 `same_service_pass=false` | 各 `mrv/*/run_manifest.json` 的 `gates.comparison` |
| 随机场景烟雾测试 | MC30：每策略 29/30 成功，Wilson 95% CI 83.33%–99.41%；失败 `scenario-0018` 被保留并可 replay | `artifacts/mc30_v04` |

### 关键的表述纪律

1. **V08 三固定场景的“碳韧协同恢复”不得表述为严格同服务降碳。** 当前三个正式 MRV bundle 已明示 `same_service_pass=false`，因此它们只支持“在公开普通服务预算内的受控服务取舍/清单差异”。
2. **MRV seal 只证明当前证据包的文件完整性与内部方程复算。** 它不等价于现场测量、可信时间戳、不可篡改存储或第三方核证。
3. **MC30 不是策略效应的严格配对推断。** 现有汇总主要是各策略的成功样本描述统计；Wave 10 将把同一冻结场景的策略结果做配对分析。
4. **V08 所有日期固定写为 2026-08-22。** 新建验证批次可有 batch/run ID 和时刻字段，但正式封面、图注、申报材料的版本日期不滚动。

---

## 1. Wave 10 验证合同：先分母、后比较；先门控、后故事

### 1.1 策略角色与预注册比较

| 代号 | 策略 | 角色 | 允许承担的结论 |
|---|---|---|---|
| A | 传统顺序恢复 | 经验/工程规则基线 | 对传统规则的描述性改进或代价 |
| B | 最小失供恢复 | 韧性服务锚点 | 对 C 的可靠性参考；不是“低碳失败者” |
| C0 | 碳韧 Pareto 的 `epsilon=0` 点 | **严格同服务候选** | 仅当 G0–G5 全过后，可做 C0–B 的严格同服务碳差比较 |
| C4 | 碳韧 Pareto 的预注册 `epsilon=4%` 点 | 受控服务取舍候选 | 只报告“关键服务不降级、普通服务预算 4% 内”的碳—服务取舍 |
| Cε | `epsilon=0,1,2,4,6,8,10%` 全前沿 | 决策曲线，不是单一冠军 | 展示取舍、失败点和推荐区间 |

`C4` 的 4% 在运行前固定，禁止事后从多条 epsilon 曲线中挑最漂亮的一点。现有暴雨 Pareto 的 4% 只是**设计可行性证据**，不是 36 场景总体效果。

### 1.2 六道门（Gate）与三类分析集

| Gate | 名称 | 每条 run 的判定 | 失败后的处理 |
|---|---|---|---|
| G0 | 输入冻结 | scenario/network/Care/factor/config/code hash 齐全且一致 | 不进入任何比较；保留 INVALID 行 |
| G1 | 求解完成 | dispatch 与反馈链路完成 | 计入可靠性分母；不以 0 代替指标 |
| G2 | 物理通过 | 24/24 可行、无功率缺口、无越压/热限，source adjustment < 0.1 kW | 计入可靠性分母；不进入性能均值 |
| G3 | 生命线通过 | CareTask、依赖、deadline、持续时长与任务电压均通过 | 计入可靠性分母；不进入主比较 |
| G4 | 服务可比 | C0 与 B 的医院/关键/普通服务 cap 相同；C4 仅满足公开 4% 普通服务预算 | C0 失去 strict 资格；C4 可留在 controlled 集 |
| G5 | MRV 复核 | `verify_mrv_bundle()==true`，对账与动作账本通过 | 计入失败与 evidence 表；不进入结果估计 |

- **Reliability/ITT 集：** 所有 36 个场景 × 每个策略；报告 attempts、G1–G5 gate 计数、失败原因、Wilson CI。
- **Strict paired 集：** 同一场景的 B 与 C0 都通过 G0–G5，且 C0 的 G4 为 strict；这是唯一可以写“严格同服务”的分析集。
- **Controlled paired 集：** 同一场景的 B 与 C4 都通过 G0–G3、G5，C4 满足预注册 4% 普通服务预算；只写“受控服务预算内的取舍”。

配对样本因某一策略失败而减少时，必须同时报告 `n_eligible / 36`、排除的 gate 与双策略状态；绝不将失败补为 0，也不把未配对的策略均值混进 C–B 主效应。

---

## 2. 36 个冻结、分层、共同随机数（CRN）场景

### 2.1 设计

采用 **3 灾种 × 3 强度 × 4 个冻结复本 = 36 个 scenario JSON**。同一个 `scenario_id` 的 A/B/C0/C4/Cε 读取**同一份** scenario JSON、SHA-256、网络、CareTask、因子快照和初始资源状态；策略仅改变策略目标/服务合同，不得重新抽样故障。

| 灾种 | 短码 | 强度层 | 核心扰动（仅使用当前 `DisasterScenario` 已有字段） |
|---|---|---|---|
| 暴雨内涝 | F | F1 / F2 / F3 | 故障支路组合、修复小时、PV derating、碳因子倍率、抢修里程、环境温度 |
| 台风 | T | T1 / T2 / T3 | 分散故障数与拓扑位置、修复小时、低 PV、碳因子倍率、抢修里程、环境温度 |
| 极端高温 | H | H1 / H2 / H3 | 故障支路组合、修复小时、PV derating、碳因子倍率、抢修里程、环境温度 |

强度不以“模型算出碳多就叫重”定义，而是在抽样前固定为：

- **S1（轻）：** 较少故障/较短修复、较高 PV 可用性、较低碳因子与较短抢修距离；
- **S2（中）：** 对应天气中心参数；
- **S3（重）：** 更多或更关键的故障、较长修复、较低 PV 可用性、较高碳因子与较长抢修距离。

`load_multiplier`、`thermal_limit_multiplier` 尚非正式 `DisasterScenario` 字段，**本轮不伪装为已支持**；它们只列为 P1 扩展，加入版本化 config、输入 hash 和回归测试后才能入正式统计。

### 2.2 冻结清单、ID 与随机数规则

| 字段 | 规范 |
|---|---|
| `scenario_id` | `GR26-F{1..3}-R{1..4}`、`GR26-T{1..3}-R{1..4}`、`GR26-H{1..3}-R{1..4}` |
| 冻结根 seed | `20260822`；单场景生成 seed 由 `(灾种,强度,复本)` 的固定映射派生并写入 JSON |
| 冻结对象 | scenario JSON、scenario SHA、network SHA、Care definition SHA、factor snapshot SHA、config SHA、code bundle SHA、依赖锁 SHA |
| CRN 规则 | 每个 scenario JSON 仅生成一次；A/B/C0/C4 与所有 ablation 复用该对象；禁止“按策略重抽” |
| 执行顺序 | 采用 Latin-style 轮换策略顺序；记录 `execution_order`、wall time、solver/version，避免机器热态被误当策略效果 |
| 可重复性 | 每个失败行写 `failure_phase/reason`，每个 scenario 写 replay manifest；重跑须得到相同 scenario SHA 与同一策略结果容差内一致 |

### 2.3 建议冻结资产目录

```text
artifacts/validation_v10_20260822/
  registry/
    scenario_catalog.csv
    scenarios/GR26-*.json
    freeze_manifest.json
    sha256s.txt
  runs/
    strict/                 # A/B/C0
    controlled/             # C4 与全 Cε 曲线
    ablations/
    sensitivity/
    mrv_tamper/
  analysis/
    experiment_runs.csv
    paired_deltas.csv
    validation_summary.csv
    exclusions_and_failures.csv
    bootstrap_manifest.json
  figures/source_csv/
  figures/png/
  figures/svg/
  README_reproduce.md
```

每个正式输出的 `created_at` 仍使用 2026-08-22 的冻结日；`batch_id` 而不是新日期区分批次。

---

## 3. 主实验、基线和统计方案

### 3.1 运行规模

| 批次 | 运行单元 | 最少物理 runs | 目的 | 优先级 |
|---|---:|---:|---|---|
| V0 | 无故障 case33bw golden + pytest | 1 + 全测试 | 物理/软件回归 | P0 |
| V1 | 36 CRN 场景 × A/B/C0 | 108 | 严格服务合同下的主比较 | P0 |
| V2 | 36 CRN 场景 × C4 | 36 | 预注册受控预算取舍 | P0 |
| V3 | 36 CRN 场景 × Cε 7 点 | 252 | 三灾种 Pareto 曲线、失败点与阈值 | P1 |
| V4 | 36 CRN 场景 × 4 个核心消融 | 144 | 机制归因 | P1 |
| V5 | OAT + 36 场景中心复核 | 见第 5 节 | 稳健性与阈值 | P1 |
| V6 | MRV 篡改矩阵 | 8–10 bundle mutations | 证据层防错能力 | P0 |

V1/V2 先于 V3–V5。若 V1 strict eligible 样本太少，结论降为“strict gate 通过率与失败机制”，而不是用 C4 或单场景替代 strict 结论。

### 3.2 终点、估计量与效应量

| 层级 | 终点 | 比较 | 主估计量 | 必报效应量 |
|---|---|---|---|---|
| Primary | `total_carbon_kg` | C0 − B（strict） | 配对平均绝对差 kgCO2 | `Δmean`、相对差%、配对标准化均差 `d_z`、wins/ties/losses |
| Co-primary safety | `critical_eens_kwh`、Care pass | C0 vs B | 配对差及任务通过差 | Δ、95% CI；任务为配对风险差和 exact/McNemar 结果 |
| Physical guardrail | minV、max loading、source adjustment | C0 vs B | 各约束余量/违例率 | 最小余量、超阈比例、Gate 计数 |
| Controlled | CO2、normal EENS | C4 − B | 配对差 | 同时报告 `epsilon=4%`、普通 EENS 绝对/相对增量 |
| Context | EENS、柴油、恢复时间、开关数 | A/B/C0/C4 | 描述性分层统计 | 均值、中位数、IQR、失败率；不夸大成因果冠军 |

约定：`Δ = candidate − B`，碳排 `Δ<0` 表示候选清单较低；EENS `Δ>0` 表示候选额外失供。百分比用 `100×Δ/B`，若 B 为 0 则写 `NA` 并保留绝对差，严禁无穷大百分比。

### 3.3 Paired bootstrap（预注册）

1. 以**场景**为重采样单位，而非将 A/B/C 行拆开重采样。
2. 在 9 个 `灾种×强度` strata 内各有 4 个复本；每次 bootstrap 在每一 stratum 内有放回抽取 4 个完整配对，保留 3×3 的平衡结构。
3. 固定 analysis seed `20260822`，`B=20,000` 次重采样，报告 percentile 95% CI；分析脚本、seed、版本与输入 CSV hash 写入 `bootstrap_manifest.json`。
4. 同时报配对均值差、中位数差、`d_z = mean(Δ)/sd(Δ)`、胜/平/负计数；图中展示所有 36 个场景点和连线。
5. 对 p 值只做辅助验证：对严格配对样本做两侧 sign-flip permutation（100,000 次、固定 seed）；同一 endpoint family 的次要 p 值用 Holm 调整。**CI 与效应量为主，不以单一 p 值当获奖故事。**
6. 成功/任务通过率使用 Wilson 95% CI；同场景策略成功差用 exact McNemar（或零 discordant pair 时明确注明不可估，而非虚报显著）。

### 3.4 分析表必须新增的字段

`experiment_runs.csv` 至少包含：

```text
batch_id, run_id, scenario_id, weather, severity, replicate, scenario_sha256,
strategy_id, epsilon, execution_order, run_seed, solver_seed,
network_sha256, care_definition_sha256, factor_snapshot_sha256, config_sha256,
code_bundle_sha256, solve_success, physical_pass, care_pass,
service_contract_pass, same_service_pass, mrv_verified,
eligible_strict, eligible_controlled, failure_gate, failure_phase, failure_reason,
wall_time_s, artifact_dir, replay_manifest_ref
```

`paired_deltas.csv` 至少包含：

```text
scenario_id, weather, severity, replicate, candidate, reference, comparison_mode,
epsilon, metric_name, candidate_value, reference_value, delta_abs, delta_pct,
pair_G0_G5, eligible_strict, eligible_controlled, exclusion_reason,
scenario_sha256, candidate_run_id, reference_run_id
```

---

## 4. 至少 24 项增强方向与优先级

| # | 增强方向 | 可执行交付 | 优先级 |
|---:|---|---|---|
| 1 | 36 个冻结 CRN 场景 | `scenario_catalog.csv` + 36 JSON + hash catalog | P0 |
| 2 | 9 个灾种×强度 strata | 3×3×4 的均衡抽样与冻结规则 | P0 |
| 3 | 策略输入同一性检查 | 每 scenario 的 A/B/C scenario SHA 一致性断言 | P0 |
| 4 | C0 strict 与 C4 controlled 分轨 | 两张主结果表、两套 claim label | P0 |
| 5 | G0–G5 gate waterfall | 每策略、每场景、每失败原因的 gate 计数 | P0 |
| 6 | paired delta 长表 | 所有 C0–B、C4–B 逐场景差值与排除原因 | P0 |
| 7 | 分层 paired bootstrap | 20,000 次、seed/hash 固化、95% CI | P0 |
| 8 | 效应量而非仅百分比 | absolute Δ、relative Δ、`d_z`、wins/ties/losses | P0 |
| 9 | 可靠性不删失败 | attempts/solved/failed、Wilson CI、failure manifest | P0 |
| 10 | 失败 replay 验收 | 抽检全部失败 + 至少一个成功，结果与 hash 对照 | P0 |
| 11 | 预注册分析计划 | endpoint、符号、CI、epsilon、排除规则写入 README | P0 |
| 12 | MRV 篡改矩阵 | activity/factor/inventory/actions/manifest/delete/rechain 等检测结果 | P0 |
| 13 | 统一证据索引 | run→source CSV→图→申报数字→视频台词的可追溯表 | P0 |
| 14 | 申报书数字校对 | 将“28项测试”统一修正为 V08 的 46 passed；所有主张加 evidence path | P0 |
| 15 | 视频台词门控 | 3:05 批量实验改为“配对估计 + CI + eligible n”；未跑完前不报总体效应 | P0 |
| 16 | 四类核心消融 | carbon objective、time-varying carbon、Care hard contract、P/Q feedback | P1 |
| 17 | DER 贡献消融 | 关 BESS/PV、报告柴油/EENS/弃电变化 | P1 |
| 18 | 安全联络重构消融 | 禁用 tie recovery，比较供电节点/开关/物理 gate | P1 |
| 19 | GFM/black-start 反例组 | 无 GFM 或无源孤岛必须 BLOCKED，不允许虚假供电 | P1 |
| 20 | OAT 参数敏感性 | PV、碳因子、修复时长、SOC、epsilon、因子范围与 failure threshold | P1 |
| 21 | 全局敏感性 | 80+ LHS 样本、PRCC/标准化回归与 bootstrap CI | P2 |
| 22 | 计算性能证据 | wall time、内存、失败率随故障数/规模的箱线或 ECDF | P1 |
| 23 | 多网规模外部效度 | 69/123 节点或匿名馈线替换实验 | P2 |
| 24 | MRV 外部可信锚定 | 签名、可信时间戳、对象锁/独立存储与 verifier release hash | P2 |
| 25 | 因子数据升级 | E 类工程假设→有来源、版本、适用期和不确定性等级的因子登记 | P2 |
| 26 | 时间分辨率闭环 | 0.5 h 的 EENS/SOC/CO2 全链单位回归；未完成前维持 1 h fail-fast | P2 |
| 27 | DER 无功能力闭环 | 每设备 `P²+Q²≤S²` 与过压吸收/充电/弃光闭环 | P2 |
| 28 | 真实资产 sidecar | GFM、黑启动、燃料、UPS、切换瞬断、频率/谐波的资产证据字段 | P2 |

**P0 完成条件：** #1–#15 完整可重跑、图源 CSV 与证据索引冻结；否则不把“36 场景总体稳健性”写入申报书或视频。  
**P1 完成条件：** #16–#20 至少形成可配置/有 hash 的实验接口，#22 报告资源消耗；否则只将其列为后续工程计划。  
**P2 是赛后研究，不占用 V08 的现有性能主张。**

---

## 5. 消融、敏感性与反例矩阵

### 5.1 核心消融（P1）

所有消融都必须复用同一 36 scenario JSON、同一 CareTask、同一因子快照并走 G0–G5；仅通过 feature/config flag 改变一个机制，flag 写入 `config_sha256`。

| ID | 固定/移除机制 | 回答的归因问题 | 主要指标 |
|---|---|---|---|
| AB-1 | 移除碳目标，保留服务合同和 P/Q | C 的碳差是否确由碳目标产生 | CO2 Δ、EENS Δ |
| AB-2 | 时变碳因子改为常数 | 时变碳信号是否改变调度时段 | grid import 时段、CO2 Δ |
| AB-3 | CareTask 硬合同改为类别优先级 | 任务级合同是否阻止“类别好看、任务失败” | Tier-1/Task pass、违约原因 |
| AB-4 | 移除迭代 P/Q feedback，仅保留事后检查 | 物理反馈是否淘汰表面最优候选 | G2 通过率、minV、max loading |
| AB-5 | 关 BESS/PV | DER 对柴油、弃电和 EENS 的贡献 | diesel、curtailment、EENS |
| AB-6 | 禁用安全联络恢复 | 重构对拓扑可达性与关键恢复的边际价值 | energized nodes、switches、Care |
| AB-7 | 移除 GFM/黑启动资格 | 成岛护照门控的防错价值 | BLOCKED island hours、虚假供电数 |

不把“关掉物理校验后更低碳”包装为绩效；它应作为**错误候选被物理门淘汰**的反例图。

### 5.2 OAT 敏感性（P1）

| 参数 | 预注册水平 | 输出 |
|---|---|---|
| PV derating | 中心值 × 0.50/0.75/1.00/1.25，截断 [0,1] | CO2/EENS/Care/G2 阈值 |
| grid carbon multiplier | 中心值 × 0.85/0.95/1.00/1.10/1.25 | C0/C4 排序是否翻转 |
| repair duration | 中心值 × 0.75/1.00/1.25/1.50 | 关键服务与失败 gate |
| BESS initial SOC | 20/40/60/80/100% | 柴油、EENS、C0 可行性 |
| Pareto epsilon | 0/1/2/4/6/8/10% | 前沿斜率、普通服务代价 |
| emission factor | -20/-10/0/+10/+20% | 碳效应符号和不确定性 |

每个点导出绝对值、相对中心点变化、G0–G5、failure gate、input hash；tornado 图中必须显示参数真实范围，不能只展示单侧“有利”变化。

### 5.3 反例/边界压力测试

| ID | 构造 | 必须出现的正确行为 |
|---|---|---|
| X-I1 | 无成网电源孤岛 | 硬失供/Blocked；不生成虚假 slack |
| X-I2 | 移除 GFM/black-start 资格 | island passport 为 `BLOCKED` 或证据不足，不涂绿 |
| X-C1 | node 17 重叠任务 25+12 kW | 30 kW 失败、37 kW 才能通过并发合同 |
| X-C2 | ICU 时段电压 0.96 pu | 即使系统潮流总体可行，任务电压门失败 |
| X-C3 | 不可能 CareTask | 形成可审计 anchor failure，不进入 frontier |
| X-M1 | 篡改 activity/factor/inventory/actions/index | verifier=FAIL，错误路径可见 |
| X-M2 | 全量重封存攻击模拟 | 清楚标为当前 integrity-only 边界；不虚称抵御有写权限者 |

---

## 6. 可执行实验矩阵与验收门

> 本表是实施清单。当前 V08 不必因本文件发生代码变更；每个尚未具备的 feature/config 接口须先实现、加测试、再入正式统计。

| Batch | 输入与规模 | 对照/配对 | 统计与验收 | 产物 |
|---|---|---|---|---|
| E00 | `pytest -q` + case33bw golden | N/A | 46 passed 基线；记录环境/依赖 hash | `logs/pytest_v08.txt` |
| E01 | 36 JSON × A/B/C0 | 同 scenario SHA | G0–G5；strict paired bootstrap；C0–B | `runs/strict/*`、`paired_deltas_strict.csv` |
| E02 | 36 JSON × C4 | 与 E01 的 B 同配对 | controlled paired bootstrap；明确 epsilon=4% | `runs/controlled/*`、`paired_deltas_c4.csv` |
| E03 | 36 JSON × A/B/C0/C4 | 同 scenario SHA | 可靠性 ITT、Wilson、McNemar、gate waterfall | `validation_summary.csv` |
| E04 | 3 灾种 × 7 epsilon（最低） | B anchor 相同 | 每点 caps/Care/P/Q/non-dominated；失败保留 | `pareto_points.csv`、`pareto_failures.csv` |
| E05 | AB-1~AB-4 × 36 | 完整 CRN | paired Δ + CI；不得绕过 G2/G3 | `ablation_results.csv` |
| E06 | OAT 中心点+全水平 | 每天气/严重度中心同配对 | threshold/tornado；报告触发失败点 | `sensitivity_results.csv` |
| E07 | MT-01~MT-08 | 从 sealed bundle 复制 | expected_detected=true；记录 verifier errors | `mrv_tamper_results.csv` |
| E08 | failure replay | 所有失败 scenario | scenario SHA 等；重放状态与原因一致或解释差异 | `replay_audit.csv` |
| E09 | 图表再现 | source CSV→PNG/SVG | 图源 hash、脚本 hash、数字与表一致 | `figures/*` + `figure_index.csv` |

### 6.1 推荐的执行序列（不触碰生产代码时的运行基线）

```powershell
cd C:\Users\ASUS\Documents\Codex\2026-08-22\n\work\gridrescue
$env:PYTHONPATH = "$PWD\src"
python -m pytest -q
python -m gridrescue.experiments --count 30 --seed 20260822 --output artifacts\validation_v10_20260822\smoke_mc30 --bootstrap-samples 20000
```

上述命令只可生成**当前 MC 接口的 smoke/replay 基线**。E01–E09 所需的 36 JSON catalog、C0/C4 batch runner、分层 paired bootstrap、消融 flags 和图表脚本应作为下一实现波次的独立验证工具，不得悄悄改写 V08 artifact。

---

## 7. 七张图重绘：每图都有统计边界、证据来源和禁止表达

| 图 | 重绘内容 | 必含元素 | 源数据 | 禁止表达 |
|---|---|---|---|---|
| Fig1 | **36 场景设计与 Gate waterfall** | 3×3×4 分层、A/B/C0/C4 attempts、G0–G5 漏斗、失败数 | `scenario_catalog.csv`、`experiment_runs.csv` | 只展示成功样本或隐藏 exclusion |
| Fig2 | **C0–B / C4–B 配对 raincloud + slope** | 所有场景点、配对线、weather facet、mean/median Δ、95% CI、eligible n | `paired_deltas*.csv` | 用未配对均值冒充效应；把 C4 标为 same-service |
| Fig3 | **主终点 forest plot** | CO2、critical EENS、Care pass、minV/loading guardrail；absolute Δ、relative Δ、`d_z`、CI | `validation_summary.csv` | 只报“下降 X%”不报绝对量/CI |
| Fig4 | **三灾种 Pareto 前沿** | epsilon、服务 caps、C0/C4 标记、淘汰点、Care/G2 状态 | `pareto_points.csv`、`pareto_failures.csv` | 删除失败点或只展示最优单点 |
| Fig5 | **物理约束热图** | scenario×strategy：minV、max loading、source adjustment、Care/G2；0.95/0.97 pu、100%、0.1 kW 阈值 | powerflow/Care exports | 只画恢复动画，不画物理余量 |
| Fig6 | **机制与敏感性双面板** | 左：AB-1~AB-4 effect/CI；右：OAT tornado 与 failure threshold | `ablation_results.csv`、`sensitivity_results.csv` | 将关 P/Q 后的假优结果作为性能宣传 |
| Fig7 | **MRV 信任链与可信边界** | 输入 hash→活动→清单→动作→seal→verifier；MT 检出矩阵；“integrity-only”红框 | bundle manifests、`mrv_tamper_results.csv` | seal=实测/第三方核证/不可篡改 |

**统一版式规则**：

- 图注固定写 `冻结日期：2026-08-22；数据类型：E 类合成赛事/工程假设（除非后续替换为可追溯实测）`。
- 每张图写 `N_total`、`n_eligible`、失败数及图源 CSV 相对路径；有 CI 的图还写 bootstrap method、B、analysis seed。
- 不截断 Y 轴制造差异；如为放大视图，保留全尺度 inset 或明确 axis break。
- C0 与 C4 用不同颜色、不同 claim label；A/B 用中性基线色。颜色不是“绿色=正确”的替代品。

### 配套两张表

- **Tab1：三主终点与证据表**——C0–B strict、C4–B controlled 分开；含 `estimate/CI/effect size/n_eligible/evidence path/claim class`。
- **Tab2：失败与反例表**——Gate、失败原因、scenario SHA、replay 路径、是否预期安全行为、处置状态。

---

## 8. MRV 可信边界：答辩时必须主动说清的“证据金字塔”

### 8.1 当前 V08 的强项

- 静态因子注册表、逐时 activity、排放清单及 `energy=power×dt`、`emission=activity×factor` 对账；
- 真实拓扑转换动作链及 terminal hash；V08 的测试已经覆盖 T33/T37/T34 自动 `open_tie` 的账本记录；
- manifest、evidence index、seal、独立 verifier；V08 三个固定场景 bundle 均为 17 文件 PASS；
- UI 复核页能显示场景错配与篡改 FAIL，而不是只展示绿色 seal。

### 8.2 当前 V08 的边界

| 边界 | 允许表述 | 禁止跳跃 |
|---|---|---|
| 数据 | E 类合成工程/赛事参数 | “等同某城市现场数据” |
| 网络 | 官方 case33bw，热限为工程假设 | “已代表真实馈线全部设备约束” |
| 因子 | 版本化 registry/快照 | “已完成权威因子或实测燃料核证” |
| seal | 文件完整性与内部复算 | “第三方核证”“不可篡改” |
| 统计 | 冻结合成场景上的条件性不确定性 | “全国/现实灾害总体效果” |
| 服务 | C0 strict 才可同服务；C4 是公开预算取舍 | “少供普通负荷也叫同服务减排” |
| 微网 | GFM/black-start 是模型推断或未知字段 | “已证明现场可孤岛运行” |
| 时间 | 当前端到端固定 1 h | “支持任意时间分辨率” |

### 8.3 建议答辩标准句

> “我们的 MRV 是合成赛事数据下的**方案级可追溯与可复算层**：它能验证输入、活动账、排放方程、动作链和文件完整性。它不替代现场测量、独立第三方核证或对拥有完整写权限者的不可篡改保证。严格同服务碳差只在 C0 与 B 的服务合同和全部物理/MRV gate 都通过时报告；允许普通服务预算的 C4 明确标注为受控取舍。”

---

## 9. 申报书、视频与答辩的证据叙事重写

### 9.1 申报书的更新规则

1. 在正式 36 场景实验尚未运行前，将“MC30 低 4.83%”保留为**原型 smoke-test 描述**，不得升级为总体稳健性或严格同服务结论。
2. `作品可行性/可操作性` 中“当前 28 项自动测试通过”应统一为 V08 可复核的 **46 passed**，并与 `release_manifest_v08.json` 保持一致。
3. “三个固定场景”的结果应改写为：
   - 三个 V08 固定场景均 24/24 h 物理可行；
   - 3 个 MRV bundle 均通过 17 文件独立复核；
   - 当前策略候选属于 `controlled_service_budget_inventory_difference`，不是 strict same-service claim。
4. 36 场景完成后，申报书只能引用 `Tab1` 的预注册 effect/CI、`n_eligible/36`、Gate 计数和图源路径；不能只摘录最佳天气或最佳 epsilon。

### 9.2 五分钟视频的替换节点

| 原视频段落 | V08 当前可说 | 36 场景完成后可替换为 |
|---|---|---|
| 2:25–3:05 Pareto | 暴雨单场景的 0/4/5/6% 物理 Pareto，清楚注明这是单场景工程证据 | Fig4：三灾种 Cε；C0 strict 与 C4 controlled 双标；失败点也可见 |
| 3:05–3:45 批量实验 | MC30 的 29/30 成功、Wilson CI、失败 replay；不把非配对均值说成总体净效应 | Fig1–3：36 CRN paired effect、95% CI、eligible n、failures/gates |
| 4:20–4:45 MRV | 三 bundle ×17 files PASS；seal=完整性+内部复算 | Fig7：完整信任链、篡改检出矩阵、integrity-only 边界 |

**视频的关键一句改写：**

> “我们不把单次漂亮结果当作总体结论。36 个按灾种和强度冻结的共同随机数场景中，所有策略共享同一故障、修复、资源与因子输入；严格同服务与受控服务预算分别计算配对效应和置信区间，失败场景与未通过门控的候选同样保留。”

### 9.3 面对评委追问的三段回答

- **为什么不是所有场景都称同服务？**  
  因为普通服务若有让步，碳差与服务差必须成对公开。C0 才承担 strict claim；C4 是固定 4% 预算下的透明取舍。
- **为什么 36 而不是 30？**  
  36 是 3 灾种×3 强度×4 复本的完整平衡设计，方便按场景配对、分层 bootstrap，并保留每一类天气压力的代表性；它仍是合成案例验证，不外推为全国实测。
- **MRV 是不是碳核证？**  
  当前是过程证据和内部复算。现场核证还需要真实计量、因子适用性、可信时间戳、独立签名/存储及第三方审阅。

---

## 10. 最终验收清单（Wave 10）

- [ ] 所有正式图表/申报/视频日期为 **2026-08-22**。
- [ ] 36 个 scenario JSON、catalog、SHA、seed 派生规则、freeze manifest 全部存在且可读。
- [ ] 同 scenario 内 A/B/C0/C4 的 scenario/network/Care/factor 输入 hash 一致。
- [ ] reliability 表保留 36 个场景的全量 attempts、G0–G5、失败原因和 Wilson CI。
- [ ] strict 主表只使用 B/C0 的 strict eligible pairs；C4 绝不写成 same-service。
- [ ] paired bootstrap 是按 9 个 strata 的完整配对重采样；B=20,000、analysis seed=20260822 已记录。
- [ ] 主结果同时给 absolute Δ、relative Δ、`d_z`、wins/ties/losses、95% CI、`n_eligible/36`。
- [ ] Cε 前沿包含全部 epsilon 和失败/淘汰点；无事后挑点。
- [ ] AB-1~AB-4、OAT、反例与 MRV tamper 的 config/input hash 都可追溯。
- [ ] Fig1–Fig7 均有 source CSV、图源 hash、图注边界和匿名检查。
- [ ] MRV 图和所有答辩材料均写清 `integrity-only`、E 类合成数据、非第三方核证。
- [ ] `release_manifest_v08.json`、V08 SHA 与冻结 artifact 原样保留；验证波次不覆盖正式 V08 目录。

---

## 11. 本轮读取范围（审计轨迹）

- `release_manifest_v08.json`
- `artifacts/v08_official/verification_summary.json` 及三场景 `run_manifest.json`
- `outputs/GridRescue_MVP验证报告.md`
- `outputs/碳韧智网_五分钟视频脚本与答辩题库.md`
- `outputs/第五届双碳赛申报书初稿_碳韧智网.md`
- `docs/competition_narrative.md`
- `tests/test_core.py`、`test_experiments.py`、`test_pareto.py`、`test_care.py`、`test_islands.py`、`test_mrv.py`、`test_app_mrv.py`
- `research_wave/wave8_validation_design.md`、`research_wave/wave8_uncertainty_calibration.md`、`research_wave/wave9_mrv_impl_audit.md`

本文件的所有“待实施”项目均为计划；未把待运行实验、待生成图表或待升级的 MRV 能力写成已经完成的事实。
