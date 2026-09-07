# Wave 6：Carbon-SOC 碳感知储能窗口控制（10 天可落地设计）

> 目标：在 GridRescue 已有的恢复调度、BESS SOC、逐时碳因子、柴油因子和节点/孤岛物理校验之上，增加一个评委能立刻读懂的控制层：**先锁住关键保供电量，再让储能把可动用部分放到碳排更高、且能真实替代购电或柴油的时段。**
>
> 本文只做设计，不改代码。它与已有 Wave 2 Carbon-SOC/MRV 设计互补：Wave 2 解决来源账本、因子版本和防双算；这里解决“为什么此刻充、为什么此刻不放、为什么现在放”。

## 1. 一句话创新

**Carbon-SOC 不是“电池里存了多少碳”，而是把 SOC 拆成保供底仓、碳可调部分和碳窗口目标三层；每一笔充放电都能给出服务、物理和碳信号三方面理由。**

评委看到现有 battery_soc_kwh 常会追问：

1. 为什么 T+19h 放电而 T+16h 不放？
2. 降碳有没有透支后续医院或关键负荷？
3. 电池放电究竟替代了购电、柴油，还是只是移动了数字？
4. 断开的孤岛之间是否被“虚拟挪电”？

本模块把这些回答固化成约束、字段、理由码和图表，而不是新增一个黑箱总分。

## 2. 三层 SOC：评委看得懂的主模型

| 层 | 符号 | 白话解释 | 调度地位 |
|---|---:|---|---|
| 物理 SOC | S(t,i) | 第 i 个储能节点现在有多少可用电量 | 既有物理状态 |
| 韧性保护储备 | R(t,i) | 未来若干小时关键负荷保命所需、不可任意动用的底仓 | 硬下界 |
| 碳可调电量 | F(t,i)=max(0,S-R) | 不触碰底仓前，可参与跨时段碳调度的电量 | 唯一可为碳目标释放的能量 |
| 碳窗口目标 | T(t,i) | 为后续高碳或柴油替代窗口，当前建议保持的 SOC | 软目标 |

页面名称建议用 **“碳韧 SOC 三层仓”**；技术名用 **Carbon-SOC Window Controller，CSWC**。

核心叙事：

    有多少电 S
      ├── 为关键保供锁住多少 R
      └── 剩下多少可灵活调度 F
    再判断后续高碳窗口需要预留多少 T

因此：

- F 为零时，即便当前碳因子高，控制器也不为低碳目的放电；
- F 大于零时，放电仍需要有可替代的网电或柴油负荷；
- T 只是准备未来窗口的目标，永远低于服务、孤岛、P/Q、电压和热限约束；
- 不把 EENS、服务和碳硬压成所谓“碳韧指数”。

## 3. 与当前 GridRescue 的接入点

### 3.1 可直接复用的现有基础

现有 dispatch.py 已具备：

- BESS 方程：soc[t+1] = soc[t] + eta × charge - discharge / eta；
- battery_soc_kwh、battery_charge_kw、battery_discharge_kw；
- 节点化 node_frame，含 hour、node_id、component_key、is_root_component、storage_energy_kwh、storage_power_kw、节点 SOC 和充放功率；
- root component 才能使用 grid import，非根孤岛需本地成网资源；
- 服务合同、医院/关键负荷、碳上限与 lexicographic 目标。

现有 scenarios.py 与 carbon.py 已具备：

- 24 个 1 小时时段；
- grid_carbon_kg_per_kwh；
- 0.72 kgCO2/kWh 柴油因子；
- 灾害、PV、负荷、故障、修复和购电/柴油/弃光序列；
- 已有的运行阶段碳核算。

pipeline.py 已有 P/Q 损耗反馈、孤岛平衡、电压/热限/源可行性验证。因此 MVP 不重写拓扑恢复与潮流模型，只在空间调度增加 SOC 下界、SOC 目标缺口变量、导出字段及 UI。

### 3.2 必须诚实写清的假设

