# Wave10-P0 发布只读审计

- 审计日期：2026-08-23
- V08 冻结日：2026-08-22
- 范围：`app.py` 评委工作台、`src/gridrescue/facts.py`、四份 facts 文档（`competition_factsheet.yaml`、`claim_dictionary.md`、`competition_narrative.md`、`scope_log.md`）、`scenario_catalog.py`、`paired_stats.py`、`scripts/build_figures.py`、`release_manifest_wave10_submission.json`。
- 原则：只读检查；未修改现有源码、证据包或 manifest。

## 检查命令与结果

1. `python -m compileall -q app.py src/gridrescue scripts/build_figures.py`：通过。
2. Manifest JSON 解析与元数据读取：通过（`generated_at=2026-08-23`、`v08_freeze_date=2026-08-22`、Wave10 测试数 56、文件数 248）。
3. Manifest 文件存在性与 SHA-256 重算：通过；248/248 文件存在，0 个 hash mismatch。
4. 场景 catalog 复算：通过；代码生成 36 条、36 个唯一 `scenario_id`，生成 manifest 与 `artifacts/wave10/catalog/catalog_manifest.json` 完全一致（root seed `20260822`）。
5. `paired_stats` 聚焦 smoke：通过；缺失/非有限值保持为 failed，不被静默转为零；bootstrap/Wilson 输出可复算。
6. 目标 pytest（`test_app_workbench.py test_app_mrv.py test_facts.py test_scenario_catalog.py test_paired_stats.py`）：在 30 秒审计预算内仅完成部分采样（输出 4 个通过点后超时，进程未给出最终汇总）。不能据此替代 manifest 中声明的完整 `56 passed`，需单独做长超时回归。

## 通过项

### 评委工作台 / MRV 边界

- 工作台先展示候选、普通服务预算、候选-参考清单差与推荐资格，再呈现 Care/Physics/MRV 三道门；`NO_GFM` 预设明确显示 `BLOCKED` 和原因码，符合评委先看门控证据的路径。
- MRV 读取同时校验 `run_id`、manifest gates 与 `claim_gates.json`，并调用现场 `verify_mrv_bundle`；失败状态会被渲染为 BLOCKED，不进入正式主张。
- UI 和 facts 统一使用 CO2、kgCO2、E 类因子、`same_service_pass=false` 与 `controlled_service_budget_inventory_difference`，没有把清单差异写成严格同服务减排。

### Facts 文档与冻结口径

- 四份文档均标注 V08/2026-08-22 冻结语义，主张边界、seal 含义（文件完整性与内部复算，不是现场实测/第三方核证）和合成数据等级一致。
- `facts.py` 的 `validate_text` 会拦截 `kgCO2e/CO₂e` 及严格同服务减排措辞；`facts_path` 指向 canonical factsheet。

### Catalog / paired stats / figures

- catalog 是 3 灾种 × 3 强度 × 4 replicate 的确定性 36 行设计，payload SHA-256、seed、factor snapshot 和 claim boundary 均落盘。
- paired stats 显式区分 total/eligible/failed，支持 None/NaN 过滤、bootstrap seed 和 Wilson 区间，避免失败样本伪装成零收益。
- `build_figures.py` 固定读取 V08 flood 官方 bundle，所有图写入 freeze date、单位和 source SHA；manifest 中图和 source index hash 已通过重算。

### Release manifest

- `release_manifest_wave10_submission.json` 元数据完整，Wave10 交付物、V08 baseline（46）与 Wave10 测试数（56）分栏记录。
- 248 个清单文件均存在且 hash/bytes 与 manifest 一致，当前未发现发布包完整性破坏。

## P0 风险（发布前必须处理或明确签字）

1. **评委首屏计算路径可能超时（P0-UX/演示可靠性）**：`app.py` 在工作台渲染前立即执行 `cached_pipeline(scenario_name)`，并同时构建 network/pipeline 结果。30 秒审计预算内目标 pytest 只跑出 4 个点即超时，说明冷启动/Streamlit AppTest 路径存在明显耗时风险；评委若现场切换灾种或首次打开，可能看不到工作台与冻结证据。建议将冻结 bundle/轻量摘要作为首屏默认，完整 pipeline 改为显式按钮或后台缓存，并记录冷启动耗时。
2. **事实源与发布测试计数存在双口径（P0-Release consistency）**：`facts.py` 与四份 V08 facts 文档固定 `46 passed / 160.6 s`，Wave10 manifest 记录 `56 passed`。manifest 已注明 `v08_baseline_passed=46`，但 UI/README/申报材料若直接引用 `FACTS.tests_passed`，会与 Wave10 交付计数不一致。发布前需在主张字典中明确“V08 冻结回归 46；Wave10 当前回归 56”的显示规则，并做一次全文数字扫描。
3. **完整 pytest 回归尚未在本次审计窗口内复证（P0-verification gap）**：manifest 的 56 passed 未被本次 ≤30 秒聚焦命令独立复核；发布门应保留一条可重复的长超时命令（建议 180–240 秒）及日志/时间戳，特别覆盖 Streamlit AppTest 与 MRV bundle 现场复核。

## 下一步建议

1. 在干净环境执行 `python -m pytest -q`（至少 180 秒 timeout），保存 stdout、耗时和 Python/Streamlit 版本；把结果与 manifest `tests.passed` 对齐。
2. 给 `app.py` 增加首屏性能探针：记录 `cached_pipeline`、`load_mrv_ui_state`、首次绘图的耗时；若冷启动 >10 秒，默认加载冻结摘要，完整推演改成按钮触发。
3. 增加 `scripts/audit_release_consistency.py`：比较 `facts.py`、四份 facts 文档、README/申报材料、UI 文案和 release manifest 的日期、测试数、bundle 数、单位、claim_status，发现 46/56 等双口径时直接失败。
4. 发布前运行 manifest 重算（存在性、bytes、SHA-256）并锁定 `artifacts/wave10/figures/figure_source_index.csv`；禁止在 V08 冻结目录内覆盖文件。

## 结论

静态完整性、冻结主张边界、catalog/paired_stats 逻辑和 manifest hash 均通过；当前 P0 主要集中在评委首屏冷启动/现场可用性，以及 V08（46）与 Wave10（56）测试计数的发布口径统一。解决上述两项并完成长超时回归后再签署 Wave10-P0 提交。
