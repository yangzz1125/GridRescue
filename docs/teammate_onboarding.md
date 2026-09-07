# GridRescue 队友 Onboarding 包（30–60 分钟/人）

> 目标：在不改核心算法的前提下，用两名真实学生完成**实验复核、演示复核、报名分工确认**。每人一次短任务即可，不要求长期维护代码。

## 0. 项目和文件位置

正式桌面工程：

```text
D:\桌面\GridRescue\_Wave11\_P1
```

源工作区（两处内容应保持一致）：

```text
C:\Users\ASUS\Documents\Codex\2026-08-22\n\work\gridrescue
```

核心叙事：

```text
Care 生命线服务合同 → Physics 配电网物理校验 → MRV 可复算碳证据
```

队友要记住的三条边界：

- 当前输入属于 E 类合成工程场景，不是现场测量；
- `SEALED / Verification=PASS` 代表文件完整性与内部复算通过，不是第三方核证；
- `same_service_pass=false`，正式表述是“受控服务预算下的运行碳清单差异”，不要说成严格同服务减排。

## 1. 分工总表

| 人员 | 任务 | 用时 | 最低交付 | 不需要做的事 |
|---|---|---:|---|---|
| 队员 A：实验复核 | 跑快速测试、看三门指标、确认失败反例仍保留 | 30–45 分钟 | 一份复核记录 + 3 个截图/终端输出 | 不改算法、不重跑整批实验 |
| 队员 B：演示复核 | 启动工作台、按脚本走一遍、指出表达卡点 | 45–60 分钟 | 一份彩排记录 + 3 个页面截图 | 不写代码、不做剪辑 |

项目负责人负责合并记录、修正阻断问题和最终提交；两名队员还需在报名系统完成真实入队确认。

---

## 2. 队员 A：实验复核任务卡（30–45 分钟）

### 2.1 任务目标

确认“代码可运行、基本测试通过、失败场景没有被隐藏”三件事，并把终端输出保存下来。只按下面命令执行，不要自行修改依赖或源代码。

### 2.2 准备（约 5 分钟）

打开 PowerShell：

```powershell
Set-Location 'D:\桌面\GridRescue\_Wave11\_P1'
$env:PYTHONPATH="$PWD\src"
python --version
```

若目录或 Python 版本有问题，直接把完整终端输出发给项目负责人。

### 2.3 快速复核命令（约 15–25 分钟）

**命令 1：核心门控测试**

```powershell
python -m pytest -q tests\test_care.py tests\test_islands.py tests\test_mrv.py
```

记录：退出码应为 `0`；终端应显示全部测试通过。若单项失败，保留完整 traceback。

**命令 2：应用健康检查**

```powershell
python scripts\smoke_demo.py
```

记录：输出应为 JSON，包含：

```text
{"health":"ok", "url":"http://127.0.0.1:8765/_stcore/health", "pid": ...}
```

**命令 3：查看已有冻结证据（不重新生成）**

```powershell
Get-ChildItem artifacts\wave10 -Directory | Select-Object Name
Get-ChildItem artifacts\wave11 -Directory | Select-Object Name
```

确认至少能看到 `pipeline_cache`、`risk_report`、`mrv_sensitivity` 等目录。不要删除 `artifacts`。

### 2.4 复核要点（约 10 分钟）

打开以下文件，各看一遍：

```text
D:\桌面\GridRescue\_Wave11\_P1\docs\technical_audit_wave11.md
D:\桌面\GridRescue\_Wave11\_P1\docs\strict_contract_9_report.md
D:\桌面\GridRescue\_Wave11\_P1\artifacts\wave10\strict_contract_9\strict_contract_manifest.json
```

确认并在记录中回答：

1. Care：医院/通信/冷链任务是否有功率、时窗、连续时长等合同字段？
2. Physics：是否检查电压、热限、P/Q 潮流和孤岛成网条件？
3. MRV：是否有 activity、factor、inventory、seal、verifier 这些证据环节？
4. 失败反例：`NO_GFM` 是否保留为 `BLOCKED`，而不是偷偷改成 PASS？
5. 主张边界：文档是否明确 `same_service_pass=false`？

### 2.5 队员 A 交付格式

复制下面模板，填完后保存为：

```text
D:\桌面\GridRescue\_Wave11\_P1\docs\review_records\teammate_A_experiment_review_YYYYMMDD.md
```

