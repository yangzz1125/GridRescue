# GridRescue 赛后论文路线图：从竞赛原型到可发表的方法研究

**正式日期：2026-08-22**  
**文档性质：赛后研究路线图与预注册式设计草案；不修改 V08 代码、参数、测试或正式 artifact。**

## 摘要结论

GridRescue V08 已经具备一个有价值、但需要准确定位的研究底座：它不是“提出全新配电网恢复求解器”，而是一个把 **CareTask 服务合同、P/Q 物理反馈、服务可比性 gate 与 kgCO2 MRV 证据包** 绑在同一推荐对象上的原型。V08 的三固定灾害场景、46 项软件回归和三个 MRV bundle 证明了代码闭环、可复算性和展示可用性；它们尚不足以证明跨灾种的统计效果、真实灾害概率校准、真实馈线外推、严格同服务降碳或全局最优恢复。

**赛后最小论文级扩展建议：**

> **CG-CVaR：面向极端天气合成压力集的“服务合同门控 + 尾部生命线风险”恢复策略选择框架。**
>
> 在一组预先冻结、共同随机数（CRN）的灾害场景中，先以现有词典序服务锚点、CareTask 与 P/Q 物理反馈生成候选恢复策略，再用受限的风险预算从有限候选目录中选择预案参数（如普通服务预算 `epsilon`、储能应急预留比例、碳/服务候选类型）。以 `CareTask-CVaR` 为主终点、严格/受控服务比较分轨、MRV 风险证据包为验证条件。

它的目标不是把 CVaR 作为一个事后图表，而是让 **风险预算改变被选中的、可执行且通过多层 gate 的预案参数**。这条路线可复用现有 `dispatch.py`、`pareto.py`、`care.py`、`pipeline.py`、`experiments.py` 与 `mrv.py` 的大部分资产，工程量明显低于两阶段随机 MISOCP、AC-OPF 联合恢复或 GNN/RL，同时能形成一篇方法、实验和可复现性三部分都完整的应用型论文。

---

## 1. V08 的真实研究资产与不可越过的边界

### 1.1 已可复用的研究资产

| 层次 | V08 已有实现/冻结事实 | 对赛后论文的价值 |
|---|---|---|
| 网络与灾害 | 官方 MATPOWER `case33bw`；暴雨、台风、极端高温三个 24 h 合成场景；多支路故障、修复时长、PV 降额、碳倍率与抢修距离。 | 可作为可重放的概念验证网络与情景接口。 |
| 恢复与调度 | 传统顺序、最小失供、碳韧协同三条恢复链；节点/岛屿层的 PV、BESS、柴油和上级电网连续调度。 | 已有可比较基线与 CVXPY 调度内核。 |
| 服务语义 | `CareTask` 已表达节点、最低功率、时窗、deadline、连续时长、依赖与任务电压阈值；任务最低功率进入硬约束，后续由潮流复核。 | 可形成区别于“关键负荷权重”的清晰方法贡献。 |
| 物理闭环 | 平衡三相径向 P/Q 前推回代、节点/支路/组件导出、无源岛阻断、损耗与容量回灌。 | 可将候选筛选建立在物理反馈而不是裸优化目标上。 |
| 可比性 | 医院→其他关键→普通负荷词典序服务锚点；`epsilon` 显式表示普通服务预算；失败 Pareto 点保留。 | 可避免“少供电导致低碳”的构念混淆。 |
| 证据/MRV | 因子快照、逐时 activity ledger、inventory、对账、动作 hash chain、manifest、seal、独立 verifier。 | 可作为可复现计算实验的证据工程贡献。 |
| 基线可靠性 | V08 `pytest -q` 为 46 passed；三个固定场景各有 17 文件通过 verifier；MC30 每策略 29/30 完成，失败场景保留且可 replay。 | 可作为后续版本的回归锚点与复现纪律，而不是性能结论。 |

### 1.2 V08 明确不支撑的结论

1. 三个 V08 bundle 都是 `same_service_pass=false`，当前主张类别为 `controlled_service_budget_inventory_difference`；因此 V08 默认 C/B 数值不属于严格同服务减排证据。
2. MC30 是离线压力烟雾测试，尚未形成预注册、分层、配对的策略效应估计；不应作为总体显著性结论。
3. 场景、DER 布置、关键负荷、热限与因子中存在 E 类合成工程假设；不应外推成真实城市、真实医院或真实馈线结果。
4. `seal` 和 verifier 证明文件完整性、引用关系和内部方程复算，不等价于现场计量、可信时间戳、不可篡改存储或第三方核证。
5. 恢复顺序、联络选择仍含启发式；P/Q 反馈闭环不等价于统一 MISOCP/AC-OPF 的全局最优。
6. 当前固定 `time_step_h=1.0`；逐设备无功能力、保护配合、短路、频率、谐波、院内 UPS 与真实 GFM/黑启动资产证据均尚未闭合。

这不是论文的缺陷清单，而是研究问题的边界。论文应把“推荐资格由多层证据决定”作为贡献，把上表限制写成可检验的 external-validity boundary。

