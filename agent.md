# GridRescue AI 交接与 Git 管理

## 当前工程

- 唯一开发目录及 Git 根目录：`D:/桌面/GridRescue/_Wave11/_P1`（A）。所有下文相对路径均从这里计算。
- 2026-09-07 按用户批准，将 `D:/桌面/GridRescue_Wave11_P1`（B）的有效文件完整替换到 A。后续不要继续编辑 B；B 保持迁移时原状。
- 这是 B 的 Competition2026 实现，不是迁移前 A 的实现。不要依照旧交接记录导入不存在的 `gridrescue.api`、`real_event_mapping`、`real_event_replay` 或医院 CSV 加载接口。
- 迁移阶段只复制 B 并初始化 Git；后续开发记录见本文末尾。源 B 不再同步修改。

## Git 与恢复

仓库使用 `main` 分支，无远端，尚未推送。使用本机已有 Git 身份；仅设置仓库级 `core.autocrlf=false`，保持数据和证据字节不被自动换行转换。

```powershell
Set-Location "D:\桌面\GridRescue\_Wave11\_P1"
git status --short --branch
git log --oneline --decorate
git diff pre-b-replacement..main -- src app.py tests
```

- 覆盖前提交：`9da8347`，标签 `pre-b-replacement`，提交说明 `chore: snapshot project A before replacement`。
- 覆盖后提交说明：`chore: replace project A with project B`。通过 `git log` 获取提交 ID，避免在提交内自引用其 hash。
- 后续每项任务单独检查 diff、验证并提交；提交前检查新文件、秘密配置及大文件。未经明确要求不设置远端、不推送、不执行破坏性 reset/clean。
- `.gitignore` 排除运行缓存、虚拟环境、秘密配置、临时日志、发布 ZIP/SHA 和原始大型下载 ZIP。源码、输入、机器可读证据、图像、必要 PDF 和可信 pipeline pickle 缓存纳入 Git。
- 完整恢复不能仅依赖 Git：被忽略的大文件保存在覆盖前完整备份。

完整备份位于工作区 `backups/A_before_B_20260907_104423/`（相对于工程根目录为 `../../backups/A_before_B_20260907_104423/`）：

| 文件 | 用途 |
|---|---|
| `A_complete.zip` | 覆盖前 A 全部 926 文件，含原始 OEDI ZIP、发布包及运行缓存 |
| `A_manifest.json` | 覆盖前逐文件字节数和 SHA-256 |
| `B_manifest.json` | B 全部 1,341 文件的来源快照与迁移排除规则 |
| `A_displaced_worktree/` | 原 A 文件移出后的完整工作树，不含后来初始化的 Git |
| `workspace_agent_before.md` | 原外层交接说明 |
| `backup_verification.json`、`migration_verification.json` | 备份/迁移校验记录 |
| `post_migration_mrv.json` | 本次 9 个正式证据包的只读验证结果 |

ZIP SHA-256：`bd4e16ca93ec6b378cdd7a0684488c4a6219cf437ac082e31eaa22ac7844ba47`。
需要回看旧功能，使用 `git show pre-b-replacement:src/gridrescue/api.py` 等只读命令；需要恢复完整旧工程时先解压到另一个目录，不直接覆盖当前开发树。

## 项目与入口

GridRescue 是极端天气配电网恢复与碳清单协同决策的离线研究/竞赛原型，不是现场自动控制系统。

- Python >=3.11，NumPy、pandas、NetworkX、CVXPY/CLARABEL、Streamlit、Plotly；pytest 为测试依赖。
- MATPOWER case33bw：33 节点、32 常闭支路、5 常开联络线；24 个一小时时段。
- 三策略：传统顺序恢复、最小失供恢复、碳韧协同恢复。
- 新入口从 `pipeline.run_pipeline()`（内置灾种）或 `pipeline.run_scenario()`（自定义场景）开始；本版本没有统一 `api.py`。
- UI 是 `app.py`，样式和公共展示函数在 `ui.py`、`ui/styles.css`、`.streamlit/config.toml`。
- 页面为决策总览加原有 8 个功能标签页，共 9 页；场景有 3 个合成灾种和 3 个公开天气案例。