```markdown
# 队员 A 实验复核记录
- 姓名：
- 学院/年级：
- 日期：
- 工程路径：D:\桌面\GridRescue\_Wave11\_P1
- Python 版本：

## 命令结果
- 核心门控测试命令：
- 退出码：
- 通过数量/失败数量：
- smoke_demo 输出：

## 人工复核
- Care 合同字段看到了什么：
- Physics 校验字段看到了什么：
- MRV 证据字段看到了什么：
- NO_GFM 失败是否保留：是 / 否
- 是否看到 same_service_pass=false：是 / 否

## 问题与建议
- 阻断问题（没有则写“无”）：
- 最容易误解的一句话：
- 建议项目负责人修改的 1 件事：

## 附件
- [ ] 终端截图 1：pytest
- [ ] 终端截图 2：smoke_demo
- [ ] 文档/证据截图 1
```

---

## 3. 队员 B：演示复核任务卡（45–60 分钟）

### 3.1 任务目标

按评委视角走完一次 5 分钟演示，重点找“页面在哪里、数字是否能解释、哪句话会让人误以为是实测/严格减排”。队员 B 不改代码，只记录问题。

### 3.2 启动工作台（约 5 分钟）

```powershell
Set-Location 'D:\桌面\GridRescue\_Wave11\_P1'
$env:PYTHONPATH="$PWD\src"
streamlit run app.py --server.headless true --server.fileWatcherType none
```

浏览器打开终端显示的本地地址，默认通常为：

```text
http://localhost:8501
```

首屏应看到 **“⚡ 碳韧智网 GridRescue”** 和左侧“灾害场景/恢复策略/恢复进程”控件。

### 3.3 固定演示路线（约 30–40 分钟）

| 顺序 | 操作 | 要说清楚的点 | 截图建议 |
|---:|---|---|---|
| 1 | 场景选“暴雨内涝”，策略选“碳韧协同恢复”，小时滑块放 4 | 先讲问题：极端天气下恢复与低碳目标冲突 | 首屏 + 三道门 |
| 2 | 展示“评委决策工作台” | Care、Physics、MRV 三门是筛选门，不是三个装饰指标 | 三道门区域 |
| 3 | 证据预设选“主推荐 · PASS” | 冻结证据来自 V08 bundle，`SEALED` 只代表内部复算 | PASS 状态 |
| 4 | 证据预设选“受控预算候选 · CLAIM GATED” | 当前是受控服务预算下清单差异，明确 `same_service_pass=false` | 警示和表格 |
| 5 | 证据预设选“NO_GFM反例 · BLOCKED” | 孤岛无成网型电源时硬失败，失败点保留在证据中 | 红色 BLOCKED |
| 6 | 查看“医院生命线 CareTask” | 任务有节点、功率、时窗、deadline、连续时长和电压约束 | CareTask 表格 |
| 7 | 查看“微网成岛能力护照” | 每个孤岛单独说明 GFM/黑启动能力和失败原因 | 护照区域 |
| 8 | 回到“主张边界与证据入口” | E 类合成输入、CO2/kgCO2、内部 verifier；不做现场实测式表述 | 主张边界抽屉 |

### 3.4 评委口播最小版本（约 60 秒）

> “GridRescue 把极端天气下的配电网恢复拆成三道门：先确认医院等生命线服务合同，再用 P/Q 潮流、电压、热限和孤岛成网条件校验物理可行性，最后用 MRV 链条把活动量、排放因子、清单和文件哈希串起来。这里的 PASS 是内部可复算通过，不是现场实测或第三方核证；受控预算页明确标注 `same_service_pass=false`，而 NO_GFM 反例会直接 BLOCKED，失败不会从分母里消失。”

### 3.5 队员 B 交付格式

保存为：

```text
D:\桌面\GridRescue\_Wave11\_P1\docs\review_records\teammate_B_demo_review_YYYYMMDD.md
```