---

## 2. 推荐主论文：CG-CVaR 的研究问题、对象与贡献

### 2.1 论文题目候选

- **中文（首选）**：**面向极端天气配电网恢复的服务合同门控尾部风险优化与可审计证据包**
- **英文（首选）**：**Contract-Gated Tail-Risk-Aware Distribution Restoration with Auditable Evidence Packages**
- **系统侧备选**：**GridRescue: Evidence-Bearing, Care-Contract-Gated Restoration under Synthetic Extreme-Weather Stress Catalogs**

### 2.2 主研究问题（RQ）

**RQ1：** 在共同的极端天气压力场景中，能否以 CareTask 服务合同和物理可行性为硬 gate，选择在尾部生命线损失上更稳健的恢复预案，而不是仅优化平均 EENS 或单场景碳清单？

**RQ2：** 当普通服务让步被公开为 `epsilon` 预算时，严格同服务候选与受控服务取舍候选的碳—韧性—尾部风险关系是否不同？这种差异能否由资格门而不是结果叙事来避免误解？

**RQ3：** 将风险定义、场景目录、tail set、活动账和结果表纳入 MRV verifier，是否能够让风险结论被独立重算与篡改检测，而不是停留在不可追溯的图表？

### 2.3 方法对象与最小形式化

设冻结场景目录为 \(\mathcal S=\mathcal S_{dev}\cup\mathcal S_{test}\)，其中开发集与外样本集的 scenario ID、seed 和 SHA 不重叠。一个候选预案 \(p\in\mathcal P\) 至少由下列可解释参数构成：

\[
p=(\epsilon,\rho^{reserve}, q),
\]

其中 \(\epsilon\) 为普通服务公开预算，\(\rho^{reserve}\) 为 BESS 应急预留/最低 SOC 参数，\(q\) 是已有恢复计划族或严格碳候选标识。对于每一个 \((p,s)\)，现有调度—P/Q 反馈链生成结果 \(x_{p,s}\)，随后计算：

\[
G(p,s)=G_0\wedge G_1\wedge G_2\wedge G_3\wedge G_4\wedge G_5,
\]

其中 G0–G5 分别对应输入冻结、求解完成、物理通过、CareTask 通过、服务可比和 MRV 复核。未通过者保留在可靠性分母中，但不混入性能均值。

定义场景级生命线损失：

\[
L_{p,s}=1000E_{H,p,s}+100E_{K,p,s}+500M_{p,s}+RRT_{p,s},
\]

其中 \(E_H\) 与 \(E_K\) 分别为医院和其他关键服务 EENS，\(M\) 为 CareTask deadline miss 数，\(RRT\) 为恢复时间指标。权重仅用于风险排序；论文必须同时报告未加权的医院/关键 EENS、任务完成率、deadline miss 与总 EENS。

在通过规定 gate 的外样本上，经验 CVaR 定义为：

\[
\operatorname{CVaR}_{\alpha}(L_p)=
\operatorname{mean}\{\text{largest }\lceil(1-\alpha)|S|\rceil\text{ values of }L_{p,s}\}.
\]

主分析建议固定 \(\alpha=0.80\)，\(0.90\) 仅作敏感性。若外样本数为 36，\(\alpha=0.80\) 有 8 个 tail 样本，仍应将结果称为“冻结合成压力集的经验尾部比较”；\(0.95\) 在此样本规模下不进入主结论。

### 2.4 论文可写的四项贡献

1. **服务合同门控的尾部风险对象。** 将 ICU/急诊、应急手术、冷链和通信的功率—时窗—连续性—deadline—电压合同置于 CVaR 风险评价之前；只有通过服务合同和物理 gate 的候选才进入可推荐集合。
2. **风险感知的有限政策目录选择。** 不宣称重造全局随机恢复优化器，而是在预注册、可解释的 \((\epsilon,\rho^{reserve},q)\) 目录中，以尾部生命线损失约束/排序选择预案，并用独立 OOS catalog 评价。
3. **严格与受控比较分轨。** 将 `epsilon=0` 的严格同服务 C0 与固定 `epsilon=4%` 的受控 C4 分开统计、分表、分图和分 claim；不允许 C4 借用 same-service 语言。
4. **可重算风险证据包。** 把 alpha、损失公式版本、场景 catalog SHA、tail scenario ID、合格样本数、bootstrap manifest 和策略 activity/inventory 引用写入 MRV evidence，使风险结论具有可核对的 provenance。

### 2.5 核心假设（预注册写法）

