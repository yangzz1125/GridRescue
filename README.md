# 碳韧智网 GridRescue

极端天气下配电网恢复预案与可复算证据平台。基于公开算例、公开气象和工程假设的研究原型，尚未接入真实馈线，不是现场自动控制产品。

## 当前版本

2026-09-07 技术审计修复版，求解源码基线 `60a65bf`。

- 33节点、37支路，三种恢复策略、三个合成灾种与三个公开天气窗口。
- 节点化资源调度、径向P/Q潮流反馈、Care生命线任务和MRV证据门。
- 单线图、关键设施、节点详情、逐小时恢复和失败反例展示。
- 物理门已补双向功率失衡检查；持续恢复时间与首次全供电时间分开报告。
- 全批36场景和有/无Care合同扫描已按新源码重算。失败点保留在分母。
- 独立PYPOWER牛顿法对六类场景550个可求解分量时段完成交叉检查；392个停电或单节点分量不适用。该检查不代表现场校准、动态稳定或全局最优。

## 启动

Python 3.11。在克隆后的工程根目录执行，首次安装依赖需要联网，已有快照支持离线演示。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:PYTHONPATH="$PWD\src"
python -m pytest -q -p no:cacheprovider
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

访问 `http://localhost:8501`。端口被占用时换空闲端口。依赖下限不代表所有版本都已验收；本次计算环境版本见新实验的 `experiment_manifest.json`。

## 当前证据目录

| 目录 | 内容 |
|---|---|
| `artifacts/competition2026_audit_20260907/` | 合成基准、36场景、严格与去合同扫描、风险、配对统计、源码快照、图表 |
| `artifacts/public_replay_audit_20260907/` | 三个公开天气案例、新MRV、节点与潮流结果 |
| `artifacts/independent_powerflow_20260907/` | 独立PYPOWER比较及误差、分母、输入hash |
| `artifacts/submission_audit_20260907/` | 最终测试、页面检查与提交验证（生成后可用） |
| `data/public/` | 气象原文件、官方因子原文、NOAA日背景和来源清单 |

`v08_official/`、`wave10/` 和 `competition2026/` 是历史证据与回归样本，不是最新主结果。不得修改旧seal后当新结果使用。

## 重新计算

输出目录必须不存在或为空，禁止覆盖旧实验。下载原始数据不是复算的必要步骤；直接使用仓库中的公开快照。

```powershell
python scripts/run_competition_validation.py --output artifacts/my_new_run
python scripts/run_public_replay.py --output artifacts/my_new_public_run
```

可用 `--stages baseline batch pareto` 选择合成实验阶段。每次运行保存输入/源码副本、哈希、Git版本、依赖版本、阶段完成状态。失败不标为完成，不提供绕过指纹保护的强制覆盖模式。

独立验证、图表和PDF使用可选依赖：

```powershell
python -m pip install -r requirements-validation.txt
python -m playwright install chromium
python scripts/check_independent_powerflow.py --inputs artifacts/my_new_run/baseline_current artifacts/my_new_public_run --output artifacts/my_independent_check
```

独立验证器读取可信本地缓存并核对hash。不要加载不可信的pickle。`ui_network.py`为绘图层，`src/gridrescue/`为计算层。

## 指标与主张

- `restoration_time_h`：从该小时起至研究窗口结束持续达到全负荷供电；若 `restoration_completed=false`，24表示窗口内未完成，不是24小时完成。
- `first_full_supply_time_h`：首次全供电小时，不保证以后仍供电。
- CO2清单只计算购电、柴油发电和抢修车辆；不将恢复电量直接折算成减排。
- 当前合格配对的清单降低伴随普通失供增加，只能称受控服务预算下的清单差异。
- 公开天气采用ERA5再分析；年度电力因子采用2023全国平均0.5306 kgCO2/kWh。故障、抢修、设备及医院任务仍为工程假设；风雨没有被校准成真实线路故障概率。
- MRV PASS表示完整性和内部复算，不是第三方核证。独立潮流检查也不等于真实现场试验。

## 材料与提交

- `docs/submission_application_2026.md`：申报正文内容稿，需由团队核对官方模板和签字。
- `docs/competition2026_experiments.md`、`docs/technical_report_2026.md`：实验与技术依据。
- `docs/presentation_materials_2026.md`：讲解顺序和问答。
- `docs/team_defense_20260907.md`：提交前队员必须理解的内容。

```powershell
python scripts/build_competition_figures.py
python scripts/build_submission_document.py
python scripts/finalize_verification.py
python scripts/build_submission.py
python scripts/check_submission_ready.py --run-extracted-smoke
```

新包为 `release/GridRescue_Competition2026_Audit_Submission.zip`。旧的 `GridRescue_Competition2026_Submission.zip` 不能代替新包。最终是否可上传以最新校验结果、学校要求和正式模板审核为准，不以文件存在为准。

## 团队协作

在功能分支开发，先读 `agent.md`，修改共享算法后更新测试并在新目录复算。工程数据必须区分历史与当前版本，禁止为改善展示而删除失败点。AI不能代替具有参赛资格的真人队员；队伍人数、签字、学校审核及上传由团队按赛事规则完成。
