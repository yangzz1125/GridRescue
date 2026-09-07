# GridRescue Wave 6：CareTask 建模与医疗场景答辩红队审查

> 审查范围：只审阅 src/gridrescue/care.py、src/gridrescue/dispatch.py、src/gridrescue/pareto.py，以及调用路径与现有 tests；不修改业务代码。
>
> 结论先行：CareTask 已把“医院/生命线”从泛化关键负荷推进到节点、时间窗、最低功率的可检查对象。最低功率窗口可进入空间调度硬约束，事后可用节点 dispatch 和电压校验生成任务级结果。这是可用原型增量。  
> 但它仍是 E 类合成模板，不是医疗运行模型或临床安全标准。最大断链为：默认 CareTask 没有被 pareto.py 注入任何 anchor 或 epsilon candidate 合同；deadline、持续时长、依赖、任务电压均只在事后评价，未进入优化或 Pareto 资格门槛。故不得声称“低碳 Pareto 已在医疗任务不降级条件下求得”。

## 1. 已确认事实与可用边界

| 已确认事实 | 代码/产物证据 | 答辩允许口径 | 禁止拔高 |
|---|---|---|---|
| 4 个默认任务：ICU、应急手术、冷链、应急通信 | care.py 的 default_care_tasks | 合成生命线任务模板 | 真实医院负荷/临床标准 |
| 任务有节点、tier、最小kW、时间窗、deadline、持续时长、电压、依赖、数据等级字段 | CareTask dataclass | 任务合同数据模型已定义 | 所有字段都已优化 |
| ServiceTaskRequirement 可在调度中施加逐节点逐时最低功率 | dispatch.py：served_critical >= task_required_kw | 最低功率窗口可作为 LP 硬约束 | 临床任务全约束已实现 |
| evaluate_care_tasks 检查功率、电压、连续性、deadline 与依赖 | care.py：evaluate_care_tasks | 可生成任务级通过/失败证据 | 已形成医疗闭环控制 |
| Pareto 对 hospital、essential、normal 分类 EENS 做服务合同 | pareto.py 的 _service_totals 与 ServiceContract | 已有类别级同服务 Pareto | 已有 task-aware Pareto |
| pareto.py 未 import CareTask，也未传 task_requirements | pareto.py 调用链 | CareTask-Pareto 尚未接线 | 医疗任务保证低碳前沿 |
| 现有 tests 未见 CareTask、deadline、依赖或 task-voltage 用例 | tests 目录检索 | Pareto 基础回归已存在 | 医疗模型已充分验证 |

## 2. P0 逻辑缺陷：答辩前必须补

### P0-1：CareTask 与 Pareto 断链
- **代码事实**：care_task_requirements 可生成 ServiceTaskRequirement；但 pareto.py 创建 ServiceContract 时未设置 task_requirements，也未调用 evaluate_care_tasks。
- **风险**：hospital 总 EENS 合格的点，仍可能在 node 17 的手术窗口或 node 2 的 ICU 时段失败；frontier_eligible 并不代表医疗任务完成。
- **评委问题**：你们把医院总 EENS 压低，是否恰好把电留给了不承担手术任务的医院节点？
- **验收口径**：每个 Pareto run_id 都输出 care_task_evaluation_runid.csv。Tier-1 全完成、声明为硬约束的 Tier-2 也通过，才可 frontier_eligible=true。
- **负向测试**：保持 hospital 总 EENS 不变，仅令 node 17 手术窗口失供；断言为 task_contract_failure 且不进 frontier。

### P0-2：优化器只认识最低 kW，deadline、持续时长、电压、依赖没有进入合同
- **代码事实**：ServiceTaskRequirement 仅含 task_id、node_id、start_hour、end_hour、min_kw；care_task_requirements 丢弃 deadline_hour、min_duration_h、voltage 阈值与 dependencies。
- **风险**：所谓任务约束实质仅是全窗口每小时最低有功功率；最关键的医疗语义全为后验标签。
- **评委问题**：若任务 0–5h 必须供电，为什么又写 deadline 和持续时长，却不纳入决策？
- **验收口径**：明确三种 service_mode：continuous_window、contiguous_block、cumulative_energy。Tier-1 连续任务用逐时硬约束；可延迟任务须使用 start binary 或离散候选窗；依赖任务须在依赖完成后启用。
- **负向测试**：窗口 0–5h、deadline=2h、持续3h，只有3–5h供电；断言任务失败且不能被 Pareto 评为合格。

