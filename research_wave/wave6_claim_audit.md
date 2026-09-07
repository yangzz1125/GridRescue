# GridRescue 竞赛主张—证据审计（Wave 6）

**审计目的：** 将答辩、申报书、视频和 UI 的每一条高价值主张绑定到可检查的当前证据。这里的“当前”只指本仓库已存在的代码、测试和导出物；研究设计、计划和路线图不计作已验证成果。

**结论总览：** 当前可稳妥定位为：**基于公开 IEEE/MATPOWER 33 节点算例、合成灾害与工程参数的预案级恢复推演原型**。它已有同服务 Pareto、任务级服务后验检查、P/Q 潮流筛查、失败留痕和部分可复现导出；它尚无真实馈线/医院/天气输入、排放因子注册表、部署验证、扩展网络实测基准或统一 run seal。因此，所有对外主张必须带上“固定输入/模型范围/原型”边界。

## 1. 证据等级与使用规则

| 状态 | 含义 | 对外使用 |
|---|---|---|
| **绿（已支持）** | 当前仓库中有可追溯产物，且该产物直接覆盖主张。 | 可陈述事实，并标出场景/策略/时间窗。 |
| **黄（部分支持）** | 有单场景、合成输入、后验验证或设计材料，但缺外部校准、统计或关键链路。 | 仅作“模型内/合成场景下/原型已演示”表述。 |
| **红（尚无证据）** | 只有目标、设计或验收门槛，或没有可复查导出。 | 从主叙事删除；只放“下一阶段验证”。 |

**通用禁止词：** “真实/已部署/已落地/实时/权威核证/临床标准/安全运行/全局最优/行业领先/首次/唯一/大规模可扩展/显著减排”。除非相应升级证据已生成并可在提交包中打开。

## 2. 主张—证据矩阵

