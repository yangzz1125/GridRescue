# GridRescue 碳韧智网：Wave 8 严谨验证体系（2026-08-22）

> 目标：在 10 天纯软件交付内，把 GridRescue 的策略结果组织为可复现、可比较、可审计、可答辩的证据包。  
> 本轮只新增本设计文档；未修改生产代码、测试和既有 artifacts。

## 1. 现状基线与结论边界

### 当前可用能力
- IEEE/MATPOWER case33bw 33 节点网络、P/Q 潮流反馈、电压/热限/功率平衡检查、无源孤岛硬失败。
- 三策略：A=传统顺序恢复；B=最小失供恢复；C=碳韧协同恢复。
- Monte Carlo 保存 run_seed、完整场景 JSON、场景 SHA-256、失败原因与 replay manifest；summary 含 bootstrap CI 与 Wilson CI。
- Pareto 已锁医院/其他关键服务锚点，候选点通过 CareTask 合同与物理反馈后才进入前沿。
- CareTask 覆盖节点、功率、时窗、deadline、连续时长、依赖、任务电压和并发需求。
- MRV bundle 有因子快照、活动账、排放清单、动作 hash chain、evidence index、seal、verify。

### 当前数值只作烟雾测试
2026-08-22 的 flood_v08 暴雨内涝结果：

| 策略 | EENS kWh | 关键 EENS kWh | 关键恢复率 | 碳排 kgCO2 |
|---|---:|---:|---:|---:|
| A 传统顺序恢复 | 10574.7753 | 4111.7766 | 87.2441% | 38338.9290 |
| B 最小失供恢复 | 2223.1143 | 0 | 100% | 42934.5150 |
| C 碳韧协同恢复 | 4787.6723 | 0 | 100% | 41178.5961 |

C 相对 B 的当前 MRV 为 controlled service budget inventory difference，不是 strict same-service reduction：MRV 已标 same_service_pass=false，因为普通负荷有 8% 服务让步。最终“同服务降碳”只引用 Pareto 合同通过且 epsilon=0 的点；epsilon>0 只写“关键生命线不降级、普通服务在公开预算内受控让步”。

mc30_v04 每策略 29/30 成功，成功率 96.667%，Wilson 95% CI 为 83.330%–99.409%。失败必须保留为失败和 replay 证据，禁止静默删除。

## 2. 总验证合同：先过门，再比较

每行证据对应 run_id × scenario_id × strategy_id × config_sha256 × seed。

| Gate | 通过条件 | 失败处理 | 证据 |
|---|---|---|---|
| G0 输入冻结 | network/scenario/CareTask/factor/config/code 哈希齐全 | INPUT_INVALID，禁止比较 | run manifest |
| G1 求解 | dispatch 与 feedback 正常完成 | SOLVER_FAIL，计入分母 | solve_success、failure manifest |
| G2 物理 | 全时段 is_feasible=true；无热/压/平衡违例；max source adjustment <0.1 kW | PHYSICAL_FAIL | powerflow exports |
| G3 生命线 | 必选 CareTask 全部完成；Tier-1=2/2；通过依赖/deadline/连续时长/电压 | CARE_FAIL | care evaluation |
| G4 服务可比 | C/B 满足相同医院/关键服务 caps；普通服务不超公开 epsilon | SERVICE_NONCOMPARABLE | Pareto anchors/points |
| G5 MRV | verify_mrv_bundle 返回 verified=true | MRV_FAIL | seal、verification、reconciliation |

严格同服务降碳资格：G0∧G1∧G2∧G3∧G4∧G5。  
受控取舍资格：G0∧G1∧G2∧G3∧G5，且必须公开 epsilon。A 仅为传统恢复基线，不用作 C 相对 B 的同服务碳排分母。

### 服务合同
先由 B 生成词典序锚点：医院 EENS cap H*，其他关键 EENS cap K*，普通 EENS cap N*；同时锁定 CareTask 的功率、并发、时窗、deadline、连续时长、依赖和电压。当前容差为 contract_tolerance_kwh=1e-3、feedback_tolerance_kw=0.10。

