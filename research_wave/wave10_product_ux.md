# GridRescue 产品交互与演示体验：10 天可落地改造清单（Wave 10 UX）

**正式日期：2026-08-22**  
**范围：** 只读评审 app.py、demo_ux_plan.md、wave8_demo_experience.md 与 wave10_judge_psychology.md；本文不修改生产代码。  
**目标：** 把当前“六个指标 + 八个同权 Tab + sidebar 自由选择”的工具界面，收敛成评委在 30 秒看懂推荐资格、3 分钟走完可信闭环、追问时能直接复核的决策产品。

---

## 1. 当前产品诊断

### 1.1 能力已齐，默认路径却不是“决策”

app.py 已有灾害场景、三种恢复策略、逐时拓扑、潮流校验、CareTask、成岛护照、Pareto、MRV bundle 复核以及证据下载。MRV 页面还会读取 manifest、seal、verification、claim gates、因子表，并执行 live verification。

当前默认路径却是：

~~~text
左栏选场景/策略/小时 → 顶部六 KPI → 八个 Tab 自行浏览
~~~

它让评委先比较算法指标，而不是先知道候选是否有资格被推荐。评委必须自行拼出：

~~~text
灾害 → 候选 → CareTask 合同 → P/Q/潮流/成岛
→ 碳—服务代价 → claim gate → seal/verify
~~~

这会让系统显得像八块功能拼图，不像能阻止错误决定的工作台。

### 1.2 主要体验风险

| 当前界面现状 | 现场摩擦 | 产品后果 |
|---|---|---|
| sidebar 默认暴露恢复策略 radio | 评委误以为自己必须从算法中选一个 | 推荐与三门资格后置 |
| 六 KPI 是恢复率、EENS、碳、柴油、新能源、动作次数 | 多数数字不改变推荐结论 | 首屏拥挤，碳数脱离服务代价 |
| 八 Tab 同权 | 叙事靠频繁跳页 | 因果链断裂、操作风险高 |
| Pareto 首次点击可能耗时几十秒 | 现场等待/重算 | 冻结证据与探索数字混读 |
| MRV 在第 5 个 Tab | 信任证据远离主线 | seal 与 verify 像附件 |
| 拓扑、CareTask、潮流、成岛分别呈现 | 同一小时状态没有并置 | 动作和结果的因果不清 |
| 负碳差可被绿色视觉放大 | same-service 未通过容易被忽略 | 易遭“少供电刷低碳”质疑 |
| 文稿常写“11 files”，但现有 test_app_mrv.py 对正式 bundle 的断言是 checked_files >= 17 | UI、口播、PPT、测试会冲突 | 低级可信度损失 |
| 已有篡改失败 AppTest | 未转为现场可见瞬间 | 少了最强信任反例 |

应把下列事实做成界面规则而非页脚：证据冻结日期为 **2026-08-22**；数据是 E 类合成工程输入；碳口径为 kgCO2；same-service gate 未通过时只能表达“受控服务预算下的清单差异”。

---

## 2. 目标信息架构

~~~text
常驻证据控制条
  ↓
30 秒 Gate：先验证服务、物理、证据
  ↓
决策工作台：拓扑 + 当前动作 + 两候选决策条
  ├─ 服务证据抽屉
  ├─ 物理证据抽屉
  └─ 碳与 MRV 证据抽屉
  ↓
被拦截反例 → 稳健性/追问库/下载
~~~

默认预设为“暴雨内涝 + 冻结主 run + 主推荐 + T+04h 或 T+06h”。场景、小时、策略和 Pareto 仍可自由探索，但必须标为 LIVE EXPLORATION；主证据标为 FROZEN EVIDENCE。

首屏最多六个数字：候选—参考清单差、普通 EENS Δ/epsilon、CareTask、Vmin、最大载流率、Evidence verification。其余进入抽屉。

---

## 3. 24 条十天内可落地改造

