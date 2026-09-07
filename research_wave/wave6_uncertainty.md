# Wave 6：最小不确定性与稳健性证据层（1–2 日 MVP）

> 目标：给 GridRescue 增加一套可复现的证据层，回答四个评委问题：输入变化后结果还成立吗？失败有没有被隐藏？低碳是否靠少供电换来？每个结论能否重放？
>
> 建议：不引入深度学习、代理模型或大型随机规划。直接把现有共同随机场景、物理潮流校验、失败 manifest、Wilson 区间和 bootstrap 区间补成固定情景目录、轻量压力组、配对比较、反例控制和透明稳健护照。

## 1. 现状审计：已具备什么，缺什么

已核查当前工程：

- experiments.py 已支持固定 seed 的合成故障样本、三策略共同场景运行、逐行 solve_success、失败阶段/原因、完整 scenario_definition、失败 manifest 和 replay。
- summarize 已对成功率给出 Wilson 95% 区间，对成功样本指标给出确定性 percentile bootstrap 区间；失败结果不会作为零失供或零碳混进均值。
- mc30_v04 实际记录为：每个策略尝试 30 场景，29 个物理管线成功，1 个场景在物理管线失败；29 个成功场景的 physical_feasible_hours 都是 24。它只能说明原型已跑过一次失败隔离和物理压力测试，不能说明 30 个场景证明真实系统稳健。
- sample_fault_scenarios 的当前范围是 2–5 条故障、3–12 小时修复、PV 降额 0.20–0.90 等合成均匀抽样；它并非暴雨、台风或高温的统计故障模型。
- ambient_temperature_c 当前被写入 scenario，但未进入负荷、设备或故障计算，不能作为已验证的不确定性维度。
- grid carbon 因子是合成年度基准乘情景倍数和峰时形状；不能称实时区域边际因子。
- crew distance 对同一场景下的三策略通常是共同项；它不能被用来制造策略间相对低碳结论。

最小缺口：

| 缺口 | MVP 修复 |
|---|---|
| 随机样本未按灾种、严重度冻结 | 建立主情景目录并记录 hazard_family、severity_band、seed 与 SHA。 |
| 只存在逐策略均值 CI | 对同一 scenario_id 的策略差值做 paired bootstrap。 |
| failure manifest 仅保存失败案例 | 增加全量 scenario catalog；成功和失败都可由冻结输入回放。 |
| 没有反例机制 | 加入平坦因子、服务放松、无储能灵活性、异常注入四个负对照。 |
| 无总览 | 输出透明分项的 Robustness Readiness Score 护照；总分不进入优化。 |

## 2. 最小交付物：Robustness Evidence Pack v1

新增一个目录，不重写恢复、调度或潮流核心：

~~~
artifacts/robust_v1/
  robustness_policy.json
  scenario_catalog.json
  robustness_results.csv
  robustness_summary.csv
  robustness_failures.json
  robustness_passport.csv
  charts/
~~~

结果行至少包含：

~~~
experiment_id,scenario_id,hazard_family,severity_band,stress_id,
run_seed,scenario_sha256,baseline_scenario_sha256,strategy,
solve_success,failure_phase,failure_reason,
physical_feasible_hours,physical_pass,
critical_contract_pass,normal_contract_pass,claim_eligible,
eens_kwh,critical_eens_kwh,total_carbon_kg,
max_branch_loading_pct,min_voltage_pu,source_adjustment_max_kw,
paired_reference_strategy,delta_total_carbon_kg,
delta_critical_eens_kwh,delta_eens_kwh,replay_status
~~~

完整 scenario_definition 放在 catalog 或原始 run 记录中；CSV 用 scenario_id 与 SHA 引用，避免复制大 JSON。

## 3. 情景采样：固定、分层、共同随机

### 3.1 主实验：60 个冻结共同场景

推荐的主报告集：

~~~
3 个灾种：暴雨内涝、台风、极端高温
× 2 个严重度层：reference、stressed
× 10 个固定 seed
= 60 个 scenario
~~~

每个策略必须跑同一份 60 行 catalog，不能为不同策略分别抽样。

严重度在运行前冻结：

| 层 | 故障/修复 | PV | 负荷 | 解释 |
|---|---|---|---|---|
| reference | 对应命名灾种锚点，修复时间基准或 0.85–1.10 倍 | 基准附近 | 基准 | 合成参考压力 |
| stressed | 多 0–1 个故障，或同等更严重组合；修复 1.10–1.30 倍 | 可用功率再降 10–20% | +5%；高温 +10% | 合成边界压力 |
| invalid_control | 有意构造不可行或违规输入 | 不用于排名 | 不用于排名 | 验证失败门 |

