# 碳韧智网 GridRescue

> **2026竞赛版入口**：运行、公开数据、最新实验、申报正文与交付说明见本页“2026竞赛复算版”。历史V08/Wave10证据保留用于版本追溯，不代表当前代码的最新结果。

极端天气下配电网故障恢复与低碳保供数字孪生竞赛原型。

> 项目定位：面向应急恢复的**服务合同门控、证据承载数字孪生**。低碳候选只有同时通过生命线任务、配电网物理和 MRV 证据门，才进入推荐；服务不等价时系统自动撤回严格同服务主张。

## 2026竞赛复算版

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH="$PWD\src"
python -m pytest -q
streamlit run app.py --server.address 127.0.0.1 --server.fileWatcherType none
```

公开数据与新实验：

```powershell
python scripts\fetch_public_data.py
python scripts\fetch_station_context.py
python scripts\run_public_replay.py
python scripts\run_competition_validation.py
python scripts\build_competition_figures.py
python scripts\build_submission_document.py
```

- 新证据：`artifacts/competition2026/`
- 公开数据与SHA：`data/public/source_manifest.json`
- 申报正文：`docs/submission_application_2026.md`、`.html`及`release/submission_application_2026.pdf`
- 技术/实验/来源：`docs/technical_report_2026.md`、`competition2026_experiments.md`、`data_sources_2026.md`
- PPT和视频素材：`docs/presentation_materials_2026.md`、`artifacts/competition2026/figures/`
- 提交检查：`docs/submission_checklist_2026.md`

2026复算采用真实公开的ERA5历史天气窗口、NOAA站点日背景和2023全国电力平均CO2因子；配电网、DER、故障、修复及医院任务仍是公开测试算例和工程假设。准确表述是“公开数据驱动的公开算例仿真”，不是现场实测数字孪生。

## 当前闭环


- 官方 MATPOWER `case33bw`：33 节点、32 条常闭支路、5 条常开联络线
- 逐节点有功/无功负荷，逐支路 R/X，10 MVA / 12.66 kV 基值
- 暴雨内涝、台风、极端高温三类灾害
- 多支路故障、孤岛识别、径向性检查和联络开关恢复
- 光伏、储能、柴油机和上级电网节点化联合调度
- 传统顺序、最小失供、碳韧协同三策略对照
- 同服务 `ε-constraint` Pareto 扫描：医院/关键服务硬锁、普通负荷让步显式化
- 每个 Pareto 候选重新执行 P/Q 潮流反馈，求解、合同、物理失败点全部保留
- 医院生命线 `CareTask`：节点、功率、时窗、deadline、连续时长、依赖与任务电压证据
- EENS、医院/关键负荷恢复率、柴油、新能源消纳和碳排指标
- 平衡三相 P/Q 径向前推回代潮流、支路负载率、电压和线损校验
- 无成网电源或资源越限孤岛硬失败，不用虚拟 slack 掩盖功率缺口
- 30 组蒙特卡洛场景、逐场景失败隔离、置信区间和失败重放 manifest
- 微网成岛能力护照：GFM/黑启动证据、P/Q/SOC/V/热限、episode与最薄弱约束
- 动作级 MRV：版本化因子注册表、逐时活动账、kgCO2 清单、碳对账、真实拓扑动作链、manifest、evidence index 与 seal
- 独立 MRV verifier：文件 SHA-256、行级语义 hash、跨表外键、能量/排放方程、动作终端 hash 和缺失/篡改检测
- Claim gate：严格同服务、受控普通服务预算与 inventory-only 三种主张资格分离
- Streamlit 数字孪生、八页交互界面、Pareto、成岛护照、生命线任务及 MRV 现场只读复核/ZIP 下载
- 评委决策工作台：推荐候选、Care/Physics/MRV 三门、FROZEN EVIDENCE、受控服务预算和 NO_GFM 反例预设
- Wave11 尾部风险卡：CVaR95、P95、failure budget 与失败分母；不使用均值掩盖台风尾部风险\n- Wave11 MRV 不确定性：固定 activity inventory，对 factor registry 的 uncertainty_pct 做 500 次确定性 LHS，输出 kgCO2 区间与排名稳定率\n- Wave10 冻结场景 catalog：3 灾种 × 3 强度 × 4 复本 = 36 条可重放 E 类合成压力场景；失败分母与 paired 统计基础函数
- 竞赛事实源与主张字典：`docs/competition_factsheet.yaml`、`docs/claim_dictionary.md`、`docs/evidence_index.csv`
- V08正式artifact重绘七张Wave10图，来源索引位于 `artifacts/wave10/figures/figure_source_index.csv`
- 评委演示预加载三灾种确定性pipeline cache；删除 `artifacts/wave10/pipeline_cache` 或设置 `GRIDRESCUE_FORCE_LIVE=1` 可切回现场重算
- 已完成36条Wave10物理批处理：`artifacts/wave10/batch36/experiment_runs.csv`、`validation_summary.csv`、`paired_deltas.csv`、`failure_manifest.json`
- C0/C4已分轨封存：`artifacts/wave10/c0_c4_gate/`；当前strict_eligible=0，controlled_eligible=36，明确保留same_service=false。
- 已增加3场景严格CareTask/Pareto合同Demo：`artifacts/wave10/strict_contract_demo/`，包含2个失败锚点且不填零。
- 第五届“双碳”大赛适配与匿名提交清单见 `docs/contest_fit_2026.md`，主申报建议赛道二。
- 网络数据 SHA-256、热限额假设和逐节点/支路结果随运行导出

## 运行

```powershell
cd <GridRescue项目目录>
$env:PYTHONPATH="$PWD\src"