1. 当前步长 delta_t 为 1 h；累计功率时仍要显式乘时长。
2. 当前 grid_carbon_kg_per_kwh 是合成场景输入，应标为 synthetic_d 质量，不代表真实城市实时边际因子。
3. 初始 SOC 72% 可参与保供，但来源未知时绝不叙述为零碳。
4. MRV 主核算因子 EF_accounting 与调度信号 EF_decision 分字段；MVP 允许暂时同值，但要标示为 proxy。
5. R、F、T 至少按 component 计算，绝不在两个电气孤岛之间共享储能。

## 4. 数学定义

### 4.1 记号

- t 是恢复小时，当前 t=0..23；i 是有储能容量的节点；c 是电气 component。
- S(t,i) 是时段开始电池侧能量，单位 kWh。
- Emax(i)、Emin(i) 是最大和最小 SOC 能量，单位 kWh。
- Pchmax(i)、Pdismax(i) 是充、放功率上限，单位 kW。
- eta_c、eta_d 是充放电效率；为兼容当前代码，首版均取 config.efficiency。
- Hr 是关键保供预测窗口，推荐 3 h；Hc 是碳窗口，推荐 6 h。
- EFgrid(t) 为调度碳信号；EFdiesel 为柴油排放因子。
- epsilon_soc 仅为数值容差，建议 1e-4 kWh。

既有物理约束显式写为：

~~~text
S(t+1,i) = S(t,i)
         + eta_c * Pcharge(t,i) * delta_t
         - Pdischarge(t,i) * delta_t / eta_d

Emin(i) <= S(t,i) <= Emax(i)
~~~

### 4.2 关键服务保护储备 R

先对每个 component 预测没有 BESS 时关键负荷的净缺口：

~~~text
Dcrit(t,c) =
max(0,
    Lcrit_forecast(t,c) + Lloss_critical(t,c)
    - Gfirm_non_bess(t,c))

Gfirm_non_bess(t,c) =
      grid_available(t,c)     # 仅 root component
    + diesel_available(t,c)
    + pv_firm(t,c)
~~~

其中 pv_firm 在比赛 MVP 使用当前的场景 PV 预测，并在 UI 标记“预测输入”。将未来 Hr 小时的关键缺口转换成 component 保护储备：

~~~text
Rcomp(t,c) =
min(sum_i_in_c Emax(i),
    sum_i_in_c Emin(i)
  + (1/eta_d) * sum[k=t..t+Hr-1] Dcrit(k,c) * delta_t)
~~~

有多台储能时，以可用容量比例分配：

~~~text
usable(i) = Emax(i) - Emin(i)
w(t,i) = usable(i) / sum[j in c] usable(j)

R(t,i) = Emin(i)
       + max(0, Rcomp(t,c)-sum[j in c] Emin(j)) * w(t,i)
~~~

硬护栏：

~~~text
S(t+1,i) >= R(t+1,i) - epsilon_soc
~~~

若 Rcomp 超过实际容量，记录 reserve_infeasible=true。系统应呈现真实关键供电缺口，不能假装电池覆盖了它。

### 4.3 碳可调电量 F

~~~text
F(t,i) = max(0, S(t,i) - R(t,i))
~~~

这是本模块最重要、最可解释的输出：

- F=0：当前电量都是保供底仓，禁止为碳优化放电；
- F>0：只表示可参与碳调度，仍受功率、服务、潮流与拓扑限制；
- Carbon-SOC 的高碳窗口放电只统计这部分 F，不把任何 BESS 放电都包装为“碳动作”。

### 4.4 后续高碳窗口与目标 SOC T

对 component c 的可替代排放因子：

~~~text
EFreplace(t,c) =
max(
  EFgrid(t),  若 root component 且购电可被替代；
  EFdiesel,   若本岛柴油出力可被替代；
  0
)
~~~

定义窗口内实际可替代功率：

~~~text
Dreplace(t,c) =
min(
  sum_i_in_c Pdismax(i),
  grid_import_baseline(t,c) + diesel_baseline(t,c),
  served_load(t,c) + charge(t,c)
)
~~~

在 Hc 内，从 EFreplace 的 70% 分位数以上且 Dreplace 大于零的时段选为高碳窗口。为这些窗口预留的电池侧能量为：

