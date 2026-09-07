# GridRescue 5 分钟答辩与 UI 导演稿

## 镜头脚本（300 秒）

| 镜头/时长 | 操作 | 旁白 | KPI | 新增字段 |
|---|---|---|---|---|
| 1 灾情首屏 0:00--0:25 | 选“暴雨内涝”，拓扑切到故障态 | “医院和通信负荷进入风险；系统锁定灾情与碳边界。” | 故障数、关键节点、初始失供 | `event_id,severity,failed_branches,critical_nodes_at_risk,initial_unserved_kw` |
| 2 三策略时间线 0:25--1:10 | 同步推演到 T+6 h | “同一资源，只改变决策：传统按顺序，韧性先保任务，碳韧再压柴油。” | 三策略 EENS、关键恢复率、碳排 | `strategy,action_seq,start_h,end_h,cumulative_eens_kwh` |
| 3 拓扑特写 1:10--1:55 | 停在首次联络线闭合，点击故障线与恢复岛 | “闭合联络线恢复医院岛，同时保持径向，并通过电压和热稳校验。” | 带电节点、孤岛、最低电压、最大负载率 | `node_energized,island_id,branch_state,action_reason,min_voltage_pu,max_loading_pct` |
| 4 医院任务 1:55--2:35 | 展开医院抽屉，从“负荷”切到 ICU/急诊/冷链 | “关键负荷不是一个百分比；每项临床任务都有功率门槛和最迟恢复时间。” | ICU 保障小时、SLA、首次恢复时刻 | `task_id,hospital_node,min_kw,deadline_h,served_kw,coverage_pct,sla_breach` |
| 5 Pareto 2:35--3:20 | 拖“低碳--均衡--高韧”滑杆，选折中点 | “不存在单一最优；该点先满足临床任务，再以少量时间换柴油和碳排下降。” | EENS、kgCO2、成本、恢复时长 | `pareto_id,epsilon_eens,carbon_kg,cost_yuan,service_equivalent` |
| 6 MRV 3:20--4:15 | 点亮电网/PV/储能/柴油流，展开碳账本并导出 | “排放按电网、柴油、抢修车辆分项；弃光只记机会损失，恢复供电不冒充减排。” | 柴油、PV 消纳、直接碳、机会碳 | `grid_kg,diesel_kg,crew_kg,curtailment_kwh,opportunity_kg,input_sha256,solver_status` |
| 7 随机扰动 4:15--5:00 | 固定 seed，加入道路、修复、PV 扰动，显示 P50/P90 | “方案不只赢一个剧本；尾部风险、回退路径和耗时留痕。” | 可行率、P50/P90 EENS、回退率、耗时 | `seed,road_delay_h,repair_multiplier,pv_derating,scenario_eens,solution_mode,runtime_s` |

## 五页升级

1. **恢复数字孪生**：灾情条、拓扑、时间线、医院抽屉共享小时游标。
2. **三策略对照**：三列同步小窗，增加 KPI 差值、Pareto 滑杆和选择理由。
3. **能源与碳流**：能源堆叠图与碳账本并排，直接排放和机会碳分色。
4. **潮流校验**：电压热图、支路负载率、违规表可反向定位拓扑。
5. **MRV 报告**：加入扰动摘要、输入哈希、求解状态、证据包。

全局只留场景、策略、小时、seed、同步推演；演示模式锁定布局。
