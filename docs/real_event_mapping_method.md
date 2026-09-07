# 真实事件到 33 节点的映射方法

`src/gridrescue/real_event_mapping.py` 把 OEDI/EAGLE-I 的区域级停电事件转换成 case33bw 的统计校准输入。它不声称恢复真实馈线拓扑，也不根据县级数据虚构 `L6/L13/L27` 等支路故障。

## 输入

OEDI merged 事件行包含州、县、开始时间、停电持续时间和最大停电客户数。由于公开行没有当前研究馈线的客户总数，映射函数要求显式传入 `reference_customers`，并计算：

```text
outage_fraction_proxy = min(max_customers / reference_customers, 1.0)
```

这个比例是区域校准代理值，不是 case33bw 馈线实测停电率。

## 节点分配

对每个 case33bw 节点采用统一区域停电比例：

```text
estimated_unserved_kw = node.base_load_kw × outage_fraction_proxy
node_weight = node.base_load_kw / total_base_load_kw
```

这样所有节点的总估计失供功率与区域比例一致，节点权重可用于后续恢复时长和服务预算校准。由于没有线路 GIS，输出不包含 `failed_branch_ids`。

## 输出边界

输出字段带有：

```text
event_id
source_id
duration_h
mapping_method=regional_statistical_mapping
data_class=E_external_aggregate
```

只有拿到带馈线 GIS、线路编号、开关状态和抢修工单的数据，才可以把该层升级为真实支路级回放。

## ZIP 直接读取

load_oedi_csv_from_zip() 与 load_oedi_event_correlated_from_zip() 直接从 data/outage/raw/OEDI_Outage_Dataset_R1.zip 读取 CSV，并复用时间戳、数值和 FIPS 校验。这样提交包保留原始证据 ZIP，但运行 replay 时不需要手工解压大文件。

完整案例见 [docs/real_event_replay_event001.md](real_event_replay_event001.md)。