C 的 epsilon 点必须满足：
- hospital_eens <= H* + tolerance；
- other_essential_eens <= K* + tolerance；
- normal_eens <= N* × (1+epsilon) + tolerance；
- care_contract_pass=true；
- physical_pass=true。

## 3. Baseline 与 A/B/C 主实验

| 组别 | 实现 | 验证角色 | 可写结论 |
|---|---|---|---|
| Baseline-0 | 无故障 case33bw 潮流 golden | 单位/电网/潮流回归 | 物理模型回归通过 |
| A | 传统顺序恢复 | 传统规则基线 | 相对传统方案的韧性变化 |
| B | 最小失供恢复 | 可靠性锚点 | 最小失供服务参考 |
| C | 碳韧协同恢复或 B 的 Pareto epsilon 点 | 碳韧候选 | 在服务合同下的碳-服务取舍 |

### 现有代码可直接执行的 P0 主实验
~~~powershell
cd C:\Users\ASUS\Documents\Codex\2026-08-22\n\work\gridrescue
$env:PYTHONPATH = "$PWD\src"
$stamp = "20260822-validation"
$root = "artifacts\validation\$stamp"
New-Item -ItemType Directory -Force $root | Out-Null

python -m gridrescue.cli --scenario "暴雨内涝" --output "$root\flood"
python -m gridrescue.cli --scenario "台风" --output "$root\typhoon"
python -m gridrescue.cli --scenario "极端高温" --output "$root\heat"

python -m gridrescue.pareto --scenario "暴雨内涝" --strategy "最小失供恢复" --fractions "0,0.01,0.02,0.04,0.06,0.08,0.10" --output "$root\pareto_flood"
python -m gridrescue.pareto --scenario "台风" --strategy "最小失供恢复" --fractions "0,0.01,0.02,0.04,0.06,0.08,0.10" --output "$root\pareto_typhoon"
python -m gridrescue.pareto --scenario "极端高温" --strategy "最小失供恢复" --fractions "0,0.01,0.02,0.04,0.06,0.08,0.10" --output "$root\pareto_heat"

python -m gridrescue.experiments --count 30 --seed 20260822 --output "$root\mc_seed_20260822"
pytest -q
~~~

## 4. 极端天气、压力场景与随机种子

### 当前已可直接运行的天气场景

| ID | 场景 | 故障支路 | 修复 h | PV derating | 碳因子倍率 | 温度 | 核心考验 |
|---|---|---|---|---:|---:|---:|---|
| W-F | 暴雨内涝 | 6,13,27 | 7,10,6 | 0.38 | 1.08 | 25°C | 多点故障、低 PV、联络恢复 |
| W-T | 台风 | 2,18,24,30 | 5,9,8,11 | 0.22 | 1.12 | 27°C | 分散故障、长抢修路径 |
| W-H | 极端高温 | 8,21 | 4,7 | 0.82 | 1.18 | 43°C | 晚峰负荷、排放高峰 |

### P1 压力矩阵

| ID | 配置变化 | 目标 | 正确行为 |
|---|---|---|---|
| X-F1 | W-F：修复×1.5，PV=0.20 | 长停电生命线 | 合同通过或可审计 CARE/PHYSICAL_FAIL |
| X-T1 | W-T：修复×1.5，PV=0.10，抢修距离×1.5 | 分散断线 | 不出现循环和虚假供电 |
| X-H1 | W-H：负荷×1.15，热限×0.90，45°C | 热浪过载 | 不可行点入 failure 表 |
| X-I1 | branch 18 断开 | 无源孤岛 | 无虚拟 slack，服务为零/blocked |
| X-I2 | 移除 GFM/黑启动资格 | 成岛资格 | island passport 标 NO_GFM/BLOCKED |
| X-C1 | node 17 重叠任务 25+12 kW | 并发合同 | 30 kW 失败，37 kW 才通过 |
| X-M1 | 因子 ±20% | 碳结论稳健性 | 报告排序翻转阈值 |

当前 DisasterScenario 已支持故障、修复、PV、碳因子、距离、温度；load_multiplier 和 thermal_limit_multiplier 尚不是显式配置字段。X-H1 补齐版本化 config、输入 hash 和回归测试后才纳入正式统计。

