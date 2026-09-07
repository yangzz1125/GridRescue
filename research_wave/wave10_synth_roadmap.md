# GridRescue Wave 10 十日夺冠实施路线图（竞赛版）

**正式日期：2026-08-22**  
**适用仓库：** `C:\Users\ASUS\Documents\Codex\2026-08-22\n\work\gridrescue`  
**目标：** 在不夸大证据、不把合成结果包装成现场结论的前提下，用十天把 V08 方法原型收敛为“评委 30 秒看懂、3 分钟复核、追问可追溯、现场可恢复”的学术低碳竞赛提交包。

---

## 0. 路线总纲：先赢证据链，再加方法亮点

Wave 10 多份审阅的一致结论是：本轮胜负不由再塞一个 GNN、RL 或大规模 MISOCP 决定，而由以下四件事决定：

1. **单一事实源。** 所有 UI、PPT、视频、申报书、CSV、MRV ZIP 共用同一份事实卡、数字字典和 claim 白名单；统一 V08、46 passed、每 bundle 17 files、`kgCO2`、冻结日 2026-08-22。
2. **36 个冻结 CRN 配对场景。** 3 灾种 × 3 强度 × 4 复本；A/B/C0 严格服务与 C4 受控预算分轨；失败保留、不填零，报告 `n_eligible/36`、gate waterfall、paired delta、CI 和 replay。
3. **推荐资格工作台。** 首屏先回答“谁被保障、三门是否通过、碳—服务代价、证据在哪里”，而不是先展示八个 Tab 或长时求解。
4. **可复算且可诚实陈述。** 当前 V08 的主张仍是 `controlled_service_budget_inventory_difference`，`same_service_pass=false`；36 场景总体效应、CVaR、天气驱动和真实馈线映射，只有在相应 gate 通过后才升级为正式结论。

**本轮方法增量的取舍：**

- **必做（P0）：** factsheet/claim 锁、36 CRN catalog、G0–G5 批处理和配对统计、失败 replay、MRV 篡改矩阵、工作台首屏、四张核心图、离线演示与干净环境复跑。
- **条件做（P1）：** weather replay 最小数据包、weather→hazard 可解释链、GHI/PV 与温敏负荷 fallback、核心消融、GFM 反例、性能证据。
- **仅在 P0 全绿后做（O4）：** CareTask-CVaR 外层评估与 risk MRV；只称“冻结合成压力集上的尾部生命线风险比较”。
- **本十日明确砍掉：** GNN/RL、完整 DRO、MISOCP/AC-OPF 联合重写、真实概率校准、实时生产控制、区块链 MRV、复杂动画和全城最优叙事。

---

## 1. 当前基线与不可覆盖资产

### 1.1 V08 已冻结事实

- 官方 MATPOWER/Baran–Wu `case33bw`；33 节点、32 常闭支路 + 5 常开联络线，网络 SHA 已在 `release_manifest_v08.json` 固化。
- 三正式场景：`flood`、`typhoon`、`heat`；每个 MRV bundle 17 文件，均 `verified=true`，但 `same_service_pass=false`。
- `python -m pytest -q`：46 passed，冻结运行时 160.60 s。
- 现有代码已具备 dispatch、CareTask、P/Q 后验、成岛 passport、Pareto、MC30、MRV seal/verifier、Streamlit AppTest。

### 1.2 只读与版本纪律

- `artifacts/v08_official/`、`release_manifest_v08.json`、V08 SHA 作为**只读母本**；所有篡改演示在临时 fixture 目录完成。
- 竞赛新增结果放入 `artifacts/wave10/<batch_id>/`，不得覆盖 V08。
- 所有新实验写入 `scenario_id`、seed、输入 hash、代码包 hash、依赖/求解器版本、`created_at`、失败阶段和失败原因。
- 任何结果数字变化必须同时提交：输入版本、seed、运行时间、旧/新差异、回滚路径。

---