| ID | 假设 | 主检验 | 结论资格 |
|---|---|---|---|
| H1 | 在外样本严格服务合同下，CG-CVaR 选择的预案相对风险中性目录选择具有更低或不更高的 `CVaR_0.80(L)`。 | 分层配对 bootstrap 的 CVaR 差与 tail 逐场景表。 | 两侧均通过 G0–G5、报告 eligible n。 |
| H2 | H1 的改善不以医院/关键 CareTask 降级或物理裕度恶化为代价。 | Hospital/critical EENS、task pass、deadline miss、minV、max loading guardrail。 | 任何 guardrail 违规即不宣称风险改善。 |
| H3 | 相对最低碳候选，CG-CVaR 会呈现可量化的平均 carbon 或普通服务代价，且这种保守性代价可解释。 | `kgCO2`、normal EENS、BESS reserve、tail 任务指标。 | 只在同一比较层内解释。 |
| H4 | 风险 MRV verifier 能检出 alpha、catalog、tail loss、权重或结果引用的篡改。 | 篡改矩阵的 expected-detected rate。 | 证明内部完整性与复算，不声称第三方保证。 |
| H5（探索性） | 碳因子翻转阈值证书能够预报固定 activity 账下的推荐排序翻转。 | 阈值两侧离散重算一致性。 | 仅是因子敏感性证书，不是未来真实碳价预测。 |

---

## 3. 最小论文级实施范围（赛后可完成）

### 3.1 最小但充分的实验规模

| 元素 | 最小建议 | 原因 |
|---|---:|---|
| 开发场景 | 36 = 3 灾种 × 3 强度 × 4 复本 | 复用 Wave 10 的平衡 CRN 设计，用于候选目录与阈值选择。 |
| 外样本场景 | 36 = 同样 3×3×4，但 seed/ID 与开发集不重叠 | 让调参与报告分离；可称 OOS synthetic catalog。 |
| 主 alpha | 0.80 | 36 个外样本有 8 个 tail 观测，适合最小经验尾部分析。 |
| 敏感性 alpha | 0.70、0.90 | 不把 0.95 写成稳定结论。 |
| 候选目录 | `epsilon={0,0.01,0.02,0.04}` × `reserve={0.12,0.20,0.30,0.40}` × 2 个计划/目标变体，最多 32 个 | 小而可解释，便于全面验证与消融。 |
| 主比较 | risk-neutral 目录选择 vs CG-CVaR 目录选择；另报 C0 vs B strict、C4 vs B controlled | 同时回答风险效应与碳/服务语义。 |
| 重采样 | 20,000 次、按 9 个 weather×severity strata 成对重采样、seed 20260822 | 与 Wave 10 验证契约一致。 |

**若计算预算有限：** 保持 36 个 OOS 场景和 `alpha=0.80`，减少候选目录的 `epsilon/reserve` 网格；不要为了增加算法名词而牺牲 OOS 分离、paired SHA 或失败保留。

### 3.2 新增的最小工程模块

| 模块 | 最小职责 | 需复用的现有资产 |
|---|---|---|
| `risk.py` | 场景级 LifeLineLoss、VaR/CVaR、tail set、risk feasibility 与 known-array 单测。 | `care.py`、`metrics.py`、`experiments.py`。 |
| `weather_catalog.py` | 生成/读取冻结的 3×3×4 场景 JSON、seed、regime、SHA、dev/test split。 | `scenarios.py`、`experiments.py` 的序列化与 replay。 |
| `risk_policy.py` | 枚举 \((\epsilon, reserve, q)\) 目录，开发集选择策略，外样本只评估。 | `pareto.py`、`dispatch.py`、`pipeline.py`。 |
| 风险结果导出 | `risk_results.csv`、`policy_selection.json`、`risk_frontier.csv` 与 failures。 | 现有 artifact 结构。 |
| 风险 MRV 扩展 | manifest 固化 risk spec、catalog hash、tail IDs、OOS split、结果/图表 hash；verifier 重算。 | `mrv.py`。 |
| 统计脚本 | 分层 paired bootstrap、sign-flip、Wilson/McNemar、表图 source index。 | `experiments.py` 的 bootstrap 与失败 schema。 |

### 3.3 不要在最小论文里同时做的事

- 不把离散修复排序、开关状态、AC-OPF、随机故障、储能来源碳、保护与频率全部塞进一个 MISOCP。
- 不用无真实标签的 GNN/RL/故障预测为论文贴 AI 标签。
- 不把天气目录称为真实概率分布、WDRO 真实最坏情形或气候风险预测。
- 不把 risk MRV 的 hash/复算能力包装成第三方碳核证。
- 不在严格比较失败时回退为“总体减排”；严格与 controlled 必须始终分轨。

---

## 4. 基线、对照与实验设计

### 4.1 必备基线

