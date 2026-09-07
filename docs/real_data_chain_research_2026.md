# 真实数据链调研：天气 → 停电/故障 → 恢复时间

**目的**：为 GridRescue 后续替换 E 类合成压力场景，筛选可公开获取的美国天气、停电和可靠性数据。本文只做数据源盘点，不把外部统计直接写成 33 节点实测。

## 推荐最小链

`NOAA Storm Events`（事件窗口） + `NOAA ISD-Lite/NSRDB`（气象强度） + `OEDI Event-correlated Outage V2`（县级停电比例/恢复时间） + `EIA Form 861`（年度可靠性校准）。

本轮已实际下载 OEDI submission 6458 的公开原始压缩包到
`data/outage/raw/OEDI_Outage_Dataset_R1.zip`，并抽取 2023 州-月份聚合样本到
`data/outage/oedi_eaglei_outages_2023_group.csv`。原始包不进入比赛 ZIP，派生样本和元数据进入发布包。

## 数据源清单

| 数据源 | 下载/API | 关键字段 | 许可/访问 | 33 节点映射判断 |
|---|---|---|---|---|
| NOAA Storm Events | [CSV目录](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/)；[说明](https://www.ncei.noaa.gov/stormevents/ftp.jsp) | `EPISODE_ID`、`EVENT_ID`、开始/结束时间、`EVENT_TYPE`、州/县、起止经纬度、强度、财产损失、叙述 | NOAA 联邦开放数据 | 经纬度+时间可形成灾害窗口；case33bw 无地理坐标，需叠加馈线 GIS 或明确采用区域级场景 |
| NOAA ISD / ISD-Lite | [官方说明](https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database)；[HTTPS目录](https://www.ncei.noaa.gov/pub/data/noaa/isd-lite/) | UTC 时刻、站点、气温、露点、站压、风向/风速、云量、降水、能见度等 | NOAA 联邦开放数据 | 选医院/馈线附近站点，UTC→本地时区，1 h 重采样；可驱动高温/暴雨/风场，不直接定位节点故障 |
| OEDI Event-correlated Outage Dataset V2 | [OEDI submission 6458](https://data.openei.org/submissions/6458) | 县 FIPS/名称、15 min 时间戳、停电客户数/比例、人口、事件关联 ID、起止时间、DOE-417 匹配字段 | 页面元数据标注 CC BY 4.0；资源包公开下载 | 最适合校准“事件→区域停电比例→恢复时间”；到 33 节点只能按节点权重分摊并标为区域统计 |
| DOE OE-417 Annual Summaries | [Open Energy Data Portal](https://openenergyhub.ornl.gov/explore/dataset/oe-417-annual-summaries/)；[DOE OE-417](https://www.oe.netl.doe.gov/oe417.aspx) | 事件日期/时间、公司/州、事件类型/原因、失供 MW、客户数、恢复时间、叙述 | 美国联邦公开摘要；存在披露和粒度限制 | 生成事件级 MW/客户/恢复时长先验，不直接指定某条 33 节点支路 |
| EIA Form 861 Reliability | [EIA-861](https://www.eia.gov/electricity/data/eia861/) | SAIDI、SAIFI、CAIDI、是否含 Major Event Days、公用事业/州/服务区域 | EIA 公开表格数据 | 年度区域基线与校准；不能替代逐事件/逐节点 outage |
| NLR/NREL NSRDB、Wind Toolkit | [NLR API](https://developer.nlr.gov/)；[WTK下载文档](https://developer.nlr.gov/docs/wind/wind-toolkit/wtk-download/) | NSRDB：GHI/DNI/DHI、温度、风；WTK：多高度风速/风向、温度、气压、湿度、降水 | DOE/NLR 公开科研数据；API 需 key，按页面条款使用 | 生成 PV/风/高温气象 profile；可对整条馈线统一赋值或空间插值 |
| EAGLE-I 学术数据描述 | [PMC 论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC10915145/) | 县级 15 min 停电客户估计、时间、区域和质量边界 | 论文方法公开；原始/派生文件优先从 OEDI V2 获取 | 县级统计，不是节点实测；适合恢复时间分布校准 |

## 建议映射方法

1. 用 Storm Events 的事件类型、经纬度和时窗筛选医院/馈线所在县的天气事件。
2. 用 ISD-Lite/NSRDB 形成逐小时降水、风速、温度和太阳辐照序列。
3. 从 OEDI V2 计算事件级停电比例、持续时间和恢复曲线；DOE-417 作为 MW/客户规模交叉核验。
4. 将县级结果映射到 case33bw 时，只能采用显式权重：`node_outage_weight`、`critical_load_weight` 或区域统一事件标签；不要写成真实 33 节点故障记录。
5. 取得 utility 的线路/馈线 GIS、开关状态和抢修工单后，才能把“县级停电”细化为支路故障与抢修动作；否则保留 `data_class=E_external_aggregate`。

## 许可与申报边界

- OEDI V2 页面元数据明确 CC BY 4.0；使用时保留来源、版本、下载日期和原始文件 SHA-256。
- NOAA、EIA、DOE/NLR 数据均为公开政府数据，但仍应遵守各站点条款和数据字典，不把公开数据误写成现场测量。
- 论文数据若通过 OEDI 派生包获得，以 OEDI 资源许可为准；不要从论文图表反推逐节点数值。
- 项目主张继续使用“公开外部数据校准/区域级统计分配”和“受控服务预算下的运行碳清单差异”；不写实时 SCADA、某医院实测或第三方核证。
