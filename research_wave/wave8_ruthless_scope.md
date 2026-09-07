# GridRescue Wave 8：10 天冲刺残酷取舍审查（2026-08-22）

> 任务：基于当前代码、28 个已收集测试、现有 artifacts 与全部 Wave 8 报告，决定 10 天版本哪些必须做、应该做、立即砍掉。  
> 原则：一等奖增益优先于功能数量；现成证据优先于新模型；能够在答辩现场被看懂、复算、质疑和回放，优先于论文式扩张。  
> 本报告只做范围审查，不修改生产代码。

## 1. 一句话裁决

GridRescue 的 10 天版本只保留一个主命题：

**系统先用 CareTask 锁定生命线服务，再用 P/Q 潮流和成岛资格淘汰假可行方案，最后用 Pareto 合同与 MRV 证据决定一个碳结论是否有资格展示。**

所有功能都必须服务这句话。不能增强这条证据链、不能在 3 分钟内被理解、或需要新数据/新模型才能站住的内容，退出当前版本。

当前最危险的问题不是缺功能，而是：
1. app.py 仍将 Pareto 碳排写成 kgCO2，而 MRV factor snapshot 和 inventory 是 kgCO2；
2. flood_v08 的 C/B 是 8% 普通服务预算下的清单差，不是同服务减排；
3. UI 有 8 个 tab，主结论分散；
4. 28 个测试覆盖物理、Care、Pareto、随机失败和成岛，但没有独立 MRV 篡改测试、UI 口径测试、三天气 Pareto 发布测试和干净环境安装测试；
5. 单 flood Pareto 和单 seed MC 只能支撑原型案例，不能支撑普适性主张。

## 2. 评分方法

每项按四维评分：

- 一等奖增益 G：1–10，是否直接提升创新、可信度、答辩可读性。
- 工时 H：完成开发、测试、产物和演示的预计工程小时。
- 失败风险 R：1–10，越高越可能破坏现有数值、拖期或产生新质疑。
- 证据就绪 E：1–10，现有代码/artifact 可复用程度。

决策指数：

Score = G × E ÷ [H × (1 + R/5)]

指数只用于强制排序，最终分类还要考虑依赖关系：
- MUST：没有它会直接损害可信度或提交稳定性；
- SHOULD：P0 全绿后才做，必须有明确停止条件；
- CUT：本赛季不进入代码、主 UI、主答辩或性能承诺。

## 3. 总评分与范围裁决

### 3.1 MUST：必须完成

| ID | 功能/工作包 | G | H | R | E | Score | 裁决理由 |
|---|---|---:|---:|---:|---:|---:|---|
| M1 | 冻结唯一主证据包 GR-COMP-01 与 canonical factsheet | 10 | 5 | 2 | 10 | 14.29 | 解决 6%/8%、42.9t/41.2t/41.18t 混用，是所有 PPT/UI/口播的单一数字源 |
| M2 | 全产品统一 kgCO2、数据等级 E、允许/禁止主张 | 10 | 4 | 1 | 10 | 20.83 | app.py 当前 kgCO2 与 MRV kgCO2 冲突，属于评委一眼可抓的硬伤 |
| M3 | 主屏显示服务门、物理门、证据门和 claim status | 10 | 8 | 3 | 8 | 6.25 | 直接呈现项目核心创新，避免评委在 8 个 tab 中找结论 |
| M4 | 固定两点 Pareto 决策条：服务锚点与一个受控 epsilon 点 | 10 | 7 | 3 | 9 | 8.04 | 同屏展示 CO2 差与普通 EENS 代价，封住“少供电换低碳”质疑 |
| M5 | UI 显示 MRV run_id、verified、11 文件、下载入口 | 9 | 6 | 2 | 9 | 9.64 | 现有 mrv.py 已实现，低风险把可信度变成可见产品能力 |
| M6 | 展示一个失败反例：NO_GFM 或 Pareto failure | 9 | 4 | 1 | 10 | 18.75 | 证明系统会拒绝方案，不是只展示成功动画 |
| M7 | 三天气 A/B/C 冻结运行与物理/Care/MRV 验证 | 9 | 8 | 3 | 9 | 7.23 | 现有 CLI 可直接执行，避免只靠单一暴雨场景 |
| M8 | 30 场景共同随机批、失败 replay、配对摘要 | 9 | 8 | 3 | 8 | 6.43 | 现有 experiments.py 可复用；必须诚实保留 29/30 成功事实 |
| M9 | MRV 最小篡改测试：activity、factor、manifest、action chain | 9 | 7 | 3 | 8 | 6.43 | 当前缺测试；完整性主张没有负向验证会显得自证 |
| M10 | 干净环境安装、pytest、三场景 CLI、MRV verify、匿名检查 | 10 | 8 | 2 | 9 | 8.04 | 提交可运行性与匿名性是淘汰级门槛 |
| M11 | 3 分钟主路径、冻结截图/录屏、备用 PDF | 10 | 8 | 2 | 9 | 8.04 | 避免现场计算 Pareto 或网络图加载失败 |
| M12 | 一张 claims dictionary：每个数字绑定场景、服务条件、单位、数据级别和证据路径 | 10 | 5 | 1 | 10 | 16.67 | 统一申报书、PPT、UI、答辩、FAQ |