| 编号 | 基线/候选 | 用途 | 公平性要求 |
|---|---|---|---|
| A | 传统顺序恢复 | 工程规则基线，展示启发式恢复代价。 | 与其他方法共享同一 scenario JSON、网络、资源、因子。 |
| B | 最小失供恢复 | 韧性服务参考与现有对照。 | 作为 C0/C4 的配对参考；不能被标签化为“低碳失败者”。 |
| C0 | `epsilon=0` 的服务合同碳候选 | 唯一 strict same-service 碳比较候选。 | 医院、关键、普通服务合同与 B 一致，全部过 G0–G5。 |
| C4 | 预注册 `epsilon=4%` 的碳候选 | 受控服务预算下的透明取舍。 | 只与 B 做 controlled 分析，显式列普通 EENS 预算。 |
| EV-catalog | 以开发集平均 \(L\) 或平均 EENS 选择的候选目录策略 | 风险中性策略选择基线。 | 与 CG-CVaR 用同一 policy catalog、同一调参预算。 |
| CG-CVaR | 以开发集 CVaR 及 guardrail 选择的候选目录策略 | 主方法。 | 选择规则、alpha、loss 权重和 tie-break 在看 OOS 前冻结。 |
| Carbon-min（可选） | 仅在满足同层服务合同后最小 inventory 的目录选择 | 展示纯碳偏好与风险代价。 | 不通过服务/物理/Care gate 的候选不得成为基线结果。 |

### 4.2 运行纪律

1. 所有方法在同一 `scenario_id` 读取同一 scenario/network/Care/factor/config input SHA；执行顺序轮换但不重新抽样。
2. 开发集只用于冻结候选目录、参数和 selection rule；外样本禁止改 alpha、损失权重、epsilon 或 reserve 网格。
3. 每个 run 完整保存 G0–G5、failure phase/reason、wall time、manifest 和 replay 路径。
4. 有一方失败时：该场景计入 reliability/ITT 分母；从相应 strict 或 controlled paired effect 中排除，并在排除表保留原因；不得填 0。
5. 每个比较明确符号约定：`delta = candidate − reference`；`ΔkgCO2<0` 为 candidate inventory 较低，`ΔEENS>0` 为 candidate 额外失供。

### 4.3 主要终点和统计方法

| 类别 | 终点 | 主统计 |
|---|---|---|
| 尾部韧性 | `CVaR_0.80(L)`、tail hospital/critical EENS、tail deadline miss、tail RRT | 场景配对差、分层 paired percentile bootstrap 95% CI。 |
| 服务 guardrail | hospital EENS、critical EENS、CareTask pass、deadline miss、连续性与依赖失败 | 全量 gate count、Wilson CI；同场景成功差用 McNemar。 |
| 物理 guardrail | 24/24 physical pass、min voltage、max loading、source adjustment、feedback iteration | 合格率与裕度分布；禁止只报告成功样本。 |
| 碳/服务取舍 | `kgCO2` inventory、normal EENS、served kWh、柴油与购电分解 | strict/C0 与 controlled/C4 分开做 paired CI。 |
| 稳定性 | factor flip、alpha、PV、repair、SOC、epsilon 的 OAT | 预注册 tornado 与 threshold；记录 gate 失败。 |
| 可信性 | verifier tamper detection、replay consistency、图源 hash 完整性 | pass/fail matrix 与错误路径。 |

主效应报告：绝对差、相对差（分母为零则 `NA`）、配对均值、中位数、`d_z`、wins/ties/losses、95% CI、`n_eligible/N_total`。辅助 p 值可使用 100,000 次 sign-flip permutation 和 Holm 校正，但不能用单一 p 值取代效应量和资格分母。

---

## 5. 论文需要的结果表、附录表与图

### 5.1 正文主表（建议 5–6 张）

| 表 | 标题与必须字段 | 读者应得到的结论 |
|---|---|---|
| T1 | **模型与场景目录**：网络、24 h、灾种×强度×复本、dev/test split、CRN、输入 SHA、E 类边界。 | 研究对象、抽样与外样本分离是否清楚。 |
| T2 | **方法与基线对照**：A/B/C0/C4/EV/CG-CVaR 的决策变量、是否风险感知、是否 strict、是否 Care/PQ/MRV gate。 | 所有方法是否真的在可比规则下运行。 |
| T3 | **OOS 严格服务主结果**：B、C0、EV、CG-CVaR 的 CVaR、医院/关键 EENS、Care、minV/loading、kgCO2、eligible n、CI。 | 尾部改善是否真实留在 strict 或明确合同层内。 |
| T4 | **OOS 受控服务取舍**：C4/CG-CVaR 的 `epsilon`、normal EENS、kgCO2、CVaR、任务/物理 gate。 | 普通服务代价是否完整披露，避免伪减排。 |
| T5 | **可靠性与失败 waterfall**：N attempts、G0–G5 通过数、failure gate、可 replay 的典型失败。 | 方法没有挑成功样本，也没有把失败当零。 |
| T6 | **消融与敏感性**：AB-1–AB-4、alpha、PV、因子、repair、SOC；结果含 CI 与 failure threshold。 | 效果来自哪个机制、结论在何种扰动下变化。 |

### 5.2 正文主图（建议 6 张）

