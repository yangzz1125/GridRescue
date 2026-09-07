# GridRescue：MATPOWER case33bw 数据与潮流审计

> 审计边界：只做研究设计，未修改 `src/`、`data/`、测试或主代码。审计对象为 `data/case33bw.m`、`src/gridrescue/network.py`、`src/gridrescue/powerflow.py`，并于当前工作区执行了既有测试（`7 passed`）。
>
> 结论先行：仓库已经保存了一份标准 MATPOWER `case33bw`，但 `build_ieee33()` 实际生成的是固定随机种子下的 “IEEE-33-inspired” 网络；它只复用了 32 条基准支路和 5 条联络线的**连接关系**，没有使用官方逐节点 `Pd/Qd`、逐支路 `R/X` 或基值；其常闭/常开状态只是按同一拓扑规则重建，未形成可追溯的逐行原始数据映射。当前 `validate_dispatch()` 是后验、单相、仅有有功近似的树形检查器，不是与 case33bw 等价的 AC 潮流。项目可以将其用于方案筛选的早期可视化，但不应将现有电压、损耗、热稳定结果描述为 IEEE 33 节点 AC 潮流结论。

---

## 1. 已核实事实与当前差异

### 1.1 case33bw 文件（仓库内）

- 系统基准：`baseMVA = 10`；母线额定电压为 `12.66 kV`。
- 母线：33 个，1 号为 REF/slack，2–33 为 PQ；负荷在文件中先以 `kW/kVAr` 写出，文件末尾统一除以 `1000` 后成为 `MW/MVAr`。
- 基准负荷合计：**`ΣPd = 3715 kW`，`ΣQd = 2300 kVAr`**。
- 支路：37 条。前 32 条 `status=1`，构成正常运行的径向树；最后 5 条 `status=0`，为常开联络线。`rateA/rateB/rateC` 均为 0，因此原始 case **没有官方热限额**。
- 原始 R/X 以欧姆存放，文件末尾按

  \[
  Z_{base}=\frac{V_{base}^2}{S_{base}}
  =\frac{(12.66\times10^3)^2}{10\times10^6}
  =16.02756\ \Omega
  \]

  转为 p.u.。因此 `r_pu = r_ohm / 16.02756`，`x_pu = x_ohm / 16.02756`。功率基准为 `10,000 kW`。

### 1.2 `network.py` 的现状

| 项 | 当前实现 | 审计判断 |
|---|---|---|
| 拓扑 | `RADIAL_EDGES_1_BASED` 和 `TIE_EDGES_1_BASED` 与 case33bw 的端点顺序一致；内部转为 0-based | **可保留**，但要建立显式 `bus_id = node_id + 1` 映射并回归测试 |
| 负荷 | `rng.uniform(55,155,33)`，seed=2026；合计实测 `3401.7295 kW` | 与官方 `3715 kW` 不一致，且无 `Qd`，必须替换为导入数据 |
| 阻抗 | 每条支路使用公式合成 `resistance_pu`，范围 `0.00045–0.00141`，且没有 `x` | 与原始 37 条 R/X 完全脱钩；当前值也不是由 `12.66 kV/10 MVA` 换算而来 |
| 热限额 | 人为设为 `1600/1800/2200/3800/5200 kW` | 这些值不是 MATPOWER case33bw 数据；需标为工程假设、单独维护来源 |
| 开关状态 | 常闭 32 条、常开 5 条；联络线序号 33–37 | 状态和端点与 case 一致；阻抗和容量不一致 |
| DER/负荷等级 | PV、储能、柴油、关键负荷均在构建器内硬编码 | 可作为竞赛情景覆盖层，但不得混同为基准网络数据 |

### 1.3 `powerflow.py` 的现状

1. `validate_dispatch()` 用 BFS 选根、子树求和；只以 `net_load_kw` 计算支路有功流。
2. 电压降为 `2 * R_pu * P / base_power_kw`；不含 `XQ`、`I^2R/I^2X`、电压分母、无功平衡或反向潮流的严格符号处理。
3. `loss = R_pu * (P/base_power_kw)^2 * base_power_kw`，默认 `base_power_kw=1000`，而 case33bw 的功率基准是 **10,000 kW**；即使 R 正确，此处基值也不一致。
4. 支路流中没有把上游损耗回代进父支路，因此能量平衡和损耗都只是近似。
5. 每个孤岛用 `_component_slack()` 选择“资源容量最大”的节点，并直接把岛内净不平衡写入该节点；未检查该节点资源的有功/无功能力、SOC、逆变器 kVA 或是否真的成网。
6. 现有 `slack_adjustment_kw` 虽被输出，但不阻止模型给出“电压合格、热限额合格”的判定。实际复跑“台风/碳韧协同恢复”：24 小时累计 slack adjustment 为 **20,055.50 kW·h**，最大单小时 **1,238.38 kW**；这是当前电气可行性结论的直接否定证据。

