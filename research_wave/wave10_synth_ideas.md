# GridRescue Wave 10 创新总清单与 Top 12

**正式日期：2026-08-22**  
**范围：** 汇总并去重 `wave10_*.md` 全部 15 份报告（算法、验证、数据真实感、竞品、产品 UX、视觉、演示运维、产业、IP/专利、评委心理、论文路线、政策标准、范围评分、学术问答、月球想法）。本文件只做研究整合，不修改生产代码。

## 1. 评分口径

每项 1–5 分，5 为最好：

- **竞赛影响（I）**：30 秒记忆点、答辩区分度、评委关注度。
- **可信度（C）**：能否封住“少供电刷低碳、物理伪可行、数据夸大、统计挑样本”等质疑。
- **10 日可行性（F）**：能否复用 V08 资产并在十日内形成可验收交付。
- **证据契合（E）**：是否有现成 CSV/manifest/test/replay 可支撑，是否可进入 MRV。
- **演示价值（D）**：是否能稳定进入 3–5 分钟现场路径并可离线回放。

加权总分（/100）= `20 × (0.30I + 0.25C + 0.20F + 0.15E + 0.10D)`。分数用于竞赛决策，不代表论文长期价值。

## 2. 去重后的主创新库存（24 项）

| ID | 归并后的创新单元 | 合并来源（报告/原 ID） | I | C | F | E | D | 总分 | 10 日状态与验收物 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| INV-01 | **推荐资格工作台：服务—物理—证据三门 + 两候选决策条** | judge D02/D03/D10；product UX01/05/08；visual 钥匙图；competitor 三门叙事 | 5 | 5 | 5 | 5 | 5 | **100** | P0；首屏、三门卡、主推荐/服务锚点 vs 受控预算候选；10 秒可读。 |
| INV-02 | **GR-COMP-01 单一事实源与主张语义锁** | scope #1；judge D01/D21；product UX03；academic/validation 口径纪律 | 5 | 5 | 5 | 5 | 4 | **98** | P0；factsheet、数字字典、claim 文案、证据索引、UI/PPT/视频一致；same_service=false 自动禁用 strict wording。 |
| INV-03 | **C0 strict / C4 controlled 分轨 + G0–G5 gate waterfall** | validation #4–#5；algorithm 正式主张门；academic P0 风险 | 5 | 5 | 4 | 5 | 4 | **94** | P0；36 场景每策略 gate 计数、失败原因、eligible 分母与两套主表。 |
| INV-04 | **可见反例链：BLOCKED:NO_GFM/物理失败 + 篡改 FAIL + 返回合格候选** | judge D06/D07；product UX12–14；visual F06；validation X-I1/X-I2/X-M1 | 5 | 5 | 5 | 5 | 5 | **100** | P0；20–25 秒完成“拦截—原因—回主推荐”，篡改 activity/factor 后 verifier=FAIL。 |
| INV-05 | **FROZEN EVIDENCE / LIVE EXPLORATION 隔离与冻结 Pareto 预加载** | judge D05/D17/D18；product UX10；scope #5；demo OP-28/32 | 5 | 5 | 5 | 5 | 5 | **100** | P0；主路径零长计算，探索页明确 live；预生成 4 点 Pareto 与回放视频。 |
| INV-06 | **36 个 CRN 分层场景、dev/OOS、paired bootstrap 与完整失败分母** | validation #1–#11；algorithm A9/A2；paper D1/D3；scope #2/#3 | 5 | 5 | 3 | 5 | 3 | **86** | P0（统计批次）；3×3×4 catalog、SHA/seed、eligible n、Wilson/配对 CI、失败 replay。 |
| INV-07 | **CareTask-CVaR（CG-CVaR）生命线尾部风险预算选择** | algorithm A2；paper D1；scope O4 | 5 | 4 | 3 | 4 | 4 | **82** | P0/P1 取决于主批；`risk.py`、LifeLineLoss、alpha 敏感性、tail Care/RRT，失败不填零。 |
| INV-08 | **Risk-of-Claim MRV gate 与风险参数篡改矩阵** | algorithm A11；paper D2；validation #12、MT-01~08；IP #11 | 4 | 5 | 4 | 5 | 4 | **88** | P0；manifest 固化 alpha/catalog/tail/OOS，verifier 重算；篡改即失败。 |
| INV-09 | **联合天气—故障—修复压力 catalog（合成机制、相关冲击）** | algorithm A1/A9；data realism #8–#11；paper D3/D9；moonshots | 4 | 4 | 3 | 4 | 3 | **76** | P0/P1；三灾种×强度相关采样、zone shock、修复/可达性延迟，保留 E 类标签。 |
| INV-10 | **碳因子翻转阈值 / 最小后悔证书** | algorithm A5；paper D4/H5；IP #13；scope O5 | 4 | 4 | 5 | 4 | 4 | **84** | P0；固定 activity ledger，输出 threshold certificate CSV/JSON，阈值两侧可复算。 |
| INV-11 | **物理裕度 envelope（Vmin、loading、source adjustment）** | algorithm A8；paper D5；scope O7；validation #20 | 4 | 5 | 4 | 4 | 4 | **86** | P1；由 pass/fail 升级为安全余度，物理抽屉双轨图，收紧 cap 消融。 |
| INV-12 | **失败候选保留、可重放与稳健性卡** | algorithm A10/A12；validation #9/#10/E08；judge D20；IP #14 | 4 | 5 | 4 | 5 | 4 | **89** | P0；attempt/solved/failed、failure gate、scenario SHA、replay 一键入口；不删除失败。 |
| INV-13 | **30 秒 Gate 动画、presenter mode、快捷键与 reduced-motion** | product UX11/23；judge D23；visual 视频分镜；scope O2 | 4 | 4 | 5 | 4 | 5 | **87** | P0；不触发求解，可跳过/重播，点击≤8 次、≤180 秒。 |
| INV-14 | **共享小时游标 + 动作—影响—理由卡 + 稳定拓扑坐标** | judge D08/D09；product UX17/18/19；visual #10/#23；IP #16 | 4 | 4 | 3 | 4 | 5 | **78** | P1；改小时同步拓扑、任务、物理、MRV action；每条理由可追到字段。 |
| INV-15 | **Data Card / B-D-E-DERIVED 标签与 weather replay/synthetic 分流** | data realism #1–#5；policy D1–D5；product UX02/10；paper T1 | 4 | 5 | 5 | 5 | 4 | **94** | P0；所有输入有 data_id、等级、seed、许可证、hash、allowed/prohibited claims；混合结果自动失败。 |
| INV-16 | **天气→hazard→故障/修复→调度最小可信闭环** | data realism #6–#15；algorithm A9；industry #9/#10 | 4 | 4 | 3 | 4 | 3 | **74** | P1；冻结 72/168 h 天气窗口、QA、单调性、共同冲击与可达性延迟。 |
| INV-17 | **外部潮流最小对照（MATPOWER/pandapower）** | data realism #20；validation #23；paper D14 相关 | 3 | 5 | 3 | 4 | 2 | **70** | P1；3 工况电压/损耗 MAE、版本和容差可复算。 |
| INV-18 | **CareTask 机会约束/分层服务合同（Tier-1 严格，Tier-2 经验覆盖）** | algorithm A7；paper D7；IP #1–#4 | 4 | 4 | 3 | 4 | 3 | **74** | P1；Wilson CI、deadline/连续性/电压门；必须与 strict/controlled 标签分开。 |
| INV-19 | **CVaR-RRT 修复时间尾部** | algorithm A4；paper D6 | 4 | 4 | 3 | 3 | 3 | **70** | P1；首次连续完成时刻、deadline miss、tail RRT；依赖天气/修复 catalog。 |
| INV-20 | **服务—碳—风险三维 Pareto** | algorithm A6；paper D8；visual F05；scope O4 | 4 | 4 | 3 | 4 | 4 | **78** | P1；在既有 epsilon 点加 OOS risk，展示非支配前沿与失败点，依赖 INV-07。 |
| INV-21 | **两阶段非前视预案（reserve/tie/repair recourse）** | algorithm A3；paper D12；moonshots | 4 | 4 | 2 | 3 | 3 | **64** | P1+；只做小目录 perfect-information gap，禁止称全局随机规划最优。 |
| INV-22 | **受限对抗场景搜索与动作 LODO 归因** | algorithm A10/A12；paper D10/D11；IP #15 | 3 | 4 | 2 | 3 | 3 | **60** | P1/P2；beam/coordinate stress search、6 动作 leave-one-out，仅称模型反事实。 |
| INV-23 | **DER 无功能力闭环（P²+Q²≤S²、过压吸收、充电/弃光）** | validation #27；paper D14；academic Q17/Q23 | 4 | 5 | 2 | 3 | 2 | **65** | P2；审稿加分但超十日主路径，需设备级数据与回归。 |
| INV-24 | **多馈线/多规模 benchmark 与真实 sidecar 接入路线** | validation #23/#28；paper D13/D17；industry #2/#20 | 4 | 4 | 1 | 2 | 2 | **52** | P2/P3；33→69/123 节点、脱敏馈线/OMS 回放，作为赛后外部效度路线。 |

