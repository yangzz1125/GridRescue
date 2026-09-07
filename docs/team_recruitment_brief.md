# GridRescue 参赛组队简报

## 一句话招募

华中科技大学电气背景，10 天做出一个可运行的软件作品：**极端天气下配电网故障恢复与低碳保供数字孪生平台**。不做硬件，核心是电气模型、优化决策、可复核证据和现场演示。

## 建议 4 人配置

| 角色 | 负责内容 | 最低交付 |
|---|---|---|
| 电气建模 | case33bw、P/Q潮流、孤岛、热限、CareTask | 1 个灾种场景可解释复现 |
| 优化与实验 | 三种恢复策略、36场景批、CVaR | `experiment_runs.csv`、配对统计 |
| MRV与软件 | factor registry、inventory、verifier、Streamlit | 可下载证据包、health smoke |
| 申报与演示 | 申报书、视频、答辩Q&A、盲审 | 180秒录屏和最终ZIP |

## 10 天分工

```text
D1：统一题目、赛道、主张边界
D2：冻结case33bw与三类灾种
D3：跑36场景和严格合同样本
D4：完成CVaR风险卡
D5：完成MRV敏感性卡
D6：工作台和视频初版
D7：校内盲审
D8：只修阻断问题
D9：打包、hash、离线备份
D10：彩排和提交
```

## 对外展示的核心指标

- 关键服务恢复率 / 关键 EENS：Care 门；
- 电压、支路热限、孤岛平衡：Physics 门；
- kgCO2 清单、factor 等级、SHA-256、verifier：MRV 门；
- CVaR95 与 failure budget：尾部风险；
- 台风 `normal_anchor → BLOCKED`：诚实失败证据。

## 每位队员必须记住的边界

```text
E类合成工程输入 ≠ 现场测量
SEALED ≠ 第三方核证
same_service_pass=false ≠ 严格同服务减排
```

## 现成工程入口

```powershell
cd C:\Users\ASUS\Documents\Codex\2026-08-22\n\work\gridrescue
python scripts\smoke_demo.py
python -m pytest -q
```