---

## 2. 官方 MATPOWER case33bw 集成清单

### P0：建立不可变的基准数据层

1. 将 `data/case33bw.m` 作为唯一 canonical source，并记录 SHA-256、MATPOWER 版本/提交号、导入日期和许可来源。
2. 新增（设计建议）`data/case33bw_baseline.csv` 或运行时 parser 输出；数据列至少包含：
   - bus：`bus_id, type, pd_kw, qd_kvar, vm0_pu, va0_deg, base_kv, vmin_pu, vmax_pu`；
   - branch：`branch_id, from_bus, to_bus, r_ohm, x_ohm, r_pu, x_pu, b_pu, rate_a_mva, rate_b_mva, rate_c_mva, status, tap, shift_deg, is_tie`；
   - system：`base_mva=10, base_kv=12.66, z_base_ohm=16.02756, s_base_kw=10000`。
3. 禁止在 `build_ieee33()` 中用随机负荷和支路参数生成“基准网”。随机性若用于 Monte Carlo，应放在显式 `load_multiplier` / `fault_scenario` 情景层，并保存 seed。

### P0：Pd/Qd 的单位与建模

- 从 `.m` 读取时需识别其文件末尾的 `/1000`：最终 MATPOWER 内部值为 MW/MVAr；项目侧推荐统一保存为 `pd_kw`、`qd_kvar`，求解器边界处再换为 MW/MVAr 或 p.u.。
- 不能再以单列 `base_load_kw` 代替基准负荷。保留 `base_load_kw` 可兼容恢复优化，但它必须等于 `pd_kw`；增加 `base_reactive_kvar`。
- 调度层必须定义功率因数策略：默认使用每节点基准 `Q/P` 比例随已供电负荷同比缩放；PV/储能/柴油的 Q 出力需由逆变器额定 kVA、功率因数或 Volt-VAR 曲线约束。
- 关键等级、医院、通信等属性属于服务优先级附加数据，不写回 case33bw 原始表。

### P0：R/X、基值与损耗

- 直接保存 `r_ohm` 和 `x_ohm`；求解前由同一函数按 `z_base_ohm` 转换，避免参数重复且互相漂移。
- 若使用 p.u. 分支流/DistFlow，统一 `Sbase=10 MVA`、`Vbase=12.66 kV`、`Zbase=16.02756 Ω`，不得在损耗函数另设 1 MW 基准。
- 若使用物理单位 DistFlow，统一 `P/Q` 为 kW/kVAr、`V` 为 kV 或 V，并推导电流；严禁把 p.u. R 与 kW 直接相乘。
- 潮流核心至少采用：AC Newton-Raphson、Backward/Forward Sweep（径向配电网优先）或 SOCP/branch-flow relaxation；后验近似器仅保留作快速筛选并明确标记 `screening_only=True`。

### P1：支路限额

- case33bw 原始 `rateA/B/C=0` 的语义是“未给定 MVA 热额定值”，不是“容量为 0”，也不是“存在 1600–5200 kW 的官方限制”。
- 竞赛模型需要热约束时，建立独立的 `engineering_limits` 数据表：`branch_id, ampacity_a, rating_mva, source, assumption_class, temperature_derating`。优先采用线路型号/导线截面/区域配网设计资料；没有资料时可定义统一或分段情景额定值，但必须在论文和界面展示“假设”。
- 约束优先使用 `|S_ij| <= rate_mva` 或 `|I_ij| <= Imax`，而非只有 `|P| <= capacity_kw`；分布式电源高无功时，后者会漏掉过载。
- 对有反送潮流场景，正反方向都需检查；对故障恢复应考虑短时紧急额定值和持续额定值的差别。

### P0：联络线与拓扑状态

| 原始 branch_id | MATPOWER 端点 | 初始状态 | R/X（Ω） | 项目 0-based 端点 |
|---:|---|---:|---|---|
| 33 | 21–8 | open | 2.0 / 2.0 | 20–7 |
| 34 | 9–15 | open | 2.0 / 2.0 | 8–14 |
| 35 | 12–22 | open | 2.0 / 2.0 | 11–21 |
| 36 | 18–33 | open | 0.5 / 0.5 | 17–32 |
| 37 | 25–29 | open | 0.5 / 0.5 | 24–28 |

- 每个时段先根据故障、检修和开关命令得到 `BR_STATUS`，再执行拓扑校验：根网/孤岛均须连通、每个带负荷孤岛必须有可成网的可用电源、每个闭合分区的环路由求解器处理或被显式禁止。
- 当前 `is_radial()` 只验证 forest；它没有验证“所有被服务负荷有可行电源”、没有验证开关操作次数/顺序，也没有防止带电合环的工程风险。

