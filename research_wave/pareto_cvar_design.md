# GridRescue：10日 Pareto、epsilon-constraint 与 CVaR 升级设计

> **范围**：本文件只做设计，不修改代码。目标是在现有三种恢复策略和 CVXPY 连续调度之上，交付可复现的碳—韧性—经济 Pareto 前沿、epsilon-constraint 扫描和 CVaR 尾部风险结果。
>
> **已核对基线**：`src/gridrescue/restoration.py` 有“传统顺序恢复、最小失供恢复、碳韧协同恢复”三种计划；`dispatch.py` 对电网、PV、BESS、柴油和失供做 24 个 1 h 时段的连续 CVXPY 调度；`scenarios.py` 可生成共同的合成多故障场景。当前碳韧策略通过加权目标和“额外正常负荷失供最多 8%”展示取舍，适合演示点，但不应单独作为跨策略低碳优胜证据。

## 1. 十日 MVP 的边界

1. 不把离散修复排序、开关状态和逐支路潮流嵌入优化器；现有三类恢复计划先生成 `grid_capacity_kw` 路径，`powerflow.validate_dispatch` 继续作后验校验。
2. 对每个计划族和共同灾害场景，求服务约束下的调度前沿；输出原始 kWh、kgCO2、元，拒绝用一个加权“总分”替代。
3. 用 Rockafellar–Uryasev 线性形式加入 CVaR；第一版的定位是**灾情已观测后的风险厌恶 recourse 调度**，不宣称为完整灾前两阶段随机承诺。
4. 严格区分运行排放清单、同服务条件下的排放差分、弃光 KPI；不把少供电、弃光减少或电池放电直接记成减排。

## 2. 数学对象

### 2.1 索引、输入

- `t∈T={0,...,T-1}`：恢复时段；当前 `T=24`，`Δt=1 h`。
- `s∈S`：灾害/故障情景，概率 `p_s`；默认共同均匀样本。
- `q∈Q`：计划族，当前 `Q={传统顺序, 最小失供, 碳韧协同}`。
- `D^c_{s,t},D^n_{s,t}`：关键/普通负荷需求，映射现有 `critical_load_kw, normal_load_kw`。
- `Gbar_{q,s,t}`：网络状态下最大上级电网进口，映射 `grid_capacity_kw`。
- `Ppv_{s,t}, gamma_{s,t}`：PV 可用功率、电网排放因子。
- `Pdbar, Pbbar, Eb, SOCmin, eta_b`：柴油/BESS 配置，映射 `ResourceConfig`。
- 新增版本化 `EconomicFactors`：`a^g_t`（分时电价）、`a^d_t`（柴油变动成本）、`a^deg`（BESS 吞吐折旧）、`a^sw`（开关动作）、`a^crew`（车辆/班组）、`a^cur`（弃光机会成本）。

所有当前 `*_kw` 列必须在公式和未来代码里显式乘 `Δt`，避免从 1 h 改成 15 min 时产生单位错误。

### 2.2 变量

对每个 `q,s,t`：

`[
x^c,x^n\ge0;\quad g,d\ge0;\quad b^+,b^-\ge0;\quad r\ge0;\quad e
`]

分别表示已供关键/普通负荷、电网进口、柴油发电、BESS 充/放电、PV 弃电和时段末储能量。CVaR 再引入共享阈值 `eta` 和每情景尾部松弛 `z_s>=0`。

### 2.3 物理约束

`[
0\le x^c_{s,t}\le D^c_{s,t},\quad 0\le x^n_{s,t}\le D^n_{s,t}
`]

`[
0\le g_{s,t}\le Gbar_{q,s,t},\quad 0\le d_{s,t}\le Pdbar,\quad
0\le b^+_{s,t},b^-_{s,t}\le Pbbar,\quad 0\le r_{s,t}\le Ppv_{s,t}
`]

`[
e_{s,0}=SOC_0Eb,\quad
e_{s,t+1}=e_{s,t}+\eta_b b^+_{s,t}\Delta t-b^-_{s,t}\Delta t/\eta_b
`]

