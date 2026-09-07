# GridRescue 可视化审计与 README 插图建议

> 审计范围：`work/gridrescue` 的 `README.md`、`app.py`、`scripts/build_figures.py`、`artifacts/wave10/figures`、`artifacts/v08_official`、`artifacts/wave11` 与 `docs/`。本报告只改动本文件和 `docs/assets/readme/`，不直接改 README。

## 1. 当前可视化盘点

### 1.1 已有静态图（Wave10/V08 官方 flood bundle）

静态图由 `scripts/build_figures.py` 生成，输入固定为 `artifacts/v08_official/flood`，冻结日期 `2026-08-22`，运行号 `run-7e495c4e6e73c188`；来源与 SHA-256 在 `artifacts/wave10/figures/figure_source_index.csv`。为便于 README 引用，七张 PNG 已复制到 `docs/assets/readme/`，文件名保持不变。

| 文件 | 表达内容 | README 推荐位置 | 备注/验收点 |
|---|---|---|---|
| `wave10_01_strategy_comparison.png` | Traditional / EENS / Carbon-resilient 三策略的 EENS 与恢复阶段清单碳排并列比较 | **核心结果**，项目闭环介绍之后 | 两个指标量纲差异很大，当前共用 y 轴容易造成视觉误读；正文必须明确“不同尺度，仅读柱顶/表格”，后续最好改成双轴或标准化图。 |
| `wave10_02_inventory_breakdown.png` | 按 `crew_estimated`、`diesel_scope1`、`grid_scope2_location` 分解三策略 kgCO2 清单 | **MRV 证据**小节 | 图例使用机器字段名；README 第一次出现时应给中文释义，并强调只统计恢复增量边界。 |
| `wave10_03_physics_voltage_gate.png` | Carbon-resilient 方案 24 小时最小节点电压与 0.95 pu guardrail | **物理校验**小节 | 直观看出最低电压仍高于 0.95 pu，可配合 `powerflow_nodes_carbon_resilient.csv` 说明。 |
| `wave10_04_action_timeline.png` | 碳韧协同恢复动作的累计执行时序 | **恢复算法/数字孪生**小节 | 图只显示累计动作数量；若 README 需要解释“哪条线何时修复”，应同时链接 `actions_carbon_resilient.csv`。 |
| `wave10_05_pareto_controlled_service.png` | 普通负荷预算 0/4/5/6% 下 EENS 与 kgCO2 的受控服务 Pareto 趋势 | **同服务 Pareto**小节 | 当前图是双 y 轴，标题中使用“controlled-service”，不能写成严格同服务减排；应同步展示 `same_service_pass=false` 与受控预算边界。 |
| `wave10_06_mrv_reconciliation.png` | 每种策略 inventory 总量与 breakdown 复算值重合 | **证据可验证性 / MRV verifier**小节 | 用于说明“清单=分解复算”，不是第三方核证；正文要保留 `SEALED` 与 `Verification=PASS` 的边界。 |
| `wave10_07_caretask_contracts.png` | 四类医院生命线 `CareTask` 的合同窗口与完成小时 | **生命线任务**小节 | 适合解释 deadline、连续时长和任务电压证据；任务参数是 E 类合成赛事模板，不是医院实测。 |

### 1.2 新增 README 专用素材

以下文件已生成到 `docs/assets/readme/`：

