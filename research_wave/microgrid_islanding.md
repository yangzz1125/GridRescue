# 微网成岛与黑启动设计

## 目标
将现有“孤岛识别+聚合调度”升级为预案级成岛链：每个非根连通分量必须有可用grid-forming（GFM）资源，按黑启动次序恢复关键任务，逐时校验P/Q/V与功率平衡；失败即拒绝候选动作并回退。

## 数据
NodeAsset：node_id、critical_level、P/Q负荷、priority（医院/通信/民生）、min_service、deadline、cold_pickup。
DERAsset：node、kind（grid/PV/BESS/diesel）、pmax/qmax/smax、soc、black_start、gfm、start、ramp、availability。
IslandState：hour、island、nodes、root_connected、gfm_node、stage、P/Q、vmin、reserve、status。
SwitchAction：tie、hour、precondition（径向/同期/遥控/容量）、effect、approval。
现有nodes补Q、S、黑启动/GFM；branches补x、thermal_kva、遥控可用；FaultState补island与供电源。

## 算法
1. graph_from_state建图；root_component外connected_components为候选岛，先验is_radial。
2. 每岛选GFM：BESS-GFM优先，其次柴油GFM；PV仅有GFM逆变器/配套BESS时可用；检查SOC/燃料、S额定、启动时长、可用性。
3. 黑启动：GFM自检→站用/控制→医院一级→通信二级→民生三级；计入冷负荷冲击，越界则削减低级或延迟。
4. 每小时每岛校验ΣPgen−ΣPload−Ploss=0、ΣQgen−ΣQload−Qloss=0；LinDistFlow下0.95≤V≤1.05、S≤Smax；频率MVP以P_reserve≥最大阶跃负荷/最大DER损失作代理。
5. 仅“径向+GFM+P/Q平衡+V/热稳定”全通过才energize或close_tie；否则infeasible，回退传统顺序+人工确认。

## 失败条件
无GFM、SOC/燃料不足、启动晚于deadline、P/Q缺额、V越界/过载、成环/同期未知、遥控拒动、slack超阈值；任一项均不得显示已恢复。

## 接口
network.py复用GridModel、graph_from_state、islands、is_radial，新增island_analyzer。restoration.py在state_at_hour后调用并扩展actions。dispatch.py节点化ResourceConfig，输出P/Q/reserve/feasible。powerflow.py扩展validate_islands，返回每岛P/Q误差、GFM、Vmin、Smax、状态。pipeline.py输出岛屿时间线、失败日志至UI/MRV。

## 测试矩阵
根网正常；无GFM；BESS SOC不足；柴油成功；PV无GFM；医院时限；冷负荷过载分级削减；Q不足低压；联络成环；GFM故障/遥控拒动回退；逐时P/Q、V、S、SOC断言；33节点三策略回归。