### 3.2 SHOULD：P0 全绿后再做

| ID | 功能/工作包 | G | H | R | E | Score | 启动条件 |
|---|---|---:|---:|---:|---:|---:|---|
| S1 | 单决策工作台完整收敛：1 主屏+3 证据抽屉 | 9 | 14 | 4 | 7 | 2.50 | H24 前 M1/M2/M7/M10 全绿，且不改求解数值 |
| S2 | 36 个冻结分层合成场景 catalog + paired bootstrap | 9 | 14 | 4 | 7 | 2.50 | 现有 30 场景结果稳定，新增 catalog 不需改优化器 |
| S3 | 三天气各 7 点 Pareto，输出 21 点失败/前沿表 | 8 | 9 | 3 | 8 | 4.44 | 三个 4 点烟测均正常、总运行可在 3 小时内完成 |
| S4 | 工程热限假设卡 + ±10% 简单敏感性 | 8 | 8 | 3 | 7 | 4.38 | 不引入新的温度物理模型，只对现有 capacity 做离线敏感性 |
| S5 | 报告型 Resilience Equity Passport + 1 个反例 | 7 | 12 | 4 | 6 | 1.94 | P0 证据完成后剩余至少 1.5 工程日；只后验报告，不改优化器 |
| S6 | 单暴雨场景 6-action LODO 边际价值归因 | 7 | 14 | 5 | 5 | 1.25 | P0 完成且 full-plan 可在 1e-3 内复现；只做一个冻结场景 |
| S7 | 一页政策/标准映射与边界 | 6 | 4 | 1 | 9 | 11.25 | 不占开发时间；不写认证、合规、核证或真实落地结论 |
| S8 | 30 秒 gate 拦截动画 | 8 | 8 | 4 | 7 | 3.89 | 冻结 UI 和数据后制作，不允许反向驱动模型改数 |
| S9 | 60 场景/多 seed 稳健性扩展 | 7 | 12 | 3 | 7 | 2.55 | 30/36 场景全部可 replay，运行时间不影响发布冻结 |

SHOULD 的硬规则：最多选择 3 项。推荐顺序 S3 → S1 → S2。S7 可作为不占代码风险的文档附录并行完成。S5/S6/S8/S9 只能在所有 MUST 完成后抢救。

### 3.3 CUT：当前版本立即砍掉