## 2. 十日执行表（D0=2026-08-22）

> 日期采用绝对日期，避免“第几天”歧义：D1=2026-08-23，D10=2026-09-01。

| 日程 | 当日目标与交付 | 文件级变更目标（新增/修改） | 实验顺序与运行物 | 当日测试门 | 冻结/停止条件 |
|---|---|---|---|---|---|
| **D1 8/23** | **事实源与范围锁**：解决所有数字、单位、claim、文件数矛盾。 | 新增 `docs/competition_factsheet.yaml`（或 JSON）；`docs/claim_dictionary.md`；`docs/evidence_index.csv`；`docs/scope_log.md`；更新 `README.md`、`release_manifest_v08.json`、`app.py` 首屏常量读取。 | 读取 V08 三 bundle 的 run/claim/checked-files；生成 canonical 数字表和禁止表述表。 | G0 规范检查：所有正式文案只出现 46 passed、17 files、`kgCO2`、2026-08-22；`same_service_pass=false` 时严格同服务文案自动禁用。 | **F0 事实冻结**。之后 UI/PPT/视频只读 factsheet；若事实冲突，停止 UX 美化，先修口径。 |
| **D2 8/24** | **36 场景 catalog**：建立 3×3×4 CRN、dev/test split、hash catalog。 | 新增 `src/gridrescue/weather_catalog.py` 或 `scenario_catalog.py`；扩展 `src/gridrescue/scenarios.py` 序列化；新增 `data/scenarios/wave10/{dev,oos}/` 36 JSON、`scenario_catalog.csv`、`catalog_manifest.json`；新增 `tests/test_weather_catalog.py`。 | 固定根 seed `20260822`；每场景写 `scenario_id`、灾种、强度、复本、seed、regime、network/Care/factor/config hash；同 ID 的 A/B/C0/C4 读取同一 JSON。 | G0 输入冻结、SHA 同一性、数量=36、strata=9×4、seed 可复放；随机顺序采用 Latin-style 轮换并记录。 | **F1 场景冻结**。不再添加场景字段；若生成器不稳，回退现有 `sample_fault_scenarios`，但必须把 36 个固定 JSON 作为外部输入。 |
| **D3 8/25** | **批处理骨架与 gate waterfall**：先跑通一层灾种 3×4，再扩展全量。 | 修改 `src/gridrescue/experiments.py`（scenario 输入、策略行、失败 schema、execution_order、solver/version）；新增 `src/gridrescue/validation_batch.py`（可并入 experiments）；新增 `tests/test_validation_batch.py`；产出 `artifacts/wave10/batch_smoke/`。 | V0 golden；V1 先执行 flood 12×A/B/C0；再接 C4。每 run 记录 G0–G5、failure_phase、failure_reason、eligible flags。 | G1 服务门、G2 拓扑/成岛门、G3 P/Q/电压/热限门、G4 CareTask 合同门、G5 MRV 输入与活动账门；失败进入 ITT/reliability 分母，不填 0。 | 若单灾种 smoke 无法端到端跑通，冻结开发在 `batch_smoke`，停止 Pareto/消融，优先修 schema 与失败回放。 |
| **D4 8/26** | **主批与配对统计**：完成 A/B/C0 36 场景，随后 C4 36 场景。 | 修改 `experiments.py`、`metrics.py`、`report.py`；新增 `src/gridrescue/paired_stats.py`（或并入 experiments）；新增 `tests/test_paired_stats.py`；产出 `experiment_runs.csv`、`validation_summary.csv`、`paired_deltas.csv`、`failure_manifest.json`、`bootstrap_manifest.json`。 | V1=36×A/B/C0（108 runs）；V2=36×C4（36 runs）；按 strata 做 paired bootstrap（建议 20,000 次，seed 固定）；同时输出 Wilson、McNemar、wins/ties/losses、绝对/相对 Δ。 | 只有 `eligible_strict` 的 C0–B 才可进入严格同服务效应；C4 单独表；报告 `n_eligible/36`、排除 gate、失败原因和 replay 路径。 | **F2 统计冻结**。若 V1 strict eligible 过低，主结论降为 gate 通过率/失败机制；禁用总体减排措辞，不用 C4 替代 C0。 |
| **D5 8/27** | **推荐资格工作台首屏**：从“八 Tab 看板”切成“1 工作台 + 3 证据抽屉 + 追问入口”。 | 主改 `app.py`；必要时新增 `src/gridrescue/facts.py`、`src/gridrescue/ui_state.py`；新增/扩展 `tests/test_app_mrv.py` 的 AT01–AT08。 | 默认只读 `artifacts/v08_official` 或已冻结 Wave10 batch；不在首屏运行 Pareto/pipeline。实现顶部证据条、结论带、三门卡、两候选条、FROZEN/LIVE 标签。 | 首屏 10 秒读到推荐、服务门、物理门、MRV 门、`kgCO2`、normal EENS Δ、run/hash、E 类标签；1366×768 不横向裁切。 | **F3 UI 语义冻结**。首屏或语义锁不稳时砍动画、额外 Tab、响应式扩展；保留静态主路径。 |
| **D6 8/28** | **三门证据抽屉与反例**：把服务、物理、MRV 证据直达字段；加入 NO_GFM/BLOCKED 反例。 | 修改 `app.py`、必要时 `src/gridrescue/islands.py`/`mrv.py` 导出字段；新增 `tests/test_app_gate_paths.py`；新增 `fixtures/tampered/` 与 `fixtures/no_gfm/`。 | 预设：主推荐、受控预算候选、NO_GFM 反例；当前小时改变时动作卡、拓扑、CareTask、Vmin/loading 同步。 | AT04/AT05/AT06/AT07：反例显示 BLOCKED/NO_GFM，无推荐 CTA；切回主推荐 PASS；服务抽屉显示 min kW、deadline、Vmin、失败码；MRV 抽屉显示 activity→factor→inventory→gate→seal。 | **F4 反例与证据冻结**。反例不稳定则放弃自由探索，只保留一个 deterministic fixture。 |
| **D7 8/29** | **MRV 篡改、复位与关键图**：让“证据门阻断错误结论”成为比赛记忆点。 | 修改 `src/gridrescue/mrv.py`（如需新增 risk 字段暂缓）；扩展 `tests/test_mrv.py`；新增 `scripts/build_figures.py`、`docs/figure_source_index.csv`、`artifacts/wave10/figures/`；更新 `app.py` tamper flow。 | V6 篡改矩阵：activity/factor/inventory/actions/manifest/delete/rechain 8–10 mutations；每次 FAIL→reset→PASS。重绘 F04–F07 和三门钥匙图，均写 source SHA/run ID。 | `verify_mrv_bundle` 正常 PASS；篡改 FAIL 且错误文件可定位；复位后官方 V08 SHA 不变；PNG/SVG/PDF、1920×1080/1366×768/黑白打印可读。 | **F5 证据与图源冻结**。停止图形重构；只修 blocker、来源和单位。 |
| **D8 8/30** | **数据真实感 P1（按资源）与可选 CVaR 探针**。 | 若天气线可落地：新增 `data/raw/weather/`、`data/processed/weather/`、`evidence/data_cards/`、`src/gridrescue/weather_replay.py`、`tests/test_weather_replay.py`；修改 `scenarios.py`、`experiments.py`、`mrv.py` 写入 weather/data card。若 P0 未全绿：不改生产代码，仅补 data card/假设登记。CVaR 才允许新增 `src/gridrescue/risk.py`、`tests/test_risk.py`。 | 先完成天气 QA、weather→hazard、资产属性/zone shock、修复时长分解；再做风险外层候选评估（alpha=0.80，0.90/0.95 敏感性）；失败场景不零填。 | 数据门：连续小时、时区、单位、缺失率、hash；单调性与 seed 重放。CVaR 门：tail_count、OOS catalog、mean/VaR/CVaR 算术、失败 gate；risk 未入 MRV 前不得展示为正式结论。 | **条件冻结**：P0 未全绿即切回 V08 合成压力集，放弃天气与 CVaR；不让新算法拖垮提交。 |
| **D9 8/31** | **答辩、视频、商业与政策证据包**：把可验证事实讲成 5 分钟故事。 | 更新 `docs/competition_narrative.md`、`docs/qa_defense.md`、`docs/policy_mapping.md`；新增 `docs/video_script_v10.md`、`docs/submission_checklist.md`、`artifacts/wave10/demo/`；若需要新增 `start_demo.ps1`、`recovery_demo.ps1`、`STOP.md`。 | 不运行长时 MC/Pareto；五分钟路径固定：三门→模型边界→暴雨 Pareto→36 场景配对/失败→MRV→落地边界；录制主路径、同构 Replay、静态证据三层。 | 3 分钟走查点击≤8；视频≤180 s（或比赛要求时 300 s）；每句台词有 evidence path；主张状态与 factsheet 一致；商业只说离线 PoV/园区单馈线入口。 | **F6 叙事冻结**。D9 后零新功能；只允许 blocker 修复、数字校对、重录与打包。 |
| **D10 9/1** | **干净环境回归、打包、冻结、提交**。 | 新增/更新 `scripts/release_audit.ps1`、`scripts/hash_manifest.py`、`release_manifest_wave10.json`、`artifacts/wave10/release/`；更新 `README.md` 运行命令和边界。 | 断网冷启动；`pytest -q`；AppTest；官方 V08 verify；Wave10 batch replay；tamper FAIL/PASS；ZIP 下载；三视口截图；检查路径/用户名/学校信息泄露。 | 全套 P0 gates 通过；关键 SHA 与 manifest 一致；核心演示不调用长时求解；下载包可独立解压并按 README 复核。 | **F7 最终冻结**。提交包只读；之后仅修阻断性错误并递增 patch 版本，不改数据、算法、claim 和图。 |