两天内若只够实现最少变化，优先做命名灾种锚点、修复/PV/负荷压力和 10 个固定 seed；不要写没有标签校准的故障预测模型。

### 3.2 现有通用抽样的正确用途

保留现有 30 场景随机生成器作为开发回归和泛化 smoke test。它可以检验失败隔离、数据结构和算法脆弱性，但不作为灾种发生概率证据。

### 3.3 共同随机数纪律

1. 冻结 catalog_id=ROBUST-V1、master_seed=20260822 和生成器版本。
2. 每一个 scenario 生成一次，所有策略复用。
3. 策略 A/B 的效应统计只在两边均成功的 scenario_id 交集上计算，同时报告两边成功数与 paired n。
4. 失败样本不填 0；成功均值与尝试/失败计数分开。
5. 第二个 seed 只能作为外部复核，不得代替主 seed 中失败或不漂亮的结果。

## 4. 参数不确定性：少而有意义的压力组

对三种命名灾种各跑五组，共 15 组；每组仍是三策略共同运行。

| stress_id | 改动 | 主要影响 | 用途 |
|---|---|---|---|
| BASE | 冻结命名灾种原参数 | 全部 | 比较锚点 |
| PV_LOW | PV 可用功率相对下降 20%，截断至 0–1 | 物理、服务、碳 | 检验资源依赖 |
| REPAIR_LONG | 每条修复时间 ceil(1.30 倍) | 拓扑、服务 | 检验恢复排序 |
| LOAD_HIGH | 每小时负荷乘 1.05；高温乘 1.10 | 物理、服务、碳 | 检验供需压力 |
| EF_HIGH | 电网因子乘 1.15，仅进碳核算与碳调度 | 碳结论 | 检验因子误差下的排序翻转 |

纪律：

- EF_HIGH 不是物理压力，只能影响碳比较。
- PV_LOW、REPAIR_LONG、LOAD_HIGH 是单因素实验，不做 3 的 3 次方组合。
- 若 LOAD_HIGH 在本轮还未真实接入 hourly profile，则延后该压力组，不能写入已完成结论。
- 所有范围进入 robustness_policy.json，标注 assumption 和版本，不能伪造成实测分布。

辅助指标采用排名翻转率，而不是复杂的 Sobol 指数：

~~~
ranking_flip_rate =
  合格最低碳推荐相对 BASE 发生改变的压力组数
  / 有合格推荐的压力组数
~~~

无合格推荐时记录 N/A，不填零。

## 5. 统计：成功率单列，策略差异用配对区间

### 5.1 成功率与物理通过率

沿用 Wilson 95% CI：

~~~
solve_success_rate = solved_count / attempt_count
physical_pass_rate =
  count(solve_success and physical_feasible_hours == 24) / attempt_count
~~~

二者均报告 count/N 和区间。失败指标保持 NA，不进入均值。

### 5.2 Pairwise bootstrap 是主比较

同一场景上比较策略 A 与 B：

~~~
delta_carbon_i = carbon_A_i - carbon_B_i
delta_critical_i = critical_EENS_A_i - critical_EENS_B_i
delta_eens_i = EENS_A_i - EENS_B_i
~~~

对 paired-success cases 重采样 2,000 次，每次计算平均差，输出 percentile 95% CI。

标准表达：

~~~
A 相对 B，paired n=58：
平均 delta carbon = -420 kgCO2，95% CI [-690, -170]
平均 delta critical EENS = +1.2 kWh，95% CI [-0.6, +3.4]
~~~

同时输出 median、IQR 和碳排 win share。不要只报 p 值，也不要由两条独立均值 CI 相减来替代配对 CI。

### 5.3 样本边界

- 60 个共同合成场景足以形成竞赛方法证据和失败披露。
- 30 个场景只作 smoke test。
- 本 1–2 日 MVP 不用 30 样本宣称 CVaR 0.95。尾部正式结论应至少 100、最好 200 个共同样本。

## 6. 结论门控：阻止少供电伪低碳

任一“低碳更优”结论必须通过：

~~~
G0 输入完整：catalog、seed、scenario SHA、因子版本齐全
G1 求解完成：solve_success=true
G2 物理门：physical_feasible_hours=24
G3 服务门：关键服务合同通过，普通服务在公开 allowance 内
G4 比较门：存在同场景对照且 paired CI 可计算
claim_eligible = G0 and G1 and G2 and G3 and G4
~~~

