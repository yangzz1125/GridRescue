# 公开停电聚合数据

本目录包含从 OEDI submission 6458 下载的 Event-correlated Outage Dataset R1 的一个派生样本：2023 年州-月份聚合表。

文件：

- `oedi_eaglei_outages_2023_group.csv`：州、月份、停电次数、最大停电时长、客户加权停电小时。
- `oedi_eaglei_outages_2023_group.metadata.json`：来源、许可、原始压缩包哈希、派生文件哈希和映射边界。
- `raw/OEDI_Outage_Dataset_R1.zip`：原始公开数据包，仅作为本地证据保存，不直接打进比赛发布 ZIP。

边界：这是美国州-月份聚合统计，不是武汉馈线数据，也不是 case33bw 的逐支路实测。它可用于校准恢复时长和停电规模的区域先验；映射到 33 节点时必须标记 `regional_statistical_mapping`。


完整事件 replay 案例位于 ../events/event_001/，方法说明见 ../../docs/real_event_replay_event001.md。