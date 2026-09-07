# GridRescue 5 分钟评委演示导演稿（Wave 6）

> **主句：先锁生命线服务，再验物理可行，最后比较可核验的运行排放。**

## 1. 叙事主线

不要逐页介绍功能。让评委沿同一条证据链走：

~~~
冻结武汉天气回放（未冻结则明确为合成暴雨）
→ 同服务 Pareto（不靠少供电刷低碳）
→ CareTask（关键负荷不是一个百分比）
→ 成岛护照（带电孤岛不等于可运行微网）
→ 动作级 MRV（动作、能流、潮流、因子可回放）
→ Carbon-SOC（电池放电不被误写为零碳）
→ 推荐点的服务门、物理门和证据门
~~~

五分钟的三个结论：

1. 系统不会用少供电伪造低碳：服务合同先于碳比较。
2. 系统不会用“带电”伪造可成岛：无 GFM、P/Q 裕度、电压、热限、SOC 任一异常都会显示。
3. 每个推荐数字可回到场景、动作、逐时 dispatch、潮流与证据文件。

纪律：只用一个主场景和固定 seed；Pareto 会前跑完；至少展示一次 BLOCKED；所有碳数字旁边都必须有服务、物理、数据质量状态。

## 2. 当前可讲与不可讲

| 主题 | 当前可讲 | 当前不可讲 | 现场策略 |
|---|---|---|---|
| 同服务 Pareto | 类别级医院/其他关键 EENS 硬锁，普通 EENS 让步显式，每点重做 P/Q、孤岛、电压、热限 | CareTask 已成为 Pareto 硬合同 | 主舞台；称“同生命线/关键服务下的普通服务—碳权衡” |
| CareTask | 四个合成任务有最低 kW、时窗、deadline、持续时长、电压、依赖和失败码，可后验核验 | 真实医院标准、临床安全、任务驱动 Pareto | 主舞台；永久标 E 类合成模板 |
| 成岛护照 | GFM/黑启动状态、P/Q 裕度、SOC、电压、热限、最弱约束、BLOCKED 原因 | 现场投运、燃料续航、保护/同期、VERIFIED | 主舞台；展示失败岛 |
| 当前 MRV | 动作时间线、逐时 dispatch、潮流 CSV、Markdown 报告、网络 SHA | action ID、因子 registry、run manifest、封签、动作归因 | 叫“方案级可复算导出” |
| 武汉天气 | 只有设计方案 | 冻结响应、规范化表、请求、hash | 缺证据时完全不说武汉，称合成暴雨 |
| Carbon-SOC | 只有设计方案；当前主快照电池几乎无充放 | 来源 bucket、initial unknown、factor assignment、ledger | 缺实现时不登台 |

### 六主题的最小上线门

| 模块 | 最低条件 | 不满足时 |
|---|---|---|
| 武汉天气 | raw response、normalized CSV、request JSON、Asia/Shanghai、source/model、SHA-256 | “合成暴雨内涝” |
| CareTask-Pareto | 每个 Pareto run 有 task evaluation；Tier-1 pass 才 frontier eligible | 类别级 Pareto + 独立后验任务审计 |
| 成岛护照 | 明确 assumed_from_model/not VERIFIED，且能展示 BLOCKED 原因 | 不宣传“微网已安全运行” |
| 动作 MRV | action ledger、factor snapshot、run manifest、G0-G4、hash index | 方案级 MRV 报告 |
| Carbon-SOC | 物理 SOC 与来源 bucket 分离；initial unknown 可见；放电不二次入账 | 只显示 SOC/功率 |
| 排放口径 | 因子有地域、年份、单位、边界、来源、版本、hash、质量状态 | “原型运行排放清单（kg）/敏感性”，不说 CO2e 或减排 |

## 3. 版本 A：六模块完成后的 5:00 强路径

会前：宽屏，隐藏终端与开发路径，所有图已加载，Pareto 四点已跑完，天气/MRV/Carbon-SOC 的离线证据可打开。