~~~text
Eopp(t,c) =
sum[k in high_carbon_window]
    min(Dreplace(k,c), Pdis_cap(c)) * delta_t / eta_d

Tcomp(t,c) = min(sum_i_in_c Emax(i), Rcomp(t,c) + Eopp(t,c))
~~~

T 按相同 w 分配至储能节点。T 是软目标，避免出现“为了追目标而强行买网电充电”的副作用。

### 4.5 低因子预充条件

从 t 充电、在 k 放电，只看运行碳的必要条件：

~~~text
ShiftGain(t,k,c) =
eta_c * eta_d * EFreplace(k,c) - EFgrid(t)
~~~

仅当以下条件同时成立时，才对额外低因子网电预充给出轻量偏好：

~~~text
S(t,i) < T(t,i)
AND ShiftGain(t,k,c) > delta_ef
AND 未来确有可替代的购电或柴油
AND 服务门、物理门、容量约束均通过
~~~

推荐 delta_ef=0.02 kgCO2/kWh，并将其写入 policy JSON 与敏感性结果。因子平坦、反转或质量缺失时，控制器采取中性策略，不做额外网购预充。

### 4.6 优化嵌入方式

推荐词典序两阶段实现，不使用一个巨大的碳权重覆盖保供：

~~~text
Stage 0: 原有恢复拓扑、孤岛、潮流、服务合同保持不变
Stage 1: 求既有服务门下的基准可行解
Stage 2: 用基准的负荷、PV、网电、柴油与 component 数据生成 R/T
Stage 3: 重解节点化 dispatch，新增 S >= R
Stage 4: 在服务门仍满足时最小化：
         C_operational
       + lambda_target * sum(target_shortfall)
       + lambda_throughput * throughput
~~~

可使用凸的 target shortfall：

~~~text
target_shortfall(t,i) >= T(t,i) - S(t,i)
target_shortfall(t,i) >= 0
~~~

并令 lambda_target 显著低于服务和实际运行排放目标。BESS 放电不再单独记成零排放，主核算保持：

~~~text
C_operational =
sum(grid_import * delta_t * EF_accounting)
+ sum(diesel_generation * delta_t * EFdiesel)
+ crew_distance * EFvehicle
~~~

## 5. 必须固定的 A/B/C 基线

同一灾害、同一修复动作、同一服务合同、同一因子版本、同一物理反馈参数下比较：

| 策略 | 定义 | 回答的问题 |
|---|---|---|
| A. 现有碳韧协同 | 当前 baseline | 原有策略怎么调？ |
| B. Reserve-only | 加 R 硬护栏，不加 T/预充偏好 | 仅防透支保供的影响是什么？ |
| C. Carbon-SOC | R 硬护栏 + T 软目标 + 合格窗口信号 | 同服务下时移有无运行排放差异？ |

结果发表次序固定为：

~~~text
G1 医院/其他关键服务门通过
G2 普通负荷让步处于预先公开的 epsilon 预算
G3 24/24 小时物理门通过：潮流、电压、热限、源平衡
G4 因子版本、时间步长和 MRV 边界完整
=> 才显示 C 相对 A 的恢复阶段运行排放估算差异
~~~

推荐术语是“运行排放估算差异”；不用“认证减排”“保证减排”“实时边际减排”。

## 6. 数据字段

### 6.1 dispatch.frame 新增 aggregate 字段

| 字段 | 单位 | 作用 |
|---|---|---|
| time_step_hours | h | 当前 1.0 |
| grid_decision_kgco2e_per_kwh | kgCO2/kWh | 调度碳信号 |
| carbon_factor_quality | enum | synthetic_d / proxy_c / sourced_b / verified_a |
| battery_reserve_kwh | kWh | sum R |
| battery_flexible_soc_kwh | kWh | sum F |
| battery_target_soc_kwh | kWh | sum T |
| carbon_window_flag | bool | 当前是否为有效替代窗口 |
| carbon_window_replace_factor_kgco2e_per_kwh | kgCO2/kWh | EFreplace |
| carbon_shift_gain_kgco2e_per_kwh | kgCO2/kWh | ShiftGain |
| carbon_soc_action | enum | protect_reserve / charge_for_window / hold_for_window / discharge_in_window / neutral |
| carbon_soc_reason_code | enum | 动作理由 |
| reserve_infeasible_flag | bool | 预测底仓无法满足 |
| carbon_soc_gate_pass | bool | 时段 SOC 护栏状态 |