| 主张域 | 当前证据状态 | 允许的对外表述 | 必需证据工件（正式发布门） | 当前已见证据 | 不允许的表述 | 一个可升级的测试或展品 |
|---|---|---|---|---|---|---|
| **创新性** | **黄** | “GridRescue 将同服务 ε-constraint、合成生命线任务、成岛资格提示与运行排放比较接入同一恢复推演链；创新点是**组合式决策与证据门控**，而非宣称单一算法首创。” | ① 竞争/文献对比表（相同评价维度、来源、检索日期）；② 一张“输入→服务门→物理门→碳比较→证据导出”架构图；③ 至少一个反例，证明服务或物理门会阻止貌似低碳的候选。 | `pareto_flood_v06` 有四个同服务候选；`care_task_*` 有任务后验；`island_passport_*` 和 `wave6_judge_story.md` 定义了失败显示。`wave1_innovation.md` 是设计与定位材料，不可单独当成果证明。 | “全球首创/国内首个”“AI 数字孪生已经自主预测故障”“动作级 MRV、Carbon-SOC 已实现”。目前 AI、动作级账本、Carbon-SOC 多为设计文档。 | **反例展品：** 演示一个普通负荷放松或任务失败的候选被 `frontier_eligible=false`/失败表剔除；配一页同行功能矩阵，逐格附来源。 |
| **低碳收益** | **黄，且对跨策略优越结论为红** | “在固定的`暴雨内涝`合成场景、相同网络/资源输入下，Pareto 的 6% 普通服务让步点相对 0% 服务锚点，模型内恢复阶段**运行排放估算**由 44,908.92 kg 降至 41,783.03 kg（约 6.96%）；医院与其他 essential EENS cap、CareTask、P/Q 后验均通过。该差异以更多普通负荷 EENS 为代价，故是显式权衡，不是无条件减排。” | ① `factor_registry` 与每次运行的 immutable factor snapshot（来源、地域、年份、单位、气体口径、hash）；② 同一服务合同或预注册 allowance；③ 对共同场景的 paired CI；④ 输入、因子、输出和门状态绑定的 run manifest。 | `pareto_flood_v06/pareto_frontier.csv`：0% 与 6% 点均为 contract/physical/care pass，24/24 可行；总碳分别 44,908.92/41,783.03 kg。`report_carbon_resilient.md` 明确边界是网电、柴油、车辆，弃绿只作机会损失。 | “项目已实现 X% 减排”“碳韧协同比最小失供更低碳且同等服务”（`flood_v05` 中两者总 EENS 4,787.67 vs 2,223.11 kWh，不是同服务）；“CO2e/实时区域边际排放/核证减排”；“恢复供电量等于减排”。现有因子仍是工程/合成输入。 | **配对碳—服务图：** 60 个冻结共同合成场景，报告 paired mean Δcarbon 与 95% CI，并设置 `NC2_SERVICE_RELAXED` 负对照，确保服务放松的低碳点永远不能标为“优越”。 |
| **韧性** | **黄** | “在固定 seed 的 30 组可复现合成压力测试中，每个策略 30 次尝试、29 次完成物理管线；已完成样本均记录为 24 个物理可行小时，失败场景另存为 replay manifest。” | ① 冻结、分层的共同情景目录（灾种×严重度×seed）；② 所有策略复用同一情景；③ 成功率/物理门/关键服务门、Wilson CI、paired CI、失败清单和成功/失败回放；④ 负对照。 | `mc30_v04/monte_carlo_summary.csv`：各策略 30 attempts、29 solved、1 failed，成功率 0.96667（Wilson 95% CI 0.8333–0.99409），成功行 `physical_feasible_hours_mean=24`。`monte_carlo_failures.json` 保存可重放失败输入。 | “30 组证明系统稳健可靠”“对暴雨/台风/高温均稳定”“真实灾害下保持韧性”“可靠性指标已校准”。当前随机样本是合成均匀抽样，非历史故障统计模型；环境温度也尚未进入核心物理计算。 | **Robustness Evidence Pack：** 按 `wave6_uncertainty.md` 建立 3 灾种×2 严重度×10 seed 的共同目录，输出 attempt/solve/physical/critical-pass 矩阵及一个成功、一个失败的现场回放。 |
| **医院生命线服务** | **黄** | “本原型把医院服务表示为 4 个**E 类合成 CareTask**；在指定 `暴雨内涝` run 中，ICU/急诊、应急手术、冷链、通信任务均通过后验功率、deadline、持续时长、依赖和电压检查，其中 Tier-1 为 2/2。” | ① 脱敏医院负荷/设备/UPS/发电机输入，或经领域专家签审的合成任务卡；② 任务与节点映射的版本化依据；③ 任务级 failure/restart/并发负荷测试；④ 任务作为 Pareto 服务合同或明确说明仅后验。 | `pareto_flood_v06/pareto_manifest.json` 定义 4 项任务且 `data_class=E_synthetic_task_template`；四个前沿点均 `care_completed_count=4`、`care_tier1_completed=2`、`care_contract_pass=True`。`tests/test_care.py` 覆盖并发需求、低电压和依赖失败。 | “保障真实医院”“符合临床标准”“ICU 已安全运行”“医院连续供电得到临床认证”。CareTask 的当前任务参数明确不代表医院实测或临床标准；在 Pareto 中任务已评估，但其服务门与类别级硬锁的关系要逐版本核实。 | **任务级验证展品：** 一个脱敏医院/园区配电负荷切片，展示任务字典的签审来源；故意将 ICU 某小时电压降至 0.96 pu，UI/报告必须显示 `VOLTAGE` failure 并剔除推荐。 |
| **物理可行性** | **黄** | “候选恢复方案经过项目内径向拓扑、分岛供需平衡和 24 小时 P/Q 前推回代潮流**后验筛查**；例如 `pareto_flood_v06` 四个前沿点均为 24/24 physical pass，最低电压约 0.9703–0.9799 pu，最大支路负载约 99.77–99.99%。” | ① 标准算例的输入 hash 与 golden power-flow；② 每个候选的节点/支路/分岛时序结果、阈值与失败原因；③ 热限、DER P/Q/S、GFM/黑启动、保护/同期的来源或适用边界；④ 外部潮流工具交叉核验或至少独立实现对照。 | `network_manifest.json`、`tests/test_core.py` 固化 `case33bw` 基准值（网损约 202.677 kW、Vmin 0.91309 pu）；`pareto_frontier.csv` 有 physical pass、Vmin、loading、source adjustment；`tests/test_islands.py` 证明 `NO_GFM` 可被 BLOCKED。 | “已完成 AC-OPF/MISOCP 联合物理优化”“工程可直接执行/现场安全运行”“热稳定、保护配合、同期、暂态频率均已验证”“DER 无功能力已完整约束”。当前 P/Q 是后验闭环；热限是项目工程假设，DER P/Q/S 与成网/黑启动许多能力仍为模型推断。 | **双重潮流核验：** 将同一冻结状态导入 pandapower/OpenDSS/MATPOWER 之一，报告节点电压、支路负荷与损耗误差；另做一份 GFM/PQ/S 限制失败夹具，必须产生不可行/阻断。 |
| **可复现性 / 可审计性** | **黄偏绿（算例级）** | “仓库提供固定网络源 SHA、固定场景定义、策略动作、逐时 dispatch、潮流 CSV、Pareto manifest、任务定义 hash，以及 Monte Carlo failure replay。相同版本与输入可重放当前算例级结果。” | ① 每个正式图表绑定 `run_id`；② `run_manifest`（代码 bundle hash、Python/solver/依赖锁、scenario/network/factor hashes、seed、命令）；③ factor snapshot、输出 hash index、独立 verify；④ 干净目录复跑记录。 | `network_manifest.json` 含 case33 SHA；`pareto_manifest.json` 含 network/care hash 与完整场景；`experiments.py` 保存 scenario SHA、seed、失败 manifest/replay；`pytest_review_latest.log` 记录一次 9 passed。 | “完全可审计/第三方可验证/符合 MRV 核证”“一键在任意环境复现”“每个碳数字已封签”。目前缺统一 run manifest、代码/依赖锁 hash、因子 snapshot、action ledger 与 verify-run；`pyproject.toml` 仅为版本下限，非锁文件。 | **Clean-room exhibit：** 在新目录/新虚拟环境执行冻结命令，生成核心 CSV；展示输入与输出 SHA 比对。篡改任一受管 CSV 后 `verify-run` 必失败。 |
| **可扩展性 / 工程化** | **红** | “当前架构以节点表、支路表、场景和导出表组织；它可作为向更大标准网络扩展的代码基础，但尚未给出规模性能实测。” | ① 33/69/123 节点的真实输入与 provenance；② 固定硬件/线程/solver 版本、计时边界、P50/P95、内存、可行率、gap、timeout/fallback；③ 相同物理/服务门；④ 原始 `benchmark_runs.csv`。 | 仅有 `research_wave/scalability_benchmark.md` 的**协议与验收阈值**；该文明确表中秒数为“验收门槛，非实测值”。当前已见模型是 case33，Pareto 单点 solve seconds 约 7–9 秒仅能说明该单场景规模。 | “已支持 69/123 节点”“可实时调度”“可大规模推广”“性能达到 P95 X 秒”。没有对应实测输出或多网络导入工件。 | **规模基准展品：** 实跑 33/69/123 × 30/100 场景，保存原始 `benchmark_runs.csv` 与求解日志；答辩仅引用 P50/P95、feasible rate 和 fallback rate 的实测数。 |
| **MRV / 数字孪生（附加高风险主张）** | **黄（方案级导出）** | “系统可导出方案级的动作序列、逐时能流、潮流结果和运行排放估算；用于预案比较与复算。” | ① 因子 registry/snapshot；② action ledger（结构化 action ID、前后拓扑、evidence refs）；③ run seal；④ 关键动作的反事实重放；⑤ 数据质量状态。 | `report_carbon_resilient.md`、`actions_*.csv`、`dispatch_*.csv`、`powerflow_*.csv` 已形成导出链。`wave6_mrv_evidence.md` 明确 action ledger、factor registry、manifest/seal 仍是目标架构。 | “现场 MRV”“单个开关减少 X kg”“碳核证”“真实数字孪生/实时闭环控制”“区块链可信”。当前动作是仿真计划，因子与归因证据未闭环。 | **单动作反事实展品：** 对 `close_tie` 或 `repair_branch` 做相同服务门下的 leave-one-out 重放，显示未通过服务等价时只展示 inventory、禁止显示“减排”。 |

