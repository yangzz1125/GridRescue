# GridRescue Wave 4：一等奖答辩红队（50 问）

> **定位**：以“第五届中国研究生双碳创新与创意大赛一等奖”答辩评委的标准发问。本文件只审阅当前代码、三场景 v03 产物、mc30_v04 产物与 research_wave 文档；不把设计文档当作已经实现的功能。
>
> **审阅结论先行**：项目已有一个可复跑的 IEEE 33 节点、三策略、逐时资源调度、后验潮流校验和报告导出原型；但冲一等奖的六个硬伤仍是：**真实数据/因子证据不足、低碳比较服务不等价、优化—电气可行性仍是迭代后验耦合、30 组模拟不足以声称稳健、AI功能尚未实装、客户/付费/部署证据不足**。答辩必须把“已实现”“当前结果”“十天计划”严格分层。
>
> **证据标记**：实现/产物为当前可复查；设计仅证明团队识别了问题；缺失表示仓库当前未见可供复核的证据。
>
> **审阅快照**：
> - 三命名场景：artifacts/flood_v03/、artifacts/typhoon_v03/、artifacts/heat_v03/。
> - 30 组压力测试：artifacts/mc30_v04/monte_carlo_summary.csv；每策略 30 次尝试、29 次成功、1 次失败，成功率 96.667%，Wilson 95% 区间 83.33%–99.41%。
> - 唯一失败案例：artifacts/mc30_v04/monte_carlo_failures.json 中 scenario-0018，三策略均因空间资源调度 infeasible 而失败。
> - 代码依赖仅含 NumPy/Pandas/NetworkX/CVXPY/Streamlit/Plotly：pyproject.toml；当前没有训练、推理、特征、模型版本或在线校准依赖/模块。
> - 当前目录没有可用 Git 仓库元数据（git status 报 not a git repository）；因此报告内所谓 commit 级追溯尚无现成证据。

## 一、数据真实性、来源与外部校准（1–10）

