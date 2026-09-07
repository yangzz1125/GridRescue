# GridRescue 碳核算与MRV计划：Carbon-SOC

## 0. 核心结论

GridRescue 的碳结果必须同时报出三件互不替代的事：

1. **恢复运行排放清单（Inventory）**：项目恢复方案实际引起的电网购电、柴油机和抢修车辆运行排放。
2. **服务等价的减排对比（Avoided / Delta）**：在同一灾害、同一需求、同一关键负荷保供下，与传统恢复基线相比的排放差。
3. **储能来源可追溯账本（Carbon-SOC）**：储能每一时段电量来自电网、现场光伏或初始存量的比例及其带入碳强度。

严禁把“少供电”“弃光减少”“电池放电”直接写成减排。只有在统一服务边界内、对照基线可复算时，才报告减排。

## 1. 对齐的规范性原则

| 原则 | GridRescue 落地规则 |
|---|---|
| 相关性、完整性、一致性、准确性、透明性 | 每个KPI有边界、单位、来源、时间、版本、公式和场景ID；不同方案使用同一因子版本与时间窗。 |
| 购入电力的地理位置与市场方式区分 | MVP默认用省/区域/全国电网平均因子报告 location-based 运行排放；若声明绿电/绿证，必须独立记录凭证状态并使用对应剩余电网因子，两个口径并列、不混合。 |
| 可核查性 | 所有结果可从输入CSV、配置JSON、方案JSON和计算日志重算；每次运行生成输入哈希和因子版本。 |
| 防止环境属性重复计算 | 同一度现场PV或绿电属性在同一时间窗只能分配给一个用途：自用低碳供电、绿证/绿电声明、或对外出售。 |
| 项目减排与排放清单分开 | Inventory 是实际排放；Delta 是基线差额。页面和报告中禁止将二者相加。 |

规范锚点：ISO 14064-1:2018 的组织层温室气体量化、报告与核查原则；GHG Protocol Scope 2 Guidance 的外购电核算与能源属性凭证质量要求；生态环境部/国家统计局发布的全国、区域、省级电力二氧化碳排放因子及“扣除市场化非化石电量”的剩余电网口径。

## 2. 恢复阶段碳边界

### 2.1 时间与功能单位

- **时间边界**：灾害发生后 T0 至 T0+24h；MVP按1小时步长，前端可显示15分钟插值但不重新核算。
- **空间边界**：IEEE 33节点配电网、其接入点的外购电、现场PV、BESS、柴油机、与本次恢复相关的抢修车辆。
- **功能单位**：在灾害场景 s 下，为同一组关键负荷提供的每kWh电能，以及整个24小时恢复服务。
- **共同服务约束**：比较方案必须满足相同的关键负荷供电下限。若方案A少供电，不能凭“少排放”宣称减排；它只能作为ENS/保供失败方案显示。
- **单位**：所有排放统一 kgCO2；若输入仅有 CO2 因子，则报表明确标注“kgCO2”而非“kgCO2”。

### 2.2 核算模块与归类

| 模块 | 是否纳入主Inventory | 计算位置 | 说明 |
|---|---:|---|---|
| 电网购电 | 是 | Scope 2 / location-based | 按每时段净进口电量乘电网因子；进口和出口分开记录，默认不净额抵扣。 |
| 柴油机发电 | 是 | Scope 1（若自营） | 按实测/模型燃油消耗乘柴油排放因子；可同时保留 CO2 与 CO2e口径。 |
| 抢修车辆油耗 | 是，但单列 | Scope 1或Scope 3 | 仅计入由方案选择导致的增量路线/车次；若各方案相同则在Delta中抵消。 |
| BESS充放电 | 间接纳入 | 通过充电来源 | 充电时计入电网或柴油排放；放电时不再生成第二笔“负排放”。Carbon-SOC负责来源证明。 |
| 现场PV直接供电 | 是，运行排放为零或设定值 | 现场能源 | 仅在其环境属性未出售、未被其他声明占用时，作为零运行排放电量。 |
| 弃光 | 否，单列KPI | 能源指标 | 记录为未利用清洁电量；不直接乘电网因子获得“减排”。 |
| 设备制造、BESS制造、线路重建 | MVP不纳入主Inventory | 生命周期附录 | 无可靠设备LCA数据时不混入运行排放；可作为边界外披露。 |
| 人员餐饮、通信、办公 | 不纳入 | 边界外 | 对方案比较影响小、数据弱，避免伪精确。 |

## 3. 数据模型与数据字典

### 3.1 核心表