## 3. 当前可直接放进材料的事实句

以下句子都应随图表附上 run/文件名、场景和时间窗。

1. **系统定位**：
   > GridRescue 是一个基于公开 `MATPOWER case33bw`、合成灾害和工程参数的预案级配电网恢复推演原型。

2. **同服务权衡**：
   > 在固定的合成暴雨场景中，系统先锁定医院与其他 essential 服务，再在公开的普通负荷 EENS allowance 内扫描运行排放权衡；前沿候选均留有潮流和任务级检查结果。

3. **物理筛查**：
   > 对展示候选，系统输出 24 小时 P/Q 潮流、节点电压、支路负载与分岛供需平衡；无源孤岛会被标记为不可服务，而不是由虚拟平衡量掩盖。

4. **任务级保供**：
   > 当前用四项 E 类合成 CareTask 将医院/通信等关键服务拆为最小功率、时窗、持续时长、deadline 和电压门，结果不等同于真实医院或临床标准。

5. **可回放试验**：
   > 30 组固定 seed 的合成压力测试保留了成功、失败和失败重放输入；其作用是检验原型失败隔离与复算链路，不是估计真实灾害发生概率。

## 4. 统一脚注模板

所有关键图、表、视频截图和 KPI 卡片使用：

```text
数据：MATPOWER case33bw + 项目工程参数 + 合成灾害场景。
范围：24 h 预案推演；结果为模型派生，不代表真实馈线/现场遥控记录。
服务门：<hospital/essential/CareTask/normal allowance>；物理门：<P/Q/V/loading/island>。
run / artifact：<RUN_ID 或文件名>；network SHA：<SHA>；seed：<SEED>；因子状态：<synthetic / conditional / approved>。
```