### 随机种子与统计
1. CRN：同一 scenario_id 的 A/B/C 使用同一 scenario JSON 和 SHA；只改变策略。
2. P0：seed=20260822，30 场景 × 3 策略=90 条运行。
3. P1：seeds=[20260822,20260823,20260824,20260825,20260826]，5×30×3=450 条运行。
4. 每条保存 seed、scenario/network/Care/factor/code hash、命令、wall time、artifact path。
5. 所有尝试进入成功率分母；性能统计仅汇总完整过 G0–G5 的配对样本，并报告 n_eligible/N_total。
6. 已冻结场景下策略求解应确定性；未来若引入随机启发式，增加 solver_seed，并每场景跑 10 个 solver seeds。

| 问题 | 主方法 | 强制报告 |
|---|---|---|
| C-B 的 CO2/EENS 差 | paired bootstrap 95% CI，10000 次，固定 analysis seed | mean/median delta、wins/ties/losses、n |
| 成功率/任务通过率 | Wilson 95% CI；同场景配对时 McNemar | attempts/solved/failed、失败原因 |
| Pareto | 合同通过率 + 相对锚点 CO2 差 | epsilon、caps、物理门 |
| 敏感性 | PRCC/标准化回归 + bootstrap CI | 参数范围、失败点 |
| 多指标 | 主终点：CO2、critical EENS、Care 完成率；Holm 校正 | adjusted p 与效应量 |

## 5. 消融与敏感性

### P0 消融
所有消融共享 scenario、CareTask、物理门、seed。

| ID | 从 C 中移除/冻结 | 归因问题 | 关键指标 |
|---|---|---|---|
| AB-0 | B 服务锚点 | 可靠性参考 | H*,K*,N*,EENS |
| AB-1 | 碳目标，保留同服务合同和物理反馈 | 碳改善是否来自碳目标 | delta CO2 |
| AB-2 | 时变碳因子，改固定倍率=1 | 时变碳信号价值 | 高碳时段 grid import |
| AB-3 | CareTask 硬合同，只留类别优先级 | 任务合同价值 | task/Tier-1 pass |
| AB-4 | P/Q feedback，仅事后校验 | 物理反馈淘汰价值 | G2、minV、max loading |
| AB-5 | BESS/PV 可用性 | DER 贡献 | EENS、diesel、renewable |
| AB-6 | 安全联络重构 | 拓扑恢复贡献 | energized nodes、switches |
| AB-7 | GFM/黑启动资格 | 成岛护照价值 | BLOCKED islands、Care |

AB-1~AB-4 为大赛必做。每项须由 feature_flag/config 驱动并写入 config_sha256，禁止手工改数。

### P0 OAT 敏感性
每个 W-F/W-T/W-H 的 B/C 执行，A 保持中心点。

| 因子 | 水平 |
|---|---|
| PV derating | 中心值×[0.5,0.75,1.0,1.25]，截断 0–1 |
| grid carbon multiplier | 中心值×[0.85,0.95,1.0,1.10,1.25] |
| repair duration | 中心值×[0.75,1.0,1.25,1.50] |
| BESS 可用 SOC | 20%,40%,60%,80%,100% |
| Pareto epsilon | 0,1%,2%,4%,6%,8%,10% |
| emission factor | -20%,-10%,0,+10%,+20% |

输出包含每水平绝对值、相对中心值变化、G0–G5、failure gate；图必须标单位与真实范围。P1 全局敏感性使用 80 个 Latin Hypercube 样本，对 CO2、EENS、CarePass、G2Pass 做 PRCC。

## 6. CareTask 与 Pareto 验证

### CareTask P0 断言
- CT-01：四任务在三天气 × A/B/C 中均有 definition SHA、功率/电压/时窗证据。
- CT-02：node 17 并发 25+12 kW；30 kW 必须失败，37 kW 才通过。
- CT-03：ICU 某小时电压设为 0.96 pu；即使系统潮流可行，任务仍因 0.97 pu 门失败。
- CT-04：10000 kW 不可能任务必须形成可审计 anchor failure，不得进入 Pareto frontier。
- CT-05：未知依赖和循环依赖必须 fail fast。
- CT-06：deadline 违约与连续供电中断分别产生 reason code。