1. **Fig. 1：CG-CVaR 架构与资格流程。** 场景目录 → policy catalog → 调度/恢复 → P/Q feedback → CareTask → strict/controlled gate → risk MRV package；失败箭头必须通向 audit evidence。
2. **Fig. 2：场景设计与 gate waterfall。** 3×3×4 dev/OOS 分层、A/B/C0/C4/EV/CG-CVaR 的 G0–G5 漏斗。
3. **Fig. 3：OOS 尾部风险配对图。** EV vs CG-CVaR 的每个场景 LifeLineLoss、tail 标记、weather facet、bootstrap CI 和 eligible n。
4. **Fig. 4：严格与受控分轨 Pareto。** C0 与 C4 使用不同形状/颜色；显示失败点、normal EENS 预算、物理/Care 状态。
5. **Fig. 5：风险代价解释图。** BESS reserve、柴油/购电、normal EENS、Care deadline/RRT 的案例时间线；至少包含一个“平均碳较低但 tail 更差”的反例。
6. **Fig. 6：风险证据与篡改检测。** catalog hash→loss rows→tail set→activity/inventory→manifest/verifier，列出 alpha/catalog/loss/weight 篡改是否被检出。

### 5.3 附录必须包含

- 全量 `experiment_runs.csv`、`paired_deltas.csv`、`risk_results.csv`、`risk_frontier.csv`、`pareto_failures.csv` 的 schema；
- 每个失败/排除的 scenario ID、SHA、gate、replay 路径；
- 所有固定权重、alpha、候选目录、bootstrap seed、package 版本和硬件/solver 版本；
- case33bw 基准回归（3715 kW / 2300 kvar、202.67713 kW loss、0.91309048 pu 基准 Vmin）与 V08 46 passed 的复现记录；
- 至少一个成功 run 和一个失败 run 的 MRV verifier 输出；
- 代码/数据许可证、合成假设登记与 artifact hash。

---

## 6. 消融、敏感性、反例与威胁有效性

### 6.1 必做消融

| ID | 变化 | 回答的问题 | 预期的正确解释 |
|---|---|---|---|
| AB-1 | 去除 CVaR，改为 EV-catalog 选择 | 尾部改善是否来自风险选择而不是偶然目录差异。 | 若无差异，诚实报告主方法未在该 catalog 形成优势。 |
| AB-2 | CareTask 硬合同降为类别权重 | 任务合同是否阻止“类别恢复好看、任务失败”的情况。 | 重点报告 deadline/连续性/电压反例。 |
| AB-3 | 移除 P/Q feedback，仅事后一次检查 | 物理回灌是否淘汰表面优的候选。 | 被淘汰的低碳候选是反例，不是性能宣传。 |
| AB-4 | 使用常数碳因子代替时变因子 | 碳时间信号是否实质改变策略选择。 | 只解释合成因子条件下的差异。 |
| AB-5（可选） | reserve 网格固定为单值 | 预留这一可操作参数是否贡献尾部韧性。 | 同时报平均碳/服务代价。 |

### 6.2 预注册 OAT 敏感性

- PV derating：中心值 × 0.50/0.75/1.00/1.25（截断至 [0,1]）；
- grid carbon multiplier：×0.85/0.95/1.00/1.10/1.25；
- repair duration：×0.75/1.00/1.25/1.50；
- BESS initial SOC 或 reserve：20/40/60/80/100% 或预注册的 reserve grid；
- `epsilon`：0/1/2/4/6/8/10%；
- 因子：-20/-10/0/+10/+20%；
- alpha：0.70/0.80/0.90。

所有敏感性点必须重新写入 config/input hash，并同时报告性能变化与 G0–G5 失败阈值。禁止只画有利方向的 tornado 图。

### 6.3 必须保留的反例

1. 无 GFM/黑启动供源的孤岛：必须硬 BLOCKED，不得形成虚拟 slack 供电。
2. node 17 同时存在 25 kW 手术与 12 kW 冷链任务：30 kW 不足、37 kW 才满足并发合同。
3. ICU 电压 0.96 pu：即便系统整体潮流“可行”，任务电压合同仍需失败。
4. 碳最低但 tail Care 差的候选：展示风险预算为何排除它。
5. 严格服务不等价候选：必须被标为 controlled/inventory-only，而不是 strict reduction。
6. 完整重封存攻击：明确当前 proof 是 integrity-only；拥有写权限者重新生成全部证据仍是系统外威胁。

### 6.4 Threats to validity（论文必须单列）