| 时间 | 点击路径 | 屏幕证据 | 可直接说的话 | 禁止扩张 |
|---:|---|---|---|---|
| 0:00-0:25 | 天气回放，选 WH_FLOOD_2020，定位 24h 窗 | 坐标、Asia/Shanghai、ERA5、请求和文件 hash、来源徽章 | “这是武汉中心点的**冻结 ERA5 再分析天气输入**。它给出风、雨、温度和辐照 forcing；故障和修复仍是工程先验，不是武汉馈线事故复盘。” | “武汉真实停电复现”“实时天气” |
| 0:25-1:18 | 公平Pareto，点 0%、4%、5%、6%，重点比 0 与 6 | 医院/其他关键 EENS、普通 EENS、排放清单、24/24 physical、Vmin、loading、run ID | “先不谈碳。医院和其他关键先锁；0% 点还锁普通服务。其他点只允许公开的普通服务预算让步，每一点重新过 P/Q、孤岛、电压和热限。” | 把 4-6% 叫“同服务减排” |
| 1:18-1:55 | 生命线任务，筛 Tier-1，展开 ICU/手术 | task ID、kW、deadline、Vmin、连续时长、pass、definition hash | “医院不是一个百分比，而是一组带功率、时间、连续时长和电压门的合成设施任务。这个 run 的 Tier-1 任务通过；任务失败候选不进入推荐。” | 临床安全、真实医院保障 |
| 1:55-2:35 | 成岛护照：传统顺序恢复/T+0，先点 BLOCKED 再点 DEGRADED | NO_GFM、assumed_from_model、P/Q reserve、SOC、最弱约束 | “被切出来不等于可成岛。这个岛因 NO_GFM 被 BLOCKED；另两个即使有模型内 GFM 候选，也因 P/Q 裕度很薄是 DEGRADED。没有现场黑启动和燃料续航证据，永远不写 VERIFIED。” | “医院孤岛已安全运行” |
| 2:35-3:22 | 数字孪生，动作表，选 T37 或联络线动作，开 MRV 抽屉 | action ID、模拟状态、拓扑前后、关联 dispatch/潮流行、ledger hash、G0-G4 | “这是**模拟动作**，不是现场遥控记录。它连到同小时能流和潮流证据；只有服务、物理和比较门通过，才允许展示方案间排放差额。” | “单个开关减排 X kg”，除非反事实重放已通过 |
| 3:22-4:00 | 能源与碳流，高负荷储能小时，开 Carbon-SOC | SOC、charge/discharge、grid/PV/diesel/initial unknown buckets、factor ID | “物理 SOC 与碳归因账是两件事。电池放电不是零碳；充电侧排放已进主账。初始 SOC 来源未知时就标 unknown。” | “电池储碳”“放电即减排” |
| 4:00-4:32 | MRV报告，Evidence/Seal，展示 manifest | run ID、天气/网络/factor/task hashes、服务门、物理门、输出 hash | “每次推演冻结输入、因子、任务、动作和输出。评委看到的不只是 KPI，而是一条可下载、可复算、可验完整性的证据链。” | 区块链、第三方认证 |
| 4:32-5:00 | 回 Pareto 推荐点 | gate 状态与推荐理由 | “GridRescue 把灾害输入、服务合同、成岛资格、恢复动作、碳账和证据接成一条决策链。当前仍是预案级标准算例原型，真实部署需接真实馈线、资产台账和地区因子。” | 已在武汉落地、替代调度员 |

**版本 A 的唯一结论：**

> 在冻结天气、资源和故障输入下，GridRescue 将 Tier-1 生命线和物理可行设为先决条件；只在通过这些门的候选中展示普通服务—运行排放权衡，并保留可回放证据。

## 4. 版本 B：当前版本就可安全演示

没有冻结武汉回放、Carbon-SOC 或动作级 MRV 时，用此版本；设计稿不冒充成果。

