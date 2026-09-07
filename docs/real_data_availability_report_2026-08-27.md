# GridRescue 真实数据可得性检索报告（2026-08-27）

> 目标：为武汉/湖北场景的 IEEE 33 节点配电网演示，核实公开天气、停电可靠性、故障事件和抢修时长数据能否直接接入。本文只记录已检索到的公开来源、字段、时间跨度、粒度和可解释边界；不把合成数据包装成现场实测。

## 1. 结论先行

| 数据层 | 公开可得性 | 可直接拿到的粒度 | 能否恢复 IEEE 33 节点身份 |
|---|---|---|---|
| 天气观测（CMA） | 可申请/下载，站点级 | 小时、日值；站点有经纬度 | **可做邻近站点映射**，但不是馈线实测 |
| ERA5 再分析 | 可下载，需 CDS 账号/API | 小时，约 0.25° 网格；1940 年至今 | **可做网格→节点邻近映射**，适合连续天气驱动 |
| 国家能源局供电可靠性报告 | 官方 PDF，年度统计 | 全国、城市/农村、省级分布和原因分类 | **不能恢复节点/馈线身份**，只能校准总体故障率、停电时长 |
| 武汉/湖北公开停电事件表 | 未检索到可直接下载的馈线级事件表 | 网页新闻多为单次事件、非结构化 | 不能直接映射；需供电企业脱敏事件表 |
| 故障—抢修资源—恢复时间 | 未发现公开结构化接口 | 企业 OMS/SCADA/抢修工单通常为内部数据 | 需企业合作或自建合成标注 |

**竞赛可用的诚实方案：** 用 CMA/ERA5 提供真实天气驱动，用国家能源局年度指标校准总体停电率和时长分布；IEEE 33 节点的故障支路、影响负荷和抢修队列仍标记为“模型假设/合成场景”，不宣称已接入武汉供电公司的真实馈线或工单。

## 2. 中国气象数据网（CMA/NMIC）

### 2.1 官方入口

- 气象科学专业知识服务系统/中国气象数据网：<https://k.data.cma.cn/>（站点数据资源目录中列出“中国地面气象站逐小时观测资料”等数据集）。
- CMA API 入口：<https://api.data.cma.cn/>。
- 国家气象信息中心数据详情页示例（中国地面气象观测国际交换站定时值）：<https://www.nmic.cn/data/cdcdetail/dataCode/A.0012.0001.S011.html>。

### 2.2 小时站点数据：`SURF_CHN_MUL_HOR`

**适合用途：** 以武汉国家/区域气象站为锚点，提供降水、温度、风和气压的小时驱动。

**常用字段（以 API 返回字段名为准）：**

```text
Station_Id_C / Station_Id_d
Year, Mon, Day, Hour
Lat, Lon, Alti
PRS_Sea, PRS, TEM, TEM_Max, TEM_Min
DPT, RHU
WIN_D_INST, WIN_S_INST, WIN_D_Avg, WIN_S_Avg
PRE_1h, PRE_6h, PRE_24h
```

**粒度与时间：** 小时观测；站点表提供站号、经纬度和海拔。API 查询通常需要注册账号/接口权限，时间范围和可返回字段受接口配额约束。不要把 API 当前滚动窗口误写成长期历史库；历史回溯应从数据网下载对应归档或向 NMIC 申请。

**推荐采集表：**

```text
station_id, obs_time_utc, obs_time_bjt, lat, lon, altitude_m,
temp_c, precip_1h_mm, wind_speed_ms, wind_gust_ms, pressure_hpa,
quality_flag, source_url, retrieval_time
```

### 2.3 日值气候资料：`SURF_CLI_CHN_MUL_DAY`（V3.0 系列）

日值文件按“数据集代码—要素—项目—年月”组织，常见要素包括：

| 要素 | 典型项目 | 含义 |
|---|---|---|
| `TEM` | `12001` | 平均/最高/最低气温 |
| `RHU` | `13003` | 平均、最小相对湿度 |
| `WIN` | `11002` | 日平均/最大/极大风速及方向 |
| `PRE` | `13011` | 20–8 时、8–20 时、20–20 时降水 |
| `PRS` | `10004` | 平均/最高/最低本站气压 |
| `SSD` | `14032` | 日照时数 |

文件记录通常含站号、纬度、经度、海拔、年月日和质量控制码；原始单位常为 0.1℃、0.1 mm、0.1 m/s、0.1 hPa 等，入库时必须按数据字典换算。历史 V3.0 资料常见覆盖 1951/1961 至 2020 的归档段，实际可下载年份以当前数据网目录和账号权限为准，报告中不要直接写成“实时”。

