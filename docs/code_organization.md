# GridRescue 代码组织说明

这一轮先做**零破坏整理**：不搬动已有模块，不改变历史 import 路径，不重写已冻结 artifact。新增统一入口和分层索引，让后续开发先从一个入口进入，再按领域深入。

## 推荐入口

```python
from gridrescue.api import build_model, run_named_scenario, replay_public_event
```

- `build_model()`：构造固定 SHA-256 的 IEEE-33 模型。
- `run_named_scenario()`：运行内置灾害场景；不传参数时使用默认场景。
- `replay_public_event(...)`：读取 `data/events/event_*` 下的天气文件和 OEDI ZIP，执行真实事件回放。

## 代码分层（按职责理解，不强制物理搬目录）

```text
app.py / scripts/                 # 入口层：UI、批处理、发布和检查
src/gridrescue/api.py             # 统一公共 API
├─ network.py + case33_data.py    # 模型层：节点、支路、拓扑、case33bw
├─ scenarios.py + faults.py       # 场景层：天气参数、故障、联络线和状态
├─ restoration.py + dispatch.py   # 决策层：修复顺序、资源调度、服务合同
├─ powerflow.py + pipeline.py     # 物理层：P/Q 潮流、反馈迭代、可行性
├─ care.py + islands.py            # 可靠性层：医院任务、孤岛护照、GFM/黑启动
├─ carbon.py + metrics.py          # 核算层：排放因子、EENS、恢复指标
├─ mrv.py + facts.py + report.py   # 证据层：hash、seal、claim gate、报告
├─ pareto.py + risk.py             # 决策分析：Pareto、P95、CVaR、failure budget
├─ experiments.py + paired_stats.py + mrv_sensitivity.py
│                                  # 实验层：Monte Carlo、配对统计、不确定性
└─ real_event_mapping.py + real_event_replay.py
                                   # 外部事件层：天气/停电证据与 33 节点统计映射
```

## 文件怎么找

| 需求 | 先看 |
|---|---|
| 改节点、支路、DER | `network.py`, `case33_data.py` |
| 改灾害和修复顺序 | `scenarios.py`, `faults.py`, `restoration.py` |
| 改优化目标和资源约束 | `dispatch.py` |
| 改电压/热限/P-Q 校验 | `powerflow.py`, `pipeline.py` |
| 改医院生命线任务 | `care.py` |
| 改碳排放清单 | `carbon.py`, `mrv.py` |
| 改 Pareto/CVaR/不确定性 | `pareto.py`, `risk.py`, `mrv_sensitivity.py` |
| 接入真实天气/停电数据 | `real_event_mapping.py`, `real_event_replay.py` |
| 改界面 | `app.py` |
| 改批处理、打包、验收 | `scripts/` |

## 兼容规则

历史代码仍可使用：

```python
from gridrescue.network import build_ieee33
from gridrescue.pipeline import run_pipeline
```

新代码优先使用 `gridrescue.api`，这样未来物理分层或模块搬迁时，只需维护一个稳定入口。

## 清理边界

- `__pycache__/`、`.pytest_cache/`：运行时缓存，不进提交包。
- `release/`：只放最终 ZIP 和 SHA-256，不作为源码依赖。
- `artifacts/`：运行证据和冻结结果，不直接放业务实现。
- `data/events/`：外部真实事件输入与 replay 输出，和核心模型代码分离。