### 1. 你们为什么把 IEEE 33 节点算例讲成“某沿海区域”的结论？真实馈线在哪里？
- **最佳回答**：我们不把 IEEE 33 结果表述为真实某地工程效益。当前是标准算例上的概念验证；网络拓扑、P/Q 与 R/X 来自 case33bw，而 DER、关键负荷、热限额和灾害参数属于工程假设。答辩仅宣称“方法可复现”，真实试点结论须以脱敏馈线校准包为准。
- **证据文件**：src/gridrescue/case33_data.py；data/case33bw.m；artifacts/*_v03/network_manifest.json；README.md 的“当前模型限制”。
- **当前缺口**：无脱敏馈线、无台账映射、无参数误差或外部留出验证。
- **10天内修复动作**：D1–D2 建立 data/provenance/network_manifest.csv；引入一套公开 69/123 节点基准并跑同协议；争取一份脱敏 10–20 节点馈线参数，出“标准算例/区域化假设/真实数据”三层标签表。

### 2. 33 节点的基础潮流最低电压是 0.9131 pu，本身就低于常见运行下限；你们的网络是不是一开始就不合格？
- **最佳回答**：是，当前 case33bw 原始重载基准的最低电压为 0.9131 pu，不能拿它直接代表一个合格的现实配网。它只作为公开压力算例。恢复场景中报告的电压是经过服务削减/反馈后得到的候选状态，必须与“基准原始工况”分开展示。
- **证据文件**：artifacts/flood_v03/network_manifest.json 的 base_powerflow.minimum_voltage_pu=0.913090；research_wave/case33_powerflow_audit.md。
- **当前缺口**：无基准工况整改、无与 MATPOWER/pandapower 的逐节点 golden 对标产物。
- **10天内修复动作**：D3 导出 baseline_pf_golden.csv、baseline_pf_error.csv；展示原始压力算例与“满足工程电压门槛的校准工况”两套结果，禁止混称。

### 3. 三类灾害的故障支路、修复时长、PV 降额究竟来自哪里？
- **最佳回答**：当前三类场景是可复现的压力测试模板，不是历史灾害复盘。代码中灾害—故障映射均为明确设定；我们将其用于检验策略差异，而不宣称对台风/内涝故障的预测准确率。
- **证据文件**：src/gridrescue/scenarios.py 的 SCENARIOS；三份 artifacts/*_v03/report_carbon_resilient.md。
- **当前缺口**：无气象时间窗、无线路暴露度、无历史停电/抢修工单和拟合方法。
- **10天内修复动作**：D4–D5 缓存公开 ERA5/Open-Meteo 历史时序，新增 weather_source.csv、情景映射参数和 seed；至少给出一个公开天气事件的回放案例及“仅方法验证”标签。

### 4. 24 小时负荷、光伏和电网碳因子曲线为什么是公式+随机扰动，而不是实测？
- **最佳回答**：当前 hourly_profiles() 是固定种子下的合成时序，用于保证复跑和控制变量；它不等于实测数据。演示固定 seed 服务于可复现，统计结论需在公开/实测时序上复验。
- **证据文件**：src/gridrescue/scenarios.py 中 hourly_profiles 和 sample_fault_scenarios。
- **当前缺口**：无原始时序 CSV、数据字典、缺失值规则或生成参数图。
- **10天内修复动作**：D4 将曲线写成版本化 CSV，新增 source_type、source_url、retrieved_at、seed；UI 以不同颜色区分“实测/公开/合成”。

### 5. 30 个蒙特卡洛情景都是同一生成器、同一 seed，怎么证明不是“可控的漂亮案例”？
- **最佳回答**：目前证明的是代码在 30 个共同随机合成压力情景下有 29/30 可解，而非证明现实稳健性。我们保留失败案例，且不会把 30 个样本称为充分统计证据。
- **证据文件**：artifacts/mc30_v04/monte_carlo_summary.csv；artifacts/mc30_v04/monte_carlo_failures.json；src/gridrescue/scenarios.py。
- **当前缺口**：无多 seed、无分布校准、无场景独立性说明；N=30 对尾部风险不够。
- **10天内修复动作**：D9 跑至少 5 个 seed × 100 场景；输出按 seed 分组的均值、95%CI、P90、CVaR 与完整失败清单，答辩只引用聚合后数字。

### 6. scenario-0018 三个策略同时失败，你们为何还敢说“物理硬校验”？
- **最佳回答**：恰恰因为失败被保留而不是静默填零。该场景表明资源/拓扑组合在空间调度阶段不可行；产品应明确显示“无可执行方案”，转入人工处置或负荷分级切除，而不是输出虚假恢复计划。
- **证据文件**：artifacts/mc30_v04/monte_carlo_failures.json；src/gridrescue/experiments.py 的失败记录与 replay 逻辑；tests/test_experiments.py。
- **当前缺口**：无失败根因分解（何时、哪个岛、P/Q/容量/服务约束触发）；无 UI 处置建议。
- **10天内修复动作**：D6/D9 生成 failure_diagnosis.csv（岛、小时、缺口、约束）；对 scenario-0018 出最小不可行证据和三种人工降级方案。

### 7. DER 的容量、位置、储能 SOC、柴油容量怎样获得？有没有选择性调参？
- **最佳回答**：当前这些均是透明工程假设，非资产台账。我们会将它们从模型常量改为可审计输入，并报告关键参数的敏感性；不把单点假设包装成现场配置。
- **证据文件**：src/gridrescue/dispatch.py 的 ResourceConfig；src/gridrescue/network.py 的节点资源字段；README.md。
- **当前缺口**：无设备清单、无铭牌、无可用率、无 SOC 初始来源。
- **10天内修复动作**：D2 建 der_asset_registry.csv，逐项标注 assumption/meter/nameplate 与不确定度；做 ±20% DER 容量、SOC、柴油上限敏感性图。

### 8. “关键负荷”是谁定义的？医院、通信、居民、工业是否被真实区分？
- **最佳回答**：当前关键等级是算例上的分类标签，仅用于方法验证；未绑定真实用户。公平与保供结论仅针对该标签体系，真实部署需由业主/应急预案定义负荷分级和最晚恢复时限。
- **证据文件**：src/gridrescue/restoration.py 的 build_demand_frame、build_node_demand_frame；research_wave/market_story_innovations.md。
- **当前缺口**：无关键用户清单、分级规则、业务任务或 SLA 来源。
- **10天内修复动作**：D1 新增匿名 critical_load_taxonomy.md 与 3 类任务模板（生命线/公共服务/普通）；每级写明来源、上限和可替换参数。

### 9. 热限额写着 engineering thermal limits v0.2，到底是什么导线、多少 A、如何换算？
- **最佳回答**：MATPOWER case33bw 没给实际 rateA/B/C，当前热限额确为项目工程假设。报告必须显著标示，不以此产生设备选型或工程安全结论。
- **证据文件**：artifacts/*_v03/network_manifest.json 的 capacity_assumption；README.md。
- **当前缺口**：无导线型号、环境温度修正、导体温升、保护整定或来源。
- **10天内修复动作**：D3 新建 thermal_limit_assumptions.csv，含每支路限额、换算、依据与敏感范围；至少用两组限额做稳健性结果。

### 10. 你们的数据血缘说有 hash 和 commit，但当前目录连 Git 仓库都不是，审计链从何谈起？
- **最佳回答**：当前已有网络源文件 SHA-256 与部分场景导出，但尚未达到 commit 级审计。答辩中把“可追溯报告”限定为现有输入/输出级，而不宣称完整软件供应链可审计。
- **证据文件**：src/gridrescue/case33_data.py；artifacts/*_v03/network_manifest.json；research_wave/data_provenance.md（设计）。
- **当前缺口**：无 .git、无运行 manifest、无依赖 lock、无输入输出总 hash。
- **10天内修复动作**：D1 初始化私有 Git、打 v0.4 tag；生成 run_manifest.json、requirements-lock.txt、文件 hash 清单和可复跑命令。

## 二、减排真实性、服务公平与 MRV（11–20）

### 11. 低碳策略的“减排”是否只是少供普通负荷换来的？
- **最佳回答**：当前 v03 确有此风险，因此不应单独用“低碳策略胜出”表述。run_scenario() 允许碳韧策略相对最小失供方案多 8% 普通负荷未供；正式减排结论只在关键和普通服务均满足预注册合同的同服务点上比较。
- **证据文件**：src/gridrescue/pipeline.py 的 +0.08 × normal_load；src/gridrescue/restoration.py 的 simulate_strategy；三份 *_v03/strategy_comparison.csv。
- **当前缺口**：无严格服务等价的 Pareto 点；v03 只能称“权衡演示”。
- **10天内修复动作**：D7 实装/产出 rho=0、1%、4%、8% 同服务 Pareto；默认答辩用 rho=0，其余层明确标“服务让步”。

### 12. 如何解释暴雨场景里低碳策略 EENS 4787.67 kWh，高于最小失供 2223.11 kWh，却仍要讲低碳？
- **最佳回答**：我们不回避：这是一个服务—碳权衡点。暴雨场景下碳韧方案碳排 41178.60 kg，低于最小失供的 42934.52 kg，但以额外 2564.56 kWh EENS 为代价；它不可作为无条件“更优”结论。
- **证据文件**：artifacts/flood_v03/strategy_comparison.csv。
- **当前缺口**：没有对普通/关键分项服务等价、没有单位服务碳强度和敏感性。
- **10天内修复动作**：D7 每张结果图同时展示 critical EENS、normal EENS、served kWh、kgCO2 和 fairness_status；删掉无条件“降碳 xx%”文案。

### 13. 极端高温里低碳策略碳排下降，但 EENS 从 411.42 增至 4198.44 kWh；这不是人为制造的悖论吗？
- **最佳回答**：是，应作为“碳悖论反例”而不是宣传主图。它说明若没有服务合同，低碳优化会通过延迟供电获得更低运行排放。项目的价值恰恰在于把这种伪优越从合格榜剔除。
- **证据文件**：artifacts/heat_v03/strategy_comparison.csv；research_wave/pareto_cvar_design.md 第4节（设计）。
- **当前缺口**：公平筛选规则未在当前运行产物中执行。
- **10天内修复动作**：D7 加一页“无合同 vs 同服务合同”的反事实图；为每个候选写入 service_not_equivalent 或 qualified。

### 14. 台风情景的关键负荷恢复只有约 68.6%，为什么系统还叫“保供”？
- **最佳回答**：台风是当前压力场景，资源不足时系统展示保供失败而非粉饰。此时输出应是“关键负荷缺供 10132.34 kWh、需要外部电源/更多抢修队/移动资源”的缺口诊断，不应称已完成关键保供。
- **证据文件**：artifacts/typhoon_v03/report_carbon_resilient.md；artifacts/typhoon_v03/strategy_comparison.csv。
- **当前缺口**：无关键负荷硬时限、无外援资源需求量、无失败告警 UI。
- **10天内修复动作**：D6 增加关键负荷 deadline、未满足时红色状态；输出“最小外援 kW/kWh/抢修小时”证据表。

### 15. 电网因子 0.5366、柴油 0.72、车辆 0.23 从哪里来？是否混淆 CO2 和 CO2e？
- **最佳回答**：代码现阶段为硬编码常数，不能作为权威 MRV 因子宣称。报告中应明确为“暂定假设”；正式版本将按来源、年份、地区、方法、气体范围和单位登记。
- **证据文件**：src/gridrescue/carbon.py 的 EmissionFactors；src/gridrescue/dispatch.py 的碳目标。
- **当前缺口**：无来源链接/PDF、无版本、无适用地域/年份、无 CO2/CO2e 边界。
- **10天内修复动作**：D8 将因子移入 data/carbon/factors.csv；对每一项建立 factor_id、value、unit、source、version、region、year、uncertainty，报告拒绝加载无来源因子。

### 16. 为什么弃光机会因子也使用 0.5366？是不是把弃光直接算成“避免排放”？
- **最佳回答**：目前代码对弃光单列 avoided_grid_equivalent_kg，但与电网因子共用数值，容易误导。答辩口径必须是：弃光是能源利用 KPI，不进入总排放或减排，除非在同服务、同时间窗中证明替代了明确高碳电源。
- **证据文件**：src/gridrescue/carbon.py；research_wave/carbon_mrv_plan.md 第4.6节。
- **当前缺口**：变量名/数值设计仍会诱导“弃光×因子=减排”的解读。
- **10天内修复动作**：D8 报告 UI 将该值改名为“弃绿机会量（非减排）”，并加单元测试：该字段不参与 total_operational_kg 或减排排行榜。

### 17. 计算“总排放”包括全部上级购电，项目本身导致的减排基线是什么？
- **最佳回答**：总排放是清单，不等于项目减排；项目减排只能定义为同一灾害窗口、同一功能单位、同一服务合同下 Proposed 与 Baseline 的差额。服务不等价时只报告 inventory 和 EENS。
- **证据文件**：README.md 的“碳边界”；docs/competition_narrative.md 第2节；research_wave/carbon_mrv_plan.md 第4.5节。
- **当前缺口**：现有 v03 报告没有正式 B0/P1 基线 ID、服务合同哈希和差额资格字段。
- **10天内修复动作**：D8 新增 baseline_id、service_contract_id、delta_kg、claim_eligible 到报告和 CSV；非等价样本自动隐藏“减排”标签。

### 18. 储能放电在报表里像零碳电源；你们是否追踪了充电来源与初始 SOC 碳强度？
- **最佳回答**：没有。当前仅追踪能量 SOC，尚未实现 Carbon-SOC。任何关于“储能低碳”的话都只能描述为后续设计，不得作为当前成果。
- **证据文件**：src/gridrescue/dispatch.py 仅有 battery_soc_kwh；research_wave/carbon_mrv_plan.md 第5节（设计）；research_wave/application_evidence_audit.md。
- **当前缺口**：无来源标签、碳质量状态量、充放电归因或双算控制。
- **10天内修复动作**：D8 实现最小 carbon_soc_hourly.csv（grid/PV/diesel/initial_unknown）；加碳守恒测试；如果来不及实现，从材料中删掉 Carbon-SOC 已落地表述。

### 19. 车辆排放只用一个 crew_distance_km，修复顺序、道路阻断、车辆油耗为何对三策略几乎没有约束？
- **最佳回答**：当前车辆碳是场景级常数，无法支持“低碳路径协同”的主张。它只是一项恢复相关的粗粒度清单，不是路线优化成果。
- **证据文件**：src/gridrescue/scenarios.py 的 crew_distance_km；src/gridrescue/carbon.py。
- **当前缺口**：无道路图、车队、工单、行程、油耗或并行抢修。
- **10天内修复动作**：D5/D8 做最小 3 队—5 故障点合成路网；输出 vehicle_log.csv 与路线/修复时序对照。来不及则把车辆从策略差异卖点降为固定背景清单。

### 20. 30 场景下碳韧协同均值碳排只比传统低约 0.30%，且 95%CI 大幅重叠，凭什么说稳健降碳？
- **最佳回答**：不能这样说。当前均值为：传统 36511.00 kg、碳韧 36400.55 kg，差异约 110.45 kg（约 0.30%），其 bootstrap 区间重叠；相对最小失供约低 4.83%，但服务差异尚未锁定。正式结论只能称“存在可观察到的低碳候选，尚待等服务多 seed 验证”。
- **证据文件**：artifacts/mc30_v04/monte_carlo_summary.csv。
- **当前缺口**：无配对差值 CI、无显著性检验、无等服务筛选。
- **10天内修复动作**：D9 使用共同随机数生成配对差 Δcarbon、ΔEENS，报告 bootstrap CI/符号检验；只报告通过服务合同的样本。

## 三、物理可行性、恢复逻辑与安全工程（21–30）

### 21. “潮流硬校验”是在优化后迭代反馈，不在联合优化内核；如何避免先产出不可执行方案再修补？
- **最佳回答**：当前是“空间 LP + P/Q 后验校验 + 容量反馈”的可行性筛选，不是联合 AC-OPF/MISOCP。我们不会宣称全局电气最优；所有展示方案须通过逐时校验，未通过者即失败。
- **证据文件**：src/gridrescue/pipeline.py 的 _simulate_with_loss_feedback；README.md 的“当前模型限制”；research_wave/application_evidence_audit.md。
- **当前缺口**：没有将分支潮流、电压、无功、热限额直接写入主优化。
- **10天内修复动作**：D6 完成至少 LinDistFlow/线性化电压约束版本，或明确冻结为“启发式候选+严格筛查”；导出候选/剔除/保留数量。

### 22. 反馈循环在物理不可行时会释放普通负荷上限，这会不会破坏你们刚强调的公平约束？
- **最佳回答**：这是当前必须披露的风险：_simulate_with_loss_feedback 对普通负荷预算 infeasible 时会释放 optional cap。关键负荷约束仍保留，但普通服务等价可能失效。进入低碳比较前须审计最终服务合同，而非只看初始参数。
- **证据文件**：src/gridrescue/pipeline.py 中 effective_normal_limit = None 的回退分支。
- **当前缺口**：无“预算被释放”显式标记；v03 无公平状态字段。
- **10天内修复动作**：D7 禁止公平 Pareto 路径释放预算；若 infeasible，记录 solver_infeasible。UI/CSV 显示 normal_cap_relaxed 并自动剔除减排主结论。

### 23. 孤岛无功约束为何用 0.60 ×（柴油+储能功率）近似？逆变器 kVA、功率因数和 Q-V 控制在哪里？
- **最佳回答**：当前 island_q_support_ratio=0.60 是简化筛查，不是设备级无功能力模型。它可防止部分明显不可行岛屿，但不替代逆变器 capability curve 与控制模式。
- **证据文件**：src/gridrescue/dispatch.py 的 island_q_support_ratio。
- **当前缺口**：无 P²+Q²≤S²、无逆变器/柴油 Q 上限、无 Volt-VAR 模式。
- **10天内修复动作**：D6 添加 DER pmax、qmax、smax、gfm 表和能力曲线约束；用一组高无功场景证明旧近似与新约束差异。

### 24. 岛内只要有柴油或储能功率就被当作可成网资源；黑启动、并网/离网转换、SOC、启动时间和保护条件满足了吗？
- **最佳回答**：目前仅用容量作为 GFM 的近似，尚未设备级确认。因此成岛结果应称“电能容量可行候选”，不是已获执行许可的微网黑启动方案。
- **证据文件**：src/gridrescue/dispatch.py 的 gfm_capacity；research_wave/microgrid_islanding.md（所需设计）。
- **当前缺口**：无黑启动状态机、启动延时、继保/同期、可用性/故障率。
- **10天内修复动作**：D6 以一个 BESS 和一台柴油机建立状态机（available/start/gfm/sync）；无 GFM/启动晚于 deadline 的岛强制不可行。

### 25. 联络开关是贪婪闭合的，保护配合、短路容量、合环、相位差、遥控拒动谁负责？
- **最佳回答**：当前只验证拓扑径向性/连通性，输出是策略建议，不是直接遥控命令。保护、同期、闭锁与现场安全票必须是执行前置门槛。
- **证据文件**：src/gridrescue/restoration.py 的 make_plan；src/gridrescue/faults.py 的 close_ties_greedily；research_wave/microgrid_islanding.md。
- **当前缺口**：无保护模型、无开关可操作状态、无拒动概率/回退动作。
- **10天内修复动作**：D6 给每个开关增加 remote_available、interlock_ok、protection_checked、sync_required 字段；演示一次拒动后重规划，不把建议包装成命令。

### 26. 修复时长串行累加，是否默认只有一支队伍？灾时多队、多车、道路受阻完全不同。
- **最佳回答**：是，当前为单抢修队基线，适合比较恢复顺序，不适合描述真实抢修调度。实际业务价值要等多队/路径模型落地后再谈。
- **证据文件**：src/gridrescue/restoration.py 的 make_plan 内 elapsed += durations；三场景动作序列。
- **当前缺口**：无 crew 数、技能、行驶时间、备件、并行任务。
- **10天内修复动作**：D5 建最小多队调度（2–3 队、道路时间矩阵、并行修复）；输出甘特图和与串行基线的差异。

### 27. 为什么“恢复时间 0 h”却同时有 EENS？评委会认为你们偷换概念。
- **最佳回答**：当前指标是“首次全供时刻”，并不等于灾害发生后所有累计失供为零；但命名确实易误导。应拆成“关键负荷达标时刻”“全负荷恢复时刻”“24h EENS”。
- **证据文件**：src/gridrescue/metrics.py 的 calculate_metrics；artifacts/flood_v03/strategy_comparison.csv、artifacts/heat_v03/strategy_comparison.csv。
- **当前缺口**：单个 restoration_time_h 无充分语义，报告未出完整服务曲线。
- **10天内修复动作**：D10 改图表/文案（无需改变模型主张）：导出逐时 critical/normal served 曲线和三个分开的 KPI 标签。

### 28. 台风报告动作最后一条在 T+24h 修复，而 24h 窗口内是否实际发挥作用？端点时间是否被错误计入？
- **最佳回答**：T+24h 恰在窗口末端，通常不会为前 24 个小时提供恢复收益。输出中必须明确时间索引的左/右闭区间，避免把窗口末修复写成已贡献的恢复成果。
- **证据文件**：artifacts/typhoon_v03/report_carbon_resilient.md；src/gridrescue/restoration.py 的 state_at_hour。
- **当前缺口**：无 repair_effective_from_hour、无事件时间轴语义测试。
- **10天内修复动作**：D6 增加端点单元测试与报表字段；动作表写成“完成时刻/生效时刻”，24h 末事件单独标记“下一窗口生效”。

### 29. 潮流报告里最大支路负载率多次接近 100%，你们的 99.90% 方案是否对测量误差和天气降额有余度？
- **最佳回答**：没有足够余度证据。99.90% 只代表假设热限额下的筛查通过，不能视为现场安全裕度。灾时应配置保守裕度和 N-1/温度敏感性。
- **证据文件**：artifacts/flood_v03/report_carbon_resilient.md（99.90%）；artifacts/heat_v03/report_carbon_resilient.md（99.64%）。
- **当前缺口**：无负荷预测误差、热动态、环境温度降额、不确定性裕度。
- **10天内修复动作**：D6/D9 加 90%/95% 热限额敏感情景与负荷/PV 扰动；报告“可行率—裕度”而非只报单次最大负载率。

### 30. 是否交叉验证过自写潮流结果？仅有 7 个测试是否足以证明模型正确？
- **最佳回答**：现有测试覆盖核心不变量和失败日志，不等于电力系统模型验证。自写前推回代须与 MATPOWER/pandapower 的稳态潮流逐节点、逐支路对标，测试数量不应被当作科学准确度证明。
- **证据文件**：tests/test_core.py、tests/test_experiments.py；README.md。
- **当前缺口**：无第三方工具 golden 文件、无随机网络回归、无 P/Q 误差表。
- **10天内修复动作**：D3 生成 OpenDSS/pandapower/MATPOWER 任一基准的 golden CSV；CI 中新增节点电压、支路 P/Q、线损误差断言。

## 四、AI 含量、数字孪生与创新性（31–37）

### 31. 标题里有“AI/数字孪生”，但当前代码看起来是规则+CVXPY；AI 到底在哪里？
- **最佳回答**：当前已实现的是优化驱动的预案数字孪生原型，不是已训练 AI 系统。不能把可视化或 CVXPY 直接称为 AI。若答辩要保留 AI，必须把 AI 角色限为一个可量化、可回退、受物理约束的模块。
- **证据文件**：pyproject.toml；src/gridrescue/ 模块；app.py；research_wave/ai_twin_innovations.md（方案清单）。
- **当前缺口**：无训练集、模型文件、推理代码、基线、精度/延迟评估。
- **10天内修复动作**：只选一个可完成模块：天气—故障风险可解释模型或优化器代理；没有实装前，将全部材料统一称“优化+规则数字孪生”。

### 32. “数字孪生”有实体层、数据层、机理层、服务层和双向闭环吗，还是一个 Streamlit 大屏？
- **最佳回答**：现状是离线预案推演/可视化，不是生产实时孪生。实体与数据映射目前主要是算例表，机理层为拓扑—调度—潮流，服务层为报告；数据接入、状态估计、人工审批回写尚未落地。
- **证据文件**：app.py；src/gridrescue/pipeline.py；research_wave/ai_twin_innovations.md。
- **当前缺口**：无 SCADA/OMS/GIS/DERMS 接口、无时间同步、无状态估计、无闭环审计。
- **10天内修复动作**：D10 做一个 CSV/MQTT mock 数据接入、置信度字段、人工“批准/拒绝”操作票状态与回写日志演示。

### 33. 若 AI 给出错误恢复动作，谁阻止它危及电网？
- **最佳回答**：AI（如有）只排序/预筛/解释，永不直接下发开关指令。最终候选必须通过拓扑径向、P/Q 潮流、热/电压、孤岛 GFM 与服务合同校验；失败即由规则回退/人工审批接管。
- **证据文件**：research_wave/ai_twin_innovations.md 第1–3项和答辩口径（设计）；当前 pipeline.py 的物理筛查流程。
- **当前缺口**：没有 AI 输出接口、硬约束网关或反例测试。
- **10天内修复动作**：D7/D10 定义 candidate → validator → approval JSON schema；构造 10 个 AI/规则候选，其中违规候选必须被拦截并出失败原因。

### 34. “天气—故障概率图谱”有 AUC、Brier、Top-k 吗？没有标签如何训练？
- **最佳回答**：当前没有预测模型，也没有真实标签，因此不能声称故障预测。十天内如实施，使用公开历史气象与公开/脱敏故障记录；若数据不足，只做专家规则风险分层，并明确它不是机器学习预测。
- **证据文件**：research_wave/ai_twin_innovations.md 第1项；src/gridrescue/scenarios.py。
- **当前缺口**：无历史故障标签、线路暴露特征、训练/测试切分。
- **10天内修复动作**：D4 确立 one-event 规则风险模型或放弃 ML；输出时间外留出集、Brier/AUC、数据许可与误报漏报案例。

### 35. 若做 GNN/代理模型，和直接跑 CVXPY 相比到底快多少、误差多少、可行率多少？
- **最佳回答**：现阶段无代理模型，不能宣称秒级 AI。任何代理都必须以优化/潮流的真值集标注，报告 MAE、Top-k 命中、物理可行率和端到端加速比，并保留精确优化裁判。
- **证据文件**：research_wave/ai_twin_innovations.md 第2–3项（设计）；research_wave/scalability_benchmark.md（目标门槛而非实测）。
- **当前缺口**：无数据集、无训练脚本、无模型卡、无实测性能表。
- **10天内修复动作**：D9 若选择代理，仅做 300–500 个离线样本的轻量 MLP；否则删 GNN 叙事，展示已有优化器耗时和明确的性能边界。

### 36. LLM 解释是否会编造原因、碳数据或电网操作？
- **最佳回答**：当前没有 LLM 模块。若加入，LLM 仅从经过 schema 校验的 JSON 生成中文摘要，所有数值必须带来源字段，且不可生成新的操作/数值；事实一致率是验收指标。
- **证据文件**：research_wave/ai_twin_innovations.md 第7项（设计）；app.py 当前无 LLM 依赖。
- **当前缺口**：无 prompt、检索、事实校验、幻觉率或离线回退模板。
- **10天内修复动作**：D10 使用 deterministic 模板先完成；若接 LLM，做 20 条回归问答并校验每个数值均来自结果 CSV。

### 37. 核心创新是不是“多目标优化+碳看板”的常见拼接？不可替代性是什么？
- **最佳回答**：创新不应押在抽象“多目标”上，而应收敛为：恢复动作、节点级供能、服务合同、碳 MRV 证据在同一 run ID 下可互相追溯；并用反事实证明碳约束会改变可执行恢复选择。没有这个反事实和审计链，就只是组合应用。
- **证据文件**：docs/competition_narrative.md；research_wave/carbon_mrv_plan.md；research_wave/literature_competitor.md。
- **当前缺口**：无已实现的 Carbon-SOC、公平 Pareto、文献15+对比矩阵或反事实 action-level 归因。
- **10天内修复动作**：D7–D8 做一份“论文/产品—变量/约束/MRV/现场性”对比表，且只列已验证差异；给出至少一例动作改变—碳差额—服务守约链。

## 五、算法、公平、稳健与工程化（38–43）

### 38. 三策略并非同一算法能力：传统策略没有初始联络开关，其他两类有；这是不是人为做弱基线？
- **最佳回答**：传统策略被定义为人工顺序基线，但其能力边界必须透明。若其不允许联络开关、而其他策略允许，则比较回答的是“整套策略包”差异，不是单纯低碳目标差异。主实验需增加同拓扑能力的规则型基线。
- **证据文件**：src/gridrescue/restoration.py 的 make_plan；artifacts/*_v03/strategy_comparison.csv 的 switch_operations。
- **当前缺口**：无控制变量消融（仅修复顺序、仅调度、仅碳权重）。
- **10天内修复动作**：D7 跑 4 组消融：共同拓扑、共同修复顺序、共同资源，仅切换目标；再单独评估联络开关价值。

### 39. 碳韧策略的权重 320、5.5、8、5 是谁给的？换一组数结论还在吗？
- **最佳回答**：这些是演示权重，不是客观政策偏好。权重型输出仅作候选点；主结论改用 epsilon-constraint/Pareto，并公布权重敏感性而非挑一组“最漂亮”的数。
- **证据文件**：src/gridrescue/restoration.py 的 strategy_weights；research_wave/pareto_cvar_design.md。
- **当前缺口**：无权重来源、归一化、敏感性或专家偏好。
- **10天内修复动作**：D7 扫 5×5 权重网格或转 epsilon-constraint；图上标全部可行点与支配关系，不只展示推荐点。

### 40. restoration_time_h、EENS、碳排、开关次数为何没有统一经济/操作成本口径？如何面向决策者推荐一点？
- **最佳回答**：当前项目只有韧性与运行碳结果，尚无可信财务成本；不应声称 ROI。推荐点由硬服务约束、物理可行和公开偏好层决定，成本作为后续模块。
- **证据文件**：src/gridrescue/metrics.py；research_wave/pareto_cvar_design.md 第3.3节（设计）。
- **当前缺口**：无电价、油价、人工、开关磨损、设备折旧、抢修成本来源。
- **10天内修复动作**：D8 若来得及仅加“归一化运行成本”并标假设；来不及则从申报书删除“经济最优/收益”字样。

### 41. 30 样本怎样做 CVaR 0.95？最坏尾部仅 1–2 个点，风险结论有没有统计意义？
- **最佳回答**：没有足够意义。30 样本只适合冒烟；CVaR 0.95 正式至少使用 100，推荐 200+ 独立场景，并说明共同随机数和分布来源。
- **证据文件**：research_wave/pareto_cvar_design.md 第6.3节；artifacts/mc30_v04/monte_carlo_summary.csv。
- **当前缺口**：无 CVaR 运行产物、无场景分布校准、无尾部稳定性分析。
- **10天内修复动作**：D9 跑 N=200（算力不足则 N=100 并明确限制），输出 alpha=0.90/0.95 敏感性和 bootstrap 区间。

### 42. 可扩展性表是实测还是愿望？33/69/123 节点的 P95 是否已经跑过？
- **最佳回答**：目前 scalability_benchmark.md 是验收门槛/计划，非实测结果。当前能确认的只是 33 节点路径与 v03/MC30 产物；没有实测就不报 69/123 节点分钟级能力。
- **证据文件**：research_wave/scalability_benchmark.md 明示“验收门槛，非实测值”；README.md。
- **当前缺口**：无 69/123 数据导入、无 benchmark CSV、无硬件/求解器/内存记录。
- **10天内修复动作**：D9 最少完成 33 与 69 节点、30 场景、5 次重复的真实 benchmark_runs.csv；所有答辩性能数字取该 CSV。

### 43. 灾时遥测坏了、通信中断、开关拒动或操作员不同意，系统如何安全降级？
- **最佳回答**：当前未接生产接口，因此系统只能做离线预案建议。可执行产品必须按数据可信度、拓扑不确定性和人工批准状态降级：低置信时禁止自动推荐开关，只给保守候选和需确认列表。
- **证据文件**：app.py；research_wave/microgrid_islanding.md；research_wave/demo_ux_plan.md。
- **当前缺口**：无 telemetry quality、无拒动注入、无审批/回滚/审计日志。
- **10天内修复动作**：D10 在 UI 加“遥测丢失/拒动”演示开关、人工批准步骤、回退到传统规则，并导出操作日志。

## 六、商业化、成果转化、IP 与答辩可信度（44–50）

### 44. 谁是第一付费客户：供电公司、园区、医院、储能商还是政府？不同客户为何愿意付费？
- **最佳回答**：十天内只锁定一个滩头：建议“园区/关键用户的灾前预案与事件级 MRV SaaS”，因为它可在不接入调度控制的情况下交付场景推演、服务等级和报告。供电调度侧定位为后续接口客户，不在 MVP 阶段声称替代 DMS。
- **证据文件**：research_wave/market_story_innovations.md；docs/competition_narrative.md。
- **当前缺口**：无客户访谈、无需求验证、无报价/合同/采购路径。
- **10天内修复动作**：D10 完成 5 个半结构访谈或 2 封意向反馈；写一页 ICP、痛点、交付物、定价假设和不可做边界。

### 45. 客户为什么不直接买成熟 DMS/OMS、能碳平台或咨询报告？你们的替代成本优势是什么？
- **最佳回答**：项目并不替代 DMS；差异应是“灾时恢复方案与同服务碳 MRV 的轻量评估层”，可以嵌入现有 EMS/DMS。若无法展示接口与独特证据链，则不应夸大壁垒。
- **证据文件**：research_wave/literature_competitor.md；research_wave/market_story_innovations.md。
- **当前缺口**：无竞品功能/价格/接口对比，无客户切换成本数据。
- **10天内修复动作**：D10 形成 6 家竞品/替代方案矩阵（功能、部署、数据要求、价格区间、差异）；选一个 mock DMS/CSV 接口演示嵌入位置。

### 46. 有什么可保护的知识产权？IEEE 33、CVXPY、MATPOWER、图标和因子都不是原创。
- **最佳回答**：不以公开算例或开源库申报核心 IP。可布局的是“服务合同约束下的恢复—碳账本—审计证据链”具体系统方法；同时建立第三方代码/数据/图片的许可清单。
- **证据文件**：src/gridrescue/case33_data.py；pyproject.toml；research_wave/literature_competitor.md。
- **当前缺口**：无 LICENSE、SBOM、素材清单、FTO 初筛、发明点权利要求草图。
- **10天内修复动作**：D10 输出 THIRD_PARTY_NOTICES.md、SBOM.cdx.json、素材来源表和 1 页专利交底（技术特征而非抽象算法口号）。

### 47. “低碳恢复”带来多少经济价值？没有成本模型，商业化是不是空话？
- **最佳回答**：当前没有可靠经济价值模型，不能报节省金额或 ROI。MVP 的付费价值是预案编制效率、风险透明和可审计报告；财务收益待接入油价、电价、停电损失和服务合同数据后验证。
- **证据文件**：src/gridrescue/metrics.py 无成本指标；research_wave/pareto_cvar_design.md 明确成本为设计。
- **当前缺口**：无成本/收益、无支付意愿、无单位经济模型。
- **10天内修复动作**：D10 做“报价不等于收益”的三层商业测算：软件交付成本、客户可验证节省项、待验证假设；不使用未经验证的 ROI 大数字。

### 48. 竞赛要求双碳，为什么项目重心看起来仍是配网恢复，碳只是报表？
- **最佳回答**：当前代码中碳已进入调度目标，但公平合同与来源账本未完全落地，因此现阶段只能说“碳参与候选策略”，还未证明双碳价值闭环。一等奖版本必须用同服务 Pareto + 因子可追溯 + 反事实来证明碳改变决策。
- **证据文件**：src/gridrescue/dispatch.py 的 carbon term；src/gridrescue/restoration.py 的 strategy_weights；research_wave/carbon_mrv_plan.md。
- **当前缺口**：没有满足条件的“项目减排”证据链。
- **10天内修复动作**：D7–D8 做一页闭环：服务合同 → 可执行动作 → 活动量 → 因子 → inventory → 合格差额；没有闭环的图不进入终稿。

### 49. 评委现场随机改一条故障、PV 降额或因子，你们能否在一分钟内重算并解释，而不是播放预制视频？
- **最佳回答**：当前项目有参数化场景和 CLI，但尚未见随机扰动/运行 manifest 的现场工作流。答辩须预演两类随机改动、展示求解耗时、失败原因与策略差异；若超过时间，展示已缓存案例并诚实说明。
- **证据文件**：src/gridrescue/cli.py；app.py；src/gridrescue/scenarios.py；research_wave/demo_ux_plan.md。
- **当前缺口**：无现场一键随机、无耗时计、无失败面板、无演练录像。
- **10天内修复动作**：D10 增加“随机故障/PV/因子”面板、运行计时和 run_manifest 下载；录制 3 次冷启动演练，按 P50/P95 选安全演示脚本。

### 50. 如果评委只给你 30 秒说明为何值一等奖，你能否给出一个不夸大的答案？
- **最佳回答**：**“我们没有把少供电冒充减排，也没有把标准算例冒充真实电网。GridRescue把极端天气下的恢复动作、关键负荷服务合同、可执行潮流筛查和逐项碳 MRV 放进同一条可复跑证据链：当低碳方案靠牺牲服务获得好看数字时，系统会把它剔出；当资源不足时，系统如实报告缺口并给出需要的外援。当前完成的是可复现原型，下一步用真实数据和同服务多场景实验完成试点验证。”**
- **证据文件**：README.md；docs/competition_narrative.md；artifacts/*_v03/；artifacts/mc30_v04/；本文件。
- **当前缺口**：上述答案中的“服务合同剔除”“完整 MRV 账本”“真实数据验证”尚未全部在代码/产物闭环完成。
- **10天内修复动作**：按下方 P0 清单完成后再使用；未完成则把措辞降为“正在构建的证据链”，并只展示当前已核验事实。

## 七、10天 P0 整改板（答辩生死线）

| 优先级 | 交付 | 验收证据 | 对应问题 |
|---|---|---|---|
| P0-1 | 同服务公平 Pareto，禁止普通服务预算静默释放 | pareto_runs.csv 含 fairness_status；rho=0 合格点；失败点保留 | 11–14, 22, 39 |
| P0-2 | 碳因子/活动量可追溯与最小 Carbon-SOC | factors registry、run manifest、carbon_soc_hourly.csv 或删除该宣称 | 15–20, 48 |
| P0-3 | 外部潮流对标 + 设备级物理硬失败 | golden CSV、P/Q误差、DER capability、失败诊断 | 2, 9, 21–30 |
| P0-4 | 多 seed ≥100 场景，配对统计与失败披露 | 每 seed 原始结果、95%CI、P90/CVaR、失败 replay | 5–6, 20, 41 |
| P0-5 | AI 主张收敛 | 选一个有指标的 AI 模块，或统一删为“优化数字孪生” | 31–37 |
| P0-6 | 真实客户/商业化最小证据 | 访谈纪要、ICP、竞品矩阵、付费交付物 | 44–47 |
| P0-7 | 一键复现和现场随机演示 | Git tag、manifest、演示脚本、冷启动计时视频 | 10, 42–43, 49 |

## 八、最终答辩禁语（未补证据前）

1. “已经在真实配电网/某沿海地区验证。”
2. “AI 已实现预测/智能决策。”
3. “低碳策略无代价优于最小失供。”
4. “30 个场景证明稳健性/显著性。”
5. “Carbon-SOC、实时孪生、成本最优、DMS 直连已经落地。”
6. “99%负载率就是工程安全。”
7. “恢复电量本身等于减排。”
8. “v03 的单次百分比就是项目可量化减排效益。”

> **红队判定**：现阶段可作为“方法完整、问题意识强、愿意如实暴露失败案例”的竞赛原型；要达到一等奖，必须在十天内拿下 P0-1 至 P0-4，AI和商业化宁可收敛主张，也不要用设计文档冒充实现。