### Pareto P0
每个天气扫描 epsilon=0,1,2,4,6,8,10%，共 21 点。每点检查：
1. solve_success、feedback_converged、physical_pass、care_contract_pass；
2. 医院/其他关键 EENS 不超过锚点 caps；
3. normal EENS 不超过 epsilon 预算；
4. 只将非支配且过门的点放入 frontier；
5. 淘汰点写 pareto_failures.csv，含 failure_phase、failure_reason、hash；
6. 推荐点报告 epsilon、普通 EENS 增量、CO2 差、minV、max loading、Care 完成率。

当前 flood Pareto v07 样例：epsilon 从 0% 到 6%，CO2 从 42912.93 降至 41156.69 kgCO2，Care/物理通过。正式答辩需在三天气和随机样本复现，不展示单场景孤证。

## 7. MRV 篡改验证

当前 seal 是文件完整性机制，不是第三方认证、可信时间戳或不可篡改存储。统一答辩表述：
“bundle 通过文件完整性、动作链和排放算式验证；结果为合成赛事数据，不主张现场实测或第三方核证。”

| ID | 篡改对象 | 操作 | 期望 |
|---|---|---|---|
| MT-01 | activity ledger | 修改 energy_kwh | hash mismatch，verified=false |
| MT-02 | factor snapshot | 修改 factor value | hash mismatch，verified=false |
| MT-03 | inventory | 修改 emission_value | hash mismatch 或方程失败 |
| MT-04 | actions | 修改 requested state/prev hash | hash chain 或 terminal hash 失败 |
| MT-05 | manifest | 修改场景/config hash | manifest hash mismatch |
| MT-06 | evidence 文件 | 删除输入/输出 | missing file，verified=false |
| MT-07 | actions 顺序 | 删行/重排序 | action chain/terminal hash 失败 |
| MT-08 | 完整本地重封存 | 同步伪造索引与 seal | 当前边界；需外部签名/对象锁 |

### MT-01 可直接执行
~~~powershell
$env:PYTHONPATH = "$PWD\src"
$src = "artifacts\flood_v08\mrv\run-7e495c4e6e73c188"
$dst = "artifacts\validation\mrv_tamper_MT01"
Remove-Item -Recurse -Force $dst -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force $src $dst
python -c "from pathlib import Path; import pandas as pd; p=Path(r'artifacts\validation\mrv_tamper_MT01\outputs\activity_energy_hourly.csv'); d=pd.read_csv(p); d.loc[0,'energy_kwh']=float(d.loc[0,'energy_kwh'])+1; d.to_csv(p,index=False)"
python -c "from gridrescue.mrv import verify_mrv_bundle; r=verify_mrv_bundle(r'artifacts\validation\mrv_tamper_MT01',write_result=True); print(r); assert r['verified'] is False and r['errors']"
~~~

## 8. 可直接执行实验矩阵与 10 天排程

| 批次 | 规模 | 交付物 | 优先级 |
|---|---:|---|---|
| PF-0 | 1 | golden physical pytest log | P0 |
| PF-1 | 3 天气 × A/B/C=9 | 三个 sealed run bundle、主表 | P0 |
| PF-2 | 3 天气 × 7 Pareto 点=21 | anchors/points/frontier/failures | P0 |
| PF-3 | 30 场景 × 3=90 | MC results/summary/failure replay | P0 |
| PF-4 | CT-02 至 CT-06 | Care 边界测试/CSV | P0 |
| PF-5 | MT-01 至 MT-07 | tamper matrix/verify JSON | P0 |
| PF-6 | 7 图+2表 | PNG/SVG 和 source CSV | P0 |
| R-1 | 5 seeds×30×3=450 | 稳健性 CI | P1 |
| R-2 | OAT | tornado/阈值表 | P1 |
| R-3 | 80 LHS×3 | 全局敏感性 | P1 |
| R-4 | 7 消融×3天气×2–3 seed | 机制归因 | P1 |