| ID | 优先级 | 改造 | 评委可见结果 | 最小验收物 |
|---|---|---|---|---|
| UX01 | P0 | 默认页改成“决策工作台”，八 Tab 收进研究/追问区 | 刷新后十秒知道推荐什么 | 无点击可见推荐、三门、碳—服务代价 |
| UX02 | P0 | 顶部常驻证据控制条：预案级、case33bw、E 类、场景、小时、预设、run、seal、verify、下载 | 范围与证据身份不丢 | 1366×768 一行可读、无本机路径 |
| UX03 | P0 | 冻结 GR-COMP-01 factsheet，统一 run、场景、单位、epsilon、hash、允许主张 | UI/PPT/视频同一组事实 | UI 文案与 factsheet 自动校验 |
| UX04 | P0 | 顶部 120px 结论带改成“推荐资格” | 先看到结论再看图 | 关键数字不超过六个 |
| UX05 | P0 | 三门资格卡常驻：服务、物理、证据；可点击进证据 | 低碳不是唯一门槛 | 三张卡均可 deep-link |
| UX06 | P0 | 碳—服务绑定卡：kgCO2 与 normal EENS Δ、epsilon、same-service gate 同卡 | 直接排除“少供电刷低碳” | gate=false 时自动使用受控预算文案 |
| UX07 | P0 | 策略 radio 从一级控件降为比较对象 | 用户从“选算法”转为“审推荐” | 默认页不先要求选策略 |
| UX08 | P0 | 两候选决策条：服务锚点 vs 受控预算候选；完整 Pareto 放追问库 | 一屏看懂让步与清单差 | 两侧均有服务、物理、EENS、kgCO2 |
| UX09 | P0 | 右侧三条可点击推荐理由：服务合同、物理可行、碳与证据 | KPI 解释不靠口播 | 每条能进入字段级来源 |
| UX10 | P0 | 所有冻结数字标 FROZEN EVIDENCE；自由页面标 LIVE EXPLORATION | 现场重算不冒充正式主张 | 切自由场景/Pareto 后显式出现 live 标签 |
| UX11 | P0 | 30 秒 Gate 动画：灾害、服务门、物理门、证据门、推荐锁定 | 建立“先拦截再推荐”记忆点 | 可跳过、可重播、不运行求解 |
| UX12 | P0 | 三预设：主推荐、被拦截反例、稳健性追问 | 一键进入答辩路径 | 反例与主推荐均一键切换 |
| UX13 | P0 | BLOCKED:NO_GFM 反例卡，显示失败码、最弱约束、筛除理由 | 证明不会把假可行方案推荐 | 20–25 秒完成切反例再回主推荐 |
| UX14 | P0 | 篡改即失效预设：官方只读 bundle + tampered clone | seal/verifier 变成可感知机制 | FAIL 显示错误文件，reset 后 PASS |
| UX15 | P1 | 服务抽屉改 CareTask 卡 + 甘特/热图 + deadline 线 | 医院服务成为有阈值时窗的合同 | 任务有 min kW、Vmin、deadline、失败码 |
| UX16 | P1 | 物理抽屉改 Vmin/loading 双轨 + 当前小时 marker | 物理通过有可见依据 | pu 与 % 不共用 y 轴；可定位最弱支路/节点 |
| UX17 | P1 | 大表改为“当前动作 → 影响 → 理由 → 状态”卡；完整表折叠 | 每个拓扑变化有行动原因 | 改小时后动作、拓扑、任务同步 |
| UX18 | P1 | 拓扑增加服务节点图层，预计算稳定坐标 | 画布成为行动主舞台 | 切预设/小时后坐标不跳动；线型兼容灰度 |
| UX19 | P1 | “为何未被推荐”折叠卡，为三策略给服务/物理/证据/碳服务理由 | 三策略图不再只是柱高比较 | 每个理由追到指标或失败码 |
| UX20 | P1 | MRV 五步证据轨：活动→因子→清单→gate→seal/verify | “ZIP 下载”升级为可理解证据链 | 因子等级、文件数、下载、语义齐全 |
| UX21 | P1 | 碳图改成 grid/diesel/crew 清单瀑布；机会损失单列 | 碳从哪里来一眼可见 | 与 reconciliation 对账，单位均为 kgCO2 |
| UX22 | P1 | 30 场景稳健性卡：成功/失败、P50/P90、seed、replay | 回应“是否挑好案例” | 失败样本可见且可回放 |
| UX23 | P1 | presenter mode 和快捷键：1 主推荐、2 反例、3 MRV、R 重播 Gate | 三分钟低操作风险 | 同时保留大按钮，键盘失效仍能走通 |
| UX24 | P2 | 决策快照 PNG/HTML/JSON + 三视口响应式样式 | 评委可独立带走结论，投屏不截断 | 快照含 scenario/hour/run/gates/hash 且无绝对路径 |

---

## 4. 30 秒 Gate：状态机而非炫技加载

所有帧只读取冻结工件，严禁在 Gate 内运行 Pareto 或 pipeline。

