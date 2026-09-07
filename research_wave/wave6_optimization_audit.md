# GridRescue Wave 6 — Optimization Credibility Audit

Scope: research-only audit. No production code was altered.

## Executive finding

GridRescue is credible as an auditable prototype: it solves explicit nodal LP constraints, retains failure rows, performs radial P/Q post-validation, and prevents source-free islands from being silently served.

The main language correction is this: the project currently produces a physically screened, sampled service-carbon trade-off set under an iterative heuristic. It does not yet prove a global lexicographic optimum, a global Pareto frontier, device-level P-Q feasibility, or a globally optimal restoration topology.

The smallest high-value changes are:

1. Require all service anchors to converge before their values become hard caps.
2. Re-solve the zero-epsilon point for carbon instead of copying the normal-service anchor.
3. Export nominal cap, applied cap, actual EENS, solver status, feedback status, and residual separately.
4. Use strict primary solves before any numerical tie-break.
5. Describe the front as sampled and screened.

## Evidence reviewed

| Area | Primary implementation evidence |
|---|---|
| LP, SOC, contracts, objectives | src/gridrescue/dispatch.py lines 273-444 |
| Service anchors and epsilon scan | src/gridrescue/pareto.py lines 314-654 |
| P/Q feedback | src/gridrescue/pipeline.py lines 34-138 |
| Nodal service classes and plans | src/gridrescue/restoration.py lines 50-115, 161-217, 240-306 |
| Radial P/Q validation | src/gridrescue/powerflow.py lines 132-213, 251-520 |
| Greedy ties and repair score | src/gridrescue/faults.py lines 43-87 |
| Current result evidence | artifacts/pareto_flood_v06 CSV files |
| Existing explicit limitation statement | README.md, section 当前模型限制 |

Observed issue: in the reviewed flood anchor table, the hospital anchor is marked solve_success true while feedback_converged is false, at eight iterations with feedback_residual_kw 6.213283. It remains useful audit evidence, but it is not a physically converged service anchor.

## Credibility map

| Area | Proven in the coded model | Approximated | Only demonstrated |
|---|---|---|---|
| Service anchors | Conditional optimum of each LP subproblem with fixed feedback inputs | Full lexicographic hierarchy across feedback trajectories | Selected successful runs |
| Epsilon scan | Explicit LP caps, within stated tolerance, on successful rows | Feedback-dependent feasible set and finite epsilon sampling | Non-dominance among emitted eligible rows |
| P/Q loop | Accepted final row passes the coded radial checks | Convergence and cap-correction rule | Convergence within eight iterations in shown cases |
| SOC | Hourly state recursion and bounds | Terminal readiness, mutual exclusivity, degradation | Current scenarios do not show an apparent cycling issue |
| DER Q | Aggregate island Q screening inequality | Device P-Q headroom and voltage control | Points pass the same simplified surrogate |
| Topology | Radiality of accepted graph states | Greedy score and repair ranking | Good outcomes on reviewed cases |

# 1. Lexicographic service anchors

## Current implementation

The scan sequentially minimizes hospital EENS, then other-essential EENS under a hospital cap, then normal EENS under both caps. This is in pareto.py lines 335-493. Care task minima are imposed as a hard lower bound on served critical load in dispatch.py lines 386-410.

This is substantially stronger than a single weighted critical-load objective.

## Safe claim

> For a fixed scenario and restoration strategy, GridRescue constructs hospital, other-essential, and normal-load service reference points through sequential constrained LP solves. Final eligible candidates are checked against explicit service caps and care-task delivery minima.

## Why exact lexicographic proof is too strong

### A. Primary objectives include a weighted secondary tie-break

DispatchObjective uses a default secondary weight of 1e-7. For example, the hospital objective adds small weights on other-essential EENS, normal EENS, and carbon. This helps break ties, but it is still scalarization. In a continuous model and within numerical tolerance, a small primary-objective increase can be exchanged for a larger secondary reduction.

A strict lexicographic result requires a primary solve with zero secondary term, then a separate solve constrained to the primary optimum plus a declared tolerance.

### B. Stages run under different feedback trajectories

The hospital result returns feedback, but the essential and normal anchor calls use no initial feedback. Loss vectors and component caps can therefore differ across stages. Sequential optimization is lexicographic only over a common feasible set.