| ID | 功能 | G | H | R | E | 裁决 |
|---|---|---:|---:|---:|---:|---|
| C1 | 完整 Carbon-SOC 来源桶账本、终端 SOC 对齐、组件级储能 provenance | 7 | 45–70 | 9 | 2 | 研究价值高，但会重写碳主张和调度约束；10 天内极易形成新漏洞。只保留 operational inventory |
| C2 | Carbon-SOC A/B/C 性能优越性结论 | 5 | 30+ | 10 | 1 | flat-factor、terminal flush、初始碳强度任一失败就必须 NO-GO，不进入当前赛季 |
| C3 | 真实天气 API、ERA5/Open-Meteo 在线接入 | 5 | 24–40 | 7 | 2 | 网络、时间、许可、缓存、版本漂移风险高；比赛使用冻结合成场景 |
| C4 | 真实 OMS/DMS/SCADA 写回、云部署、多用户审批 | 6 | 80+ | 10 | 1 | Wave 8 部署报告明确为 P2；当前只做离线预案级原型 |
| C5 | 真实园区/医院/配网试点 | 7 | 6 周+ | 10 | 1 | 不满足 10 天；作为路线图，不作为已完成落地 |
| C6 | 人口属性、地理弱势群体权重和公平约束入优化器 | 5 | 40+ | 9 | 1 | 缺治理数据、隐私审查和利益相关方授权；仅允许合成后验 passport |
| C7 | AI/ML 故障概率预测、可靠性图、真实概率校准 | 5 | 40+ | 9 | 1 | 当前 sampling 是合成压力，不是历史拟合；强做会制造伪校准 |
| C8 | 80 LHS 全局敏感性、Sobol、完整 PRCC | 5 | 24–40 | 6 | 3 | 图多但不直接改善主证据；OAT 或 36 场景足够 |
| C9 | 全灾种×全策略×30 MC×全动作 LODO/Shapley | 5 | 50+ | 8 | 2 | 运行量与解释复杂度失控；最多单场景 6-action LODO |
| C10 | 统一 MISOCP、整数开关联合优化、AC-OPF 重构 | 7 | 100+ | 10 | 1 | 超出 10 天且会破坏稳定结果；作为论文后续 |
| C11 | 将 kgCO2 升级为完整 kgCO2/GHG Protocol 核证体系 | 5 | 30+ | 8 | 2 | 当前最快正确动作是全产品改为 kgCO2；不临时扩因子边界 |
| C12 | 现场实时 Pareto 求解和远程依赖 | 4 | 12 | 7 | 4 | 演示读取冻结 artifact；现场点击计算属于无收益风险 |
| C13 | 八个 tab 全部继续扩展 | 2 | 20+ | 6 | 7 | 功能分散主命题；只保留工作台与证据抽屉 |
| C14 | 为政策/标准制作“符合/认证”badge | 1 | 6 | 10 | 3 | 直接产生合规误导；政策只作背景对齐 |
| C15 | 6 周教学试点作为本次完成项 | 4 | 6 周+ | 8 | 2 | 保留一页试点计划，不占本次开发与验收 |

## 4. 72 小时 P0 强制顺序

目标：72 小时后拥有一个可提交、可演示、可回放的候选版本。后续 7 天只允许增强，不允许重建核心。

### H0–H4：证据与口径冻结
1. 选择唯一主 run，命名 GR-COMP-01。
2. 生成 canonical_factsheet：run_id、scenario、network/care/factor/code hash、A/B/C 数值、Pareto 选点、claim status、数据等级。
3. 冻结允许表述和禁止表述。
4. 确认所有日期字段使用 2026-08-22。

验收：
- 所有主数字只有一个来源；
- C/B 明确是 controlled epsilon trade-off 或 strict same-service；
- kgCO2 口径统一。

### H4–H10：修复淘汰级口径问题
1. UI/PPT/图轴/报告统一 kgCO2。
2. 所有主屏显示 E 类合成数据。
3. 删除“显著减排、同服务优势、真实医院、实时调度、合规认证”等无证据文本。
4. 建 claims dictionary。

