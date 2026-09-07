# scripts 入口索引

脚本仍保留在当前目录，避免打破 README、评委命令和历史路径；按用途分组如下。

## 开发与演示

- `smoke_demo.py`：启动 Streamlit 并做健康检查。
- `run_strict_contract_demo.py`：运行严格服务合同示例。
- `run_wave10_batch.py`：运行 36 场景批处理。
- `real_event_replay.py`：回放 `data/events/event_*` 的公开真实事件。

## 数据、分析与报告

- `build_c0_c4_gate.py`：生成主张门和服务预算比较。
- `build_paired_report.py`：生成配对统计报告。
- `build_risk_report.py`：生成 P95/CVaR/failure budget。
- `build_mrv_sensitivity.py`：运行因子不确定性传播。
- `audit_claims.py`：扫描材料中的主张边界。

## 图像与视频

- `build_readme_visuals.py`、`build_figures.py`：重建正式图表。
- `build_demo_video.py`、`build_demo_narrated_video.py`：生成演示视频。
- `prepare_submission_media.py`、`render_submission_pdf.py`：准备提交媒体。

## 发布与验收

- `build_submission.py`：构建 ZIP 和 manifest。
- `check_submission_ready.py`：检查文件、媒体、claim、ZIP 和 smoke。
- `finalize_submission.ps1`：Windows 发布封装。

优先从项目根目录运行：

```text
python scripts/real_event_replay.py --event-id Texas-1 --county Harris --year 2021
python scripts/check_submission_ready.py
```