### C. Two upstream anchors may proceed without feedback convergence

The hospital and other-essential anchors set require_convergence false. The normal anchor is gated, but caps feeding it can originate from a nonconverged anchor. The reviewed flood artifact demonstrates this exact condition.

### D. Reported caps are nominal, not the literal applied limits

Dispatch enforces nominal cap plus tolerance. The post-solve scan check allows the larger of ten times tolerance and 0.001 kWh. Thus a cap field alone does not show the actual accepted upper bound. In the reviewed artifact, nominal hospital cap is 0.003626 kWh and accepted actual values are near 0.00462 kWh because the applied optimization tolerance is 0.001 kWh.

## Minimum correction

1. Use zero secondary weight when discovering each primary anchor.
2. If deterministic tie-breaking is needed, perform a second solve with the first objective constrained to star plus tolerance.
3. Require feedback convergence for hospital and essential anchors. A nonconverged anchor remains a failure row and cannot generate a cap.
4. Export nominal cap, applied cap, actual EENS, and audit tolerance as different fields.
5. Compare different strategies only under one common absolute service contract. Otherwise show one curve per strategy.

# 2. Epsilon-constraint Pareto scan

## What is solid

For positive epsilon, the code fixes hospital and other-essential caps, sets normal EENS to normal-star plus allowance fraction times normal demand, and minimizes carbon. Failure rows are retained. Non-dominance is filtered over eligible rows only. This is strong audit practice.

Safe statement:

> This point is an audited solution of the current constrained LP plus iterative physical-screening procedure at its stated normal-EENS allowance.

## Zero epsilon is a service endpoint, not a carbon endpoint

At fraction zero, code copies the normal-EENS anchor into the result table rather than re-solving minimum carbon under the zero-epsilon service contract. It is therefore a valid minimum-service reference point, but it has not been established as the carbon-minimum dispatch among all zero-epsilon schedules.

## Sampled non-dominance is not a global frontier proof

The filter compares returned rows only on normal EENS and total carbon. The reviewed v06 result has four epsilon values. It supports four sampled eligible trade-off points, not a continuous or global frontier across topology, dispatch, and nonlinear AC feasibility. The feedback loop also makes the effective feasible region schedule-dependent.

## Minimum correction

1. Re-solve epsilon zero using minimum carbon under the exact service contract. If it fails, retain it as a failed point.
2. Use the UI/export phrase: sampled non-dominated screened points.
3. Store solver status, applied caps, feedback seed or hash, and residual per row.
4. Compute frontiers per scenario, strategy, and service-contract hash.

# 3. Iterative P/Q feedback

## Current implementation

The loop is:

    nodal LP dispatch
    -> radial P/Q validation
    -> update P/Q losses
    -> tighten component served-load caps for voltage or thermal conditions
    -> repeat, at most eight times

The final candidate is accepted only when feedback converges and all validation hours are feasible. Validation checks radial sweep convergence, branch loading, voltage, source/balance residuals, source-free islands, and simplified reactive shortfall.

## Classification

Proven: an accepted final point passes the coded validation gate.

Approximated: there is no contraction proof, damping rule, monotone feasible-region proof, or optimality proof for the feedback map. Component caps only tighten, which is conservative but can keep excess restriction after dispatch changes. The voltage cap scale is hand-coded, not a sensitivity-derived power-flow constraint. Island validation chooses one slack bus even though resources may be distributed.

Demonstrated: selected runs converge within the iteration limit. The method has no general convergence guarantee and does not establish the least-curtailed physically feasible dispatch.

## Safe claim

> Each eligible point was re-dispatched and post-validated with the prototype’s balanced radial P/Q model. Rows failing the configured convergence, voltage, thermal, or source-balance gates are excluded from the recommended set.

## Minimum correction

- Export final LP feedback inputs, the next validated feedback vector, and max residual.
- Add feedback_status values: converged, iteration_limit, solver_failure, post_validation_failure.
- Reject anchors as cap sources unless status is converged.
- Keep monotone cap tightening for now, but call it a conservative feasibility heuristic.

# 4. Storage SOC

## What is valid