---

## 3. 实验执行顺序（不可倒置）

1. **V0 Golden/回归：** 官方 case33bw、现有 pytest、V08 MRV verify。任何基线失败，暂停所有新实验。
2. **Catalog smoke：** 先 3 灾种×1 强度×4 复本，验证 schema/hash/重放，再扩展完整 36。
3. **V1 Strict：** 36×A/B/C0；主安全终点为 `critical_eens_kwh`、Care pass，物理 guardrail 为 minV/max loading/source adjustment。
4. **V2 Controlled：** 36×C4；仅报告受控普通服务预算下的碳清单差异。
5. **V3 Pareto：** 仅 V1/V2 稳定后执行 Cε 7 点×36；保留失败点，不展示被失败筛掉的“漂亮前沿”。
6. **V4 消融：** carbon objective、time-varying carbon、Care hard contract、P/Q feedback；再考虑 DER、tie recovery、NO_GFM 反例。
7. **V5 OAT/稳健性：** PV、碳因子、修复时长、SOC、epsilon、因子范围；必须输出全范围与失败 gate。
8. **V6 MRV 篡改矩阵：** 独立于算法结果，验证 activity/factor/inventory/actions/manifest/delete/rechain 任何改动均可检测。
9. **O4 CVaR（条件）：** 仅当 1–8 的 P0 gate 全绿、至少两次完整演示通过、剩余净工时≥8 h 时进入；先外层评估，后考虑有限 CVXPY 扩展。

