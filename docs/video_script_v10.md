# GridRescue五分钟演示脚本 V10

**总时长：4分40秒以内**  
**素材：离线pipeline cache、V08冻结MRV、Wave10 36场景结果**

## 0:00–0:25 事件与问题

画面：暴雨/台风/高温三个灾种卡片，切入case33bw故障拓扑。  
旁白：极端天气下，恢复速度、生命线供电和运行碳排会互相牵制。GridRescue不只给一个结果，而是先判断这个结果是否有资格被相信。

## 0:25–1:10 三道门

画面：评委决策工作台，展示Care、Physics、MRV三张卡。  
旁白：第一道门锁定生命线CareTask；第二道门检查成岛、P/Q潮流、电压和热限；第三道门把活动账、因子、清单和seal串成可复算证据链。

## 1:10–1:45 推荐与受控差异

画面：主推荐预设→受控预算候选预设。  
旁白：碳韧候选的运行清单低于最小失供参考，但普通服务EENS增加。系统因此显示`same_service_pass=false`，只允许使用“受控服务预算下的运行碳清单差异”，不把少供电包装成严格减排。

## 1:45–2:10 NO_GFM反例

画面：切换NO_GFM反例，红色BLOCKED，不显示推荐按钮。  
旁白：如果孤岛缺少成网型电源，方案直接被物理门拦截。失败候选不会被删除，而是保留失败码和重放信息。

## 2:10–2:45 MRV复核

画面：MRV抽屉，展示17 files、Factor data class E、Verification PASS、reconciliation。  
旁白：SEALED只代表文件完整性与内部复算，不代表现场实测或第三方核证。我们可以现场篡改活动账，再运行verifier，系统会定位错误并FAIL。

## 2:45–3:35 36场景批处理

画面：3×3×4 catalog、validation summary、paired report。  
旁白：我们固定三种灾害、三档强度和四个复本，共36个scenario_id。三种策略共108条物理策略行全部完成。碳韧候选相对最小失供的配对均值差为EENS增加3192.85 kWh、运行清单减少2331.35 kgCO2；这是一项受控服务差异，不是严格同服务减排。

## 3:35–4:10 结果可追问

画面：七张图、动作时间线、CareTask时间线、source SHA。  
旁白：每张图都能反向追到run_id、输入hash、CSV和证据包；每个失败和每个主张都有明确边界。

## 4:10–4:40 落地与收束

画面：园区/医院/数据中心/单馈线离线PoV路径。  
旁白：当前版本定位为离线预案、演练和复盘工具，不写回现场SCADA。未来接入真实馈线、天气和因子后，沿同一数据卡和MRV schema重算。GridRescue不是让碳数字看起来更低，而是让它在服务、物理和证据条件下值得被相信。
# Wave11 增强插入点（2026-08-23）

在原 180 秒演示的 MRV/决策工作台段落中插入 20 秒：

1. **尾部风险卡**：展示 `mean / P95 / CVaR95 / failure budget`，说明推荐不是只看平均 EENS。
2. **因子不确定性卡**：展示 500 次确定性 LHS 的 `q05–q95 kgCO2` 区间；activity inventory 固定，只有 factor registry 扰动。
3. **边界句**：这两张卡只改变风险排序和不确定性表达，不改变 Care、Physics、MRV 三门，也不把 `same_service_pass=false` 包装成严格减排。

机器证据：

```text
artifacts/wave11/risk_report/risk_report.json
artifacts/wave11/mrv_sensitivity/sensitivity_report.json
```