| 表 / 文件 | 主键 | 必填字段 | MRV用途 |
|---|---|---|---|
| scenario.json | scenario_id | 灾种、失败支路、起止时间、修复时长、随机种子、需求版本 | 保证每个策略在相同灾情下比较。 |
| dispatch_hourly.csv | scenario_id, strategy_id, hour, bus_id | grid_import_kwh、pv_direct_kwh、pv_to_bess_kwh、diesel_kwh、bess_charge/discharge、unserved_kwh | 每小时能量守恒和排放计算。 |
| fuel_log.csv | asset_id, hour | fuel_litre、fuel_type、meter_or_model、uncertainty_pct | 柴油机/车辆直接排放依据。 |
| vehicle_log.csv | crew_id, trip_id | km、litre_per_100km、fuel_litre、repair_task_id | 只计与恢复路线优化相关的车辆排放。 |
| factor_registry.csv | factor_id, geography, year, method | factor_value、unit、source_title、publication_date、retrieval_date、scope | 因子版本锁定，禁止硬编码散落于函数中。 |
| energy_attribute.csv | attribute_id, asset_id, hour | pv_or_green_power_kwh、status、owner、retired_flag、certificate_ref | 防绿电/绿证/自发自用的重复声明。 |
| carbon_soc_hourly.csv | storage_id, hour, origin | stored_kwh、carbon_mass_kg、carbon_intensity、charge_kwh、withdrawal_kwh | 储能来源、碳强度与放电分摊证据。 |
| run_manifest.json | run_id | git_commit、input_sha256、factor_registry_version、solver_version、timestamp | 完整可重现和审计追溯。 |
| result_summary.csv | run_id, strategy_id | served_critical_kwh、ENS、inventory_kg、delta_kg、curtailment_kwh | 面板KPI唯一来源。 |

### 3.2 数据质量字段

每一项因子或估算活动数据都附带：source_type（meter/model/assumption）、evidence_level（A/B/C）、uncertainty_pct、owner、last_updated、approval_status。

- A：官方发布因子、计量表、实际油单。
- B：公开技术参数、设备铭牌、经校准模型。
- C：竞赛合成假设；只能用于情景推演，前端必须标“模拟”。

## 4. 计算公式

令 t 为小时，Delta t=1h，策略 r 属于 baseline 或 proposed。

### 4.1 电网购电

E_grid(r) = Sum_t [ Import(r,t) x EF_grid(t) ]

- Import(r,t) 仅取接入点正向净进口，单位kWh。
- Export(r,t) 单列记录，MVP默认不把出口作为负排放。
- 默认 location-based：选择与场景地理范围相匹配的公开平均电网因子。
- 市场方式仅在具备可追溯能源属性、未重复声明时启用；其余电量使用“扣除市场化非化石电量”的剩余电网口径。
- 为避免伪造小时级精度，若仅有年度因子，则EF_grid(t)=EF_year，并在UI标记“年度因子，非实时边际排放因子”。

### 4.2 柴油机

Fuel_gen(r,t) = Diesel_kWh(r,t) x SFC_gen(t)

E_diesel_gen(r) = Sum_t [ Fuel_gen(r,t) x EF_diesel ]

其中 SFC_gen 为 L/kWh，优先使用设备负荷率曲线；MVP可用公开或设备参数中的常数，但必须在 factor_registry 中登记。若柴油因子包含 CH4/N2O，报kgCO2；若只含燃烧CO2，报kgCO2。

### 4.3 抢修车辆

Fuel_vehicle(r) = Sum_trip [ distance_km x fuel_rate_l_per_km ]
E_vehicle(r) = Fuel_vehicle(r) x EF_diesel

仅在路线、车次或抢修顺序因策略不同而改变时，纳入方案Delta；同一灾害中不可避免的共同车辆排放可计Inventory，但其Delta为0。

### 4.4 运行排放清单

E_inventory(r) = E_grid(r) + E_diesel_gen(r) + E_vehicle(r)

面板必须分别显示三个分项，不能只显示总数。

### 4.5 服务等价减排

对同一场景，先校验：

ServedCritical(proposed) >= ServedCritical(baseline) - epsilon

仅通过此门槛后：

DeltaE = E_inventory(baseline) - E_inventory(proposed)

CarbonIntensity_service(r) = E_inventory(r) / ServedPriorityEnergy(r)

若服务未等价，则只报“排放清单、ENS、关键负荷保供率”，不显示“减排xx kg”。

### 4.6 弃光

CurtailPV(r) = Sum_t [ PV_available(t) - PV_direct(r,t) - PV_to_BESS(r,t) - PV_export(r,t) ]_plus

AvoidedCurtail = CurtailPV(baseline) - CurtailPV(proposed)