`[
SOCmin\cdot Eb\le e_{s,t}\le Eb
`]

`[
g_{s,t}+d_{s,t}+b^-_{s,t}+Ppv_{s,t}
=x^c_{s,t}+x^n_{s,t}+b^+_{s,t}+r_{s,t}.
`]

这与现有 `dispatch_resources()` 同构，仍是 LP。当前线性吞吐成本会抑制同刻充放电；MVP 另做 QA：逐时要求 `min(b^+,b^-)<=1e-5`。充放互斥若以后需要严格物理保证，再引入二进制变量和 MIP，不进入十日主线。

## 3. 三个原始目标

### 3.1 韧性

`[
U^c_{q,s}=\sum_t(D^c_{s,t}-x^c_{s,t})\Delta t,\quad
U^n_{q,s}=\sum_t(D^n_{s,t}-x^n_{s,t})\Delta t
`]

引入 `P^{un}_{q,s}`，满足：

`[
P^{un}_{q,s}\ge D^c_{s,t}-x^c_{s,t}+D^n_{s,t}-x^n_{s,t},\quad\forall t.
`]

尾部优化损失采用：

`[
R_{q,s}=v_cU^c_{q,s}+v_nU^n_{q,s}+v_pP^{un}_{q,s}.
`]

建议 MVP 用透明相对值 `v_c=10, v_n=1, v_p=0.25h`。报告始终并列 `critical_eens_kwh`、`eens_kwh`、`peak_unserved_kw`，不让加权损失遮住关键保供。

### 3.2 碳

`[
C_{q,s}=\sum_t(\gamma_{s,t}g_{s,t}+\phi^d d_{s,t})\Delta t+C^{crew}_{q,s}.
`]

其中 `Ccrew=phi^crew * km`。沿用 `calculate_carbon()` 的电网、柴油、车辆分解。PV 运行排放为零；弃光仅为能源机会损失，绝不写为负排放。

### 3.3 经济

`[
K_{q,s}=\sum_t(a^g_tg_{s,t}+a^d_td_{s,t}+a^{deg}(b^+_{s,t}+b^-_{s,t})+a^{cur}r_{s,t})\Delta t
+a^{sw}N^{sw}_{q,s}+a^{crew}km_{q,s}+a^{repair}\sum_{\ell\in F_s}h^{repair}_{\ell}.
`]

同一场景下总维修工时可能在三种顺序中相同而抵消，仍要记录，避免未来多班组/路径优化时遗漏。价格和排放因子必须集中到带版本和来源字段的 CSV/JSON；资料不足时只能称“归一化运行成本”，不得称为真实财务收益。

## 4. 公平比较：阻止“少供电反而低碳”

### 4.1 每个计划—情景的词典序服务锚点

对每个 `(q,s)` 先独立计算：

1. `U^{c,*}_{q,s}=min U^c_{q,s}`；
2. 施加 `U^c<=U^{c,*}+delta_c` 后，求 `U^{n,*}_{q,s}=min U^n_{q,s}`；
3. 保存锚点总供电量：

`[
H^*_{q,s}=\sum_t(D^c+D^n)\Delta t-U^{c,*}_{q,s}-U^{n,*}_{q,s}.
`]

建议 `delta_c=max(1e-4 kWh, 1e-6*critical_demand_kwh)`。锚点对每个计划各算一次，避免网络能力不同的计划拿另一计划的服务上限冒充公平。

### 4.2 服务合同

进入 Pareto、低碳或低成本排名的候选必须满足：

`[
U^c_{q,s}\le U^{c,*}_{q,s}+\delta_c
`]

`[
U^n_{q,s}\le U^{n,*}_{q,s}+\epsilon_n,\quad
\epsilon_n=\rho_n\sum_tD^n_{s,t}\Delta t.
`]

扫描 `rho_n∈{0,0.5%,1%,2%,4%,6%,8%,10%}`，并执行：