理由码建议：

~~~text
RESERVE_LOCKED
RESERVE_FORECAST_INFEASIBLE
NO_REPLACEABLE_LOAD
FACTOR_FLAT_OR_UNCERTAIN
LOW_FACTOR_PRECHARGE
PV_SURPLUS_CHARGE
HIGH_FACTOR_GRID_DISPLACEMENT
HIGH_FACTOR_DIESEL_DISPLACEMENT
SOC_TARGET_ALREADY_MET
POWER_LIMIT
ISLAND_SEPARATION
~~~

### 6.2 新导出：carbon_soc_hourly_strategy.csv

每行对应 run_id、hour、node_id：

~~~text
run_id,scenario,strategy,hour,node_id,component_key,is_root_component,
storage_energy_kwh,storage_power_kw,
soc_start_kwh,soc_end_kwh,soc_pct,
reserve_kwh,flexible_soc_kwh,target_soc_kwh,
charge_kwh,discharge_kwh,
critical_deficit_forecast_kwh,reserve_horizon_h,carbon_horizon_h,
grid_decision_factor_kgco2e_per_kwh,replacement_factor_kgco2e_per_kwh,
shift_gain_kgco2e_per_kwh,factor_quality,
window_flag,action,reason_code,reserve_feasible,
component_isolation_flag,input_snapshot_sha256
~~~

### 6.3 冻结 policy JSON

~~~json
{
  "policy_id": "CSWC-V1",
  "time_step_hours": 1.0,
  "reserve_horizon_h": 3,
  "carbon_window_h": 6,
  "high_factor_quantile": 0.70,
  "shift_margin_kgco2e_per_kwh": 0.02,
  "factor_mode": "scenario_synthetic",
  "factor_quality": "synthetic_d",
  "reserve_distribution": "usable_capacity_proportional",
  "allow_grid_precharge": true,
  "require_same_service_gate": true,
  "require_physical_validation": true
}
~~~

policy 与场景、dispatch、factor snapshot 一起写入 manifest hash；UI 改参数也必须生成新 run_id。

## 7. 算法伪代码

### 7.1 Envelope builder

~~~python
for hour in horizon:
    for component in components_at(hour):
        stores = storage_nodes(component)
        if not stores:
            continue

        reserve_need = 0
        for k in range(hour, min(hour + Hr, N)):
            deficit = max(
                0,
                critical_forecast(k, component)
                + critical_loss(k, component)
                - firm_grid(k, component)
                - firm_diesel(k, component)
                - firm_pv(k, component),
            )
            reserve_need += deficit * dt / eta_d

        Rcomp = clamp(sum(Emin(stores)) + reserve_need,
                      0, sum(Emax(stores)))
        reserve_feasible = reserve_need + sum(Emin(stores)) <= sum(Emax(stores))

        candidates = replacement_rows(hour, component, Hc)
        threshold = quantile(
            [r.factor for r in candidates if r.replaceable_kw > tol], q=0.70
        )
        Eopp = sum(
            min(r.replaceable_kw, total_pdis(stores)) * dt / eta_d
            for r in candidates
            if r.replaceable_kw > tol and r.factor >= threshold
        )
        Tcomp = min(sum(Emax(stores)), Rcomp + Eopp)

        distribute_R_and_T_by_usable_capacity(stores, Rcomp, Tcomp)
~~~

### 7.2 重求解和解释器

~~~python
baseline = solve_existing_dispatch(inputs)
envelope = build_carbon_soc_envelopes(node_demand, baseline, policy)

add_constraint(soc_next >= envelope.reserve_kwh - eps)
add_constraint(target_shortfall >= envelope.target_kwh - soc)
add_constraint(target_shortfall >= 0)

