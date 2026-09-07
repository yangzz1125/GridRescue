# GridRescue Wave 10：竞赛视觉设计与证据叙事报告

**正式日期：2026-08-22**  
**版本：GridRescue 碳韧智网 V08**  
**范围：** 已审阅 app.py、Wave 8 视觉规范、申报书初稿、五分钟视频脚本、V08 release manifest、V08 工件与 7 张现有 PNG；本报告不修改生产代码。

> 核心视觉句：先过生命线服务门、物理可行门、证据完整门；通过后才展示带普通服务代价的恢复阶段碳清单差异。

## 1. 现状判断

当前应用拥有拓扑、恢复动作、三策略、潮流、MRV、Pareto、成岛和 CareTask 等完整能力，但八个 Tab 让评委自行拼因果链。应收敛为“推荐资格”工作台，而不是功能集合。

现图必须整体重绘。关键原因如下：

- 图 01 数字与 V08 正式暴雨策略表不一致：现图传统策略 EENS 为 6,610 kWh，V08 官方值为 10,574.78 kWh。
- 图 03 将负载率与电压放进双 y 轴，投影时不利于判断阈值。
- 图 04 标题称故障和孤岛，但画面几乎全绿，L6/L13/L27、T33/T34/T37、关键服务和状态没有可读编码。
- 图 05 标为 kgCO2e，但 V08 manifest 的正式口径为 kgCO2；同服务门未通过时，只能表述“受控服务预算下的运行碳清单差异”。
- 图 06 的 READY、CONDITIONAL 图例与画面状态不完全对应，BLOCKED/DEGRADED 没有统一原因码。
- 图 07 应将“E 类合成赛事模板”提升为标题级边界，且改为服务合同时间证据而不是两张孤立柱图。

V08 正式事实：暴雨碳韧协同恢复为 CareTask 4/4、关键负荷恢复率 100.00%、24/24 h 物理可行、Vmin 0.9703 pu、最大负载率 99.90%、清单 41,178.60 kgCO2。三个 MRV bundle 均为 SEALED 和 verification PASS，每包核验 17 个文件；这只表示完整性与可复算，非现场实测或第三方认证。

## 2. 冻结图源与统一口径

**唯一正式来源：**

1. 一级：artifacts/v08_official/flood、heat、typhoon 内的策略、调度、拓扑、潮流、成岛、CareTask、MRV 工件。
2. 二级：被 V08 ZIP 收录的 artifacts/mc30_v04 与 artifacts/pareto_flood_v07；图注必须标 V08 release-archived experiment。
3. 禁止混用根目录旧 CSV、flood_v02 至 flood_v07、debug_mrv 和人工抄写数。

每张正式图固定保留证据行：

    GridRescue V08 | 2026-08-22 | 场景 | 策略/候选 | E-SYNTHETIC | run ID/source SHA | 单位

碳统一写 kgCO2；CareTask 一律写 E-SYNTHETIC；INTEGRITY VERIFIED 旁写“文件完整性和内部复算，非现场核证”。所有正式文件名附 _V08_2026-08-22。

## 3. 具体改进清单（31 项）