`[
H_{q,s}\ge H^*_{q,s}-\epsilon_n-\delta_c.
`]

规则：

- `rho_n=0` 为严格服务等价层，才可直接比较绝对 kgCO2 和元；
- `rho_n>0` 是公开的普通负荷服务让步层，图例/CSV 必须写明预算；只允许**同层**比较碳与成本；
- 未通过关键服务或供电量检查的点只作为失供失败点，禁止获得“低碳”“减排”标签；
- 每张图同时展示绝对碳、served kWh、关键/普通 EENS、`kgCO2/served_kWh`。强度指标只作诊断，不能盖过绝对服务量。

审计断言：若 `C<C_anchor` 且 `served_kWh<anchor_served_kWh-epsilon_n-tol`，则写 `fairness_status=service_not_equivalent` 并从前沿/减排榜剔除，仍保留完整 CSV。

## 5. epsilon-constraint Pareto 求解

### 5.1 主问题

给定 `q,s,rho_n` 和碳预算 `Cbar`，以最低运行成本为例：

`[
min\ K_{q,s}
`]

subject to 物理约束、服务合同，以及：

`[
C_{q,s}\le Cbar.
`]

镜像子问题为：

`[
min\ C_{q,s}\quad s.t.\ service\ contract,\ K_{q,s}\le Kbar;
`]

`[
min\ U^n_{q,s}\quad s.t.\ U^c\le U^{c,*}+\delta_c,\ C_{q,s}\le Cbar,\ K_{q,s}\le Kbar.
`]

每个可行结果保存原始三元组 `(Un,C,K)` 和 `Uc`。只在相同服务层内做非支配判定：A 的三项都不高于 B 且至少一项严格更低时，A 支配 B。去重容差建议 `1e-4`。

### 5.2 预算扫描

每层先解两个端点：

- 经济端点：服务合同下 `min K`，得到 `C^K`；
- 碳端点：服务合同下 `min C`，得到 `Cmin`。

扫描：

`[
Cbar_j=Cmin+\lambda_j(C^K-Cmin),\quad
\lambda_j∈{0,.125,.25,.375,.5,.625,.75,.875,1}.
`]

若相邻点的碳/成本差异最大，在该区间二分两次。先跑 `rho_n={0,1%,4%,8%}` 冒烟；全量再跑 8 层。单层约 9--13 个 LP，远比盲目权重网格更可解释。

### 5.3 多场景前沿

共同样本上的期望指标：

`[
\bar C_q=\sum_sp_sC_{q,s},\quad \bar K_q=\sum_sp_sK_{q,s},\quad
\bar U^c_q=\sum_sp_sU^c_{q,s},\quad \bar U^n_q=\sum_sp_sU^n_{q,s}.
`]

正式图必须同时画每情景散点与 bootstrap 区间，避免均值掩盖尾部。

## 6. CVaR 风险优化

### 6.1 线性形式

`[
CVaR_\alpha(R_q)=
min_{\eta,z}\left\{\eta+\frac{1}{1-\alpha}\sum_sp_sz_s\right\}
`]

subject to：

`[
z_s\ge R_{q,s}-\eta,\quad z_s\ge0.
`]

它只增加一个 `eta` 和每情景一个 `z_s`，因此在当前线性模型中仍是 LP。

### 6.2 推荐实验形式

**主线：尾部约束 epsilon**

`[
min\ K_q\ {\rm or}\ C_q
`]

subject to逐场景服务合同、`CVaR_alpha(R_q)<=Rbar_alpha`，以及可选 `C_q<=Cbar`。

将 `Rbar_alpha` 从服务优先下界扫描为 `{1.00,1.02,1.05,1.10,1.20}` 倍。这样可以直接读出容忍更多最坏情景损失换来多少碳/成本。

**对照：风险价格**

`[
min\ \bar K_q+\lambda_C\bar C_q+\lambda_R CVaR_\alpha(R_q)
`]

