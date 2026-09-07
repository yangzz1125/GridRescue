# GridRescue Wave11 技术闭环审计

**审计日期：2026-08-26**  
**审计对象：** `D:\桌面\GridRescue\_Wave11\_P1`

## 1. 审计范围

沿真实调用链检查：

```text
network → scenarios → restoration → dispatch → powerflow
       → pipeline feedback → Care / islands / metrics / carbon → MRV
```

## 2. 当前验证结果

### 2.1 自动化测试

聚焦技术测试：

```text
python -m pytest -q tests/test_core.py tests/test_care.py tests/test_pareto.py tests/test_mrv.py tests/test_islands.py
38 passed
```

项目全量回归基线：

```text
python -m pytest -q
62 passed
```

### 2.2 三灾种端到端复核

对 `暴雨内涝`、`台风`、`极端高温` 逐一运行 `run_pipeline()`，三种策略均满足：

- `physical_pass=true`；
- `feedback_converged=true`；
- 最大 source adjustment 小于 `0.1 kW`；
- 最大反馈残差小于 `0.1 kW`；
- 24 小时结果为有限数值。

策略层面的可解释关系保持：

- `最小失供恢复` 的 EENS 通常最低；
- `碳韧协同恢复` 在受控普通服务预算下减少运行清单，但可能增加普通服务 EENS；
- 不是把某个策略无条件包装成赢家，而是按目标函数和门控结果推荐。

## 3. 逐层结论

### 3.1 Network / Fault

- `case33bw` 固定为 33 节点、32 条常闭支路和 5 条常开联络线；
- 网络源文件 SHA-256 有回归断言；
- 联络线闭合使用无环约束；
- 故障支路、孤岛和根分量均有显式图状态。

### 3.2 Restoration

- 传统策略按输入顺序修复；
- 最小失供和碳韧协同使用相同的物理修复排序与联络线选择；
- 两者主要差异来自资源调度权重和普通服务预算，减少拓扑优势混入碳比较；
- 每条修复/开关动作可写入动作时间线和 MRV hash 链。

### 3.3 Dispatch

- CVXPY/CLARABEL 负责连续资源调度；
- 上级电网只出现在根组件；
- PV、BESS、柴油机保留在安装节点；
- BESS SOC、功率、能量和充放电效率进入约束；
- CareTask 最低功率直接转为 `served_critical >= task_required_kw`；
- 无源孤岛服务量强制为 0，不使用远端资源偷送。

### 3.4 Physics

- 每小时重建拓扑并执行平衡 P/Q 径向 backward/forward sweep；
- 输出节点电压、支路潮流、热限、损耗、组件 slack 和可行性；
- 线损与组件服务上限反馈给调度，最多 8 轮；
- 低压、热限、功率缺口、无 GFM、潮流不收敛都会进入失败记录。

### 3.5 Care / Islands / MRV

- CareTask 独立检查最低功率、时窗、deadline、连续时长、依赖和任务电压；
- 非根孤岛生成 capability passport 和 episode；
- 柴油/BESS 容量只表示 GFM 候选，不冒充现场 inverter commissioning 证据；
- MRV verifier 复核文件 hash、行级 hash、外键、碳方程、动作终端 hash 和 claim gate。

## 4. 评委追问时必须主动说明的边界

| 追问 | 准确回答 |
|---|---|
| 是不是现场实时控制？ | 不是；当前是离线预案/演练/复盘工作台。 |
| 是不是实测天气和医院数据？ | 不是；当前为 E 类合成工程输入。 |
| 是不是严格同服务减排？ | 不是；`same_service_pass=false`。 |
| 为什么碳韧策略 EENS 可能更高？ | 普通服务预算被公开放宽，换取受控运行碳清单差异。 |
| SEALED 是不是第三方认证？ | 不是；只表示文件完整性和内部复算。 |
| 潮流是不是完整三相 AC-OPF？ | 不是；当前是平衡 P/Q 径向前推回代和工程热限校验。 |

## 5. 当前没有发现的阻断项

- 没有发现空间调度把孤岛资源跨节点转移的测试漏洞；
- 没有发现 MRV 活动量与排放方程不一致；
- 没有发现 Pareto 失败点被静默删除；
- 没有发现三策略使用不同故障输入导致比较失真；
- 没有发现反馈未收敛却被标为 PASS 的路径。

## 6. 下一轮建议

下一块审计转向 Streamlit 演示：检查评委 5 分钟内能否看懂三门、NO_GFM 反例、Pareto、MRV 和风险卡；技术内核暂不扩张。