| ID | 改进 | 验收 |
|---|---|---|
| 01 | 采用四域色：Service #16865B、Carbon #007F8B、Physics #C27605、Evidence #4F5FBF。 | 颜色只表示领域。 |
| 02 | PASS/CONDITIONAL/BLOCKED/UNVERIFIED 以图标、文字、颜色共同表达。 | 黑白打印仍可识别。 |
| 03 | 固定策略色：传统灰、最小失供 Evidence 蓝、碳韧 Carbon 青。 | 所有材料一致。 |
| 04 | 深色用于演示、浅色用于海报；数据色、线型、marker 不变。 | 两主题不改语义。 |
| 05 | 取消渐变、霓虹、重阴影和大圆角；采用 12 列网格。 | 工程控制台气质。 |
| 06 | 图题写结论，不写“平台介绍”“指标对比”。 | 3 秒读懂结论。 |
| 07 | 数字绑定单位：kWh、kgCO2、pu、%。 | 图表和口播一致。 |
| 08 | 每个碳数同时显示对象、普通 EENS Δ、epsilon、claim status。 | 无孤立“低碳”大数字。 |
| 09 | 图注含 run ID、数据等级、冻结日期、来源。 | 脱离 PPT 可追溯。 |
| 10 | 拓扑改为稳定正交馈线坐标，替换 spring layout。 | 三个时刻节点位置不变。 |
| 11 | 支路区分运行、常开、闭合、故障、修复、超限的线型/宽度。 | L6/L13/L27 与 T33/T34/T37 一眼可见。 |
| 12 | 节点填充仅表示带电；关键服务以绿色环，资源以小图标。 | 不混合关键性和带电状态。 |
| 13 | Vmin/负载率改上下双轨共享 x 轴，分别标 0.95 pu 和 100%。 | 不再有双 y 轴。 |
| 14 | Pareto：锚点菱形、候选圆、推荐外环、BLOCKED 红叉。 | 资格不依赖颜色。 |
| 15 | 主画面只放锚点和推荐候选，完整前沿进备份页。 | 首屏不超过两候选。 |
| 16 | MRV 改为输入→活动→因子→清单→gate→seal/verify 证据链。 | 每步可定位工件。 |
| 17 | 统一显示 17 FILES，淘汰旧材料“11 files”。 | 无文件数矛盾。 |
| 18 | CareTask 改任务×小时热图，固定 Tier/node/min kW/截止。 | 服务窗口可读。 |
| 19 | 成岛只显最危险岛；BLOCKED 显 NO_GFM，DEGRADED 显 P/Q/SOC 最弱约束。 | 状态带原因码。 |
| 20 | MC 图显样本数、29/30、scenario-0018 失败记录。 | 失败不被画成 0。 |
| 21 | 单图图例不超过 6 项，按 Service→Physics→Carbon→Evidence→状态排序。 | 图例与实体完全对应。 |
| 22 | 状态变化用 250–350 ms 缓动；BLOCKED 瞬切并显原因码。 | 录屏无闪烁。 |
| 23 | 小时游标联动拓扑、动作、任务、物理和 MRV action。 | 改一小时四处同步。 |
| 24 | 1920×1080 主结论≥32 px；1366×768≥28 px。 | 后排可读。 |
| 25 | 横轴最多 6 个刻度，关键点才贴数据标签。 | 无标签堆叠。 |
| 26 | 截图禁地址栏、用户名、绝对路径、终端、hover、spinner、宽表。 | 匿名审查通过。 |
| 27 | 固定 16:9 决策、4:3 证据、1:1 缩略图三种裁切。 | 不拉伸截图。 |
| 28 | 图标统一线性风格：hospital、activity、shield-check、database、alert、file-check。 | 20 px、同线宽。 |
| 29 | 首屏改结论带+三门+主拓扑+两候选条+证据入口。 | 10 秒说明推荐资格。 |
| 30 | A0 海报左 3 列问题，中 6 列主图，右 3 列 Pareto/MRV，底部证据带。 | 远看读问题，近看查来源。 |
| 31 | 每张图同名 JSON 记录源文件 SHA、导出脚本 hash、冻结日期。 | 版本可审计。 |

## 4. 7 张必须重生成的正式图

| 图 | 正式新图名 | 仅用 V08 冻结源 | 重绘与验收 |
|---|---|---|---|
| F01 | 01_暴雨内涝_三策略绝对量对照_V08 | v08_official/flood/strategy_comparison.csv；MRV carbon_reconciliation.csv | 用 EENS、关键 EENS、kgCO2、动作数四个绝对量小倍图。校验 EENS=10574.78/2223.11/4787.67 kWh；清单=38338.93/42934.51/41178.60 kgCO2；拒绝归一化柱。 |
| F02 | 02_MC30_稳健性与失败留痕_V08 | V08 release-archived 的 mc30_v04 results、summary、failures | 左 EENS、右 kgCO2 箱线图；标 29/30 solved；保留 scenario-0018、seed=20260822、失败 SHA 前 12 位。 |
| F03 | 03_暴雨碳韧协同_物理双轨校验_V08 | v08_official/flood/powerflow_carbon_resilient.csv | 上轨 loading，下轨 Vmin，标 T+7/T+13/T+23；24 点等于 CSV；最大 99.90%、最小 0.9703 pu；无双 y 轴。 |
| F04 | 04_暴雨T+0_故障隔离与联络恢复_V08 | v08_official/flood network_nodes、network_branches；MRV topology_state_carbon_resilient；actions_carbon_resilient | 稳定单线图；红 L6/L13/L27，青 T33/T34/T37，关键任务节点绿色环。验收 T+0=33 带电节点、0 孤岛、failed=[6,13,27]、closed=[33,34,37]。 |
| F05 | 05_服务锚点与受控预算候选_Pareto_V08 | V08 release-archived 的 pareto_flood_v07 manifest、points、frontier | 主图突出 epsilon=0% 与 6%。验收四点均 CareTask 4/4、24/24 h、physical_pass=True；6%=4815.40 kWh、41156.69 kgCO2；只写受控预算清单差异。 |
| F06 | 06_传统恢复_成岛门控时间线_V08 | v08_official/flood island_passport_hourly_traditional、summary_traditional | 三孤岛状态轨道，BLOCKED 必显 NO_GFM，DEGRADED 显 P/Q reserve 或 SOC endurance。验收 episode=3、rows=47、DEGRADED=40、BLOCKED=7；图例不出现无实体 READY。 |
| F07 | 07_碳韧协同_CareTask合同与电压门_V08 | v08_official/flood care_task_definitions、care_task_evaluation_carbon_resilient、summary | 4×24 热图+任务卡。验收 4/4、Tier1=2；ICU/手术门槛 0.97 pu，冷链/通信 0.95 pu；标题级写 E 类合成赛事模板。 |