### P0-3：依赖按列表顺序计算，既无 DAG 验证也无时序验证
- **代码事实**：evaluate_care_tasks 内用 completed 字典跟随单个 for-loop；dependency_pass 只看此前是否已处理。
- **风险**：JSON 排列顺序会影响结果。未知依赖、循环依赖、依赖晚完成而子任务早开始均无法可靠审计。
- **评委问题**：把任务 JSON 顺序调换，结果会变吗？
- **验收口径**：加载时校验 task_id 唯一、依赖存在、无环；拓扑排序后评价；输出 completion_hour 与 dependency_ready_hour。
- **负向测试**：前向引用、未知依赖、A→B→A 环、依赖完成晚于子任务开始，分别必须产生结构化错误/失败码。

### P0-4：duration_pass 被 window_pass 吞没
- **代码事实**：task_complete 同时要求 duration_pass 和 window_pass。全窗口通过时最长连续时长必然是全窗；一小时失败时，即便达到 min_duration_h，window_pass 仍失败。
- **风险**：min_duration_h 不能表达“deadline 前连续运行 3h 即完成”的任务，却给人已经支持的印象。
- **评委问题**：连续时长与全窗不间断供电究竟选哪个？
- **验收口径**：每任务显式 service_mode；报告输出实际合格区间，不只输出 first_qualified_hour。
- **负向测试**：窗口0–5h、连续3h，供电状态 false,true,true,true,false,false；block 模式应通过，continuous_window 模式应失败。

### P0-5：同节点多任务的负荷会相加，但无回路/计量定义，容易重复计量
- **代码事实**：node 17 在 0–5h 同时有手术25kW与冷链12kW，调度约束把需求相加为37kW；当前该节点 critical envelope 为约56.33–60.14kW，因此可行。
- **风险**：37kW 是额外负荷、基荷内切片，还是同一 UPS 的重复声明，当前无法辨别。
- **评委问题**：手术和冷链是否在同一院内负荷里被重复算了两次？
- **验收口径**：每个任务增加 load_accounting_mode（exclusive_slice/additive_load/shared_capacity）和 source_load_id；同一 source_load_id 不能重复计量。
- **负向测试**：shared slice 总和超可分配切片必须失败；additive 任务超 envelope 必须 infeasible；重复 source_load_id 明确拒绝。

### P0-6：任务电压是后验判据，Pareto 资格可能与医疗电压要求不一致
- **代码事实**：调度只加 served_critical 下限，task 电压由 evaluate_care_tasks 后验检查。通用物理合格门槛约为0.95pu，而 ICU 模板要求0.97pu。
- **风险**：0.960pu 可以全网 physical pass，但 ICU task fail；当前 Pareto 仍可能推荐该点。
- **评委问题**：系统说0.96pu合格，ICU说0.97pu，最终到底成功还是失败？
- **验收口径**：拆分 grid_physical_pass、care_voltage_pass、care_task_pass、claim_eligible；task voltage fail 直接取消推荐和减排资格。
- **负向测试**：注入 ICU 0.960pu、全网无通用低压；断言 physical pass 但 care contract fail。

### P0-7：时间步长固定为1h，能量和任务时间语义不可迁移
- **代码事实**：required_energy_kwh=min_kw×len(hours)，各种 EENS 对 kW 直接求和，range(24) 固化。
- **风险**：迁到15min/30min 时，kWh、连续时长、deadline 与碳核算均会失真。
- **评委问题**：UPS 转供和手术窗口是分钟级，为什么直接把 kW 求和成 kWh？
- **验收口径**：manifest 带 time_step_h；所有能量用 sum(kW)×Δt；duration=合格步数×Δt。
- **负向测试**：同一6h任务以1h和0.25h网格求解，能量和通过状态一致。

### P0-8：默认医学参数无来源、无版本化任务字典
- **代码事实**：28/25/12/20kW、0.97pu、0–5h等写在代码常量中；虽然 data_class 已写 E_synthetic_task_template，但没有外部定义文件、来源、审阅人和版本。
- **风险**：评委会判断为用医疗外衣包装调参。
- **评委问题**：这些数字来自哪家医院、哪种设备、哪份标准？
- **验收口径**：迁出为 data/care_task_template_v1.json，逐字段带 source_type、evidence_level、approved_by、scope、uncertainty。没有医疗专家背书时永久标 E 类合成。
- **负向测试**：缺少 source/evidence/data_class 的任务定义必须阻断对外报告或醒目标红。