归一化后扫 `lambda_R∈{0,0.25,0.5,1,2,4}`。这只用于权重敏感性，不替代 epsilon 前沿。

### 6.3 CVaR 样本规定

- `alpha=0.90`：MVP 主结果，30 场景即可冒烟；
- `alpha=0.95`：正式至少 100 场景，推荐 200；30 个样本只有约 1--2 个尾部观测，不可当稳定结论；
- 并列报告均值、P90/P95、VaR、CVaR、关键服务合同失败概率，不能只报总 EENS 的均值。

### 6.4 最小共同风险策略

当前三种计划会随观察到的故障情景生成；十日版明确称为 adaptive recourse。若需真实跨情景共同决策，外层枚举 BESS 应急预留：

`[
rho^{reserve}∈{0.12,0.20,0.30,0.40},\quad e_{s,t}\ge rho^{reserve}Eb,\ \forall s,t.
`]

外层候选为 `(plan_family,rho_reserve,rho_n,Cbar)`，内层按情景调度，再由 CVaR 选择前沿。此做法在十日内可实现且口径诚实。

## 7. 参数、实验和统计

### 7.1 实验组

| 组 | 目标 | 扫描/比较 | 交付 |
|---|---|---|---|
| G0 | 回归现有三策略 | 原权重、原 8% 机制 | 对齐现有 KPI，容差说明 |
| G1 | 公平 Pareto 主实验 | 3计划 × rho_n={0,1,4,8%} × 9碳预算 | 分服务层前沿 |
| G2 | 方法消融 | G1 对比多组现有加权和 | 权重敏感性、前沿漏检区 |
| G3 | CVaR 主实验 | 代表服务层 × alpha={.90,.95} × 5 CVaR cap × reserve网格 | 期望—尾部前沿 |
| G4 | 敏感性 | grid EF ±20%，柴油价 ±30%，PV ±20%，BESS ±25%，修复时长 +30% | tornado、推荐点翻转率 |
| G5 | 防伪优越 | 去服务合同、去 CVaR、去 reserve；都跑潮流后验 | 少供电低碳被剔除率、物理违例率 |

### 7.2 场景与统计

- 开发：三个命名灾害 + `sample_fault_scenarios(30, seed=20260822)`；
- 主报告：100 个共同随机场景，建议至少三组固定 seed；每策略必须使用完全相同的情景列表；
- CVaR95：200 个共同场景优先；
- 参数筛选先用 30 场景，候选前沿再用 100--200 场景复算。

每点报告：mean、median、std、IQR、P90、P95、max、expected carbon/cost、diesel、PV curtailment、served kWh、关键 EENS 的 CVaR、可行率、服务合同通过率、潮流后验违规率、平均求解时间。

同一情景做配对差分（Δ碳、Δ成本、Δ关键 EENS），用 2,000 次 paired bootstrap 给 95% CI；偏态分布补 Wilcoxon signed-rank。每个服务层将三目标以该层公共最差可行点归一化，固定 reference point 为最大可行值的 1.05 倍，报告 3D hypervolume、非支配点数和对 G0/G2 的 coverage。

## 8. 可视化与结果文件

### 8.1 图

1. 三维 Pareto：x=碳，y=成本，z=关键 EENS 或 CVaR90；颜色=rho_n，形状=计划族。
2. 主图：按 rho_n 分面的“碳—成本”前沿，点大小=CVaR90 关键 EENS；服务失败点以灰色空心显示。
3. 碳—服务曲线：x=服务率/普通失供预算，y=绝对碳；关键失供单独警戒线。
4. CVaR exceedance：按场景损失排序，显示 VaR 阈值和最坏尾部。
5. 碳/成本瀑布：grid、diesel、crew 与购电、柴油、BESS、开关、抢修分解。
6. 不确定性：不同 seed 的 hypervolume、CVaR、前沿点数 bootstrap 区间。

图例必须写：`服务合同：critical anchor + delta_c；normal allowance=rho_n`。只允许“该服务合同下碳最小”，禁止脱离服务层的“碳最优”。