The spatial model enforces:

    SOC[t+1] = SOC[t] + eta * charge[t] - discharge[t] / eta
    min_SOC * capacity <= SOC <= capacity
    charge and discharge <= power_limit

for every node and hour. With the present 24 one-hour periods, sums of kW numerically equal kWh, so the recurrence is internally consistent.

## Important approximations

1. There is no explicit dt_hours. A 15-minute or variable-step extension would misstate energy, EENS, carbon, and SOC without it.
2. There is no terminal SOC or reserve constraint. Depleting at the final hour can be optimal for this finite horizon but does not establish next-day readiness.
3. Charge and discharge are both nonnegative LP variables without a mutual-exclusivity constraint. The throughput penalty discourages overlap under present settings, but does not structurally rule it out.
4. A common efficiency and common SOC fraction are used. Device-specific availability, degradation, temperature, self-discharge, and inverter apparent-power sharing are outside scope.

## Exact wording

> The prototype enforces hourly SOC conservation, power limits, and SOC bounds over a 24-hour horizon. It currently assumes a fixed one-hour step, a common efficiency abstraction, and no terminal reserve or degradation model.

## Minimum correction

- Add explicit dt_hours and use it in all energy, EENS, carbon, and SOC expressions.
- Add an optional terminal reserve constraint and report whether it binds.
- Post-solve audit the minimum of charge and discharge for each node and hour. Add binary exclusivity only if the audit exposes overlap.
- Export node-level SOC start/end and reserve margin.

# 5. DER reactive-power approximation

## Current implementation

For non-root islands, served-load reactive demand plus reactive loss must not exceed 0.60 times aggregate diesel and storage active-power capacity. Validation repeats a related 0.60 aggregate screen. Load Q derives from a fixed Q/P ratio; PV is active-power-only.

## Classification

This is a useful aggregate VAR screening guardrail. It prevents an active-power-balanced island from being called feasible when Q demand is clearly excessive.

It is not a device-level reactive model. There are no individual diesel, battery, or PV Q variables; no P squared plus Q squared apparent-power constraint; no inverter/diesel voltage-control limits; no PV VAR support; and no device allocation of Q burden. Installed P nameplate is used as a proxy for Q capability.

## Exact wording

> For islanded operation, GridRescue applies an explicit aggregate reactive-support screening constraint. It is an engineering approximation of grid-forming VAR capability, not a device-resolved inverter or generator P-Q capability model.

## Minimum correction

Add per-device Q variables and a four- or eight-sided linear polygon approximation of the apparent-power capability circle. This retains a lightweight LP or MILP prototype while removing the most visible physics shortcut.

# 6. Heuristic topology restoration

## What is proven

Candidate ties are rejected if they create a graph loop. Hourly state logic filters ties that become unsafe while faults remain. This supports the claim of radiality-preserving topology construction.

## What is heuristic

Tie closures are greedily scored from the initial fault state by restored load or critical score. Repair order uses a branch score from the branch failed alone divided by repair duration. The method does not jointly optimize topology with DER, SOC, or service contracts, nor include crew routing, switching time, protection coordination, cold-load pickup, or electrical feasibility in its selection objective.

## Exact wording

> GridRescue uses a radiality-preserving greedy restoration heuristic to construct candidate repair and tie-switch actions. The resulting plan is then evaluated by nodal dispatch and P/Q validation; it is not presented as a globally optimal reconfiguration schedule.

## Minimum correction

- Rename optimal-sequence language to heuristic restoration plan.
- Recompute marginal repair/tie benefit in the current multi-fault state.
- Include declared scores for essential load, duration, operations, and a light voltage/thermal screen.
- Keep topology fixed during one Pareto scan for clearer service-carbon comparison.

# 7. Claims matrix

| Topic | Safe now | Avoid |
|---|---|---|
| Service priority | Sequential constrained service anchors with tolerance audit | Global exact lexicographic optimum |
| Pareto | Sampled screened non-dominated points | Global continuous Pareto frontier |
| Same service | Contract pass within stated tolerance for one scenario and strategy | Identical service across strategies without a common contract |
| Physics | Passed prototype balanced radial P/Q gates | Certified AC-OPF or field guarantee |
| Storage | Hourly SOC-constrained dispatch | Multi-day reserve or degradation-aware claim |
| Reactive power | Aggregate island VAR screen | Device-level P-Q optimization |
| Restoration | Radiality-preserving greedy plan | Globally optimal restoration schedule |