AvoidedCurtail 是能源利用指标，不能单独乘EF_grid得到减排。减排只通过减少同一时段柴油机发电或外购电得到，并已体现在 DeltaE 中。

## 5. Carbon-SOC：储能来源与碳强度追踪

### 5.1 目的

储能会跨时转移电量。若只看放电时刻，电池似乎“零碳”；若充电和放电都算一次，又会双计。Carbon-SOC将储能内能量和随能量携带的已归因碳质量一起建账。

### 5.2 状态量

对于每个BESS b：

- S_b,t：时段末内部储能量，kWh。
- M_b,t：储能中随电量携带的已归因碳质量，kgCO2。
- CI_b,t = M_b,t / S_b,t：储能内平均碳强度，kgCO2/kWh；S=0时置空。
- C_grid、C_pv、C_diesel：进入电池前的充电电量，按来源分别记录。
- W_b,t：本时段从电池内部抽取的能量；D_b,t = eta_dis x W_b,t 为送至母线的放电量。

### 5.3 账本递推

设 eta_ch 为充电效率，alpha_t = W_b,t / max(S_b,t, epsilon)。

S_b,t+1 = S_b,t + eta_ch x (C_grid + C_pv + C_diesel) - W_b,t

M_b,t+1 = M_b,t x (1-alpha_t) + eta_ch x [ C_grid x EF_grid(t) + C_diesel x EF_diesel_per_kwh + C_pv x EF_pv_operational ]

对现场PV，EF_pv_operational 默认取0，只代表运行期直接排放；其环境属性仍受 energy_attribute 表约束。初始SOC必须建一条 origin=initial_unknown 记录：

M_b,0 = S_b,0 x CI_initial

CI_initial 的默认保守值取场景首小时电网因子；若能证明初始电量来自未售出的现场PV或合格绿电，可改为其可审计来源因子。

### 5.4 放电规则

- 放电不在 E_inventory 中创建第二笔负排放。
- 放电按时段开始时的来源比例从 M_b,t 和 S_b,t 中等比例抽取。
- 结果页面可显示“本时段电池放电的Carbon-SOC强度”，用于解释其历史来源。
- 方案Delta只通过同一小时少发柴油或少购电自然体现；禁止再使用 D_b,t x EF_grid 额外加一笔“储能减排”。

### 5.5 强制来源标签

origin 仅可为：grid_location、grid_residual、on_site_pv_unclaimed、diesel、initial_unknown。

任何 PV/绿电电量若 energy_attribute.status 为 sold、retired_by_other、unknown，则不得以 on_site_pv_unclaimed 的零运行排放来源进入Carbon-SOC。这个检查是避免环境权益重复计算的关键。

## 6. 防止双重计算：九条硬规则

1. 电网进口与柴油发电绝不在同一kWh上同时计排放。
2. BESS充电排放在来源发生时进入Inventory；放电只转移能量，不再创造第二次减排。
3. 现场PV直接供电与PV充BESS是不同能量流；同一PV kWh每小时只能分配一次。
4. 弃光减少只报kWh；若其替代柴油/购电，减排已在对比的能源流中体现。
5. 绿电/绿证/自发自用环境属性必须单一归属；已出售或被外部注销的属性不能在项目内作零碳声明。
6. 不以出口电量抵扣本地Inventory；出口影响只在边界扩展、且有合格反事实时另作附录。
7. 不把“未供电负荷”视为减排。保供下降时，减排声明自动锁死。
8. 车辆排放只计算策略变化带来的增量；不要把所有灾害应急活动重复归因给算法。
9. 同一策略的结果只能使用一个因子版本；基线与方案必须使用同一因子版本、同一气象/需求轨迹。

## 7. 基线设计

### Baseline B0：传统恢复

- 固定故障隔离规则；
- 不做跨馈线低碳重构；
- BESS按安全保底SOC或不参与协同；
- PV仅就地消纳，无法消纳则弃光；
- 关键负荷不足由柴油机优先补给；
- 抢修按距离最近或固定顺序。

### Proposed P1：GridRescue低碳恢复

- 约束满足的联络线重构与孤岛划分；
- PV—BESS—关键负荷协调；
- 在保供约束内最小化柴油、购电和操作次数；
- 可选：车辆路径/抢修顺序优化。

### 公平性锁定

B0与P1共享：同一故障集合、同一修复时间、同一需求、同一PV可用量、同一设备容量、同一时钟和因子表。若P1使用了额外储能或额外车辆，必须作为“增量资源情景”单列，不与无资源B0直接宣称算法减排。

## 8. 验证、审计轨迹与敏感性分析

### 8.1 每次运行的自动校验