python -m pytest -q
python -m gridrescue.cli --scenario "暴雨内涝" --output artifacts/flood `
  --created-at "2026-08-22T18:00:00+08:00"
python -m gridrescue.mrv verify artifacts/flood/mrv/run-7e495c4e6e73c188
python -m gridrescue.pareto --scenario "暴雨内涝" --strategy "最小失供恢复" `
  --fractions "0,0.04,0.05,0.06" --output artifacts/pareto_flood
python -m gridrescue.experiments --count 30 --seed 20260822 --output artifacts/mc30
python -c "from gridrescue.scenario_catalog import write_catalog; write_catalog('artifacts/wave10/catalog')"
streamlit run app.py
python scripts/smoke_demo.py
```

当前竞赛复算版全量回归测试为74项；V08历史冻结包的基线口径为46 passed，旧Wave11开发记录为61项。

2026竞赛提交包：

```text
release/GridRescue_Competition2026_Submission.zip
SHA-256 见 `release/GridRescue_Competition2026_Submission_SHA256.txt`
```

三个冻结证据场景位于：

```text
artifacts/v08_official/flood
artifacts/v08_official/typhoon
artifacts/v08_official/heat
```

## MRV 与主张边界

- 当前气体边界为 `CO2`，正式单位统一使用 `kgCO2`。
- 因子均标记为 E 类合成工程假设、`engineering_prior`、`conditional`。
- `SEALED` 表示证据文件已封存；`Verification=PASS` 表示文件完整性、内部引用和复算方程通过，均不代表现场实测或第三方核证。
- 当前碳韧策略相对最小失供策略存在额外普通负荷 EENS，因此主张状态为 `controlled_service_budget_inventory_difference`，不是严格同服务清单降低。
- 新能源弃电只作为机会损失指标单列，不进入主排放清单；开关和修复动作不直接乘排放因子。
- 当前模型固定为 24 个一小时时段；MRV 在配置、活动账和 verifier 中显式校验 `time_step_h=1.0`。

## 同服务 Pareto 口径

系统采用严格两阶段词典序求解，依次求医院、其他关键负荷和普通负荷的物理服务锚点：先最小化当前层服务损失，再把主目标最优值锁成硬上限并做确定性次级优化。三个锚点均须通过反馈收敛，之后只允许普通负荷在公开的 ε 预算内让步，并最小化恢复阶段碳排。每个点重新通过分岛平衡、P/Q 潮流、电压、支路热限额和损耗反馈。

四个合成 `CareTask` 的逐节点逐时最低功率同时进入每个锚点和候选的硬合同；任务级 deadline、连续时长、依赖和更严格电压阈值由潮流证据复核。任何任务失败的点保留在失败表中，不进入推荐前沿。任务参数永久标记为 E 类合成赛事模板，不代表医院实测或临床标准。

- `0%`：最小普通失供服务锚点；
- `ε>0`：受控普通负荷让步点；
- 求解失败、服务合同超限或物理失败：保留在 `pareto_failures.csv`，不进入推荐前沿；
- 碳排边界：上级电网购电、柴油发电和抢修车辆；新能源弃电作为机会损失单列。

## 当前模型限制

- 网络电气参数来自官方 MATPOWER `case33bw`；DER 位置、关键负荷类别和支路热限额属于项目工程假设，尚未接入实际馈线。
- 恢复计划仍采用启发式修复顺序和联络线选择；节点化资源调度与 P/Q 潮流通过迭代反馈闭环，尚未形成含整数开关决策的统一 MISOCP。
- DER 无功能力当前使用显式工程近似，下一阶段补充逐设备 `P²+Q²≤S²`。
- 故障概率为可复现实验场景，下一阶段接入武汉 ERA5/Open-Meteo 固化天气回放。
- 因子注册表当前已版本化并带行级 SHA-256，但数值仍为 E 类合成工程假设；接入公开或实测因子后需新增来源文件 hash 与审批记录。
- 当前只支持 `time_step_h=1.0`；开放半小时/十五分钟分辨率前，SOC、EENS、服务上限、碳核算和指标需端到端乘以时间步长。