**明确禁止：** 把 MC30 smoke-test 的 4.83% 当总体效应；把未配对均值当 C0–B 因果比较；把失败场景填 0；把 E 类合成因子/天气称为现场测量；把 `SEALED` 说成第三方核证。

---

## 4. 文件级变更地图

### P0 必改

- **事实与材料：** `docs/competition_factsheet.yaml`、`docs/claim_dictionary.md`、`docs/evidence_index.csv`、`docs/scope_log.md`、`docs/video_script_v10.md`、`docs/submission_checklist.md`。
- **实验与统计：** `src/gridrescue/scenario_catalog.py`（或 `weather_catalog.py`）、`src/gridrescue/experiments.py`、`src/gridrescue/metrics.py`、`src/gridrescue/report.py`、`tests/test_weather_catalog.py`、`tests/test_validation_batch.py`、`tests/test_paired_stats.py`。
- **MRV 与门控：** `src/gridrescue/mrv.py`、`tests/test_mrv.py`、`fixtures/tampered/`、`artifacts/wave10/<batch_id>/`。
- **产品与演示：** `app.py`、`tests/test_app_mrv.py`、`tests/test_app_gate_paths.py`、`start_demo.ps1`、`recovery_demo.ps1`、`STOP.md`。
- **图与发布：** `scripts/build_figures.py`、`scripts/release_audit.ps1`、`scripts/hash_manifest.py`、`docs/figure_source_index.csv`、`release_manifest_wave10.json`。