验收：
- 全仓与提交材料检索不到错误 kgCO2；
- 每个性能结论都包含服务条件；
- 每个 CareTask 表述都包含合成模板边界。

### H10–H18：回归与可复现基线
1. 跑 28 个现有测试并保存日志。
2. 跑暴雨、台风、高温三场景 CLI。
3. 核验三个 MRV bundle verified=true、carbon reconciliation 为零差。
4. clean directory 重装与命令复现。
5. 检查绝对路径、用户名、临时缓存和敏感信息。

验收：
- 28/28 测试通过；
- 三场景均有完整输出；
- clean run 不依赖网络和本机绝对路径。

### H18–H30：单一决策视图
1. 首屏只保留推荐状态、服务门、物理门、证据门。
2. 同屏展示 CO2 差、普通 EENS 差、关键/Care 状态。
3. Pareto 只展示冻结锚点和一个候选；全前沿进入证据抽屉。
4. MRV 抽屉展示 run_id、verified、文件数和下载。
5. 其余 8 tab 内容降级为证据区，不继续扩功能。

验收：
- 30 秒内可回答：推荐什么、牺牲什么、为何物理可行、证据在哪；
- 不需要现场运行 Pareto。

### H30–H40：负向证据
1. 固定一个 NO_GFM/BLOCKED 成岛反例。
2. 固定一个 Pareto failure 或 impossible CareTask 反例。
3. 执行 4 个 MRV 篡改烟测：activity、factor、manifest、action。
4. 输出 tamper matrix 和 failure reason。

验收：
- 至少一个候选明确被 gate 拒绝；
- 四类篡改均 verified=false；
- 失败 artifact 可下载或展示。

### H40–H52：公平比较与随机证据
1. 冻结 30 场景 common-random-number catalog。
2. 核对 A/B/C scenario SHA 一致。
3. 输出 attempts、solved、failed、Wilson CI、失败 replay。
4. 有余力则补 36 个分层场景 catalog；无余力维持 30 场景并准确写成 deterministic synthetic stress set。

验收：
- 不把失败填零；
- paired comparison 只使用同 scenario SHA；
- 29/30 的失败原因可回放。

### H52–H62：答辩图与文本
只做 4 张主图：
1. 服务锚点—epsilon 候选 Pareto；
2. 24h CareTask/关键服务恢复；
3. 物理门：Vmin 与 max loading；
4. MRV 证据链与 tamper result。

只做 2 张表：
1. A/B/C 主结果和 claim class；
2. 失败/反例/replay。

验收：
- 图源 CSV 与图一起归档；
- 图中标 n、失败数、epsilon、单位、数据等级。

### H62–H68：演示与材料绑定
1. 录制 3 分钟无剪辑主路径和 30 秒备用片段。
2. PPT、视频、UI、申报书、FAQ 全部引用 canonical factsheet。
3. 预热/读取冻结 artifact，禁止现场长求解。
4. 准备失败时的静态截图/PDF 路径。

验收：
- 三次连续彩排均在 3 分钟内；
- 断网情况下可完整演示；
- 任一主数字能在 15 秒内指出证据文件。

### H68–H72：版本冻结
1. 停止功能开发。
2. 重跑 tests、三场景 smoke、MRV verify。
3. 生成 SHA256SUMS、VERSION、environment、known limitations。
4. 只读复制 final_submission。
5. 从 final_submission 本身执行一次完整演示。

验收：
- release gate 全绿；
- 归档包可解压、运行、验证；
- 提交目录没有未引用草稿和冲突数字。

## 5. 停止条件

满足任一条件，立即停止对应功能并回到最后一个绿色版本。