| 时间 | 点击路径 | 准确口径 | 现有证据 |
|---:|---|---|---|
| 0:00-0:25 | 首屏：暴雨内涝/碳韧协同恢复/T+0 | “这是公开 case33 上的**合成暴雨内涝推演**；三策略使用同一故障、资源与负荷。” | L6/L13/L27、拓扑、动作 |
| 0:25-1:05 | 三策略对照 | “传统、最小失供和碳韧协同只改决策。传统关键恢复率 87.2%，后两者 100%，所以不能只看一个碳数字。” | strategy comparison |
| 1:05-1:50 | 公平Pareto，预热四点 | “医院与其他关键先锁；0% 是普通服务锚点；4-6% 显式显示普通负荷让步。” | 四点、P/Q、Vmin、loading、run ID |
| 1:50-2:25 | 生命线任务，碳韧协同 | “四项合成任务在本冻结 run 的后验功率/电压检查均通过，参数和结果可下载。” | ICU、手术、冷链、通信、failure codes |
| 2:25-3:10 | 成岛护照：传统顺序恢复/T+0 | “系统敢判失败：一座岛 NO_GFM，另两座 DEGRADED。模型推断不冒充现场成网验证。” | 3 非根岛：1 BLOCKED、2 DEGRADED |
| 3:10-3:45 | 数字孪生：碳韧协同/T+7 | “T+0 闭合 T37/T33/T34，T+7 修复 L6。当前是模拟动作序列，逐时调度和潮流可导出。” | action CSV、网络图 |
| 3:45-4:25 | 能源与碳流，再到潮流校验 | “主快照物理不可行小时为 0；最低电压约 0.970 pu，最大支路负载约 99.9%。碳为电网、柴油、车辆的原型运行清单。” | dispatch、powerflow、report |
| 4:25-5:00 | MRV报告，下载 report/CSV | “已有方案级可复算导出：网络 SHA、动作、逐时能流、P/Q 校验和碳分项。下一版才升级 action ID、因子快照、任务门和封签。” | Markdown MRV、逐时 CSV |

版本 B 收束：

> “我们不把标准算例包装成真实武汉馈线，也不把未实现的动作归因包装成 MRV。当前已完成的是：在同一场景中，把服务、潮流、成岛资格和方案级碳清单统一复算。”

## 5. Pareto 必背数字与准确句式

暴雨内涝、最小失供恢复、四点物理 Pareto：

| 普通负荷让步 | 普通 EENS kWh | 原型运行排放清单 kg | 医院 EENS kWh | 其他关键 EENS kWh | 物理可行小时 | Vmin pu | 最大支路负载率 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0% | 956.533 | 44980.421 | 0.004624 | 0.029602 | 24/24 | 0.980785 | 99.591% |
| 4% | 2660.928 | 42646.482 | 0.004634 | 0.029609 | 24/24 | 0.970374 | 99.965% |
| 5% | 3087.026 | 42348.217 | 0.004618 | 0.029562 | 24/24 | 0.970439 | 99.947% |
| 6% | 3513.125 | 42046.310 | 0.004622 | 0.029606 | 24/24 | 0.970255 | 99.897% |

允许：

- “0% 点是严格服务锚点：医院、其他关键和普通负荷都贴住物理服务锚点。”
- “4%、5%、6% 保持医院和其他关键服务锁定，但公开允许普通负荷让步；它们是受控权衡，不是无代价减排。”
- “从 0% 到 6%，清单降低约 2934 kg、约 6.5%，普通 EENS 增加约 2557 kWh；服务代价被强制显示。”

禁止：

- “所有 Pareto 点同服务减排。”
- “CareTask 已被 Pareto 硬锁。”
- “这些 kg 是真实 CO2e/真实武汉排放。”
- “系统得到全局最优。”

## 6. 成岛护照的强示例

暴雨内涝、传统顺序恢复、T+0：

| 组件（0-based；括号为 UI 节点） | 状态 | 关键证据 | 演讲解释 |
|---|---|---|---|
| 6-12（N07-N13） | BLOCKED | NO_GFM；grid_following_only；black start not available | “只有跟网型 PV 不能成为成网电源。” |
| 13-17（N14-N18） | DEGRADED | assumed_from_model；P reserve 接近零 | “有容量候选不等于有安全裕度。” |
| 27-32（N28-N33） | DEGRADED | Q reserve 接近零 | “有有功不等于有无功裕度。” |

全场最应留下的 25 秒，就是系统“拒绝错误推荐”，而非全绿截图。

## 7. 高频质疑与回答