| 类型 | 风险 | 缓解与诚实写法 |
|---|---|---|
| Construct validity | LifeLineLoss 的 1000/100/500 权重带有规范性。 | 报告原始任务、EENS、RRT；alpha/权重 OAT；不把加权分数当唯一真实效用。 |
| Construct validity | `epsilon` 是普通服务预算，不是社会公平性的完整代理。 | 分开报告服务类别与普通负荷；公平扩展留作后续，不将其写成 equity proof。 |
| Internal validity | 物理反馈、Care 与风险选择交织，难以归因。 | AB-1–AB-4、同一 CRN、同一 policy catalog、完整失败表。 |
| Statistical conclusion | 小样本 tail CVaR 易不稳定；失败导致 eligible n 缩小。 | 主 alpha=0.80、报告 tail count、stratified bootstrap、全量 reliability 分母；0.90 仅敏感性。 |
| External validity | case33bw、合成 DER/任务/因子/天气不代表真实馈线。 | 明确概念验证；赛后增加 69/123 节点和脱敏馈线 sidecar，仍不直接泛化。 |
| Model validity | 平衡三相模型未覆盖保护、短路、频率、谐波、动态成岛。 | 用“P/Q restoration feasibility screen”而非全电磁暂态安全；未来接入资产/保护验证。 |
| Algorithmic validity | policy catalog 和启发式恢复顺序可能限制最优性。 | 与“给定候选目录内的风险选择”对齐，不宣称全球最优；报告目录覆盖与运行时。 |
| Data/MRV validity | 合成因子与本地 hash seal 不是计量/核证。 | 用 E 类和 integrity-only 标签；不形成碳资产、真实减排或认证主张。 |
| Researcher degrees of freedom | 看过 OOS 后调整 alpha、目录或 epsilon 会造成选择偏差。 | dev/test split、analysis plan、script/hash、冻结日期和变更日志。 |
| Reproducibility | solver 版本与数值容差可能改变边界可行点。 | 锁依赖、环境、solver、seed、容差；保存 raw run、manifest、replay 与 tests。 |

---

## 7. 20 条赛后研究方向与优先级

| ID | 方向 | 研究价值 | 最小交付 | 发表潜力 | 优先级 |
|---|---|---|---|---|---|
| D1 | **CareTask-CVaR 有限目录选择（CG-CVaR）** | 将尾部生命线损失纳入可执行预案选择。 | `risk.py`、36+36 catalog、OOS 表图。 | 高；主论文。 | P0 |
| D2 | 风险 MRV gate | 将 alpha、tail set、catalog 与 loss 变成可重算证据。 | manifest/verifier/tamper tests。 | 中高；与 D1 绑定。 | P0 |
| D3 | 联合天气压力 catalog | 用相关规则化扰动替代独立故障随机。 | 3×3×4 dev/test catalog、相关性登记。 | 高；D1 必需。 | P0 |
| D4 | 碳因子翻转阈值证书 | 由固定 activity 账计算排序何时翻转。 | certificate CSV/JSON、阈值两侧复算。 | 中高；强解释性副贡献。 | P0 |
| D5 | 物理余度 envelope | 从 pass/fail 变为电压/热限安全余度。 | margin 指标、收紧 cap 消融。 | 中高。 | P1 |
| D6 | CVaR-RRT（修复时间尾部） | 关注恢复速度的高损失尾部。 | `CareTask` 首次连续完成时刻、repair tail。 | 中高。 | P1 |
| D7 | 机会约束 CareTask | tier-1 严格、tier-2 样本通过率约束。 | finite-sample chance gate、Wilson CI。 | 中。 | P1 |
| D8 | 三维 service-carbon-risk Pareto | 将 C0/C4 与风险投影统一展示。 | risk-augmented Pareto/frontier。 | 中；需 D1。 | P1 |
| D9 | 轻量 WDRO-lite 压力复验 | 对相关有限压力集做 worst/regret 检查。 | 固定 stress set、regret 表。 | 中；限于合成鲁棒性。 | P1 |
| D10 | 对抗式受限场景搜索 | 在 catalog 支持域内寻找最差 Care/物理案例。 | beam/coordinate stress search、replay。 | 中。 | P1 |
| D11 | 动作 LODO 风险归因 | 解释某联络/修复动作的模型内边际贡献。 | 6 个动作 leave-one-out、风险 delta。 | 中低；仅模型反事实。 | P1 |
| D12 | 两阶段非前视预案 | 在灾前固定 reserve/tie policy，灾后 recourse。 | 小目录预案 + perfect-information gap。 | 高，但工程量增加。 | P1+ |
| D13 | 多馈线规模与分解 | 33→69→123 节点的运行时、内存、可行率验证。 | 实测 benchmark CSV、P50/P95。 | 高；外部效度增强。 | P2 |
| D14 | DER `P^2+Q^2≤S^2` 与无功闭环 | 弥补无功能力、过压与弃光的物理缺口。 | 设备级约束、物理回归。 | 高；电力系统审稿加分。 | P2 |
| D15 | 维修队路径/开关—恢复联合优化 | 将当前启发式修复升级为决策变量。 | 小规模 MIP/分解对照。 | 高，但会改变论文重心。 | P2 |
| D16 | Carbon-SOC 来源账本 | 处理储能初末 SOC、公平边界与充电损耗。 | source buckets、terminal SOC contract。 | 中高；需严谨数据边界。 | P2 |
| D17 | 真实天气/OMS 事件回放 | 提供真实故障时间线、资产和因子验证。 | 脱敏 sidecar 与数据治理协议。 | 很高；依赖合作数据。 | P3 |
| D18 | 图 surrogate/GNN 筛选器 | 加速候选筛选而不替代物理 gate。 | topology holdout FNR/recall。 | 中；需大量标签。 | P3 |
| D19 | 安全 RL / GNN-RL | 学习策略或 warm start。 | violation/OOD/sample-cost 评测。 | 不确定；当前不建议。 | CUT |
| D20 | 统一 MISOCP/AC-OPF 恢复 | 提升优化理论完整性。 | feasible optimum/runtime/gap。 | 高但成本极高。 | CUT（另起项目） |

