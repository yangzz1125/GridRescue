# 第五届研究生“双碳”创新与创意大赛：GridRescue评委策略

## 1. 赛道定位

官方赛题说明将“极端气候应对与韧性电网规划”列入赛题2.1“新型电力系统”，并说明涉及AI与数字孪生的通用方法/平台应投赛道10，而行业专用电网验证留在2.1。因此GridRescue主投2.1，副标题突出“极端天气下配电网故障恢复与低碳保供”。

## 2. 一等奖叙事

评委听感按四段走：

1. **硬问题**：极端天气下，关键服务、潮流安全、低碳目标互相冲突。
2. **硬创新**：Care→Physics→MRV三道资格门，禁止“少供电所以低碳”。
3. **硬证据**：同scenario_id配对，保留失败分母、NO_GFM反例、MRV verifier。
4. **硬落地**：医院/园区/数据中心/单馈线离线预案与演练入口，真实馈线按同一schema替换。

推荐首句：

> 我们不是给恢复系统贴一个碳看板，而是规定一个碳数字在什么服务、物理和证据条件下才有资格被相信。

## 3. 指标组合

- Care：关键EENS、关键负荷恢复率、essential_anchor通过率。
- Physics：潮流收敛率、电压/热限违规数、孤岛可行性、NO_GFM阻断数。
- MRV：kgCO2清单、activity→factor→inventory链、seal/verifier状态、17文件bundle完整率。
- 代价：普通服务EENS、预算百分比、失败场景数。

Wave10当前结果：关键EENS配对差−15.05 kWh；关键恢复率+0.0466个百分点；普通EENS+3192.85 kWh；运行清单−2331.35 kgCO2。该组结果只支持“受控服务预算下的运行碳清单差异”，不支持严格同服务减排。

## 4. 必做对照

- C0：最小失供参考；C4：碳韧协同候选；相同scenario_id、root seed、payload hash。
- NO_GFM/BLOCKED：证明系统不会让物理不可行候选进入推荐。
- 严格合同Demo：4/6点frontier eligible；台风2点在essential_anchor失败并保留，不填零。
- 9场景严格合同批：报告通过率、失败阶段、失败分母和OOS边界。

## 5. 五张主图

1. 三门漏斗/状态机。
2. 普通EENS—kgCO2 Pareto图，标C0/C4/blocked。
3. 配对森林图及bootstrap区间。
4. NO_GFM失败卡。
5. MRV抽屉：17 files、factor class E、manifest/hash、verifier PASS。

## 6. 十日排期

- D1：冻结赛道、主张字典、申报摘要。
- D2：完成严格合同9场景和报告。
- D3：3分钟工作台演示和录屏。
- D4：claim→artifact/run_id可追溯矩阵。
- D5：高压问答，重点练合成数据、减排边界、SEALED含义、现场控制边界。
- D6：首屏可读性、颜色、缓存和失败态。
- D7：盲审三轮，收集高频问题。
- D8：修复、全量测试和重跑。
- D9：manifest/hash/ZIP testzip，双备份。
- D10：只彩排，不新增算法。

## 7. 禁止夸大

- E类合成输入不是现场测量；36场景不是概率样本。
- strict_eligible=0不能写严格同服务减排。
- SEALED=内部文件完整性和复算，不是第三方核证。
- 离线预案原型不等于SCADA/OMS实时控制。
- 108/108策略行成功不等于真实灾害泛化。
- 本轮不加GNN、RL、MISOCP、AC-OPF或实时写回。