- 能量守恒：每bus、每小时输入=供电+充电+损耗+出口。
- SOC范围：0 <= S <= capacity；放电和充电功率不越限。
- Carbon-SOC：M >= 0；S=0时M=0；来源份额和为1。
- 拓扑可行：故障支路断开、闭合网络径向、关键孤岛含有效电源。
- 服务一致：通过 ServedCritical 门槛后才激活 DeltaE。
- 碳守恒：分项和=Inventory总排放；不允许PV、BESS或弃光字段生成未定义的负排放。

### 8.2 敏感性矩阵

| 参数 | 建议扰动 | 输出 |
|---|---|---|
| 电网排放因子 | 年度因子、区域因子、全国因子；±10% | DeltaE区间与方案排序稳健性。 |
| 柴油机SFC | 负荷曲线或基准值±15% | 柴油替代贡献与总减排变化。 |
| 柴油排放因子 | ±5%或来源版本切换 | Scope 1不确定性。 |
| BESS效率 | eta_ch/eta_dis 各±5% | Carbon-SOC与PV移峰价值。 |
| 初始SOC来源 | 保守电网、可审计PV、未知高碳 | 早期放电的碳强度差。 |
| PV可用率 | 灾害情景的P10/P50/P90 | 弃光、柴油和保供变化。 |
| 关键负荷门槛 | 90%、95%、100% | “保供-低碳”权衡前沿。 |
| 车辆路线 | 距离/油耗±20% | 抢修碳的量级及是否改变排序。 |

实现：先做单因素龙卷风图；再对电网因子、PV可用率、SFC、修复时长做200次蒙特卡洛，报P50/P90 DeltaE。若策略排名在大多数样本中一致，报告“排序稳健率”。

## 9. 答辩问答

**Q1：你们的碳减排为何可信？**  
A：每个策略使用同一故障、负荷、PV、设备和因子版本；先锁定关键负荷保供，再比较实际运行排放。输入、因子、方案和结果带run_id与哈希，可一键重算。

**Q2：电池充电时用了高碳电，放电还叫低碳吗？**  
A：不直接叫低碳。Carbon-SOC追踪充入电量的来源和碳强度；电池放电不是负排放，只有它在同一服务水平下替代柴油或同时段外购电时，方案总排放才下降。

**Q3：弃光减少为什么不直接折算成减排？**  
A：弃光减少本身只说明清洁能源利用增加。是否减排取决于它实际替代了什么；系统只在柴油和外购电的实物流对比中计算减排，避免重复计算。

**Q4：绿电或绿证如何防止重复声明？**  
A：每笔环境属性有状态、所有者、注销标志和时间窗。已出售、已被他方注销或来源不明的绿电，不得以项目自用零碳电量进入Carbon-SOC。

**Q5：为何使用年度电网因子而不是实时边际因子？**  
A：竞赛MVP使用官方公开、可核查的年度因子，强调结果透明性；页面明确其非实时边际因子。实时边际因子作为未来扩展，不能在没有公开可验证数据时伪装成实测。

**Q6：少供电当然少排放，怎么防止算法钻空子？**  
A：减排标签只有在关键负荷服务等价校验通过后才显示。否则只展示ENS和保供失败，无法获得“低碳”分数。

## 10. 十天内交付物

- factor_registry.csv：至少登记电网、柴油、车辆燃油和PV运行期因子，含来源与日期。
- carbon_mrv.py：计算Inventory、Carbon-SOC、服务等价校验、DeltaE、弃光和审计检查。
- 一套B0/P1对照场景：台风或暴雨，24小时、至少两处故障。
- 四张核心图：能源流桑基图、Carbon-SOC堆叠图、B0/P1排放分解、敏感性龙卷风图。
- 导出MRV报告JSON/CSV：包含run_manifest、边界、因子版本、结果、校验状态和免责声明。

## 11. 规范来源登记（用于报告参考文献）

1. ISO 14064-1:2018，组织层温室气体排放与清除的量化、报告和核查要求；ISO官方页面显示该版本于2024年复审确认。
2. GHG Protocol Scope 2 Guidance（2015，含后续修订记录）：外购电、能源合同/属性凭证、location-based与market-based核算的透明披露要求。
3. 生态环境部、国家统计局：《关于发布2023年电力二氧化碳排放因子的公告》及2026年1月5日答记者问。公开口径包括全国/区域/省级平均因子、扣除市场化非化石电量后的全国平均因子、全国化石能源电力因子。
4. 截至本方案编制时，2023年全国电力平均二氧化碳排放因子为0.5306 kgCO2/kWh；扣除市场化交易非化石电量后的全国平均因子为0.6096 kgCO2/kWh。二者适用场景不同，严禁混用。