服务或物理不合格的点保留在 CSV 和图中，使用灰色空心符号，但从合格碳比较中排除。

声明阈值：

| 可用主张 | 证据条件 | 口径 |
|---|---|---|
| 合成压力集下碳排较低 | mean delta carbon 的 95% CI 上界小于 0，且所有门通过 | 在 ROBUST-V1 合成共同场景及该服务合同下，运行排放估算较低。 |
| 未超过关键服务容差 | delta critical EENS 的 95% CI 上界不高于预注册容差 | 未观察到超过预注册关键服务容差的平均恶化。 |
| 压力下可运行 | 物理/服务通过率、Wilson CI、失败清单、replay | 在该冻结压力集上具有明确的通过和失败记录。 |
| 更稳健 | 同一服务合同下 RRS 分项更高 | 按预注册稳健护照，在本样本范围内得分更高。 |

禁止使用真实配网可靠性、认证减排、实时边际减排、所有情景均优于、零碳等说法。

## 7. 稳健性评分：透明护照，不进优化器

定义 Robustness Readiness Score，RRS，范围 0–100。它只做答辩总览，不参与调度目标、不替代 EENS、碳、电压、载荷率或 Pareto。

若 catalog/hash/replay 完整性失败，RRS=N/A。

分母均为 attempt_count：

~~~
P = physical_pass_count / attempt_count
C = critical_contract_pass_count / attempt_count
N = normal_contract_pass_count / attempt_count

V = clamp((Q10(min_voltage_pu)-0.95)/0.03, 0, 1)
L = clamp((100-Q90(max_branch_loading_pct))/20, 0, 1)
M = 0.5*V + 0.5*L

RRS = 100*(0.40*P + 0.30*C + 0.15*N + 0.15*M)
~~~

Q10 电压和 Q90 负载率只在物理成功样本上计算；没有成功样本时 M=0 且写明原因。碳排不进入 RRS，避免把低碳与稳健混为一个黑箱数。

护照每一行必须并列原始分项：

~~~
RRS | physical pass | critical pass | normal pass |
Q10 voltage | Q90 loading | attempt/solve/physical count |
critical EENS mean and CI | paired carbon CI | failure manifest link
~~~

解释规则：

| RRS | 解释 |
|---:|---|
| 大于等于 90 | 冻结样本下通过记录较强，仍必须读分项和失败清单。 |
| 75–90 | 有压力敏感性或裕度不足。 |
| 小于 75 | 候选/诊断策略，不宣称稳健优选。 |
| N/A | 证据链不可重放或输入不完整。 |

## 8. 四个必须跑的负对照

| 控制 | 处理 | 正确预期 | 失败含义 |
|---|---|---|---|
| NC1_FLAT_EF | 全部小时电网因子设为常数 | 不出现择时减排或额外预充的碳优势结论 | 碳时移/核算有错误 |
| NC2_SERVICE_RELAXED | 有意放宽普通服务合同 | 可能碳更低，但 claim_eligible 必须为 false | 服务门形同虚设 |
| NC3_NO_FLEX_BESS | 储能功率或可调能量设为 0 | 储能控制退化为无灵活储能基线 | SOC/储能归因错误 |
| NC4_INJECTED_FAILURE | 注入可预期异常或读取已知失败 replay | 失败行保留、指标 NA、摘要失败数增加、可回放 | 失败被吞掉或污染统计 |

可选 NC5：打乱小时碳因子。动作应可追溯地改变；若完全不变，碳信号可能未实际进入决策。NC5 是机制检查，不是物理真实性证明。

## 9. 四张答辩主图

### 图 1：情景覆盖与失败台账

hazard_family × severity_band 的计数矩阵，格内展示 attempt / physical pass / critical contract pass；旁边列失败 scenario_id。这张图回答样本从哪里来、有没有挑样本、失败去了哪里。

### 图 2：配对碳—服务散点图

横轴为 delta critical EENS，纵轴为 delta total carbon。颜色表示灾种，形状表示严重度；任一策略失败或服务门未过的案例是空心灰点。

- 左下：服务不差且碳更低；
- 右下：靠服务恶化换低碳，不准宣称优越；
- 左上：服务改善但碳代价更高；
- 右上：两者都更差。

图角注必须写 paired n、关键服务容差与 CI。