### 8.2 推荐产物

| 文件 | 最少字段 |
|---|---|
| `pareto_runs.csv` | run_id, seed, scenario, plan_family, rho_normal, carbon_cap_kg, cvar_alpha, cvar_cap, solver, status, solve_seconds, raw objectives |
| `pareto_frontier.csv` | 上述字段 + frontier_layer, dominates_count, eligible_service, fairness_reason |
| `risk_summary.csv` | expected_cost/carbon, mean/P90/P95/CVaR critical_eens, mean/CVaR resilience_loss, failure probability |
| `fairness_audit.csv` | anchor critical/normal EENS, candidate EENS, anchor/candidate served kWh, contract pass |
| `economic_factor_registry.csv` | factor_id, value, unit, date_window, source, retrieved_at, version_hash |
| `run_manifest.json` | 输入哈希、seed、时间步、因子版本、求解器/状态、失败解清单 |

## 9. 求解器兼容与数值规则

- MVP 是连续 LP：优先现有 `CLARABEL`；批量 LP 可在实际 `cp.installed_solvers()` 含 `HIGHS` 时优先 HiGHS；后备为实际已安装的 `GLPK/ECOS`。
- 二进制开关或强制充放互斥属于未来 MIP，需要 `HIGHS/CBC/GLPK_MI/SCIP` 等；Clarabel 不承担整数问题。
- 实现 `solver=auto`，基于 `cp.installed_solvers()` 选择；不同 solver 传各自选项，不能把 Clarabel 的 `max_iter` 原样传给所有后备。
- 用 `cp.Parameter(nonneg=True)` 表示 epsilon/cap/权重，重用问题结构并 warm start。
- `OPTIMAL_INACCURATE` 单列，复跑高精度或后备 solver；不与 `OPTIMAL` 混合。
- 对每个解重算：功率平衡、SOC、供电上界、服务合同、排放/成本、`min(charge,discharge)`、潮流后验。infeasible 只记录，不用松弛解伪造前沿。

## 10. 十日执行顺序

| 日 | 工作 | 验收 |
|---:|---|---|
| 1 | 冻结 G0、输入/输出哈希；定义 EconomicFactors 和单位 | 原三策略可复跑 |
| 2 | 独立实现词典序服务锚点与 fairness audit | 每个 (q,s) 有 Uc*, Un*, H* |
| 3 | 单场景 epsilon 端点、碳 cap、非支配过滤 | 暴雨/台风前沿 CSV |
| 4 | 接成本分解、因子注册和重算 QA | 碳/成本可由逐时表重算 |
| 5 | 跑 G1、完成分层 Pareto 与服务合同图 | rho_n 四层可审计 |
| 6 | 接 CVaR90，30 场景冒烟与手工重算 | VaR/CVaR 一致 |
| 7 | 100 场景共同随机数、paired bootstrap | 置信区间和尾部摘要 |
| 8 | G2/G4/G5、solver fallback、潮流失败处理 | 权重/敏感性/失败率表 |
| 9 | 固化 artifacts、manifest、答辩图表 | 可复算结果包 |
| 10 | G0 回归、固定种子重跑、性能和文档审查 | 发布候选与已知边界 |

## 11. 最终决策输出

不输出“某策略永远最好”，而输出四类可选点：

1. **保供优先点**：rho_n=0 的最小失供点；
2. **严格服务等价低碳点**：rho_n=0 下碳最小，可合法比较绝对排放；
3. **受控让步点**：rho_n=1% 或 4%，明确写新增普通 EENS 换来的 kgCO2/成本变化；
4. **尾部防御点**：满足 CVaR90/95 阈值的最低成本或最低碳点。

每个点都附带计划族、参数、服务合同、期望目标、尾部目标、碳/成本分解、最差情景、solver status、潮流后验和因子版本。这样比较的是可审计的服务—碳—成本—风险边界，而不是靠少供电刷出来的低碳数字。