solve_lexicographic(
    service_contract_first=True,
    operational_carbon_second=True,
    target_shortfall_small_penalty=True,
    throughput_tiny_penalty=True,
)

for row in output:
    if soc <= reserve + eps:
        reason = "RESERVE_LOCKED"
    elif charge > eps and shift_gain > margin:
        reason = "LOW_FACTOR_PRECHARGE"
    elif discharge > eps and window_flag and diesel > eps:
        reason = "HIGH_FACTOR_DIESEL_DISPLACEMENT"
    elif discharge > eps and window_flag:
        reason = "HIGH_FACTOR_GRID_DISPLACEMENT"
    else:
        reason = "FACTOR_FLAT_OR_UNCERTAIN"
~~~

## 8. 测试与验收

### 8.1 必测单元测试

| 测试 | 断言 |
|---|---|
| SOC 守恒 | 状态方程误差小于 1e-6 |
| 时间步长 | 1 h 与拆分 0.5 h 的能量/排放守恒 |
| R 下界 | 所有储能节点 S(t+1) 大于等于 R(t+1)-eps |
| 无未来关键缺口 | R 回落至 Emin |
| reserve infeasible | 真实标红，不能伪造满足 |
| 低—高因子玩具案例 | 仅满足 ShiftGain 条件时低时充、高时放 |
| 平坦/反转因子 | 不出现额外网购预充 |
| 柴油替代 | 理由码为 HIGH_FACTOR_DIESEL_DISPLACEMENT |
| 双孤岛 | 不跨 component 共享 SOC、R 或 T |
| 初始 SOC | 放电不重复改变运行排放总计 |
| 确定性 | 同输入、同 seed、同 policy 的导出 hash 一致 |

### 8.2 三灾害集成测试

对 暴雨内涝、台风、极端高温 各运行 A/B/C：

1. 三组均输出 24 × 储能节点数的 Carbon-SOC 行。
2. C 显示碳差异前必须 physical_feasible_hours=24。
3. 医院和其他关键 EENS 不得超过 A 的预设容差。
4. aggregate 值与 node 表求和一致：R、F、T 均可复算。
5. 每一条高窗口放电必须有正的可替代购电或柴油；否则理由为 NO_REPLACEABLE_LOAD。
6. 将全时段因子修改为常数后，预充动作消失或归为 neutral。
7. 移除 factor snapshot 后可求解但 UI 显示证据不完整，碳差异主卡显示 N/A。

## 9. UI：新增 Carbon-SOC 控制台页签

不需要另做花哨大屏，在现有 Streamlit 7 页后增加第 8 页即可。

### 9.1 顶部四卡

~~~text
当前 SOC             保供底仓 R          碳可调 F          当前动作
648 kWh / 72%        412 kWh / 未来3h   236 kWh          保持窗口电量
~~~

颜色：蓝色为物理 SOC，深绿为 R，青色为 F，黄色为高碳窗口，红色为 reserve infeasible 或比较门失败。

### 9.2 主图

同一张图使用：

1. SOC 实线；
2. R 深绿实线；
3. T 青色虚线；
4. 充电/放电正负柱；
5. EFdecision 右轴线或浅灰背景带；
6. 有效高碳窗口淡黄竖带；
7. hover 显示 component、因子质量、理由码、服务/物理门。

设计规则：每一个放电柱都必须能看见放电后仍高于 R；否则评委很容易质疑“为了碳排牺牲保供”。

### 9.3 小时理由卡

对 T+19h 的可读模板：

~~~text
T+19h：component island_3 进入高替代因子窗口。
替代对象：上级购电；EFreplace=0.66 kgCO2/kWh。
当前 SOC=648 kWh，保护储备 R=412 kWh，可调 F=236 kWh。
本小时放电=120 kWh，放电后 SOC=520 kWh，仍高于 R 108 kWh。
服务门通过；物理门通过；因子质量为 synthetic_d。
~~~

不放电的解释也要展示：

~~~text
T+16h：当前因子较高，但未来 3h 关键负荷预测缺口需要 430 kWh 底仓；
当前 SOC 仅 442 kWh。Carbon-SOC 锁定保护储备，未为碳目标放电。
~~~