通用验收：导出 1920×1080 PNG、SVG、PDF；图内含 V08/2026-08-22/source；50% 缩放、黑白打印、1366×768 实机投影均可读；图、申报书、视频的数字只取同一 factsheet。

## 5. 钥匙图：三门—证据链—推荐

图名为“为什么该候选有资格被推荐：服务、物理、证据三门”，应成为海报中心、答辩第 3 页和视频 0:50–1:25 的同一视觉锚点。

    暴雨内涝 L6/L13/L27
             ↓
    候选动作 T33/T34/T37
             ↓
    [服务门] CareTask 4/4
             ↓ 不通过→ BLOCKED:TASK_FAILURE
    [物理门] 24/24 h | Vmin 0.9703 pu | loading 99.90%
             ↓ 不通过→ BLOCKED:NO_GFM/OVERLIMIT
    [证据门] SEALED | PASS | 17 FILES
             ↓ 不通过→ UNVERIFIED
    受控服务预算候选 41,178.60 kgCO2
    普通 EENS 代价 +2,564.56 kWh vs 最小失供

三门按 Service、Physics、Evidence 着色；通过线保持中性，拦截线红色；右下固定 claim boundary：controlled service budget、same-service=false、E-SYNTHETIC。

## 6. 五分钟视频分镜

| 时间 | 画面 | 关键文字/动作 |
|---:|---|---|
| 0:00–0:20 | 灾害线稿与三条故障支路。 | “恢复更快，是否也更低碳？” |
| 0:20–0:50 | 传统先复电后核算，对照三门流程。 | “不把恢复电量直接认定为减排”。 |
| 0:50–1:25 | 钥匙图逐门展开。 | 服务先行、物理校验、证据封签。 |
| 1:25–2:05 | F04，T+0 至 T+7。 | L6/L13/L27 故障；T33/T34/T37 联络恢复。 |
| 2:05–2:35 | 两候选条+F05。 | 公开普通服务让步，不用权重隐藏。 |
| 2:35–3:00 | F02。 | 29/30 成功，scenario-0018 留痕。 |
| 3:00–3:30 | F03。 | 24/24 h、0.9703 pu、99.90%。 |
| 3:30–4:00 | F06 反例后返回推荐。 | “系统主动拦截假可行”。 |
| 4:00–4:25 | 六步 MRV 证据链。 | SEALED、PASS、17 FILES、非现场核证。 |
| 4:25–5:00 | 应用边界与结论。 | 供电价值与碳代价可计算、可比较、可复核。 |

视频规格：1920×1080、16:9、25/30 fps；每屏最多 2 个关键数字和 4 个 badge；同一小时游标驱动所有转场；不录入 spinner、宽表、终端、路径或现场长计算。

## 7. 截图、投影、图标、海报

**截图必留：** 主推荐 16:9、BLOCKED:NO_GFM 16:9、物理双轨 4:3、MRV 4:3、MC 4:3、海报 1:1。截图前核对场景、hour、run、17 FILES、kgCO2、E-SYNTHETIC、claim wording。

**投影：** 图题 20–28 px、badge 15–20 px、正文 14–18 px；横轴最多 6 个刻度；图 04 只常驻关键节点/故障端标签，其他节点交给放大版。

**图标：** hospital=服务、activity=物理、shield-check=证据、cloud/receipt=清单、octagon-x=BLOCKED。统一 20 px、同线宽，图标旁必须有文字。

**海报：** A0 横版 12 列；左 3 列问题和边界，中 6 列钥匙图/F04/F03，右 3 列 F05/F06/MRV；底部写 case33 SHA、CareTask definition SHA、因子 E 类、run ID、V08 ZIP hash 前 12 位。

## 8. 最终验收

- [ ] F01–F07 均来自 V08 冻结源，带来源 SHA。
- [ ] “kgCO2、E-SYNTHETIC、受控服务预算清单差异、17 FILES”在图、申报书、视频中完全一致。
- [ ] 10 秒内能看出推荐是否通过三门；3 分钟内能看到主推荐、服务代价、BLOCKED 反例、MRV 证据。
- [ ] 1920×1080、1366×768、黑白打印全部通过。
- [ ] 所有正式材料日期均冻结为 2026-08-22；无路径、用户名、学校或人员信息。

> GridRescue 的视觉任务不是把数字装饰得更像科技大屏，而是让评委能逐项审问：谁被保障、什么约束通过、普通服务付出什么代价、结论是否可在 V08 工件中复核。
