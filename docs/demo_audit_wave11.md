# GridRescue Wave11 演示工作台审查记录

**审查日期：2026-08-26**  
**对象：** `D:\桌面\GridRescue\_Wave11\_P1\app.py`

## 1. 审查方法

使用 Streamlit `AppTest` 从真实 `app.py` 启动工作台，并对三个证据预设逐一重跑：

```text
python -m pytest -q tests/test_app_workbench.py tests/test_app_mrv.py
6 passed
```

另执行发布检查：

```text
python scripts/check_submission_ready.py --run-smoke
passed=true
```

## 2. 评委首屏验收

默认场景启动无异常，首屏包含“评委决策工作台”，并同时展示三门闸指标：

- `Care / 服务合同`
- `Physics / 物理校验`
- `MRV / 证据复算`

推荐卡片同时给出普通服务预算、候选—参考清单差和推荐资格。当前文字明确使用“受控服务预算下的清单差异”，没有把结果包装成严格同服务减排。

## 3. 三个证据预设

### 主推荐 · PASS

- 工作台正常渲染；
- 评委可以直接看到 Care、Physics、MRV 三门状态；
- MRV 复核状态来自归档 bundle 的实时 verifier，而不是静态截图。

### 受控预算候选 · CLAIM GATED

- 明确显示 `same_service_pass=false`；
- 说明当前结论是“受控服务预算下的清单差异”；
- 不把普通服务让步隐藏在图表或下载文件之外。

### NO_GFM反例 · BLOCKED

- 以红色错误状态显示 `BLOCKED / NO_GFM`；
- 保留 `gate=G2`、`reason=NO_GFM`、`recommendation=disabled` 复放信息；
- 反例不进入推荐结果，验证失败原因可被评委复述。

## 4. 页面结构与讲解顺序

1. **恢复数字孪生：** 灾害场景、小时进程、故障支路、联络线和动作时间线。
2. **三策略对照：** EENS、柴油电量、碳排和峰值失供的同口径比较。
3. **能源与碳流：** 上级电网、柴油、BESS、PV 与 SOC 的逐时变化。
4. **潮流校验：** 电压、热限、线损、不可行小时和孤岛功率缺口。
5. **MRV报告：** 文件 hash、因子等级、seal、verification、claim gate 和下载入口。
6. **公平Pareto：** 固定修复顺序与联络线方案，仅扫描普通服务预算让步；失败点保留。
7. **成岛护照：** 展示 GFM 条件、最弱裕度和 BLOCKED 原因。
8. **生命线任务：** 医院、通信、冷链等 CareTask 的时窗、deadline、连续达标和电压约束。

## 5. 结论

演示链路已通过自动化验收。评委演示时应先讲三门闸，再展示 `NO_GFM` 反例，最后打开 Pareto 与 MRV 下载，形成“可服务 → 物理可行 → 可复算”的闭环。所有碳结论沿用 `claim_dictionary.md` 的受控服务预算口径。
## 6. Walkthrough correction (2026-08-26)

- Care/Physics/MRV are headline metrics, not clickable controls. The live walkthrough now uses the bottom tabs: `生命线任务` -> `潮流校验` -> `MRV报告`.
- The `NO_GFM反例 · BLOCKED` preset now synchronizes the headline `推荐资格` metric to `BLOCKED`; this removes the previous visual PASS/BLOCKED contradiction.
- The video script no longer refers to an MRV drawer, a recommendation button, or a paired forest plot that is not rendered by `app.py`; it names the actual evidence panel, metric, tables, and submission evidence package.