## 3. P1 审计与模型缺口

| ID | 缺口 | 必新增负向测试 | 验收口径 |
|---|---|---|---|
| P1-1 | CareTask 无参数校验：负 tier、负功率、deadline 越窗、duration=0、Vmin>Vmax、重复ID未被拒绝。 | 逐项非法定义。 | 加载阶段 fail fast，错误含 task_id 与字段。 |
| P1-2 | flow/dispatch 缺行时被填0，数据缺失与真实失电混为一谈。 | 删除一个节点-时段 evidence。 | 区分 DISPATCH_MISSING、FLOW_MISSING、DEENERGIZED、POWER、VOLTAGE。 |
| P1-3 | tier 只出现在统计，未进入合格策略。 | Tier-1 fail/Tier-2 pass；反向用例。 | claim policy 明确：Tier-1全通过为最低门槛，Tier-2可配置。 |
| P1-4 | 所有任务都挤在 served_critical；normal任务无明确模型。 | task指向normal node。 | 必须显式 load_channel；禁止静默跨类。 |
| P1-5 | task constraint infeasible 没有 task级 slack/最小冲突集。 | 多任务冲突。 | 失败说明 hour/node/task ids 与最小缺口。 |
| P1-6 | deadline 只看首次满足，不记录满足后的连续区间。 | T0短暂供电后持续掉电。 | completion_interval 必须满足 mode。 |
| P1-7 | 稳态电压不代表医疗电能质量。 | 缺 frequency/THD/transfer evidence。 | 显示 quality_not_verified，不能称临床安全。 |
| P1-8 | data_class 是文本，不进入 claim gate。 | 混合A/B/E任务。 | E类任务的临床/商业 claim=false。 |
| P1-9 | write_care_tasks 首次写定义，后续同目录变更不覆写/比hash。 | 定义A后写定义B。 | 定义hash进入evaluation/summary；变更必须新版本。 |
| P1-10 | summary 只报数量，缺失败任务和run linkage。 | 有失败任务。 | 含 run_id、definition hash、失败task、原因直方图、数据等级。 |
| P1-11 | Pareto run_id hash 不含任务定义、因子/DER/负荷/solver版本。 | 修改min_kw或Vmin。 | run identity或manifest hash 必须变化。 |
| P1-12 | nondominance 只比较 normal EENS 与 carbon。 | 人工points混入care fail。 | care fail点绝不得 nondominated。 |

## 4. 医疗假设红队问答（12问）

1. **28kW ICU、25kW手术等从哪来？**  
   最佳回答：均为E类合成压力模板，用于验证任务合同接口，不是医院测量或医疗标准。

2. **ICU为何没有 N+1、UPS、ATS、院内柴油和设备清单？**  
   最佳回答：当前只验证配网侧最低供电 slice，不验证院内配电可靠性或临床安全。

3. **手术为何固定0–5h、deadline=0且连续6h？**  
   最佳回答：这是灾时worst-case合成脚本，不代表排班或临床流程；现版本不主张手术排程优化。

4. **node17 的手术与冷链会不会重复计量？**  
   最佳回答：当前按可加切片处理，最低37kW，未超过合成 envelope；真实应用需通过回路和source_load_id确认。

5. **IEEE 33 的节点2/17为何叫医院？**  
   最佳回答：标准算例没有医院含义，医院标签是本项目服务情景附加数据。

6. **0.97pu 是医疗设备标准吗？**  
   最佳回答：不是，只是更保守的合成稳态阈值；设备标准须来自厂商/医院规范。

7. **频率、谐波、闪变、相不平衡、切换瞬断呢？**  
   最佳回答：当前只做配网稳态P/Q与电压筛查；临床电能质量不在已验证边界。

8. **冷链为何24h连续12kW，不考虑温度惯性？**  
   最佳回答：保守供电模板，未建热模型；不能说已模拟药品/血液温控。

9. **通信是否有双路由、卫星或移动基站？**  
   最佳回答：无；当前只是电力侧优先级节点，不是通信网络韧性模型。

10. **类别级hospital EENS会掩盖具体任务失败吗？**  
   最佳回答：会，因此必须把Tier-1 task合同接入Pareto资格门槛。