| 文件 | 用途 | README 推荐位置 | 生成方式 |
|---|---|---|---|
| `case33bw_topology.png` / `.svg` | 33 节点 case33bw 拓扑；实线为常闭支路、虚线为常开联络线，红色节点为关键负荷 | **数据与网络模型**小节，解释为何使用 33 节点馈线 | Python + NetworkX，从 `gridrescue.network.build_ieee33()` 读取内置 MATPOWER 数据。 |
| `gridrescue_architecture.svg` | 场景→故障恢复→联合调度→P/Q 潮流→Care/Physics/MRV 三门→Claim/UI 的闭环架构 | README 开头“项目简介/系统原理” | 静态 SVG；同源 Mermaid 为 `gridrescue_architecture.mmd`。 |
| `claim_gates.svg` | CareTask、Physics、MRV 三门依次阻断失败候选，再分到 same_service / controlled budget / inventory_only | **主张边界**小节 | 静态 SVG；同源 Mermaid 为 `claim_gates.mmd`。 |
| `streamlit_tabs.svg` | 评委工作台及八个 Streamlit 交互页的导航关系 | **运行与界面**小节 | 静态 SVG；同源 Mermaid 为 `streamlit_tabs.mmd`。 |
| `*.mmd` | 可编辑 Mermaid 源图，方便后续更新 README 或答辩材料 | 作为源码附件或开发文档链接 | 直接编辑 Mermaid 后可由 Mermaid CLI/在线渲染导出 SVG。 |
| `figure_source_index.csv` | 七张官方图的冻结日期、run_id、单位和输入 SHA-256 | **可复现与证据**小节 | 从 `artifacts/wave10/figures/` 复制，供审阅者追溯。 |

## 2. README 建议的插图编排

建议 README 至少放 8 张图，按阅读路径排布：

1. **架构总览**：`gridrescue_architecture.svg`。回答“系统由哪些模块组成、三道门在哪里”。
2. **拓扑图**：`case33bw_topology.png`。回答“输入网络是什么，常闭/联络线和关键节点如何分布”。
3. **策略结果对比**：`wave10_01_strategy_comparison.png`。回答“为什么不是只看碳排，要同时看 EENS”。
4. **恢复动作时序**：`wave10_04_action_timeline.png`。回答“恢复计划如何随小时推进”。
5. **物理门证据**：`wave10_03_physics_voltage_gate.png`。回答“潮流、电压 guardrail 如何被验证”。
6. **CareTask 合同**：`wave10_07_caretask_contracts.png`。回答“医院生命线如何硬约束调度”。
7. **Pareto 前沿**：`wave10_05_pareto_controlled_service.png`。回答“普通服务预算与碳排/EENS 的权衡是什么”。
8. **MRV 复算**：`wave10_06_mrv_reconciliation.png` + `claim_gates.svg`。回答“证据如何封存、复算和决定主张等级”。

若 README 篇幅受限，优先保留 1、2、3、5、7、8；其余图链接到 `docs/visuals.md`（后续可由主 agent 创建）。

## 3. Streamlit 页面截图建议

`app.py` 是动态 Plotly/Streamlit 页面，静态 PNG 无法代替现场截图。README 应增加一个“交互界面”小节，至少给出以下截图或录屏帧：

| 截图 | 页面状态 | 如何复现 |
|---|---|---|
| 工作台 PASS | 侧栏 `暴雨内涝`、策略 `碳韧协同恢复`；证据预设“主推荐 · PASS” | `streamlit run app.py`，默认读取 `artifacts/wave10/pipeline_cache/`；截图工作台与三道门。 |
| 工作台 CLAIM GATED | 证据预设“受控预算候选 · CLAIM GATED” | 同上，切换 radio；用于展示 `same_service_pass=false`，避免 README 夸大结论。 |
| 工作台 BLOCKED | 证据预设“NO_GFM反例 · BLOCKED” | 同上；用于展示失败原因和重放入口。 |
| 恢复数字孪生 | `恢复进程/小时` 滑块在 0、4、12、23 各截一帧 | 展示故障支路、已闭合联络线、节点颜色和累计动作。 |
| 能源与碳流 | `能源与碳流` 页 | 展示 grid/diesel/BESS/PV area chart 与 unserved/SOC line chart。 |
| 潮流校验 | `潮流校验` 页 | 展示最低电压、最大支路负载率、不可行小时和逐时表。 |
| Pareto / 护照 / CareTask | 各页运行后 | Pareto 需点击“运行4点物理Pareto扫描”；护照需要选择策略；CareTask 直接展示。 |