先读 `app.py`、`src/gridrescue/pipeline.py`、`src/gridrescue/scenarios.py`、`src/gridrescue/public_data.py`，需要实验背景再读 `README.md`、`docs/technical_report_2026.md` 和 `docs/competition2026_experiments.md`。旧研究计划及旧 README 段落可能滞后，不能当作当前实现。

## 运行命令

必须从实际工程根目录执行，避免相对路径或包导入指向 B：

```powershell
Set-Location "D:\桌面\GridRescue\_Wave11\_P1"
$env:PYTHONPATH = "$PWD\src"
$env:PYTHONUTF8 = "1"
python -m pytest -q -p no:cacheprovider
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

端口被占用时换空闲端口。需要安装新环境时使用 `python -m pip install -e ".[dev]"`；已有可用环境不必重装。当前依赖只设最低版本，没有锁定文件。浏览器脚本需要额外的 Playwright 及浏览器，不是运行主程序的必要依赖。

```powershell
python scripts/smoke_demo.py --port 18766
python -m gridrescue.cli --scenario "暴雨内涝" --output artifacts/new_experiment
python -m gridrescue.mrv verify artifacts/competition2026/baseline_current/flood/mrv/run-3d4fa009bfe41047
```

新实验使用新的输出目录；不要覆盖已有结果。MRV verify 默认只读，不要对冻结证据随意使用 `--write-result`。smoke 只检查健康端点并关闭测试进程，不是浏览器视觉验收。

## 核心职责

| 需求 | 源码（src/gridrescue/） | 主要测试（tests/） |
|---|---|---|
| 网络、拓扑、修复顺序 | `case33_data.py`, `network.py`, `faults.py`, `restoration.py` | `test_core.py` |
| 资源调度和潮流反馈 | `dispatch.py`, `pipeline.py`, `powerflow.py` | `test_core.py`, `test_competition_regressions.py` |
| 生命线任务与孤岛能力 | `care.py`, `islands.py` | `test_care.py`, `test_islands.py` |
| 内置/公开场景 | `scenarios.py`, `public_data.py`, `scenario_catalog.py` | `test_public_data.py`, `test_scenario_catalog.py` |
| 碳与证据 | `carbon.py`, `metrics.py`, `mrv.py` | `test_mrv.py`, `test_app_mrv.py` |
| Pareto/批实验/统计 | `pareto.py`, `experiments.py`, `paired_stats.py`, `risk.py`, `mrv_sensitivity.py` | 对应同名测试及 `test_competition_regressions.py` |
| UI | 工程根目录 `app.py`, `ui.py`, `ui/styles.css` | `test_app_workbench.py`, `test_app_mrv.py` |
| 发布 | 工程根目录 `scripts/build_submission.py`, `check_submission_ready.py` | `test_submission.py` |

调用链：场景/网络 -> 修复计划/空间调度 -> 径向 P/Q 潮流 -> 损耗与服务上限反馈 -> Care/孤岛/指标 -> MRV 导出/复核。普通 pipeline 与严格 Pareto 合同不能混同：普通碳韧路径有普通负荷预算放松兼容行为；严格候选不可用这一行为掩盖失败。

## 缓存与公开数据

- 新结果主目录为 `artifacts/competition2026/`。`baseline_current/` 为合成场景当前演示缓存和证据；`public_replay/` 为公开天气案例；另有批实验、风险、敏感性、图表与验证记录。
- `cached_pipeline()` 校验源代码指纹与 pickle SHA；UI 还核对公开输入、归档 dispatch 和代码 hash。不能任意改文件后继续使用原封存主张。
- `$env:GRIDRESCUE_FORCE_LIVE="1"` 可强制求解，设置后应重启应用/清缓存；不自动生成新 MRV。
- `GRIDRESCUE_MRV_BUNDLE` 可指定证据；`GRIDRESCUE_RISK_REPORT` 可指定风险报告。来源/版本不匹配必须阻断推荐。
- 只加载可信本地 pickle，不接受用户上传或不可信下载的 pickle。
- `data/public/source_manifest.json` 管理公开天气、全国年度电力因子及 NOAA 背景数据来源。
- 三案例：武汉高温 2022-08-15、武汉降雨 2020-07-06、厦门大风 2016-09-15。
- `public_data.py` 用逐时温度/辐射经工程转换生成负荷/PV曲线；全国2023年度电力因子为 0.5306 kgCO2/kWh。天气与因子年份不同，属于参考情景，不是历史排放重建。
- 本版本没有美国 OEDI 事件回放模块；对应旧源码只能从覆盖前 Git/备份取回，不应无测试直接混入。

## 不可突破的边界

- 当前是公开算例、ERA5 再分析、官方统计与工程故障/设备/任务假设的混合输入，不称真实馈线事故复原或临床实测。
- 正式气体边界 CO2、单位 kgCO2、步长 1.0h；不可只改界面就宣称更细时间精度。
- 服务不等价时只比较受控服务预算下的运行碳清单差异，不宣称严格同服务减排。
- SEALED/verification PASS 只说明内部完整性与复算，不代表第三方核证。
- 故障、合同、物理、证据失败保留原因和分母，不填零或删行换取通过。
- 冻结数据、manifest、hash、seal 不手动改；新算法或因子实验写新目录。

## 本次迁移验收（2026-09-07）

- B 的 1,287 个有效文件迁入 A，逐文件 hash 和文件集合核对一致；只新增 Git 管理和本文档。源 B 保持不变。
- 在 A 指定 `PYTHONPATH=A/src` 跑全量回归：**75 passed in 172.19s**。
- competition2026 正式验收清单中 9 个 bundle 全部只读验证通过：6 个合成包各17文件，3个公开数据包各20文件。
- 已知失败的中间 bundle 保留原样，不纳入正式9包通过声明。
- Streamlit 健康检查端口18766通过，临时进程已退出。
- 本次未重跑36场景、未重新截图、未修改算法、未重建发布包。历史文档中74项测试为旧验收，不能冒充本次数据。

## 前端开发记录（2026-09-07）

- 修复 `app.py` 的预设与顶部资格不同步：读取当前 session state，NO_GFM 显示 BLOCKED，受控预设在实际证据通过时显示 CLAIM GATED，返回主推荐恢复真实资格。
- 缺失或不合格证据始终优先 BLOCKED，不允许演示预设把失败升级为 PASS。三门明确标为“当前推演证据”，保持真实值，NO_GFM 文案标明演示预设。
- 将旧的仅检查错误文字测试替换为有效证据下完整切换测试，另扩展缺失证据的三预设回归；测试数量未增加，但覆盖更强。
- UI/MRV 专项：12 passed；全量：75 passed in 171.04s。新增回归在修复前确实因 PASS != BLOCKED 失败。
- Playwright 实测1440×1000桌面、390×844手机：三预设状态、6个KPI、33节点、无页面级横向溢出；桌面9标签页和小时滑块切换通过。截图和检查在 `artifacts/frontend_review_20260907/`，没有覆盖旧验收图。
- 浏览器脚本增加可选输出目录，复跑命令：`python scripts/check_frontend.py --url http://127.0.0.1:8501 --output artifacts/frontend_review_20260907`。该脚本假设默认暴雨页面具有合格的当前证据。
- 本地开发服务当前地址为 `http://127.0.0.1:8501`，最近重启进程37452，日志在系统临时目录 `gridrescue_frontend_8501.log`；后续会话先确认存活，不假设服务永久运行。
- 未修改求解模块、因子、冻结证据、CSS或发布ZIP；本轮不是全面视觉重构。