### 去重说明

- **“三门叙事、推荐资格、两候选条、八 Tab 收敛”**合并为 INV-01；不再把同一 UI 概念拆成多个“创新”。
- **“事实卡、数字字典、claim 文案、日期/单位统一”**合并为 INV-02；所有报告中的 46 passed、17 files、kgCO2、2026-08-22 统一从此处读取。
- **“36 场景、配对比较、bootstrap、失败分母、replay”**拆为 INV-06（统计设计）与 INV-12（可见失败/重放），避免把实验设计与演示产品混为一谈。
- **A1/A9/天气真实感/共同冲击/修复可达性**合并为 INV-09；历史天气冻结与 QA 属其数据前置，不另算算法。
- **MRV seal、证据链、tamper、风险参数重算**合并为 INV-08；“integrity-only、非第三方核证”是主张边界，不算独立创新。
- **GNN、RL、完整 Wasserstein DRO、MISOCP/AC-OPF、Carbon-SOC 绩效、实时 SCADA/OMS**均保留在报告中作为后续/裁掉项，未列入 Top 12。

## 3. Top 12（竞赛十日版本）

| 排名 | ID | 选择理由（简洁版） | 主要风险与控制 |
|---:|---|---|---|
| 1 | INV-01 | 直接回答评委第一问“谁有资格被推荐”，把现有能力收敛成一个可记忆的工作台；冲击、可信和演示均满分。 | UI 重构易蔓延；只做主推荐、两候选条和三门 deep-link，不扩第九个 Tab。 |
| 2 | INV-04 | BLOCKED:NO_GFM 与 tamper FAIL 是最强反例：证明系统会主动拦截假可行/被篡改结论，而不是只展示漂亮结果。 | 反例必须来自冻结工件；每次切换保留失败码和返回路径。 |
| 3 | INV-05 | Frozen/Live 隔离和预加载 Pareto 同时解决现场等待、数字混读和“现场重算冒充正式结果”三类质疑。 | 研究探索区不能覆盖 V08 只读工件；主路径超 1 秒即切回放。 |
| 4 | INV-02 | 一页事实源可一次性消灭 28/46 测试、11/17 files、kgCO2/kgCO2e、灾种和 claim 口径冲突，是最低成本的可信度杠杆。 | 所有 UI/PPT/视频/申报引用同一 JSON/CSV；改动需 hash 和审阅记录。 |
| 5 | INV-03 | strict 与 controlled 分轨让“低碳是否靠少供电”可被形式化回答；G0–G5 waterfall 给出失败分母和资格链。 | 36 场景未完成前不发布总体效应；C4 永不写成 strict。 |
| 6 | INV-15 | 数据等级、谱系、seed、许可证和合成/回放分流把“数字孪生”从标签变成可审计数据工程。 | 仅展示可用事实；E 类结果必须带边界，不冒充实测。 |
| 7 | INV-12 | 失败保留与 replay 直接回应“是否挑好案例”，并能接入现场稳健性卡、论文和 MRV。 | 失败不得按零填充；报告 attempts、eligible、原因码和 scenario SHA。 |
| 8 | INV-08 | Risk-of-Claim gate 把 alpha、tail catalog 和风险重算纳入 verifier，是方法和证据层的差异化结合。 | 风险参数需冻结、篡改测试全绿；称内部完整性，不称第三方核证。 |
| 9 | INV-13 | 30 秒 Gate 动画/快捷键把三门闭环变成评委记忆点，且不依赖求解器，现场收益高。 | 动画只播冻结状态；支持跳过、重播、reduced-motion 和静态截图。 |
| 10 | INV-06 | 36 个 CRN 场景和配对 bootstrap 是从 smoke-test 走向可辩护统计的唯一主路径。 | 十日资源紧；先完成 catalog、G0–G5、主终点和 CI，消融放后。 |
| 11 | INV-10 | 因子翻转阈值证书用固定 activity 账回答“换因子/边界会不会翻转推荐”，解释力强、实现小、可复算。 | 只称敏感性/最小后悔证书，不称真实未来碳价预测。 |
| 12 | INV-11 | 物理余度 envelope 将“通过/失败”升级为 Vmin/loading 安全距离，增强电力系统审稿可信度并适合双轨展示。 | 保留当前平衡三相、24 h 边界；不扩张为完整 AC-OPF/动态安全。 |