11. **柴油、储能和转供可能造成短瞬断，如何保证手术？**  
   最佳回答：当前不模拟毫秒级切换；必须依赖ATS/UPS，模型只陈述小时级稳态合同。

12. **双碳会不会以患者服务换来？**  
   最佳回答：Tier-1任务必须硬通过；任何任务、电压、证据失败的低碳点没有减排/推荐资格。

## 5. 必新增负向测试

| 优先级 | 测试 | 必须断言 |
|---|---|---|
| P0 | task合同注入Pareto | 每个run都有task requirements和任务级evaluation。 |
| P0 | 类别EENS通过但手术任务失败 | care_contract_pass=false，frontier_eligible=false。 |
| P0 | ICU 0.960pu | grid physical pass 与 care voltage fail 被分开记录，点不入前沿。 |
| P0 | 任务窗口最低供电 | 任何硬窗口缺供不可被绿灯。 |
| P0 | dependency unknown/cycle/order invariance | 明确错误；JSON排序不影响结果。 |
| P0 | duration mode | contiguous block 与 continuous window 不混淆。 |
| P0 | overlapping task accounting | additive/shared/exclusive 的累加或拒绝符合定义。 |
| P0 | task definition validation | 功率/时间/电压/tier/重复ID fail fast。 |
| P0 | missing evidence | DATA_MISSING 不得伪装成 POWER/VOLTAGE，也不得算通过。 |
| P0 | task definition hash | 改 min_kw、window或Vmin后run identity必须变化。 |
| P1 | 非1h时间步 | 1h与15min等价输入的kWh/状态一致。 |
| P1 | Tier policy | Tier-1失败一定阻断claim；Tier-2按配置。 |
| P1 | task infeasibility diagnosis | 返回task_id、node、hour、缺口。 |
| P1 | quality evidence | 无频率/谐波/切换证据只能标quality_not_verified。 |
| P1 | failed point nondominance | care fail点不得进入nondominated/frontier。 |

## 6. 统一验收口径

### 6.1 四层状态
| 字段 | 通过条件 |
|---|---|
| solver_pass | solver optimal/accepted |
| grid_physical_pass | 所有时段拓扑、P/Q、电压、热限额、孤岛平衡通过 |
| care_task_pass | required task满足功率、时间、依赖、任务电压和数据完整性 |
| claim_eligible | 前三项通过，且服务合同/数据等级与碳基线可比 |

只有 claim_eligible=true 才可写“低碳”“减排”“推荐”。

### 6.2 Tier 政策
- Tier-1：100%任务完成；窗口内逐时最低功率；任务电压满足；数据缺失即失败。
- Tier-2：默认硬约束；若允许让步，必须合同化、图例公开，且不得宣称医疗全保供。
- 普通负荷：仅进入 normal EENS epsilon；绝不与医疗任务完成混算。

### 6.3 时间和审计
- 每次运行记录 time_step_h；能量=功率积分。
- 每任务输出 completion interval、failure reason、data class、definition hash。
- Pareto point 增加 care_task_pass、tier1_pass、tier2_pass、care_failure_count、care_definition_hash、claim_eligible。
- 失败点一律保留 replay；禁止用 aggregate hospital EENS 覆盖任务失败。

## 7. 30秒答辩口径

> “我们没有把 IEEE 33 的两个节点称成真实医院，也没有把类别级医院EENS当作临床保供。当前CareTask是带数据等级的合成生命线模板：它把最低功率与时间窗口映射进配网调度，并用潮流结果做任务级核验。只有Tier-1任务、稳态电气可行和同服务合同同时通过时，我们才讨论低碳方案；任务失败、数据缺失或电压不达标的候选会保留为失败记录，不进入碳Pareto推荐。院内UPS、切换瞬断和临床标准不属于当前已验证边界。”

## 8. 红队判定

- **当前可说**：合成医疗任务模板、节点时窗最低功率约束接口、任务级后验功率/电压评价已具备。
- **当前不可说**：医疗任务已经驱动Pareto；医院临床连续性已验证；默认kW/电压阈值来自医疗标准；系统可直接指导医院应急供电。
- **一等奖最低修复线**：完成P0-1至P0-8及负向测试。若时间不足，宁可把CareTask降为“待接入的任务级审计模块”，也不要把定义字段包装成已实现医疗优化能力。