## 第二轮布局修复（2026-09-07）

- 风险卡将策略名单独放一行，CVaR/失败率放下一行；修复 Streamlit 指标内部子元素的 nowrap/ellipsis，长值可换行，不只修改外层 CSS。
- 拓扑标签按固定横坐标交错上下位置，代替节点编号奇偶，解决320px屏幕下 N22/N26 同侧文字重叠。未改变节点、拓扑、服务状态或字号。
- 浏览器回归扩展到1440、1024、390、320px：33节点及33文字标签保留、节点文字框零重叠、风险策略值无裁剪、页面无横向溢出、三预设切换通过。检查与截图在 `artifacts/frontend_layout_20260907/`。
- 新浏览器断言在修复前因 `risk strategy clipped` 失败；修复后通过。UI/MRV专项12 passed，全量75 passed in 169.43s；未修改算法、证据或发布ZIP。
- 默认暴雨是本轮浏览器几何检查场景，不代表全部场景、所有图表均经过视觉验收。

## 比赛展示样式调整（2026-09-07）

用户明确此项目用于比赛展示，不应改成日常运维后台。当前方向：项目身份、恢复现场、候选差值及验证依据优先，减少模板化装饰。

- 主标题突出“碳韧智网 GridRescue”及实际题目，去掉GR方块、侧栏编号、赛事角标。保留场景/策略/时间操作和9标签页。
- KPI去底色与分隔小卡，重点加粗前三项；拓扑去灰色框底；评估区改为“方案评估”，首屏三门使用简洁中文名称。
- 方案碳清单差突出显示，仍连同普通服务预算、真实资格和主张边界呈现；不得将其包装为严格同服务减排。
- 节点提示补充实际服务功率与供电状态；恢复曲线图增加坐标和图例留白，策略颜色更易区分。
- 清理未使用CSS规则，字号不随屏幕宽度缩放；必要内容按布局换行，不隐藏失败告警或证明字段。
- 全量75 passed in 169.80s；重启开发服务后浏览器1440/1024/390/320px检查通过。截图与结果在 `artifacts/contest_visual_20260907/`。测试中的首屏标题/门标签断言随显示文案更新，门控逻辑未变。服务禁用了文件监听，修改入口或UI模块后需重启再做浏览器验收。
- 未修改核心算法、冻结证据或重新发布。视觉风格是否符合评委演示需求，仍以用户实际查看后的反馈为准。