### 全局停止条件
- H12 时现有 28 个测试仍未全绿：停止所有 UI 重构和新功能，只修回归。
- H24 时三场景 CLI 或 MRV verify 有任一不稳定：停止 SHOULD，冻结单主场景证据并修可复现性。
- H36 起禁止修改求解器、调度目标、CareTask 数值、排放边界和网络参数。
- H48 后任何预计超过 8 小时的新任务直接砍掉。
- H60 起禁止新增页面、指标、场景、依赖和数据源。
- 任一功能改变 GR-COMP-01 主指标超过既定 solver 容差且无预注册原因：不得进入发布版本。
- 任一新功能需要在线 API、账号、远程服务或真实组织数据：退出当前版本。

### 碳主张停止条件
- same_service_pass=false：停止“同服务减排”措辞，改为受控 epsilon trade-off。
- epsilon=0 没有碳优势：不强造结论；展示可行前沿和诚实 trade-off。
- carbon reconciliation 非零：停止全部碳比较，只修账本。
- flat-factor 或 terminal-SOC 测试推翻 Carbon-SOC 优势：Carbon-SOC 退出当前主张。
- kgCO2 与 kgCO2 无法在 H10 前统一：主 UI 暂时只写“运行碳清单”，不展示百分比减排。

### 演示停止条件
- 页面冷启动超过 15 秒或 Pareto 超过 20 秒：演示改为读取冻结 artifact。
- 连续两次现场路径失败：停止交互扩展，以冻结录屏+静态证据抽屉提交。
- 评委必须跨 3 个以上页面才能理解推荐原因：停止加 tab，收敛到单工作台。
- 图表无法追溯 source CSV：图退出主答辩。

## 6. 版本冻结门

### F0 Evidence Freeze，H4
- GR-COMP-01 run_id 唯一；
- factsheet、claims dictionary、scenario/config/factor/code hash 完成；
- 允许/禁止主张签字确认；
- 日期统一为 2026-08-22。

### F1 Model Freeze，H36
- network、CareTask、factor registry、strategy weights、resource config、solver tolerances 冻结；
- 禁止修改主数值模型；
- 之后只允许 UI、文档、测试、导出和严重 bug 修复；
- 严重 bug 修复必须生成新 run_id，并重新绑定 factsheet。

### F2 Data And Claim Freeze，H54
- 主 Pareto 点、三天气输出、MC catalog、失败 replay、MRV bundle 冻结；
- 图表只能从冻结 CSV 生成；
- PPT/UI/报告只能使用 claims dictionary；
- 新实验只能进入 appendix，不能替换主数字。

### F3 Release Candidate Freeze，H68
- 依赖、入口、文件结构、截图、视频、PPT、README 冻结；
- 只允许修提交打包错误；
- 每次变更重跑 release smoke 和 SHA256SUMS。

### Release Gate，H72
全部满足才可提交：
- 28/28 tests green；
- 三命名场景 smoke green；
- GR-COMP-01 MRV verified=true；
- carbon reconciliation pass；
- 至少一个 blocked/failure 反例；
- 至少四个 tamper 测试 detected；
- clean offline install/run pass；
- UI、PPT、视频、报告数字一致；
- 无 kgCO2 混用、无真实数据/认证夸大；
- final_submission SHA 完整。

## 7. 最终提交清单

### 运行包
- source 目录、app.py、pyproject.toml、requirements.txt；
- VERSION.txt、ENVIRONMENT.md、SHA256SUMS；
- README 一键运行与离线演示命令；
- clean_install_test.log、pytest.log、smoke_test.log；
- 第三方依赖与数据来源说明。

### 主证据包 GR-COMP-01
- canonical_factsheet.md；
- claim_dictionary.csv；
- network/scenario/config/factor/CareTask/code hash；
- 三策略 strategy_comparison.csv；
- dispatch、powerflow、CareTask、island passport；
- Pareto anchors、points、frontier、failures；
- MRV run_manifest、activity、inventory、actions、seal、verification；
- carbon_reconciliation.csv；
- 失败反例与 replay 命令。