### P1（P0 全绿后）

- `evidence/data_cards/*.yaml`、`data/raw/weather/**`、`data/processed/weather/**`。
- `src/gridrescue/weather_replay.py`、`tests/test_weather_replay.py`。
- `src/gridrescue/risk.py`、`tests/test_risk.py`、`tests/test_risk_mrv.py`、`src/gridrescue/risk_policy.py`。
- `src/gridrescue/attribution.py`、`tests/test_attribution.py`（仅有余力时）。

### 不进入本轮

`learning_policy.py`、GNN/RL 训练管线、完整 `two_stage.py` 随机规划、MISOCP/AC-OPF 联合重写、真实概率校准、SCADA/AMI 生产接入、实时控制执行器、区块链 MRV、复杂 3D/全息 UI。

---

## 5. Gate 与测试总表

| Gate | 判定内容 | 必须留存 |
|---|---|---|
| **G0 输入/谱系** | scenario/network/Care/factor/config/code/dependency hash 齐全且同一；数据等级、单位、时区、许可/假设完整 | manifest、data card、hash catalog、invalid 行 |
| **G1 服务合同** | 医院/关键/普通服务锚点及 CareTask min kW、deadline、连续时长、依赖满足 | care_task_evaluation、failure reason |
| **G2 拓扑/成岛** | 径向性、故障隔离、联络恢复、GFM/黑启动和 source-free island 判定 | topology state、island passport、NO_GFM BLOCKED |
| **G3 物理反馈** | P/Q 平衡、潮流收敛、Vmin、支路热限、DER P/Q/kVA/SOC；违规硬失败 | powerflow validation、constraint margins |
| **G4 MRV 证据** | activity→factor→inventory→claim gate→seal/verify 可重算；文件外键/语义 hash 正确 | verification.json、evidence index、tamper logs |
| **G5 比较资格** | strict/controlled 分轨、同场景 SHA、eligible 分母、paired delta/CI、失败 replay 齐全 | validation_summary、paired_deltas、bootstrap manifest |

**验收硬规则：**

- 一方失败时进入 reliability/ITT 分母；从对应 paired effect 排除并写明原因；不填 0。
- `same_service_pass=false` 时不出现“严格同服务减排/降碳”；只能显示受控服务预算下清单差异。
- 所有结论必须能从 `run_id → source CSV → figure → submission sentence` 反向定位。

---

## 6. 冻结点与变更控制