## 4. 十日落地顺序（防范围蔓延）

1. **D1：INV-02 + INV-15**：冻结 factsheet、Data Card、claim 字典、证据索引，先解决所有数字/等级冲突。  
2. **D2–D3：INV-01 + INV-03**：首屏三门、两候选、strict/controlled 标签与 G0–G5 结构。  
3. **D3–D4：INV-04 + INV-05 + INV-13**：主推荐/反例/tamper 三预设、冻结 Pareto、30 秒 Gate。  
4. **D4–D6：INV-06 + INV-12**：36 catalog、paired 表、失败分母、Wilson/Bootstrap、replay。  
5. **D6–D7：INV-08 + INV-10**：风险 MRV、篡改矩阵、因子翻转证书。  
6. **D7–D8：INV-11**：物理余度和双轨图；若主批不稳立即停。  
7. **D9–D10：**离线冷启动、双机接管、投影可读性、五分钟视频、Q&A 索引、干净环境回归；冻结 V08 只读，不再加模型。

## 5. 明确不进入本十日 Top 12 的方向

- 完整 GNN/RL、GNN surrogate/warm-start、安全 RL：缺标签、OOD/FNR、约束违约证据。
- 完整 Wasserstein DRO、真实概率校准、真实天气 API/OMS/SCADA 回放：数据治理和外部验证周期不匹配。
- 统一 MISOCP/AC-OPF、维修队联合 MIP：会重写稳定的调度—反馈链。
- Carbon-SOC 绩效优越、真实减排/碳资产/第三方核证、实时生产控制：当前证据边界不支持。
- 69/123 节点、多馈线、多园区规模化：保留为赛后外部效度，不替代当前 33 节点闭环。

## 6. 统一结论

Wave 10 的最大创新不是再堆一个算法名词，而是把已有恢复、CareTask、P/Q 反馈、成岛和 MRV 组织成**可失败、可追问、可复算的推荐资格链**。竞赛十日版本应优先交付：

> **先过服务门，再过物理门，最后过证据门；通过后才展示受控服务预算下的运行碳清单差异。**

所有正式材料继续固定：**2026-08-22、V08、46 passed、3 个 bundle×17 files、单位 kgCO2、E 类合成边界、same_service=false 时不写严格同服务减排。**