---

## 3. 建议的回归测试套件（数据、潮流、恢复三层）

| 优先级 | 测试 | 断言/验收 |
|---|---|---|
| P0 | 数据完整性 | 33 bus、37 branch；`sum(Pd)=3715 kW`、`sum(Qd)=2300 kVAr`；bus 1 为 REF；32 closed + 5 open |
| P0 | 支路逐行完整性 | 37 行的 `from/to/R/X/status` 与 canonical 表逐行相等；特别校验五条 tie 的端点、R/X、status=0 |
| P0 | 单位转换 | `Zbase=16.02756 Ω`；每行 `r_pu*r_zbase≈r_ohm`、`x_pu*zbase≈x_ohm`；`MW*1000=kW` round trip |
| P0 | 正常拓扑 | status=1 的子图为 33 节点、32 边、连通、树；0-based/1-based 映射一一对应 |
| P0 | 基准 AC 潮流对标 | 与 MATPOWER `runpf(case33bw)` 比较每个母线 `Vm/Va`、每支路 `Pf/Qf/Pt/Qt`、总损耗；误差阈值在相同算法/容差下设为 `1e-6 p.u.` 或 `1e-3 kW` |
| P0 | pandapower 对标 | `from_mpc` 后 `runpp(algorithm="bfsw")`；与 MATPOWER 结果逐字段比较，记录版本、频率和求解容差 |
| P0 | 功率平衡 | 每个连通分区检查 `ΣPgen-ΣPload-ΣPloss=0`、`ΣQgen-ΣQload-ΣQloss=0`；残差超阈值即不可行，不以虚拟 slack 悄悄吸收 |
| P1 | 电压/热约束 | 所有 bus `Vmin≤Vm≤Vmax`；支路检查 `S` 或 `I` 正反向限额；无官方 rating 时测试应明确跳过而非套用伪官方值 |
| P1 | 恢复开关状态机 | 故障/修复/联络闭合后：状态合法、无非法合环、带负荷孤岛有 grid-forming source、开关操作次数受限 |
| P1 | DER 与孤岛 | PV、储能、柴油的 P/Q、SOC、kVA、爬坡和孤网 slack 限制全部有效；资源为 0 的孤岛不得被“平衡” |
| P2 | 数值稳健性 | 高/低负荷、PV 反送、单联络重构、多孤岛、求解不收敛时均返回可解释 infeasible 状态，而非有限数值 |

当前 `tests/test_core.py` 只验证有限值、拓扑森林和 `min_voltage_pu > 0.80`，因此它能发现程序崩溃，却验证不了基准数据正确性和电气可行性。

---

## 4. MATPOWER / pandapower 对标方法

### 4.1 冻结对标工况

1. **Baseline**：仅 case33bw 原始 PQ 负荷、1 号平衡母线、37 条支路按原始 status，不加 PV/储能/柴油/故障/限额假设。
2. **Overlay**：先完成 Baseline 的逐节点/逐支路对标，再叠加本项目 DER、关键负荷、故障和开关策略；每个 overlay 工况都导出一个可被 MATPOWER/pandapower 读取的 case。
3. 所有对标输出保存到 `artifacts/powerflow_benchmark/<case>/<solver>/<version>/`，至少包括输入 case、参数、收敛标志、bus 表、branch 表、误差表和图表。

### 4.2 MATPOWER 基准命令

```matlab
mpc = loadcase('data/case33bw.m');
mpopt = mpoption('verbose', 0, 'out.all', 0, ...
                'pf.alg', 'NR', 'pf.tol', 1e-10, 'pf.nr.max_it', 50);
[results, success] = runpf(mpc, mpopt);
assert(success == 1);

writematrix(results.bus,    'artifacts/matpower_baseline_bus.csv');
writematrix(results.branch, 'artifacts/matpower_baseline_branch.csv');
```

导出字段：bus 的 `BUS_I, VM, VA`；branch 的 `F_BUS, T_BUS, PF, QF, PT, QT`；系统的平衡机 `Pg/Qg` 与总损耗。`case33bw.m` 的 R/X 已在加载时转换为 p.u.，不得二次转换。

### 4.3 pandapower 交叉校验

```python
import pandapower as pp
from pandapower.converter import from_mpc

net = from_mpc("data/case33bw.m", f_hz=50, validate_conversion=True)
pp.runpp(net, algorithm="bfsw", init="flat", tolerance_mva=1e-10,
         max_iteration=100, calculate_voltage_angles=True)
assert net.converged

net.res_bus.to_csv("artifacts/pandapower_baseline_bus.csv")
net.res_line.to_csv("artifacts/pandapower_baseline_line.csv")
```

