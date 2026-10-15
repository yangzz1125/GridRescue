# GridRescue 项目导航

碳韧智网 GridRescue 用于比较极端天气下配电网恢复预案，并提供交互页面、实验复算与提交材料。计算层、展示层和实验记录分开组织。

## 按目的进入

| 目的 | 入口 |
| --- | --- |
| 启动演示、查看当前版本 | [项目首页](../README.md) |
| 理解实验设计 | [实验说明](competition2026_experiments.md) |
| 阅读技术依据 | [技术报告](technical_report_2026.md) |
| 准备讲解与问答 | [汇报材料](presentation_materials_2026.md)、[队员答辩说明](team_defense_20260907.md) |
| 核对指标含义 | [主张与指标字典](claim_dictionary.md) |
| 修改项目 | [开发交接](../agent.md) |

## 启动本地演示

需要 Python 3.11 以上，以下命令在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

打开 `http://127.0.0.1:8501`。离线演示使用仓库中的快照；重新计算实验按首页的“重新计算”执行。

## 目录职责

| 路径 | 职责 |
| --- | --- |
| [app.py](../app.py) | Streamlit 应用入口 |
| [src/gridrescue/](../src/gridrescue/) | 网络、调度、指标与计算逻辑 |
| [ui_network.py](../ui_network.py) | 网络图展示 |
| [scripts/](../scripts/) | 批量实验、检查、绘图与提交包生成 |
| [tests/](../tests/) | 计算及页面相关回归测试 |
| [data/public/](../data/public/) | 公开来源数据与快照 |
| [artifacts/](../artifacts/) | 分版本的实验记录、指纹与图表 |
| [release/](../release/) | 提交包 |

## 开发和复算

安装开发依赖后运行 `python -m pytest -q -p no:cacheprovider`。算法改变后，使用新的实验输出目录复算，并保留输入、源码、版本和完成状态。

当前结果使用公开算例、公开气象与工程假设。阅读恢复时间、首次全供电时间、CO2 和 MRV 时，使用首页及指标字典中的定义。