## 5. 发布门禁（按优先级）

### P0 — 当前材料必须执行

- [ ] 删除“真实医院、真实馈线、实时、已部署、核证、显著减排、规模化”类超出证据的表述。
- [ ] 把所有碳比较都改为“运行排放估算”，并同时显示服务合同和输入因子状态。
- [ ] 任何非同服务的策略比较只叫“策略差异”，不叫“减排优越”。
- [ ] 对每张主图写清数据等级：公开标准算例 / 工程假设 / 合成场景 / 派生仿真。
- [ ] 视频使用 `wave6_judge_story.md` 的版本 B 叙事，除非天气、Carbon-SOC、MRV 封签已真正交付。

### P1 — 最小可信度升级

- [ ] 生成冻结情景目录、paired CI、负对照和失败回放，才能升级“低碳与韧性”主张。
- [ ] 生成 factor registry/snapshot 与 run manifest/seal，才能升级“MRV/可审计”主张。
- [ ] 以外部潮流工具复核一个冻结场景，才能升级“物理可行”表述。
- [ ] 生成一份脱敏服务输入或专家签审的任务模板，才能提升“医院服务”可信度。
- [ ] 导出真实 benchmark 数据，才能开始说“可扩展”。

## 6. 评委追问的短答规则

| 追问 | 推荐回答 |
|---|---|
| “你们是不是用少供电换了低碳？” | “我们把医院和其他 essential 服务先锁住，普通服务让步公开写在 allowance 中；不满足合同或物理门的候选不会进入推荐。” |
| “这是真实医院吗？” | “当前是 E 类合成任务模板，用于把保供从百分比拆到功率、时窗和电压；真实医院数据和临床签审是下一阶段验证。” |
| “这是真实配电网吗？” | “网络电气参数来自公开 case33bw，DER、热限和灾害是工程假设；当前目标是验证预案推演闭环，不是复盘某条真实馈线。” |
| “碳因子可信吗？” | “当前为版本化目标尚未完成的原型输入，因此我们只展示运行排放估算与敏感性；因子 registry 和来源快照是上线门。” |
| “能推广到更大规模吗？” | “当前没有规模实测，因此不报性能承诺；下一步会用 69/123 节点和原始 benchmark 表验证。” |

---

## 审计判定

**可以主打：** 同服务恢复权衡、任务级服务表达、失败透明、标准算例上的 P/Q 后验筛查、方案级可导出结果。  
**必须降级：** 低碳“收益”、医院“保供”、韧性“可靠”、数字孪生/MRV“可审计”。  
**必须暂缓：** 真实部署、AI 故障预测、碳核证、Carbon-SOC/action-level attribution 已实现、规模化/实时性能。