- **F0（D1）：** 事实、单位、claim、文件计数冻结；UI/PPT/视频只读 factsheet。
- **F1（D2）：** 36 catalog、seed、scenario JSON/SHA 冻结；不得临时重抽样。
- **F2（D4）：** 主实验结果、分母、失败表、CI、strict/controlled 口径冻结。
- **F3（D5）：** 首屏信息架构、默认主路径、FROZEN/LIVE 语义冻结。
- **F4（D6）：** 反例、证据抽屉、NO_GFM/BLOCKED 行为冻结。
- **F5（D7）：** MRV 篡改矩阵、七张正式图和图源索引冻结。
- **F6（D9）：** 视频、讲稿、申报书、商业/政策表述冻结。
- **F7（D10）：** 干净环境、下载包、manifest、SHA、回归结果冻结并只读。

**变更控制规则：**

1. 新功能必须 ≤4 h 可验收，且以“1 进 1 出”替换已有可选项；不得提高 Day 10 风险。
2. 任一任务超原估时 150%，立刻切最小验收版本。
3. 连续两天出现 P0 事实或回归问题，自动冻结全部可选项。
4. D9 之后零新功能；只修 blocker、重跑、重录、校对和打包。

---

## 7. 失败时的 fallback cuts（按顺序砍）

### 7.1 计算/算法失败

1. 先砍 Cε 7 点 Pareto 全扫描，保留 V08 已冻结 Pareto 点和 36 场景主比较。
2. 再砍 V4/V5 消融与 OAT，保留失败 manifest、G0–G5、paired CI。
3. CVaR、WDRO-lite、GHI/PV、动态热额定全部移入赛后论文路线；不得为增加“算法名词”牺牲 catalog/OOS/paired SHA。
4. 求解超时改为“启发式候选 + 潮流硬校验”，只报告可行解和运行时，不说全局最优。

### 7.2 外部数据/API 失败

1. 使用已下载、带时间戳、来源、SHA 的天气缓存；不在现场临时抓取。
2. 无天气原始文件时，保留 E 类合成压力集，补齐 data card、生成器版本、seed、假设登记和 synthetic/replay 分流。
3. 不把 Open-Meteo/ERA5 不可用包装成真实天气证据；文案降级为“可审计合成压力集”。

### 7.3 UI/浏览器失败

1. 主路径从 Live 切 Replay（同构 MP4/截图/只读 CSV/MRV ZIP）。
2. 再切 Static（PDF、factsheet、release manifest、verification JSON）。
3. 投影异常时不在台上排障超过 30 秒；使用备用设备和离线包。

### 7.4 统计资格不足

- strict `n_eligible` 太低：只报告可靠性、gate 通过率和失败机制，撤回总体效应。
- C4 有结果但 C0 无资格：只展示“受控服务预算下的清单差异”，不得替代严格同服务。
- bootstrap 不稳定：报告配对绝对差、wins/ties/losses、Wilson/McNemar 与失败分母，明确 CI 未形成。

### 7.5 工期不足（只够六项时）

优先完成：**事实源与 claim 锁、合成数据标签、36/至少 12 个 CRN catalog、G0–G5 失败保留、MRV 篡改/复位、主工作台首屏。** 其余天气真实化、CVaR、动画、复杂商业化全部后置。

---

## 8. 竞赛可用主张与禁用主张

### 可用

- “GridRescue 是基于官方 `case33bw` 与 E 类合成工程输入的预案级方法原型。”
- “候选只有同时通过服务合同、P/Q 物理反馈和 MRV 证据三门，才进入推荐比较。”
- “在冻结的 3×3×4 合成压力集上，我们报告严格服务与受控服务两条分轨的配对差、失败分母和置信区间。”
- “MRV `SEALED/Verification=PASS` 表示文件完整性与内部方程复算，不等同于现场测量或第三方核证。”
- “首个落地入口是园区/单馈线/医院/数据中心的离线 PoV、演练与复盘，不是自动控制。”
- 若 O4 完成：“这是冻结合成压力集上的 CareTask-CVaR 尾部风险比较；不外推现实灾害概率。”

### 禁用