### 稳健性包
- frozen_scenario_catalog.csv/json；
- monte_carlo_results.csv、summary.csv、failures.json；
- scenario SHA 配对检查；
- paired_deltas.csv 与 bootstrap summary；
- tamper_results.csv 和对应 verification JSON。

### 答辩包
- 3 分钟 PPT/PDF；
- 8 分钟备份 PPT/PDF；
- 3 分钟无剪辑录屏；
- 30 秒离线备用录屏；
- 4 张主图及 source CSV；
- 2 张主表；
- 评委 FAQ 与允许/禁止表述；
- policy_alignment_onepager.pdf；
- known_limitations.md 和路线图。

### 提交前删除
- 绝对用户路径、用户名、IDE 配置、缓存、临时输出；
- 未绑定 factsheet 的旧图和旧数字；
- kgCO2 错误口径；
- “真实调度、真实医院、官方认证、核证减排、显著优于”等未获证据支持的文本；
- 现场需要联网或长时间求解的入口；
- 未完成的 Carbon-SOC、真实接口、公平优化、AI 预测入口。

## 8. Wave 8 报告到范围决策的映射

| 报告 | 吸收结论 | 当前决策 |
|---|---|---|
| academic_novelty | 核心创新是 Contract-Gated Evidence Digital Twin，不是新优化算法 | MUST，作为总叙事 |
| judging_strategy | 唯一证据包、单位纪律、三门、失败反例、匿名终检 | 全部 MUST |
| demo_experience | 一个决策工作台+证据抽屉，现场读取冻结 artifact | MUST/S1；现场求解 CUT |
| deployment_architecture | 离线预案级原型；OMS/DMS/SCADA 为 P2 | 离线 MUST，真实接口 CUT |
| policy_standards | 政策对齐不是认证 | S7，一页附录；认证 badge CUT |
| pilot_plan | 教学试点需 6 周 | 路线图保留，本期实施 CUT |
| uncertainty_calibration | 36 冻结分层合成压力集；不做伪概率校准 | S2；AI/可靠性校准 CUT |
| resilience_equity | 只做合成、后验、报告型 passport | S5；公平权重入优化 CUT |
| marginal_value | 单场景 6-action LODO 是最小 MVP | S6；全量归因 CUT |
| carbon_soc_skeptic | Operational inventory 与 Carbon-SOC 分离，Carbon-SOC 有严格 NO-GO 门 | operational inventory MUST；完整 Carbon-SOC CUT |
| validation_design | G0–G5、A/B/C、Care/Pareto/MRV/tamper/统计 | 核心 P0 合同 |

## 9. 最终产品范围

### 10 天提交版本包含
- 三天气离线预案运行；
- A/B/C 对照；
- CareTask 任务合同；
- P/Q 潮流与成岛资格门；
- 同服务/受控 epsilon Pareto；
- 运行碳清单与 MRV 可验证 bundle；
- 失败点、篡改检测和 replay；
- 一个决策工作台；
- 冻结合成场景的稳健性摘要；
- 清晰的数据与主张边界。

### 10 天提交版本不包含
- Carbon-SOC 性能结论；
- 实时或真实生产调度；
- 真实天气/馈线/医院/用户数据；
- 官方认证、合规或核证结论；
- AI 预测校准；
- 人口公平优化；
- MISOCP/AC-OPF 重构；
- 大规模 Shapley/LODO；
- 现场在线计算依赖。

## 10. 最后裁决

前三天只做可信度和交付稳定性。第 4 天之后，只有已经证明不会改变冻结主数字、不会扩大主张边界、不会制造现场依赖的功能才能进入候选版本。

一等奖策略不是展示最多模块，而是让评委清楚看到：

1. 一个候选为什么被推荐；
2. 它牺牲了什么服务；
3. 它是否真实物理可行；
4. 它的碳数字如何重算；
5. 一个不合格候选如何被系统拒绝；
6. 所有数字能否在离线、匿名、冻结环境中复现。