### 9.4 A/B/C 对照表

| 策略 | 医院 EENS | 其他关键 EENS | 普通 EENS | 物理可行小时 | 运行排放 | R 覆盖率 | 高窗口灵活放电占比 | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| A 现有碳韧 | | | | | | - | - | baseline |
| B 韧性底仓 | | | | | | 100% | - | pass/fail |
| C Carbon-SOC | | | | | | 100% | | comparable/gate failed |

若 gate failed，运行排放差异显示 N/A，禁止画成绿色胜利。

## 10. 十天切片

| 日 | 工作 | 验收 |
|---:|---|---|
| D1 | 冻结术语、A/B/C、policy JSON | 参数有版本 |
| D2 | 实现 component 级 R | R 序列和玩具测试 |
| D3 | 实现 T、ShiftGain、平坦因子中性行为 | 三个时移测试 |
| D4 | 在空间 dispatch 加 S>=R 和目标缺口 | 暴雨 A/B/C 可解 |
| D5 | 生成 aggregate/node CSV 与理由码 | 守恒、原因测试 |
| D6 | 三灾害与物理/服务门回归 | 失败点保留 |
| D7 | UI 四卡、主图、理由卡 | 90 秒讲清 |
| D8 | Hr=2/3/4、Hc=4/6/8 敏感性 | 默认参数有依据 |
| D9 | MRV manifest、下载、答辩截图 | 可独立复算 |
| D10 | 固化 seed、回归、录屏、打包 | 离线 demo 完整 |

首轮硬砍：不做真实实时 MPC、不接市场出清和机组组合、不加入电池全生命周期 LCA、不训练 AI 预测器、不做复杂 MISOCP。

## 11. 风险与不夸大规则

| 风险 | 规避方式 |
|---|---|
| 当前因子是合成值 | 标为 synthetic_d；只做场景运行排放对比，不做城市实测减排主张 |
| 平均/边际因子混淆 | EF_accounting 与 EF_decision 分字段；没有可信边际数据时明确为 proxy |
| 电池放电被重复记碳 | 主总计只计网购、柴油、车辆；SOC 来源账本只解释，不再加总 |
| 少供电换低碳 | A/B/C 同服务门；普通 EENS 差异透明；失败则 N/A |
| 孤岛虚拟挪电 | R/F/T 严格随 component_key 计算，沿用节点化平衡与潮流校验 |
| 预测误差 | R 是预测型护栏，公开 Hr/PV/负荷敏感性，不宣称现场控制保证 |
| 参数挑选 | policy 固化并 hash，敏感性结果随交付物导出 |
| 1 小时粒度 | 定位为灾害恢复计划级；不声称适合秒级 AGC/EMS |

## 12. 答辩口径

**30 秒版本：**

> 储能有电不等于随时都该放。我们把 SOC 分为保供底仓和碳可调部分：系统先根据未来几小时医院等关键负荷的预测缺口锁住底仓，再判断后面是否存在能够真实替代购电或柴油的高碳窗口。只有不伤害服务且物理校验通过时，才让可调部分参与时移。每一次放或不放都能从 SOC、底仓、碳因子和理由码复算。

**“电池放电是不是零碳？”：**

> 不是。恢复阶段实际排放只记录网购、柴油和车辆；电池放电不会被重复记成零排放。它只改变这些活动在哪个时段、由什么边际对象被替代。初始 SOC 来源未知也明确显示未知。

**“是不是少供电换来的？”：**

> 我们先过医院、关键负荷、普通负荷预算和潮流物理门。门不通过，结果标记不可比较，不把小数包装成低碳收益。

## 13. 结论

建议将 Carbon-SOC Window Controller 作为 GridRescue 的 P0 创新模块。最小高分版本是：

1. component 级保护储备 R；
2. 可调电量 F；
3. 高碳窗口目标 T；
4. A/B/C 同服务和同物理门；
5. 一张三层 SOC 图与逐时理由卡；
6. 因子质量和 MRV 边界标注。

它复用现有 dispatch/BESS/碳因子/物理验证，10 天内能做出可运行闭环，又能避免“电池放电天然低碳”的过度宣称。