| 时段 | 画面变化 | 评委得到的信息 | 交互 |
|---:|---|---|---|
| 0–6 秒 | 拓扑由中性转故障态，医院/通信节点出现风险标识 | 灾害发生，先锁定生命线与边界 | 展示场景、T+0、E 类标签 |
| 6–13 秒 | 服务门由灰转状态色，出现 CareTask 与 deadline | 先验证服务合同 | 查看服务可随时打断播放 |
| 13–20 秒 | 定位最弱节点/支路，展示 Vmin/loading 或 BLOCKED | 有电量不等于物理可行 | 当前小时与动作卡同步 |
| 20–27 秒 | MRV rail 依次点亮，显示 run、claim gate、verify | 结论有冻结、可复算来源 | 查看 MRV 直接跳到结果 |
| 27–30 秒 | 推荐卡锁定；kgCO2 与 normal EENS Δ 同时出现 | 三门通过才有推荐资格 | 明示非严格同服务降低 |

必要设计：

1. 默认自动播放一次，顶部始终有“跳过 Gate”和“重播”。
2. presenter mode 不循环，防止抢口播。
3. reduced-motion 下改成静态四步条或逐帧切换。
4. Gate 失效时仍显示最终结论带，不得阻断答辩。

---

## 5. 篡改演示：把已有 AppTest 变成证据门高光时刻

现有 test_app_mrv.py 已验证：正式 bundle 会显示 Verification=PASS；复制 bundle 后将 outputs/activity_energy_hourly.csv 中的 energy_kwh 改动 1.0，会显示 Verification=FAIL、复核失败提示及该文件名。该能力应做成低风险演示。

### 15–20 秒操作

1. 主推荐页显示 Evidence PASS、SEALED、run ID。
2. 点击“证据门 → 演示篡改副本”，页面带明显标签“DEMO CLONE · NOT OFFICIAL EVIDENCE”。
3. 加载预制 tampered fixture，或点击“活动账本 +1 kWh”。
4. 证据门转红：Verification FAIL；错误框显示 activity_energy_hourly.csv；推荐结论灰化，显示“证据门未通过，禁止进入正式主张”。
5. 点击“恢复官方冻结包”，重新得到官方 run 和 PASS。

### 硬约束

- artifacts/v08_official 目录全程只读；篡改只发生在临时目录或预制 fixture。
- 演示副本绝不使用官方 run 名称，绝不作为正式包下载。
- 文案只宣称文件完整性/可复算校验，不宣称第三方现场核证。
- 必须存在 deterministic reset，每次演示均得到同一失败文件与错误类型。

---

## 6. 三分钟演示操作路径（不超过八次点击）

| 时间 | 操作 | 画面证据 | 要回答的疑问 |
|---:|---|---|---|
| 0:00–0:30 | 刷新或重播 Gate | 灾害→服务门→物理门→证据门→推荐 | 你在解决什么？ |
| 0:30–0:55 | 查看服务 | 4 个 CareTask、deadline、功率/电压、失败码 | 关键负荷怎么定义？ |
| 0:55–1:20 | 查看物理 | Vmin/loading 双轨、最弱约束 | 是否物理可行？ |
| 1:20–1:45 | 预设 2：被拦截反例 | BLOCKED:NO_GFM 与筛除理由 | 是否会放过假方案？ |
| 1:45–2:05 | 预设 1：主推荐 + 两候选条 | 锚点/受控预算、kgCO2 与 normal EENS Δ | 是不是少供电换低碳？ |
| 2:05–2:30 | 预设 3：MRV | 活动→因子→清单→gate→seal/verify | 数字从哪里来？ |
| 2:30–2:45 | 篡改副本 | FAIL 与具体失败文件 | 证据如何防改？ |
| 2:45–3:00 | 稳健性卡后回首页 | 成功/失败、P50/P90、replay | 是否挑了好案例？ |

主线中不点击“运行4点物理 Pareto 扫描”；扫描留在研究模式和追问路径。

---

## 7. 移动投屏与可读性规范

| 视口 | 优先任务 | 布局规则 |
|---|---|---|
| 1920×1080 会场大屏 | 完整叙事 | 拓扑占 2/3，理由/动作 1/3，三门横排，抽屉右侧浮出 |
| 1366×768 笔记本投屏 | 结论优先 | 顶部一行、结论带不高于 150px、拓扑 430–480px、抽屉改底部叠层 |
| 390×844 手机预读 | 远程可读 | 结论带→三门→小拓扑，抽屉全屏，宽表转卡片或下载 |

具体规则：