### 2.4 武汉映射建议

1. 从 CMA 站点清单筛选武汉市行政范围及周边 50–100 km 站点；不要手填站号，先下载站点表核验 `Station_Id`、经纬度和海拔。
2. 将站点时间统一到北京时间（BJT）或 UTC，项目内部统一保存 `obs_time_utc`，展示层再转 BJT。
3. 对每个 IEEE 33 节点保存最近站点距离和来源：

```yaml
node_id: 17
weather_source: CMA_SURF_CHN_MUL_HOR
station_id: STATION_ID
station_distance_km: DIST_KM
mapping_method: nearest_station
mapping_confidence: medium
```

4. 站点到节点只用于天气暴露度/故障概率特征，不能解释成“节点 17 的实测雨量”。

## 3. Copernicus/ECMWF ERA5

### 3.1 官方数据集

- ERA5 小时单层数据（1940 年至今）：<https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=download>
- ERA5 单点长时序子集（ARCO）：<https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries?tab=download>
- ECMWF 数据说明：<https://confluence.ecmwf.int/plugins/viewsource/viewpagesrc.action?pageId=181127817>

ERA5 是再分析产品，不是武汉现场站点观测；完整单层产品的空间分辨率约 0.25°，小时粒度，覆盖 1940 年至今并持续近实时延伸。单点长时序接口适合批量抽取武汉及 33 节点附近时间序列。

### 3.2 GridRescue 建议变量

| ERA5 变量 | 用途 | 单位/处理 |
|---|---|---|
| `2m_temperature` | 高温/寒潮风险、负荷修正 | K → ℃ |
| `total_precipitation` | 暴雨累积、湿润暴露 | m → mm；按小时差分/累计 |
| `10m_u_component_of_wind`, `10m_v_component_of_wind` | 风速与风向 | m/s；合成风速 `sqrt(u²+v²)` |
| `instantaneous_10m_wind_gust` | 阵风冲击 | m/s |
| `surface_pressure` 或 `mean_sea_level_pressure` | 可选气象协变量 | Pa → hPa |

### 3.3 节点映射

- 对每个节点经纬度取最近网格点，或对四邻域做双线性插值；保留 `grid_lat/grid_lon`、距离和插值方法。
- ERA5 网格约 25–30 km，武汉 33 节点模型的节点间距远小于网格尺度，因此天气输入在多个节点间高度相关；故障差异应由拓扑、设备脆弱性和合成随机项表达。
- 适合作为统一的“天气场”，再通过节点暴露度函数生成故障概率：

```text
p_fault(node, t) = sigmoid(
    beta0 + beta_rain * rain_24h(t)
    + beta_gust * gust(t)
    + beta_heat * max(temp_c(t)-T0, 0)
    + beta_asset * vulnerability(node)
)
```

## 4. 国家能源局《2023 年全国 10 千伏供电系统用户供电可靠性》

### 4.1 官方来源与覆盖

- 报告页：<https://prpq.nea.gov.cn/ndbg/10969.html>
- PDF：<https://prpq.nea.gov.cn/uploads/file1/20240911/66e102e09bfea.pdf>
- 已下载副本：`C:\Users\ASUS\AppData\Local\Temp\nea_2023_reliability.pdf`（180 页，约 11.4 MB）。

报告主体覆盖 2023 年 10 kV 供电系统用户可靠性，并给出 2019–2023 趋势、城市/农村对比、省级分布、停电原因和典型统计表。报告打印页码约 132–141 进入“用户供电可靠性”，打印页 150 起为停电原因分析。

### 4.2 可直接使用的统计量（全国基准）

报告摘要（打印页 132–133）给出：

- 全口径用户平均供电可靠率：**99.911%**；
- 用户平均停电时间：**7.83 小时/户·年**；
- 用户平均停电频率：**2.30 次/户·年**；
- 城市用户：99.976%、2.14 小时/户·年、0.68 次/户·年；
- 农村用户：99.900%、8.74 小时/户·年、2.56 次/户·年。

报告另一张“计划/非计划停电”表（打印页 133）给出非重大事件日口径下的分解：平均停电时间 4.82 小时/户，其中预安排停电 3.00 小时；平均停电频率 1.83 次/户，其中预安排停电 0.47 次；非计划停电平均每次约 3.21 小时。由于统计口径不同，使用时必须同时保存表号、脚注和“是否剔除重大事件日”，不能把 7.83 与 4.82 混成同一指标。

### 4.3 对 GridRescue 的正确用法

可校准：

```text
annual_customer_saidi_h
annual_customer_saifi_per_year
urban_rural_mix
planned_vs_unplanned_share
outage_duration_distribution_prior
```