```markdown
# 队员 B 演示复核记录
- 姓名：
- 学院/年级：
- 日期：
- 浏览器/分辨率：

## 演示检查
- [ ] 首屏在 30 秒内打开
- [ ] 暴雨内涝 + 碳韧协同恢复 + T+4h 可选
- [ ] 主推荐 PASS 可见
- [ ] 受控预算候选 CLAIM GATED 可见
- [ ] NO_GFM反例 BLOCKED 可见
- [ ] CareTask 页面可解释
- [ ] 微网成岛能力护照可解释
- [ ] 主张边界抽屉可打开

## 表达审查
- 最难听懂的 3 句话：
  1.
  2.
  3.
- 评委可能追问的数字：
- 哪个页面最容易被误读成“实测/严格减排”：
- 建议删掉或改短的 1 句话：

## 计时
- 首屏到三门：     秒
- 三门到 NO_GFM：   秒
- 全程：            分 秒
- 是否控制在 4:55 左右：是 / 否

## 附件
- [ ] PASS 截图
- [ ] CLAIM GATED 截图
- [ ] BLOCKED 截图
```

---

## 4. 招募短文（直接复制发送）

### 4.1 30 分钟实验复核版

> 【招募双碳赛队友｜一次 30 分钟】我是华中科技大学电气方向研究生，已做完一个纯软件项目：极端天气下配电网故障恢复与低碳保供数字孪生平台。现在需要 1 名真实学生队友，帮忙按 3 条命令跑测试、看一次结果并填一页复核记录，不写代码、不长期维护。项目代码、界面和材料已完成，感兴趣私聊，报名信息按真实情况填写。

### 4.2 60 分钟演示复核版

> 【招募双碳赛队友｜一次 1 小时】项目是 GridRescue：极端天气下配电网故障恢复、生命线保供和可复算碳证据工作台。需要 1 名同学按 5 分钟脚本走一遍 Streamlit 页面，指出 3 处表达问题并完成一次报名确认，不要求写代码。电气、计算机、自动化、经管等专业都可以，感兴趣私聊。

### 4.3 线下当面一句话

> “代码和申报材料已经有了，你只需要真实参与一次实验复核或演示彩排，再完成报名确认；我把任务压到 30–60 分钟。”

---

## 5. 项目负责人验收表

在两名队员交回记录后，项目负责人逐项勾选：

- [ ] 队员 A 是真实学生，完成实验复核并留下终端输出；
- [ ] 队员 B 是真实学生，完成演示彩排并留下计时/截图；
- [ ] 两人都完成报名系统入队确认；
- [ ] 队员 A 能用一句话解释 Care / Physics / MRV；
- [ ] 队员 B 能指出 `same_service_pass=false` 和 `NO_GFM/BLOCKED` 的含义；
- [ ] 任何材料没有把 AI 写成报名队员或署名作者；
- [ ] 复核记录已放入 `docs/review_records/`，不覆盖原始证据；
- [ ] 最终 ZIP、视频和申报书各保留两份备份。

## 6. 彩排检查表（最终一次，约 15 分钟）

### 技术

- [ ] 从 `D:\桌面\GridRescue\_Wave11\_P1` 启动，不依赖 C 盘源目录；
- [ ] 断网时首屏仍能启动并读取冻结证据；
- [ ] 暴雨成功路径能在 60 秒内讲清；
- [ ] 台风/NO_GFM 失败路径能在 30 秒内讲清；
- [ ] 评委问“是不是严格减排”时，回答“当前不是，主张是受控服务预算下的运行碳清单差异”；
- [ ] 评委问“SEALED 是不是权威认证”时，回答“只证明文件完整性与内部复算”；
- [ ] 评委问“数据来源”时，回答“E 类合成工程输入，后续可替换为现场计量数据”。

### 表达

- [ ] 开场 20 秒说清对象、痛点和软件形态；
- [ ] 先讲三门闭环，再讲指标，不反过来堆数字；
- [ ] 每个页面只说一个结论；
- [ ] 4:55 内结束，留 5–10 秒缓冲；
- [ ] 不使用“实时控制、现场实测、第三方核证、严格同服务减排”等超出当前证据的表述。

## 7. 记录文件夹约定

若不存在记录目录，先创建：

```powershell
New-Item -ItemType Directory -Force 'D:\桌面\GridRescue\_Wave11\_P1\docs\review_records'
New-Item -ItemType Directory -Force 'C:\Users\ASUS\Documents\Codex\2026-08-22\n\work\gridrescue\docs\review_records'
```

队友记录文件只新增、不覆盖；文件名格式：

```text
teammate_A_experiment_review_YYYYMMDD.md
teammate_B_demo_review_YYYYMMDD.md
```

项目负责人完成验收后，把两份记录和截图加入最终提交包的 `docs/review_records/`，便于答辩时说明真实分工和可复核过程。