| 日期 | 交付 |
|---|---|
| D1 2026-08-22 | 冻结 inputs 与验证目录；PF-0/PF-1 |
| D2 | PF-2 Pareto、Care 导出检查 |
| D3 | PF-3、failure replay |
| D4 | PF-4、PF-5 |
| D5 | 主表、统计、首版图 |
| D6 | AB-1~AB-4 feature flag 与回归 |
| D7 | OAT、X-I1/X-I2/X-C1 |
| D8 | 多 seed MC 与 CI |
| D9 | 全部重跑、证据 hash、演示演练 |
| D10 | 冻结 final_validation_bundle、只读备份、彩排 |

## 9. 预期 CSV Schema

### experiment_runs.csv
主键 run_id。一行=场景×策略×配置×seed。

| 字段 | 类型 | 含义 |
|---|---|---|
| run_id,batch_id,timestamp | string | 唯一运行与批次 |
| scenario_id,scenario_name,scenario_sha256 | string | 场景身份 |
| strategy_id,strategy_name | string | A/B/C |
| ablation_id,sensitivity_id | string/null | 配置标签 |
| seed,solver_seed | int/null | 随机性 |
| network_sha256,care_definition_sha256,factor_snapshot_sha256,config_sha256,code_bundle_sha256 | string | 输入冻结 |
| solve_success,physical_pass,care_pass,service_contract_pass,mrv_verified,eligible_strict,eligible_controlled | bool | G1-G5 与资格 |
| failure_gate,failure_phase,failure_reason | string/null | 失败不可丢失 |
| wall_time_s,peak_memory_mb | float/null | 性能 |
| artifact_dir,replay_manifest_ref | string | 证据定位 |

### strategy_metrics.csv
复合主键 run_id,metric_name。字段：
run_id,scenario_id,strategy_id,metric_name,metric_unit,value,numerator,denominator,data_class,status,source_file,source_row_hash。

主指标：eens_kwh、critical_eens_kwh、critical_recovery_pct、restoration_time_h、peak_unserved_kw、total_carbon_kg、grid/diesel/crew carbon、renewable_consumed_kwh、min_voltage_pu、max_branch_loading_pct、max_source_adjustment_kw、care_completion_rate、tier1_completed_count、solve_success。

### paired_deltas.csv
主键 scenario_id,seed,candidate_strategy,reference_strategy,comparison_mode。字段：
metric_name,candidate_value,reference_value,delta_abs,delta_pct,common_scenario_sha256,care_contract_pass,physical_pair_pass,same_service_pass,epsilon,eligible_strict,eligible_controlled。

### care_task_evaluation.csv
主键 run_id,strategy,task_id。冻结现有字段并新增 scenario_id,seed,config_sha256,physical_pass。保留：
definition_sha256、required_energy_kwh、credited_energy_kwh、maximum_coincident_required_kw、minimum_served_kw、minimum_voltage_pu、deadline/duration/dependency/window pass、task_complete、failure_reason_codes。

### pareto_points.csv
主键 run_id。字段：
scenario,strategy,point_kind,normal_allowance_fraction,hospital_eens_cap_kwh,other_essential_eens_cap_kwh,normal_eens_cap_kwh,hospital_eens_kwh,other_essential_eens_kwh,normal_eens_kwh,total_carbon_kg,care_contract_pass,physical_pass,feedback_converged,max_source_adjustment_kw,min_voltage_pu,max_branch_loading_pct,non_dominated,failure_phase,failure_reason,seed,config_sha256,mrv_verified。

### sensitivity_results.csv
主键 scenario_id,seed,strategy_id,parameter_name,parameter_value。字段：
parameter_unit,center_value,relative_change,all_G0_G5_pass,eens_kwh,critical_eens_kwh,total_carbon_kg,care_completion_rate,min_voltage_pu,max_branch_loading_pct,failure_gate,artifact_dir。

### mrv_tamper_results.csv
主键 tamper_run_id。字段：
tamper_id,source_bundle,source_manifest_sha256,mutation_file,mutation_description,expected_detected,verified,error_count,verification_errors_json,detection_pass,executed_at,artifact_dir。

### validation_summary.csv
主键 experiment_id,scenario_group,strategy_or_comparison,metric_name。字段：
n_total,n_solved,n_G2,n_G3,n_G4,n_G5,estimate,ci_lower,ci_upper,test_name,p_value_adjusted,effect_direction,claim_class,figure_ref。