不可校准/不可声称：

- 某条武汉 10 kV 馈线或 IEEE 节点的故障时间；
- 具体开关、变压器、杆塔、保护装置身份；
- 抢修队从接单到到场/修复的工单级时长；
- 33 节点之间的真实空间相关性。

因此报告数据源标签应写为 `E_external_aggregate` 或 `official_annual_reliability_baseline`，而不是 `SCADA`、`OMS_event` 或 `field_verified`。

## 5. 湖北/武汉停电和抢修事件公开性

### 5.1 已检索结果

- 武汉市公共数据开放平台：<https://data.wuhan.gov.cn/>。平台条例明确将气象服务、民生保障等列为重点开放方向，但目录访问需要在线签署数据开放服务协议；当前检索未发现可直接下载、含“馈线 ID—故障开始—派单—修复—影响用户数”的公开数据集。
- 武汉供电公司、地方政府和媒体网页可找到单次停电公告、抢修新闻或保供电通报，但通常是自然语言叙述，缺少稳定字段、完整历史和可复用 API。
- 国家能源局报告提供年度/区域统计和原因分类，不提供武汉配电网事件明细。

### 5.2 需要企业合作的数据字段

若要把“抢修时间”从合成变成可审计实测，至少需要脱敏后的：

```text
event_id, feeder_id, substation_id, fault_type,
start_time, detection_time, dispatch_time, crew_depart_time,
arrival_time, isolation_time, restoration_time,
affected_customers, interrupted_load_kw, weather_snapshot,
switching_actions, cause_code, repair_team_count
```

这些字段通常来自 OMS/SCADA/配网自动化/DMS/抢修工单系统，属于供电企业内部生产数据。竞赛阶段可以先用合成工单，但要在 README 和答辩中明确 `synthetic_repair_log=true`。

## 6. 10 天竞赛落地方案（不改变当前模型边界）

### Day 1–2：真实天气接入

1. 申请/下载 CMA 小时站点数据，至少覆盖 2023–2025 武汉周边站点；若账号或历史权限卡住，先用 ERA5 单点时序跑通。
2. 下载 ERA5 2023–2025 的四个核心变量，缓存为 Parquet/CSV，并记录检索时间、数据集版本和变量单位。
3. 建 `weather_nodes.csv`：`node_id, lat, lon, grid_lat, grid_lon, station_id, distance_km, mapping_method`。

### Day 3–4：可靠性校准

1. 把国家能源局 2023 全国、城市、农村指标写入 `data/factor_registry.csv` 或独立 `reliability_registry.csv`。
2. 在场景生成器中增加“年度先验校准”开关，使 Monte Carlo 的总停电小时/用户年均值落在官方基准附近。
3. 输出校准前后对照图，脚注写清统计口径。

### Day 5–6：事件级模型标注

1. 保留现有 IEEE 33 节点故障和恢复逻辑。
2. 新增字段：`data_class`、`source_provenance`、`synthetic_assumption`、`calibration_target`。
3. 将天气变量只作为暴露度/故障概率输入，不把节点标签伪装成武汉真实馈线。

### Day 7–8：验证与可视化

- 画武汉天气时间线、节点暴露度热力图、官方 SAIDI/SAIFI 校准图、合成抢修甘特图。
- 每张图显示数据源、时间范围、单位和“观测/再分析/官方统计/合成”标签。

### Day 9–10：答辩材料

- README 增加“真实数据边界”章节；
- 申报书使用“公开数据驱动 + 官方指标校准 + 节点级仿真”表述；
- 禁用“已接入武汉供电 SCADA”“真实抢修工单验证”等无法举证的句子；
- 附上本报告和数据字典，便于评委复核。

## 7. 建议的数据血缘字段

```text
source_id
source_name
source_url
dataset_code
provider
retrieval_time
coverage_start
coverage_end
temporal_resolution
spatial_resolution
license_or_access
raw_file_sha256
processing_script
data_class                 # observed / reanalysis / official_aggregate / synthetic
mapping_method
uncertainty_note
```

## 8. 最终判断

当前最稳、最快、可答辩的组合是：

```text
CMA/ERA5 天气场
        ↓
节点邻近/网格映射（保留距离与不确定性）
        ↓
天气驱动的节点故障概率
        ↓
IEEE 33 拓扑 + 抢修策略仿真
        ↓
国家能源局 SAIDI/SAIFI/停电时长年度基准校准
        ↓
碳排、韧性、关键负荷服务和 Pareto 结果
```

这条链条能把“数据真实”与“节点级推演”分开，既使用公开权威数据，又不越界宣称拥有企业馈线或抢修工单。