- “实时全城最优低碳恢复”“自动控制已接入现场馈线”。
- “MC30 4.83% 证明总体降碳”或任何非配对均值的总体效应。
- “严格同服务减排”——除非 C0–B 全部 service/physical/MRV gate 通过且 `same_service_pass=true`。
- “新能源弃电已计入主碳清单”；弃电只能作机会损失单列。
- “SEALED 等于第三方核证/现场实测”。
- 将标准算例、E 类因子、合成天气、医院任务模板说成真实资产、临床标准或地方灾害概率。

---

## 9. 最终提交 checklist（D10 必须逐项打勾）

### 证据与代码

- [ ] `release_manifest_v08.json` 原样保留，V08 SHA 与 Wave10 目录分离。
- [ ] `release_manifest_wave10.json` 含代码、依赖、数据、catalog、图、视频、docs 的 SHA-256。
- [ ] `python -m pytest -q` 通过；报告准确写明 passed 数和运行时。
- [ ] 36 JSON、catalog CSV、seed、scenario/network/Care/factor/config/code/dependency hash 齐全。
- [ ] A/B/C0/C4 输入同场景 SHA；strict/controlled 两张结果表；`n_eligible/36`、失败原因和 replay 路径齐全。
- [ ] `verify_mrv_bundle` 三 bundle PASS；tamper/delete/rechain fixture 均 FAIL；reset 后官方包 SHA 不变。
- [ ] 失败场景不填 0；ITT/reliability 分母、Wilson、paired delta/CI、wins/ties/losses 均可追溯。

### 产品与演示

- [ ] Streamlit 首屏 10 秒读到推荐、三门、kgCO2、normal EENS Δ、数据等级、run/hash。
- [ ] 首屏无长时 Pareto/pipeline；默认读取冻结工件；FROZEN/LIVE 标签清楚。
- [ ] 主推荐、受控预算候选、NO_GFM/BLOCKED 反例可一键切换；反例无推荐 CTA。
- [ ] 服务/物理/MRV 三抽屉分别能追到 CareTask、Vmin/loading、activity→factor→inventory→gate→seal。
- [ ] 30 秒 Gate 可跳过/重播；reduced-motion 可用；三分钟路径 ≤8 次点击。
- [ ] F04–F07 与钥匙图含 source SHA、run ID、冻结日、数据等级、单位；1920×1080、1366×768、黑白打印可读。
- [ ] 离线 Live、Replay、Static 三层路径各自演练；`start_demo.ps1`/`recovery_demo.ps1` 可冷启动。

### 申报、答辩与合规

- [ ] 申报书、PPT、视频、README、UI 数字全部来自 factsheet；46/17/kgCO2/2026-08-22 无矛盾。
- [ ] 五分钟答辩明确区分 case33bw、E 类合成输入、冻结压力集、现场落地边界。
- [ ] MC30 4.83% 仅标 smoke-test；36 场景未完成前不报总体稳健性。
- [ ] 产业证据包只写离线 PoV、数据模板、12 周校准路径和审计友好 MRV，不写已商业化收入或现场 ROI。
- [ ] 政策/标准只作映射与设计依据，不宣称认证、合规通过或法定核证。
- [ ] 去除用户名、学校、绝对路径、临时文件名、未授权 API key；README 可在干净环境复核。
- [ ] 生成 `docs/submission_checklist.md` 与 `docs/qa_defense.md`，现场按 checklist 逐项签字。

---

## 10. 最终判定

**夺冠版本 = V08 可信基线 + 36 CRN 配对证据 + 推荐资格工作台 + MRV 反错演示 + 可恢复的离线交付。**  
CVaR、天气 replay、消融和专利/产业材料是加分项，绝不能反过来挤占事实源、分母、失败保留、三门 gate、图源索引和现场恢复路径。十日后的论文主线可沿 CG-CVaR、联合压力 catalog、风险 MRV 和真实数据校准展开；本次比赛只提交已经通过对应 gate、可以被复算、能够被诚实描述的结果。