**推荐资源序列：** 先完成 D1–D4，形成一篇完整的应用方法论文；若有额外 4–6 周，追加 D5 或 D6；若获得真实数据/合作单位，再将 D13/D14/D17 发展为第二篇电力系统论文。D19/D20 不应挤占第一篇论文的时间。

---

## 8. 哪些内容是“竞赛强项”，哪些可写进论文

| 内容/主张 | 竞赛展示价值 | 论文中可用性 | 正确处理 |
|---|---|---|---|
| 服务合同—物理—MRV 三门叙事 | 很高，易被评委记住。 | **可发表**，但需形式化、对照与 OOS 实验。 | 作为系统/方法学贡献，而非营销口号。 |
| CareTask 的任务级约束和电压复核 | 高。 | **可发表**。 | 与类别权重消融和失败案例一起报告。 |
| `epsilon` 公开普通服务预算 | 高。 | **可发表**，但 epsilon 方法本身不是新算法。 | 贡献在可比性治理语义和 gate。 |
| P/Q feedback、无源岛阻断、失败保留 | 高。 | **可发表**为约束闭环设计的一部分。 | 不宣称完整 AC-OPF 或动态安全验证。 |
| activity/inventory/action hash/verifier | 高。 | **可发表**为 reproducibility/evidence engineering。 | 只称 integrity/recomputation，不称第三方核证。 |
| V08 三场景的碳清单差 | 高。 | **仅概念演示**。 | 默认 C/B 属 controlled trade-off，不可写 strict reduction。 |
| MC30 29/30 和 4.83% 之类描述统计 | 中。 | **仅 smoke/replay 基线**。 | 不作主效应或显著性证据。 |
| 8 页 Streamlit 数字孪生 UI | 高。 | 低到中。 | 放系统演示/补充材料，不作为学术创新主体。 |
| “AI 数字孪生”标签 | 高但风险也高。 | 不宜作为当前论文主张。 | 论文写 optimization/evidence digital twin，不假称学习模型。 |
| 真实减排、真实医院、真实配网、实时控制 | 竞赛中也应避免。 | **不可用**。 | 需真实数据、计量、治理与现场验证后再讨论。 |
| Carbon-SOC 绩效优越 | 视觉上诱人。 | 当前不可用。 | 另立来源账本与终端 SOC 合同研究。 |
| GNN/RL/MISOCP 全局最优 | 容易制造“技术感”。 | 当前不可用。 | 作为 future work；不进入主实验。 |

---

## 9. 目标发表渠道：按论文类型匹配，而不是先追最高影响因子

> 下列为**渠道类别与匹配策略**，不是针对某一期 deadline 的投稿承诺；提交前再核对当期 scope、格式、数据/代码政策与开放获取要求。

| 论文成熟度 | 渠道类别 | 典型目标范围 | GridRescue 应强调的内容 |
|---|---|---|---|
| 赛后 3–6 个月，方法原型 + 36/36 OOS | 电力系统应用/可持续配电网期刊 | distribution restoration、resilience、DER dispatch、energy systems application。 | CG-CVaR、CareTask、P/Q gate、OOS catalog、严格/受控分轨。 |
| 方法与系统闭环更成熟 | 智能电网/电力系统高标准期刊 | restoration optimization、resilience planning、microgrid/distribution operations。 | 更强基线、多节点、设备无功、运行时和严谨统计。 |
| 证据工程和数字孪生更突出 | energy informatics / digital twin / sustainable systems 交叉期刊 | auditable digital twins、decision support、MRV/reproducibility。 | recommendation evidence package、claim governance、verifier、human-auditable workflow。 |
| 先获得同行反馈 | IEEE PES/智能电网/能源信息学会议或 workshop | 短文、demo、方法预告、可复现 benchmark。 | 冻结 catalog、风险 gate 与失败反例；不抢先承诺大规模现场结论。 |
| 有真实合作数据后 | 高影响 energy / power systems 应用期刊 | real feeder/event replay、asset constraints、field-informed resilience。 | D13/D14/D17，真实数据治理与外部验证。 |

**实务建议：** 第一篇更适合“应用型电力系统/智能电网方法论文”，不要把第一稿定位为纯优化理论顶刊。若想冲刺更高标准渠道，最低补强项是：多网络规模证据、更多 OOS 场景、无功能力/设备约束、严格基线复现和一份脱敏真实数据 sidecar。

---

## 10. 赛后 12 周执行表