### 图 3：配对效应森林图

按灾种和严重度层展示：

~~~
mean delta carbon with paired 95% CI
mean delta critical EENS with paired 95% CI
mean delta EENS with paired 95% CI
~~~

这是“不是挑单场景”的核心证据。

### 图 4：稳健护照和负对照表

不要用雷达图。使用热力表展示：

~~~
physical pass | critical pass | normal pass | Q10 V | Q90 loading | RRS
NC1 | NC2 | NC3 | NC4 | replay integrity
~~~

绿色表示门通过，黄色表示裕度不足，红色表示失败，灰色表示 N/A。所有主图都应展示或可下载原始点，不能只放箱线图。

## 10. 测试与验收

已有 tests/test_experiments.py 的失败隔离、CI、failure replay 测试应继续保留。新增最小测试：

| 测试 | 断言 |
|---|---|
| catalog deterministic | 同 policy 和 seed 得到相同 scenario JSON、ID、SHA 和顺序。 |
| stratification | 主 catalog 恰好 3×2×10=60，每层数量正确。 |
| paired completeness | 三策略引用相同 scenario ID；paired n 等于成功交集。 |
| range validation | PV、负荷、修复时间、因子压力均在 policy 范围。 |
| physical gate | physical pass 当且仅当 solve success 且可行小时=24。 |
| service gate | 服务放松或超容差行必须 claim_eligible=false。 |
| paired bootstrap deterministic | 固定数据/seed/B=2000 时 CI 可复现；交换 A/B 后结果符号对称。 |
| no zero fill | 失败行所有指标 NA，RRS 分母仍保留失败 attempt。 |
| success replay | catalog 成功场景重跑后 scenario SHA 相同，数值在 solver 容差内。 |
| failure replay | 失败 scenario 的输入 SHA、phase 和记录可恢复；代码修复后允许新状态不同。 |
| NC1–NC4 | 四个控制的预期门控都成立。 |
| score bounds | RRS 在 0–100 或 N/A；replay integrity 失败时必须 N/A。 |

运行验收：

1. pytest -q 通过；
2. 主 catalog 60×3 和压力组 15×3 都输出原始行；
3. 负对照有 pass/fail 记录；
4. 现场各回放 1 个成功与 1 个失败案例；
5. 记录真实 P50/P95 运行时与 solver/hardware，不伪称实时。

## 11. 两日实施顺序

### Day 1：冻结输入并跑数据

1. 建 robustness_policy.json，冻结 catalog ID、seed、压力范围、服务容差、CI 次数和 RRS 权重。
2. 在现有实验封装外增加 scenario catalog，不改恢复、调度和潮流核心。
3. 输出 hazard_family、severity_band、stress_id 和 scenario SHA。
4. 复用现有 run_single_scenario 和失败隔离跑 60 主场景、15 压力组。
5. 写 robustness_results、catalog 和 failures。

### Day 2：统计、反例和图表

1. 加 paired bootstrap summary、服务/物理门和 RRS 护照。
2. 跑 NC1–NC4；负对照失败时优先修门控/核算，不包装主结果。
3. 补单元测试以及成功/失败 replay。
4. 输出四张图、一页方法和一页已知边界。
5. 演练：选 scenario ID，显示输入 SHA，运行策略，展示服务/物理门，下载证据。

不做 GNN、LLM、强化学习、未校准故障预测、30 样本 CVaR95 结论，或把 RRS 送回优化器。

## 12. 可直接用于答辩的 30 秒表述

“我们不只报一次最好看的恢复结果。GridRescue 在同一批冻结灾害压力场景下让所有策略共享故障与资源不确定性；每一条低碳比较都先经过关键服务、潮流和失败重放门。我们报告配对置信区间、失败率和反例控制：如果低碳只是靠少供电、平坦因子或异常求解得到，系统会把它标为不合格。当前结论限于可复现的合成竞赛原型，真实馈线与真实因子是下一阶段验证项。”

## 13. 最终建议

核心不是增加一个花哨模型，而是完成下面这条最小证据链：

~~~
固定共同场景
+ 单因素压力
+ 配对置信区间
+ 失败不归零
+ 成功/失败均可回放
+ 服务门阻断伪低碳
+ 负对照验证机制
= 可答辩的最小稳健性证据链
~~~

先完成该层，再扩展 Carbon-SOC、Pareto/CVaR 或真实气象/馈线数据。否则图表会越来越多，证据会越来越薄。