| 问题 | 30 秒回答 |
|---|---|
| 低碳是不是少供电？ | 0% 锁全部服务；epsilon 点公开普通 EENS 增量。医院与其他关键先锁，代价不能被碳数字掩盖。 |
| 任务数字来自哪家医院？ | E 类合成模板，用于验证任务合同接口；不是医院测量或临床标准。真实部署要用设备、回路和预案数据替换。 |
| 关键 EENS 为零等于患者安全？ | 不等于。当前仅是小时级配网侧最低供电和稳态电压；UPS/ATS、瞬断、频率/THD、临床流程未验证。 |
| Pareto 保证手术任务了吗？ | 当前锁类别级医院/其他关键 EENS，任务独立后验审计；任务级 gate 完成前不称医疗任务保证。 |
| GFM/黑启动从何而来？ | 当前由柴油/BESS容量推断，故为 assumed_from_model；没有燃料、保护、控制和投运试验就不写 VERIFIED。 |
| 电池放电是否零碳？ | 不是。主账在充电/燃料活动入账；Carbon-SOC 只做来源归因，未知初始 SOC 为 unknown。 |
| 一个开关减多少碳？ | 当前不归因到单动作。需要撤销动作重放，并使双方服务/物理门都通过，才有模型内差额。 |
| 是武汉真实网吗？ | 不是。case33 基准叠加工程假设；武汉只能是冻结天气 forcing，不是馈线事故复盘。 |
| 算法全局最优吗？ | 当前是固定计划下 epsilon-constraint 扫描并含 P/Q 反馈的可执行前沿，不声称统一整数优化全局最优。 |
| 30 个场景能证明鲁棒吗？ | 是固定 seed 的合成压力测试，用于可重复比较，不是现实故障频率统计。 |

## 8. 必须切掉的内容

| 切掉 | 原因 | 替换 |
|---|---|---|
| “武汉真实天气/真实馈线/真实医院” | 当前数据链不足 | 冻结再分析输入，或合成场景 |
| “实时碳排”“实时边际因子”“CO2e” | 因子未完成来源、边界、版本、registry | 原型运行排放清单（kg）、因子敏感性 |
| 现场跑 Pareto | 等待破坏节奏 | 会前预热 run |
| 主线的 30 场景 Monte Carlo | 稀释闭环 | 放 Q&A 备用 |
| AI 风险预测 | 没有真实标签校准 | 放路线图 |
| 无 ledger 的 Carbon-SOC 概念图 | 会被追问数据位置 | 有 bucket 的 run 才展示 |
| 无反事实的单动作减排图 | 虚假归因 | 先展示动作证据链 |
| 全绿成岛截图 | 无法证明严谨 | 展示 NO_GFM/DEGRADED |

## 9. 收口

20 秒版：

> “GridRescue 不把恢复电量直接说成减排，也不把带电孤岛直接说成可运行微网。它先把医院与关键服务写成合同，再用潮流和成岛资格筛掉不可行方案，最后把动作、能流、因子和输出组织为可复算证据。当前是预案级标准算例原型；真实部署需要真实馈线、资产、任务字典和地区因子。”

15 秒版：

> “先保生命线、再验物理、后比碳，并让每一个推荐点都能回到天气、动作、能流和证据。”

## 10. 本地证据依据

- README.md：case33、三策略、Pareto、P/Q、护照、当前限制。
- app.py：八个页签、Pareto、CareTask、护照、MRV 下载。
- artifacts/pareto_flood_v05/pareto_frontier.csv：四点 Pareto 数值。
- artifacts/flood_v04/strategy_comparison.csv、report_carbon_resilient.md：主场景和碳韧快照。
- artifacts/flood_v04/island_passport_episodes_traditional.csv：传统策略成岛 episode。
- src/gridrescue/care.py：四项默认 CareTask。
- research_wave/wave2_weather.md：武汉 ERA5/Open-Meteo 回放设计。
- research_wave/wave2_carbon_soc.md：Carbon-SOC 不双算和因子 registry。
- research_wave/wave3_hospital_tasks.md、wave3_island_passport.md：任务/护照设计。
- research_wave/wave6_mrv_evidence.md：动作级 MRV、G0-G4、封签设计。
- research_wave/wave6_care_redteam.md：CareTask-Pareto 断链和不可主张项。

## 11. 进入版本 A 的工程优先级

1. CareTask 接入 Pareto gate：Tier-1 task pass 才能推荐。
2. factor registry、run manifest、data-quality badge。
3. 冻结一个武汉天气案例及完整 manifest。
4. action ledger、G0-G4、evidence index；动作反事实归因后置。
5. Carbon-SOC source bucket，只在有明显充放电的 case 中登台。
6. 真实资产、医院任务字典和地区因子，作为区域化验证阶段。

> 红线：CareTask gate、因子/manifest、天气冻结任一缺失时，采用版本 B；不要把设计稿说成部署完成。