## 10. 答辩固定 7 图 + 2 表

| 编号 | 内容 | 必须标注 |
|---|---|---|
| Fig1 | 三天气 A/B/C：EENS、critical EENS、CO2 | n、失败数、G4 状态 |
| Fig2 | 随机场景 C-B 配对 slope/raincloud | 同场景、95% CI |
| Fig3 | Pareto：普通 EENS 对 CO2 | epsilon、合同 caps、淘汰点 |
| Fig4 | 24h 韧性恢复曲线 | 故障/修复时刻、Care 时窗 |
| Fig5 | minV/max loading/source adjustment 热图 | 0.95/0.97 pu、100%、0.1kW 阈值 |
| Fig6 | 敏感性 tornado | 中心值、参数范围、失败点 |
| Fig7 | MRV 信任链 | integrity-only 边界 |
| Tab1 | 三主终点：CO2、critical EENS、Care pass | effect + CI + evidence path |
| Tab2 | 失败/反例 | gate、原因、replay、处置 |

禁止：只展示成功样本；C/B 服务不等却写同服务；只展示一个 Pareto 点；将 E 类合成 CareTask 说成真实医院数据；截断 Y 轴不注明。

## 11. P0 发布前测试清单

### 基础与物理
- [ ] pytest -q 完整通过并保存日志、Python/OS/requirements hash。
- [ ] case33bw golden：33 节点、32 闭支路、3715 kW/2300 kvar、p_loss≈202.6771 kW、minV≈0.91309 pu、slack≈3917.6771 kW。
- [ ] 三天气×A/B/C 都导出 dispatch、powerflow、Care、island passport、MRV。
- [ ] 所有主张运行均 24/24 物理可行，无热/压/平衡异常，source adjustment<0.1kW。
- [ ] 无源孤岛和无 GFM 反例不出现虚假供电。

### 公平性、Care 与 Pareto
- [ ] 每个 scenario_id 内 A/B/C 的 scenario SHA 完全相同。
- [ ] strict same-service 结论只使用 epsilon=0 且 G4 通过点。
- [ ] epsilon>0 结论公开服务预算与 normal EENS 增量。
- [ ] 四个 CareTask 均有 definition SHA；Tier-1=2/2。
- [ ] 30 vs 37 kW 并发、0.96 pu 电压、不可能任务、依赖环、deadline/连续时长反例全部通过。
- [ ] Pareto 每点都有 anchors、caps、epsilon、Care、物理、feedback；失败点保留且不入 frontier。

### 随机性、统计与 MRV
- [ ] seed=20260822 的 30 场景批可重复，scenario JSON/SHA 相同。
- [ ] 每个 failure manifest 可 replay，结果保存。
- [ ] summary 同时报 attempt/solved/failed、Wilson CI、bootstrap seed、有效 n。
- [ ] C-B 使用 paired_deltas；无未配对样本混入主统计。
- [ ] 三个 sealed MRV bundle 均 verify=true，carbon reconciliation 差异在浮点容差内。
- [ ] MT-01 至 MT-07 全部 detected，输出 mrv_tamper_results.csv。
- [ ] final_validation_bundle 只读备份，包含总索引、图源 CSV、命令、README、hash。

## 12. 答辩结论模板

1. “进入主比较的方案均通过逐时 P/Q 潮流、电压、热限和功率平衡；失败场景保留为可 replay 证据。”
2. “生命线不是类别口号，而是 ICU、手术、冷链、通信的任务级功率、时间、连续性、依赖和电压合同。”
3. “严格同服务降碳和 epsilon 受控服务取舍分开报告，避免以服务下降换取减排结论。”
4. “每个排放数字可回溯至场景、因子、活动账、清单、动作链与 seal；当前验证为文件完整性和方程验证，不替代第三方核证。”

## 13. 本轮核查记录

已只读核对 README、三策略、Monte Carlo/replay/CI、CareTask 单测、Pareto 合同、MRV 验证结构、flood_v08、pareto_flood_v07 与 mc30_v04。现有可执行命令见第 3 节和第 7 节；消融和热限/负荷配置为 P1 实施项，进入正式统计前须增加版本化 config、hash 和回归测试。