截图不应提交浏览器地址栏、绝对路径或未冻结的临时缓存；建议保存到 `docs/assets/readme/ui_*.png` 并在图片下标注场景、策略、小时、run_id。

## 4. 现有图表质量问题与 README 文案约束

- **量纲问题**：`wave10_01_strategy_comparison.png` 将 EENS(kWh) 与 kgCO2 同轴，必须在图注中明确不同尺度；更佳方案是重绘双轴/标准化图。
- **主张边界**：`wave10_05_pareto_controlled_service.png` 只能支撑“受控服务预算下的清单差异”，不能写成“严格同服务碳排下降”。
- **数据级别**：CareTask 参数、DER 位置、支路热限额和排放因子均属于 E 类合成/工程假设；图注需保留这一标签。
- **时间冻结**：所有 Wave10 图均来自 2026-08-22 的 flood V08 bundle；README 应标注冻结日期，避免与实时 Streamlit 结果混淆。
- **证据语义**：MRV `SEALED`/`Verification=PASS` 表示文件完整性、引用一致和方程复算通过，不等同现场实测或第三方核证。
- **机器字段名**：`crew_estimated`、`diesel_scope1`、`grid_scope2_location` 第一次出现时需映射为“抢修车估算、柴油 Scope 1、上级电网 Scope 2 location-based”。
- **网络图来源**：case33bw 拓扑是 MATPOWER 官方案例 + 项目 DER/关键节点工程标注，README 应把二者区分说明。

## 5. 复现命令

```powershell
cd <GridRescue项目目录>
$env:PYTHONPATH="$PWD\src"
python scripts/build_figures.py
streamlit run app.py
```

拓扑图已由 Python + NetworkX 生成；复核时调用 `gridrescue.network.build_ieee33()`，以 `spring_layout(seed=18)` 绘制 33 节点和联络线，并输出 `docs/assets/readme/case33bw_topology.png/.svg`。

## 6. 主 agent 验收清单

- [x] 七张 Wave10 PNG 已进入 `docs/assets/readme/`。
- [x] 官方图索引 `figure_source_index.csv` 已随图复制。
- [x] 架构、三门、Streamlit 导航各有 Mermaid 源图和 SVG 成品。
- [x] case33bw 拓扑同时提供 PNG 和 SVG。
- [x] 每张图均记录表达内容、来源文件、生成命令和 README 放置位置。
- [ ] 主 README 插入图片并补充图注（由主 agent 统一编辑，避免多 agent 冲突）。
- [ ] Streamlit 动态页面截图（需要主 agent 启动应用后选择状态并截屏）。

## 7. 已存在的 UI 截图补充

`docs/assets/readme/app_overview.png` 与 `app_decision_workbench.png` 当前二进制内容和画面一致（均为暴雨内涝 + 碳韧协同恢复 + T+4h 的评委工作台 PASS 视图）。README 只保留一个主图即可，建议命名为 `app_decision_workbench.png`，另一个作为兼容别名或删除，避免文档出现重复截图。该截图适合放在“运行与界面”小节，图注应写明：V08 frozen evidence、2026-08-22、三道门 PASS、MRV 因子不确定性表。

## 8. 中文字体修复记录

2026-08-23 主代理发现初版 `case33bw_topology.png` 的中文图例和脚注显示为方框。现已新增 `scripts/build_readme_visuals.py`，统一显式选择 `Microsoft YaHei`，并设置 `svg.fonttype=path`：

- PNG 使用已验证的中文字体直接栅格化；
- SVG 将中文 glyph 转为路径，不再依赖阅读者机器是否安装同一字体；
- 已重绘 `case33bw_topology`、`gridrescue_architecture`、`claim_gates` 和 `streamlit_tabs` 的 PNG/SVG；
- 验证结果：四个 SVG 均不再包含 `<text>` 节点，中文已嵌入为路径。

重建命令：

```powershell
$env:PYTHONPATH="$PWD\src"
python scripts/build_readme_visuals.py
```

