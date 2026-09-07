# GridRescue 规模与性能基准

## 协议

- 数据源：仓库 MATPOWER `case33bw.m`、Baran-Wu 69-bus、IEEE PES 123 Node Test Feeder。统一为 `nodes.csv/branches.csv`，记录来源、版本、许可证、SHA-256，校验 `P/Q`、支路和径向性。
- 跑 33/69/123 节点×30/100/500 场景。种子 `20260822`，每组合 5 次，共45批；固定硬件、线程、Python/CVXPY/求解器版本。
- 计时边界为场景载入后至结果表生成前，分记建模、求解、潮流校验；预热两轮。下表是验收门槛，非实测值，单位秒。

| 节点/场景 | P50 | P95 | 可行率 | gap |
|---|---:|---:|---:|---:|
| 33/30 | 2 | 5 | 99% | 0.5% |
| 33/100 | 5 | 15 | 99% | 1% |
| 33/500 | 20 | 60 | 98% | 2% |
| 69/30 | 6 | 20 | 98% | 1% |
| 69/100 | 20 | 60 | 97% | 2% |
| 69/500 | 75 | 180 | 95% | 5% |
| 123/30 | 20 | 60 | 97% | 2% |
| 123/100 | 60 | 180 | 95% | 5% |
| 123/500 | 180 | 300 | 90% | 10% |

可行率须通过能量、SOC、径向、热稳和电压校验。gap 取求解器上下界，无下界时对比最佳已知目标。

## 记录与展示

单实例软限 120 s、硬限 300 s。回退链：incumbent；5% gap warm-start；K-medoids 约简至 30 场景；收益/(旅行+修复+碳)贪心。统一后验校验，以 `solution_mode` 分组。

`benchmark_runs.csv` 记录：`network,scenarios,seed,solver,version,threads,status,solution_mode,build_s,solve_s,validate_s,total_s,peak_rss_mb,objective,bound,gap_pct,feasible,timeout`；另存求解器日志和配置 JSON。聚合输出 `runs,feasible_rate,p50_s,p95_s,max_rss_mb,median_gap,p95_gap,fallback_rate`。

答辩图：规模×P95 热力图；时间--gap 散点图（按模式着色）；可行率与回退率折线图。注明硬件、求解器、时限、样本数，只引用实测 CSV。