| 周 | 目标 | 关键产物 | Go/No-Go 门 |
|---:|---|---|---|
| 1 | 冻结 V08、建论文分支与注册表 | `paper_protocol.md`、依赖锁、V08 SHA、分析计划。 | V08 artifact 保持只读，46 passed 可重现。 |
| 2 | 建 dev/OOS weather catalog | 72 个 JSON、catalog CSV、seed/SHA、split manifest。 | 目录可重复生成；dev/OOS 无 ID/SHA 重叠。 |
| 3 | 实现/测试风险算术 | `risk.py`、known-array tests、LifeLineLoss 解释表。 | CVaR、并列 tail、失败不填零测试全绿。 |
| 4 | policy catalog 与最小 CVaR 选择 | `policy_selection.json`、开发集初步结果。 | 选择规则在看 OOS 前冻结。 |
| 5 | OOS 批量运行与 replay | runs、gate waterfall、failures。 | 每个场景可重放；任何 failure 有原因。 |
| 6 | 统计与主表 | paired delta、bootstrap manifest、T1–T5 草稿。 | strict/controlled 分轨，eligible n 完整。 |
| 7 | 消融与 OAT | AB-1–AB-4、factor/SOC/PV/repair/alpha。 | 至少一个负例和一个机制消融可解释。 |
| 8 | 风险 MRV 与 tamper | verifier 扩展、tamper matrix。 | 篡改 alpha/catalog/loss/weight 全被检出。 |
| 9 | 图表与复现包 | Fig.1–Fig.6、figure index、supplement。 | 图源 hash、数值与表一致。 |
| 10 | 初稿写作 | Introduction–Methods–Results–Threats。 | 无超出 evidence 的 claim。 |
| 11 | 内部审稿/反例复跑 | reviewer checklist、独立机器复跑。 | 关键结果不依赖本地缓存或手工修图。 |
| 12 | 投稿版冻结 | code/data release、cover letter、final checks。 | 所有 claim 均能追到 run/table/hash。 |

---

## 11. 最终决策与写作口径

### 11.1 推荐选题的最终判定

**选 D1 + D2 + D3 + D4，即：CG-CVaR + risk MRV + 合成联合压力 catalog + 因子翻转证书。**

理由：

- 与当前代码资产的接口最短：已有 ServiceContract、CareTask、Pareto、Monte Carlo、P/Q feedback、MRV/verifier 和 failure replay；
- 研究问题明确：从平均/单场景表现转向尾部生命线服务风险；
- 方法不是仅加一个 KPI：风险选择会决定可执行候选目录中的 reserve/epsilon/策略参数；
- 可形成正反两种结果：若风险改善成立，报告风险—碳代价；若不成立，也能形成“在该合成 catalog 和候选空间内未观察到改善”的可复现负结果；
- 能保持 V08 最重要的优势：不让低碳数值脱离服务、物理和证据资格；
- 规避 MISOCP、RL、GNN 和真实气候概率等高风险扩张。

### 11.2 投稿摘要中可用的谨慎句式

> 本文提出一种面向冻结合成极端天气压力集的服务合同门控尾部风险恢复框架。该框架在任务级生命线合同、P/Q 物理反馈、服务可比性和可审计 MRV 证据约束下，从可解释的恢复参数目录中选择风险敏感预案。实验采用共同随机数、开发/外样本分离和分层配对统计，报告严格同服务与受控服务预算两类比较，并保留求解、物理、合同与证据失败。结果的适用范围限于 case33bw 及版本化合成工程假设；MRV verifier 用于内部完整性与复算，不替代现场测量或第三方核证。

### 11.3 绝对不要写入论文结论的句子类型

- “已证明真实灾害风险降低/真实城市减排”；
- “V08 默认 C 相比 B 在同服务下减排”；
- “全局最优 AC 恢复”或“完整随机规划最优”；
- “seal 保证不可篡改/第三方核证”；
- “真实医院需求、真实 GFM/黑启动能力、实时自动控制”；
- “GNN/RL 赋能”而没有对应模型、数据、OOD 评价和安全 gate。

**最适合论文结尾的一句话：**

> GridRescue 的贡献不是让优化器报告一个更低的数字，而是规定一个面向尾部生命线风险的恢复建议在何种服务、物理、可比性与证据条件下才有资格被相信。

---

## 12. 本路线图的审计依据

本报告已对照以下仓库资产与研究报告：

- `README.md`、`release_manifest_v08.json`；
- `src/gridrescue/dispatch.py`、`pareto.py`、`pipeline.py`、`powerflow.py`、`care.py`、`restoration.py`、`scenarios.py`、`experiments.py`、`mrv.py`；
- `artifacts/v08_official/{flood,typhoon,heat}` 的策略比较表和 MRV gate；
- `artifacts/mc30_v04/monte_carlo_summary.csv`；
- `research_wave/wave8_synthesis.md`、`wave8_academic_novelty.md`、`wave8_validation_design.md`、`wave8_uncertainty_calibration.md`；
- `research_wave/wave10_validation_story.md`、`wave10_algorithm_frontier.md`、`wave10_academic_qa.md`、`pareto_cvar_design.md`、`scalability_benchmark.md`。

所有“将新增”“建议”“可发表”的措辞均为路线图，不表示 V08 已完成对应实现或已取得对应实验结果。