## 比赛展示层重构（2026-09-07）

用户要求从头重建展示层，不再局部简化。保留Streamlit与求解/证据模块，重写 `ui.py` 和 `ui/styles.css`，调整 `app.py` 的首屏及主要分析页。

- 新布局：深色操作侧栏、三项主要KPI与三项次要数据、高对比电网恢复图、集中方案结论、三策略实数对比卡和服务轨迹/风险区。
- `render_strategy_comparison()` 从当前 `comparison` DataFrame生成三策略卡，同时保留碳清单、EENS和关键恢复率；`STRATEGY_COLORS` 在卡片与对比图复用，选择的策略高亮，不代表最低碳自动获胜。
- 新增时间前后步进图标按钮，键 `hour-previous` / `hour-next`；小时滑块键 `restoration_hour`，0和23边界禁用对应方向，原预设门控不变。
- 三策略页采用不同量纲的独立横向柱图，不再混合归一化柱；能源页用PV可用量减弃光显示实际光伏利用，功率和储能电量拆图；潮流页分电压和热限图，标注现有0.95pu/100%工程限值。均为展示层转换，不改原始数据。
- 修复深色侧栏按钮对比度、手机KPI断行以及柱图策略标签裁切。手机主KPI逐行排列，三策略卡纵向排列，全部数字不拆行。
- 全量75 passed in 170.50s；最终图表留白调整后UI/MRV专项12 passed in 20.07s。六场景AppTest逐一无异常，均保留9页及三策略结果。
- 浏览器1440/1024/390/320px验证通过，包括33节点/标签、数字单行、卡片数量/高亮/溢出、策略名完整和预设切换；保存所有桌面标签页截图。产物目录 `artifacts/showcase_rebuild_20260907/`。
- 开发服务仍为8501，修改UI模块后已重启；当前PID见上方记录。未重建发布ZIP、未改核心算法或封存证据。

## 已知后续事项

1. 手机各分析图的完整视觉体验仍可继续打磨；本轮四宽度浏览器几何检查以默认暴雨总览为主，其余页面有桌面截图及六场景AppTest，但不等于每个场景/页面/尺寸组合均验收。
2. `release/GridRescue_Competition2026_Submission.zip` 是 B 原有旧包，未包含最新 UI 文件。`build_submission.py` 白名单已经更新，但重新发布前必须重跑验收并重建包。
3. `ui.py` 仅抽出部分展示函数；本次不继续分拆 `app.py` 或更换前端框架。
4. A 独有 API、医院来源字段与 OEDI 功能没有自动合并；仅在用户明确需要时逐项移植和回归。

后续任务先 `git status`、读取相关代码和调用方，按最小范围修改并验证；不要把源码迁移任务扩展成算法重写或覆盖历史证据。