1. 投屏主结论至少 28px；门状态至少 18px；说明文字至少 14px。
2. 红绿状态必须同时含 PASS/BLOCKED/DEGRADED/UNVERIFIED 文本和图标。
3. 图例可折叠；小屏隐藏节点文字，以 tooltip 或节点选择卡补足。
4. 可点击目标至少 44px；按钮用动作词，不使用仅名词 Tab。
5. 第一屏没有 dataframe 宽表；轴标题和卡片必须自带单位。
6. 录屏采用 16:9，关闭通知；浏览器标题、文件名、截图均不泄露学校、人员、用户名、绝对路径。

---

## 8. 10 天节奏

| 日期 | 交付 | 验收 |
|---:|---|---|
| Day 1 | GR-COMP-01 factsheet、数字/单位/主张字典、checked-files 单一来源 | 解决“11”与“>=17”矛盾 |
| Day 2 | 顶部条、结论带、三门、主张语义锁 | 1366×768 首屏可读 |
| Day 3 | 主画布、理由卡、动作卡、稳定坐标 | 改小时三类证据同步 |
| Day 4 | 两候选条、FROZEN/LIVE 分层、冻结 Pareto | 默认路径无长计算 |
| Day 5 | 服务/物理/MRV 三抽屉 | 每门直达字段来源 |
| Day 6 | 三预设、NO_GFM 反例 | 一键切换、可回归 |
| Day 7 | 30 秒 Gate、快捷键、reduced-motion | 可跳过、可重播、可截图 |
| Day 8 | tampered fixture、决策快照、追问库 | 官方 bundle 只读，FAIL 可复现 |
| Day 9 | 三视口适配与三分钟录像 | 点击≤8、录像≤180 秒 |
| Day 10 | 干净环境测试、离线录屏、下载回归 | 主推荐/反例/tamper/MRV 全通过 |

---

## 9. AppTest 验收矩阵

保留现有正式 bundle PASS、下载、场景错配、篡改 FAIL 测试；新增以下黑盒验收。

| 测试 | AppTest 行为 | 断言 |
|---|---|---|
| AT01 | 首次 AppTest.from_file 运行 | 无 exception；默认出现主推荐预设，非八 Tab 首屏 |
| AT02 | 读取首屏 | 推荐、三门、E 类、kgCO2、normal EENS Δ 同时存在 |
| AT03 | 读取主张 | same-service 未通过时，不出现严格同服务降低标题；出现受控预算清单差异 |
| AT04 | 切换被拦截反例 | 出现 BLOCKED 和 NO_GFM 或固定失败码；无正式推荐 CTA |
| AT05 | 由反例切回主推荐 | 三门为 PASS；run ID 与 factsheet 一致 |
| AT06 | 改变 hour | 动作卡、拓扑标题、服务/物理当前小时一致改变 |
| AT07 | 打开服务抽屉 | 有任务数、deadline、min kW、minimum voltage、failure reason |
| AT08 | 打开物理抽屉 | 有 Vmin、max loading、阈值、最弱约束；图轴未混单位 |
| AT09 | 打开 MRV 抽屉 | Seal、Verification、checked files、factor class、claim status、下载均在 |
| AT10 | 加载篡改 fixture | Verification=FAIL；error 含失败文件；推荐降级 |
| AT11 | 恢复官方 fixture | 再次 PASS；官方 bundle hash 不变 |
| AT12 | Gate 重播/跳过 | 无 exception；跳过后结论完整；不触发 Pareto/pipeline 重算 |
| AT13 | LIVE EXPLORATION 操作 | 出现 live 标签，不覆盖 frozen run 和主张 |
| AT14 | 下载决策快照 | 产物含 scenario、hour、candidate、run、gate、hash，无绝对路径 |
| AT15 | Playwright 截图补充 | 1366×768 与 390×844 首屏不横向裁切主结论，主要按钮可点 |

建议命令：

~~~powershell
cd C:\Users\ASUS\Documents\Codex\2026-08-22\n\work\gridrescue
pytest -q tests/test_app_mrv.py
pytest -q tests/test_app_*.py
~~~

AppTest 负责状态和语义；视口视觉回归交给 Playwright 截图基线，基线仅覆盖结论带、三门、主画布首屏和抽屉头部，避免 Plotly 微小字形差异造成误报。

---

## 10. 结论

十天内最值钱的工作不是新增模型、地图、3D 或第九个 Tab，而是把现有能力改造成会主动阻断错误结论的产品：

> **GridRescue 先验证生命线服务、物理可行和证据完整性；三门通过后，系统才展示受控服务预算下的运行碳清单差异并给出推荐。**

这条主张应在 30 秒 Gate、NO_GFM 反例、篡改 FAIL、两候选决策条和 MRV 抽屉中反复被看见，而不只是停留在答辩稿里。