比较时按母线 ID、原支路行号/端点定向 join，统一单位（MW/MVAr 与 kW/kVAr）和符号约定。建议先比较电压幅值、再比较角度、再比较两端 P/Q，最后比较总网损。算法可不同（NR vs BFSW），但在收敛条件下应给出同一物理解；若差异超阈值，优先排查 `baseMVA`、欧姆/p.u. 二次换算、支路方向和 Q 符号。

### 4.4 推荐的验收锚点

文献中常见的原始 case33bw 基准结果约为总有功网损 **202.7 kW**、最小电压约 **0.913 p.u.**。该数值只作为 smoke-check；正式验收值应由锁定版本的 MATPOWER 运行结果自动生成并写入 golden CSV，避免版本、算法、无功/平衡机设置差异造成伪失败。

---

## 5. 电气评委最可能质疑的 10 点与修正优先级

| 排名 | 质疑点 | 证据/后果 | 优先级与修正动作 |
|---:|---|---|---|
| 1 | “IEEE 33”是否真用标准数据？ | 当前代码随机 Pd、合成 R，实测负荷 `3401.7295 kW` vs 标准 `3715 kW` | **P0**：导入逐节点 Pd/Qd 和逐支路 R/X；名称改为“case33bw+项目情景层” |
| 2 | 无功潮流在哪里？ | 模型没有 Qd、Q 流、XQ 压降、Q 限制 | **P0**：采用 AC/BFSW/branch-flow 求解，并纳入 DER Q/kVA |
| 3 | p.u./kW 基值是否一致？ | case 为 10 MVA，校验器默认 1 MW，R 也为合成数 | **P0**：集中基值对象；所有换算单元测试 |
| 4 | 恢复后孤岛真的可供电吗？ | “台风”运行出现最大 `1238.38 kW` 虚拟 slack adjustment，结果仍显示合格 | **P0**：把无资源/越界平衡判为 infeasible；显式 grid-forming、P/Q/SOC 约束 |
| 5 | 损耗和电压是否是真实 AC 结果？ | 单次 P-only 近似、未回代损耗，电压公式缺 XQ 与 V 分母 | **P0**：替换为经 MATPOWER/pandapower 对标的潮流内核；近似器只做筛选 |
| 6 | 线载约束来源是什么？ | `1600–5200 kW` 为硬编码，case 原始 rate 全为 0 | **P1**：独立工程额定表、来源/假设标签；以 MVA/电流约束 |
| 7 | 联络线参数和开关操作是否可信？ | 端点/状态对，但 tie R 使用合成数；缺开关次数、合环、带电操作规则 | **P0/P1**：逐行使用原始 tie R/X/status；增加状态机和操作约束 |
| 8 | 分布式电源配置是否有物理依据？ | PV/储能/柴油容量和节点分布硬编码，与 case33bw 混在同一构建器 | **P1**：基准网与情景覆盖分层；给出容量来源、kVA、SOC、时序和排放参数 |
| 9 | 服务恢复与电气拓扑是否耦合？ | 调度先聚合、潮流后分摊，按关键等级比例分配而非节点级功率平衡 | **P1**：将节点级 load shedding、DER dispatch、开关状态和潮流约束联合优化/迭代校正 |
| 10 | 验证是否只证明“无 NaN”？ | 既有测试只看有限值和 `V>0.80`，无外部基准曲线 | **P0**：golden benchmark + 全量数据、潮流、孤岛、拓扑回归测试 |

### 建议实施顺序

- **第一里程碑（答辩前必须完成）**：P0 的 canonical import、Pd/Qd/R/X/base 导入、正常态 MATPOWER/pandapower 对标、孤岛不可行性硬失败、基值修正。
- **第二里程碑（模型可信度）**：P1 的支路工程限额、DER P/Q/SOC/kVA、开关状态机、节点级恢复耦合。
- **第三里程碑（加分项）**：P2 的高渗透 PV、反送、潮流不收敛处理、灵敏度/不确定性与 N-1 情景。

---

## 6. 参考来源

1. MATPOWER 官方 `case33bw.m`：https://github.com/MATPOWER/matpower/blob/master/data/case33bw.m （仓库内 `data/case33bw.m` 与此类 case-format 一致；最终应记录锁定提交）。
2. MATPOWER Case Format / `runpf` 文档：https://matpower.org/docs/ 。
3. pandapower MATPOWER converter 与 power flow 文档：https://pandapower.readthedocs.io/ 。
4. M. E. Baran, R. F. Wu, “Network reconfiguration in distribution systems for loss reduction and load balancing,” *IEEE Transactions on Power Delivery*, 4(2), 1401–1407, 1989, doi:10.1109/61.25627。