# 8. Exact judge wording

## Opening, 25 seconds

> 我们没有把“低碳”建立在少供电上。每个展示点先经过医院、其他关键负荷和普通负荷的显式服务合同，再进入碳优化；成功点还要通过节点级分岛平衡、P/Q 潮流、电压、热限和损耗反馈校验。当前原型输出的是经过物理筛选的 ε 服务—碳权衡样本，不把它包装成全网全时段的全局最优证明。

## “Pareto 前沿是全局最优吗？”

> 目前我们严谨地称它为“预先设定 ε 网格上的非支配、物理筛选点集”。每个点都在同一场景、固定恢复计划和公开服务上限下重新求解，并保留失败点。它不是含开关整数决策、逐设备 P–Q 能力和 AC 潮流的一体化全局 MISOCP 最优前沿；那是下一阶段扩展方向。

## “医院服务是硬约束还是权重？”

> 在 Pareto 扫描中，医院和其他关键负荷先通过顺序服务锚点得到参考值，随后以显式 EENS 上限和任务最低功率约束写入调度问题。展示时我们同时给出名义 cap、应用容差、实际 EENS 和任务完成记录；任何超出物理或服务门的点不进入推荐集合。

## “为什么说词典序？”

> 当前实现采用顺序约束构造服务优先级：先医院、再其他关键、再普通负荷；各阶段内部保留极小的数值 tie-break。因此我们称它为“词典序式服务锚定”，并把严格两次求解 tie-break 和所有锚点强制收敛列为下一版增强项，而不夸大为统一模型的严格全局证明。

## “P/Q 反馈是不是后验补丁？”

> 它是一个明确的 sequential dispatch–power-flow feedback loop：调度给出节点计划，潮流计算损耗、电压和热限，再把可核查的损耗与组件供电上限反馈给下一轮。最终展示点必须通过最后一轮物理门。它是适合原型规模的迭代近似，不替代统一 AC-OPF；结果公开迭代次数、残差和失败记录。

## “储能会为碳排牺牲医院供电吗？”

> 当前调度先受服务合同和 SOC 下界约束，碳优化只在合同允许的普通负荷让步层内发生。储能模型是 24 小时、1 小时时步的 SOC 约束调度；我们不把它宣传成多日备用电源保证。下一版将增加终端保供底仓并逐节点公开 SOC 裕度。

## “无功模型真实吗？”

> 当前采用分岛 aggregate VAR screening：负荷无功和潮流无功损耗不能超过假设的成网资源无功支撑额度。它的价值是提前排除有功平衡但无功显著不足的孤岛；它不是逐设备 P²+Q²≤S² 的逆变器/柴油机模型。

## “开关和修复顺序是不是最优？”

> 不是。当前是保持径向性的贪心恢复启发式，用于产生可解释、可复现的候选计划；每个计划随后再接受节点调度与潮流筛选。我们不会把它叫作全局最优重构。

# 9. Priority correction queue

| Priority | Change | Gain |
|---|---|---|
| P0 | Require convergence for hospital and essential anchors | Removes current nonconverged-cap weakness |
| P0 | Re-solve epsilon zero with minimum carbon | Gives a real carbon endpoint |
| P0 | Export nominal cap, applied cap, actual EENS, solver and feedback state | Makes tolerance semantics auditable |
| P1 | Strict primary anchor then constrained tie-break | Supports lexicographic wording |
| P1 | Label frontier sampled/screened and segment contracts | Prevents overclaim |
| P1 | Add dt and terminal reserve option | Strengthens SOC accounting |
| P2 | Per-device polygonal P-Q envelope | Largest small physics upgrade |
| P2 | Current-state topology marginal score | Strengthens heuristic |

## Bottom line

Present GridRescue as an auditable planning demonstrator: explicit nodal LP service contracts, radiality-preserving heuristic restoration, iterative P/Q screening, and transparent failure retention. That claim is supported today. Avoid claims of exact global lexicographic optimality, a global Pareto frontier, device-level reactive optimization, or globally optimal restoration topology until the P0 and P1 corrections are implemented.

