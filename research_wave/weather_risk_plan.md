# GridRescue：武汉/湖北历史小时级天气与配电故障风险场景方案

> **研究定位**：天气数据只驱动“灾害条件下的合成配电设备故障情景”，不宣称已用真实停电工单训练出实际故障率模型。竞赛原型以可复现下载、可解释风险映射、跨源核验和离线可运行作为验收重点。  
> **资料访问日期：2026-08-22。**

## 1. 结论：双层数据路线

| 层级 | 用途 | 首选来源 | 原因 | 在 GridRescue 中的定位 |
|---|---|---|---|---|
| 演示主数据 | 一键下载、24 h / 7 d 回放、无需预处理 NetCDF | **Open-Meteo Archive，显式选 `ERA5`** | API 可按经纬度、日期、小时字段直接取数；ERA5 提供降水、10 m 风、2 m 温度 | 竞赛 Demo 的默认数据入口 |
| 科研可复现实验 | 固定版本、保存原始 GRIB、方法可写进论文 | **Copernicus CDS ERA5 hourly single levels** | 原始 ERA5 为小时、0.25°全球再分析；可下载 `2t/10u/10v/tp` | 主实验数据与 Open-Meteo 的溯源核验 |
| 中国区域精细核验 | 更贴近湖北、强调本地观测融合 | **国家气象数据服务 CLDAS-V2.0** | 0.0625°、小时；含 2 m 气温、10 m 风速、降水，并基于中国站网/卫星/同化融合 | 答辩中的“中国数据交叉验证”证据 |
| 辅助陆面敏感性 | 地表温度/土壤湿度、低洼和积水持续性 proxy | **Copernicus ERA5-Land** | 0.1°、小时、1950 年起，适合陆面状态；对温度/土壤状态有价值 | 不作为降水+风速的唯一来源；与 ERA5 配对 |

**关键选型细节**：Open-Meteo 的历史 API 文档明确列出 ERA5 的小时降水、10 m 风与 2 m 温度；其数据表同时提示 ERA5-Land 在该 API 中的降水和风速依赖 ERA5 forcing。因此，三要素灾害主线应显式使用 `models=era5`；ERA5-Land 保留给温度、土壤湿度与积水持续性敏感性分析，而不是硬拼成唯一气象源。

## 2. 三类数据源比较与字段映射

| 项目 | Open-Meteo Archive | Copernicus ERA5-Land | 国家气象科学数据中心 / CLDAS-V2.0 |
|---|---|---|---|
| 获取门槛 | HTTP API，适合演示与批量脚本 | 注册 CDS、接受数据条款、`cdsapi` 下载 | 平台实名/普通注册访问；按产品页面/资源说明下载 |
| 原始/产品性质 | 对 ERA5、ERA5-Land 等再分析的 API 封装 | ERA5 陆面模式再分析产品 | 中国区域观测、卫星、数值资料融合分析 |
| 覆盖与分辨率 | API 文档列：ERA5 0.25°、小时、1940 起；ERA5-Land 0.1°、小时、1950 起 | 0.1°、小时、1950 起；原生约 9 km | 亚洲 0.0625°、小时；页面标注起于 2017-01-19，近实时日更 |
| 本项目字段 | `temperature_2m`、`precipitation`、`rain`、`wind_speed_10m`、`wind_gusts_10m` | `2m_temperature`；可取土壤湿度/温度作积水/高温敏感性；降水与风统一由 ERA5 提供 | 2 m 气温、10 m 风速、小时降水；可扩展短波辐射支撑 PV 降额 |
| 推荐角色 | **主 Demo + 快速回放** | 陆面补充 / 温度敏感性 / 学术追溯 | **本地化交叉验证**，优先用于 2017 年以后案例 |
| 主要局限 | 为第三方 API，比赛前需固化 CSV、记录响应与版本 | 单独用于风雨灾害会缺少完整大气灾害字段；需配对 ERA5 | 需注册、下载口径及二次发布条件应以平台当期条款为准 |

## 3. 推荐空间采样点与案例时间窗

### 3.1 空间采样

所有坐标使用 WGS84；先用单点完成 MVP，再用 5 点作为武汉都市圈空间离散化。每个节点把天气值映射给最近的配电馈线/故障区。

| 节点 ID | 代表区域 | 纬度, 经度 | 用途 |
|---|---|---:|---|
| WH-CENTRE | 武汉主城区中心 | `30.5928, 114.3055` | 默认单点 Demo 与发布截图 |
| WH-HANKOU | 汉口北部负荷区 | `30.6220, 114.2810` | 城区高负荷 / 内涝场景 |
| WH-WUCHANG | 武昌—光谷方向 | `30.5200, 114.3400` | 商业/高校/关键负荷区 |
| WH-CAIDIAN | 蔡甸西南 | `30.5830, 114.0300` | 暴雨洪涝敏感区与抢修距离差异 |
| WH-JIANGXIA | 江夏南部 | `30.3800, 114.3200` | 农网/郊区馈线与分布式新能源区 |

**10 天范围控制**：第 1 版采用 `WH-CENTRE`；第 2 版把五点视为五个“天气区”，而不是伪造逐杆塔的精确气象观测。线路天气采用最近点或 inverse-distance weighting：

\[
X_{l,t}=\frac{\sum_{z\in Z} X_{z,t}/(d_{l,z}+0.5)^2}{\sum_{z\in Z}1/(d_{l,z}+0.5)^2}
\]

其中 \(X\) 可为降水、风速或温度，距离单位 km；`0.5` 防止近点数值不稳定。

### 3.2 推荐历史回放窗口

| 标签 | 时间窗口（北京时间） | 选取理由 | 用途 |
|---|---|---|---|
| `WH_RAIN_2016` | **2016-06-30 00:00 至 2016-07-06 23:00** | 中国天气网湖北页记录武汉在该过程 7 天累计 560.5 mm，且 7 月 5–6 日中心城区/蔡甸出现暴雨至特大暴雨 | **主答辩案例**：暴雨—内涝—多点故障—低碳恢复 |
| `WH_FLOOD_2020` | **2020-07-04 00:00 至 2020-07-06 23:00** | 湖北省水利厅记录 2020 年 7 月 4–6 日武汉连续三天发布暴雨橙色预警 | 稳健性第二案例：连续强降水而非单峰暴雨 |
| `HB_HEAT_2022` | **2022-08-01 00:00 至 2022-08-10 23:00** | 湖北应急部门当期风险分析称 8 月上旬将有阶段性高温、局地 39°C 以上风险 | 高温—负荷上升—设备热应力场景；实际数值完全由下载数据决定 |

> 时间窗口在下载后应以原始小时序列确认为准；历史事件公告是“选窗依据”，不替代测站或再分析数据本身。

## 4. 可复现下载方案

### 4.1 Open-Meteo Archive：零配置主链路

**API**：`https://archive-api.open-meteo.com/v1/archive`

```powershell
$uri = 'https://archive-api.open-meteo.com/v1/archive?latitude=30.5928&longitude=114.3055&start_date=2016-06-30&end_date=2016-07-06&hourly=temperature_2m,precipitation,rain,wind_speed_10m,wind_gusts_10m&timezone=Asia%2FShanghai&wind_speed_unit=ms&models=era5'
Invoke-WebRequest -Uri $uri -OutFile data/raw/openmeteo_wh_centre_20160630_20160706.json
Get-FileHash data/raw/openmeteo_wh_centre_20160630_20160706.json -Algorithm SHA256
```

**必存元数据**：完整 URL、抓取时间、HTTP 响应、SHA-256、请求的 `models=era5`、`timezone=Asia/Shanghai`、点位坐标及 API 返回中的 elevation/timezone。

**标准化字段**：

| 输出列 | 单位 | 源字段 | 处理 |
|---|---|---|---|
| `timestamp_bjt` | ISO-8601 | `hourly.time` | 固定 `Asia/Shanghai`，不混 UTC |
| `temperature_2m_c` | °C | `temperature_2m` | 直接使用 |
| `rain_1h_mm` | mm/h | `rain`；缺失时 `precipitation` | 小时累计量 |
| `precipitation_1h_mm` | mm/h | `precipitation` | 保留总降水作 QA |
| `wind_speed_10m_ms` | m/s | `wind_speed_10m` | 请求参数锁定 `ms` |
| `wind_gust_10m_ms` | m/s | `wind_gusts_10m` | 用于架空线脆弱性敏感性 |
| `source` | text | 固定值 | `openmeteo_archive_era5` |

### 4.2 Copernicus CDS：可审计 ERA5 / ERA5-Land 下载

CDS 注册、接受数据许可后在本机配置 `~/.cdsapirc`。主灾害字段使用 `reanalysis-era5-single-levels`；ERA5-Land 只作为陆面补充。以下请求下载最小化区域 `[31.00, 113.85, 30.20, 114.70]`（北、西、南、东），避免不必要的大文件。

```python
# scripts/fetch_era5_wuhan.py
import cdsapi

client = cdsapi.Client()
client.retrieve(
    "reanalysis-era5-single-levels",
    {
        "product_type": ["reanalysis"],
        "variable": [
            "2m_temperature",
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "total_precipitation",
        ],
        "year": ["2016"],
        "month": ["06", "07"],
        "day": ["30", "01", "02", "03", "04", "05", "06"],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": [31.00, 113.85, 30.20, 114.70],
        "data_format": "grib",
    },
    "data/raw/era5_wuhan_20160630_20160706.grib",
)
```

转换规则：`T_2m[°C]=t2m[K]-273.15`；`V_10m=sqrt(u10²+v10²)`；`tp[m]×1000 = mm`。累积变量须按 CDS 产品文档和时标检查“该时刻对应的累计区间”；导入后强制执行非负、连续小时和累计量校验。

ERA5-Land 扩展字段建议：`2m_temperature`、`soil_temperature_level_1`、`volumetric_soil_water_layer_1`；它们用来描述高温和长时段地表湿润条件，不替代 ERA5 的风雨风险字段。

### 4.3 国家气象数据：CLDAS-V2.0 本地核验链路

在国家气象科学数据中心/中国气象数据网检索 **CLDAS-V2.0 近实时产品**，选择武汉周边 bbox 或最近网格，下载小时 **2 m 气温、10 m 风速、降水**。CLDAS 产品页说明其为 0.0625°、1 小时产品，并给出了对 2 m 温度、10 m 风速、小时降水的站点评估统计；2017 年起可覆盖 2020/2022 案例，适合验证而非 2016 主案例。

下载留痕：数据集标识、下载日期、账号级别、页面截图/许可快照、原文件 checksum、空间和时间筛选条件。原始 CLDAS 文件不放入公开仓库；只提交本项目衍生的、按条款允许的聚合特征或演示截图。

## 5. 从天气到设备故障概率：可解释科研模型

### 5.1 小时气象特征

对每条线路/设备 \(i\)、小时 \(t\) 计算：

\[
R_{1,t}=rain_{1h},\quad R_{6,t}=\sum_{k=0}^{5}rain_{t-k},\quad R_{24,t}=\sum_{k=0}^{23}rain_{t-k}
\]
\[
W_t=wind\_speed_{10m},\quad G_t=wind\_gust_{10m},\quad H_t=\max(0,T_t-T_{hot})
\]

推荐阈值为**模型超参数而非气象预警标准**：`T_hot=35°C`，`W0=10 m/s`，`G0=15 m/s`，并在配置页可调。由于 Open-Meteo/ERA5 和 CLDAS 的格点/观测属性不同，阈值仅用于风险排序，不能宣传为设备行业失效定值。

### 5.2 资产类型脆弱性与 hazard 映射

将天气风险先映射为非负 hazard，再转为小时失效概率，避免直接 Logistic 分数难以解释的问题：

\[
\lambda_{i,t}=\lambda_{0,i}\cdot a_i\cdot
\exp(\beta_{r,i}\ln(1+R_{1,t})+
\beta_{r6,i}\ln(1+R_{6,t})+
\beta_{r24,i}\ln(1+R_{24,t})+
\beta_{w,i}[W_t-W_0]_+ +
\beta_{g,i}[G_t-G_0]_+ +
\beta_{T,i}H_t +
\beta_{rw,i}\ln(1+R_{6,t})[W_t-W_0]_+)
\]
\[
p_{i,t}=1-\exp(-\lambda_{i,t}\Delta t),\qquad \Delta t=1\;hour
\]

- `λ0,i`：晴天基线小时故障强度，使用**合成基线**并在论文表明假设；
- `a_i`：设备状态乘子（新设备 `0.7`、一般 `1.0`、老旧 `1.5`）；
- 系数向量随资产类别不同：
  - **架空线/杆塔**：较高 `βw, βg`，中等 `βr`；
  - **电缆分支箱/环网柜**：较高 `βr6, βr24`，强调积水浸泡；
  - **配电变压器**：较高 `βT`，可叠加负荷率热应力；
  - **开关站**：`βr24` 与抢修可达性联动。

建议的 MVP 系数不是“真值”，而是以 `config/weather_fragility_priors.csv` 管理，答辩时展示三组先验（保守/基准/恶劣）做敏感性分析。真实工单到位后，使用带 L2 正则的 Poisson / cloglog GLM 拟合 `λ`，按时间滚动验证，替换人工先验。

### 5.3 空间相关故障与修复时间

逐条线路独立 Bernoulli 会产生不真实的随机散点。加入区域共同冲击：

\[
Z_t\sim N(0,1),\quad p'_{i,t}=\sigma(logit(p_{i,t})+\rho_{zone(i)}Z_t)
\]

然后按 \(p'_{i,t}\) 采样设备故障。`ρ=0` 是独立情景，`ρ=0.5` 是中等共因，`ρ=1.0` 是强区域性灾害。故障后修复时长采用 LogNormal：

\[
repair_i\sim LogNormal(\ln(m_i)+0.03R_{24,t}+0.05[W_t-W_0]_+,\sigma_i)
\]

`m_i` 为资产类型的基准小时数。该部分与现有 `DisasterScenario(repair_hours, pv_derating, crew_distance_km)` 对接：天气生成器输出故障支路、修复时长、PV derating 和抢修距离倍率。

### 5.4 PV 与负荷耦合（低碳恢复的必要连接）

- `pv_derating[t]`：若只下载雨、风、温度，则使用 `clip(1 - 0.04*R1 - 0.01*cloud_proxy, 0.1, 1)` 作为**演示参数化**；更严谨的第二版直接下载短波辐射/GHI。
- `load_multiplier[t]`：高温场景可用 \(1+\eta[T_t-30]_+\)，其中 `η` 在 `0.01–0.03 / °C` 进行敏感性扫描；该项须明确为园区负荷假设。
- 故障风险、PV 降额和负荷上升在同一小时输入恢复优化器，防止只把天气当背景图。

## 6. 离线 fallback 与文件契约

### 6.1 离线运行包

比赛前固化三份经清洗的 CSV：

```text
artifacts/weather/
  weather_WH_RAIN_2016_openmeteo_era5.csv
  weather_WH_FLOOD_2020_openmeteo_era5.csv
  weather_WH_FLOOD_2020_cldas.csv          # 若许可允许随提交包分发；否则不分发原始值
  weather_HB_HEAT_2022_openmeteo_era5.csv
  weather_manifest.json                     # URL、来源、访问日期、SHA256、字段、时区、许可证快照
```

CSV 最小契约：

```csv
scenario_id,zone_id,timestamp_bjt,temperature_2m_c,rain_1h_mm,precipitation_1h_mm,wind_speed_10m_ms,wind_gust_10m_ms,source
WH_RAIN_2016,WH-CENTRE,2016-06-30T00:00:00+08:00,24.1,0.0,0.0,2.3,4.1,openmeteo_archive_era5
```

### 6.2 API 不可用时

1. 默认读取打包 CSV，严禁运行期自动换源却不提示；
2. 页面显示 badge：`离线固化数据 / scenario / source / SHA-256 前 12 位`；
3. 若文件缺失，切到 `scenarios.hourly_profiles()` 合成天气，并在 UI 显式标为“合成情景”；
4. 研究结果表分别统计 `real_weather_replay` 与 `synthetic_stress_test`，不得混在同一结论里。

## 7. 验证指标与答辩证据

| 层级 | 验证指标 | 通过判据 / 展示证据 |
|---|---|---|
| 下载完整性 | 行数、连续小时、缺失率、hash | 7 天单点应为 168 行；五点应为 840 行；无缺时；manifest 可复核 |
| 单位一致性 | 温度、降水、风速范围 | `T` 合理范围、`rain>=0`、`wind>=0`；ERA5 `tp` 已从 m 转 mm |
| 跨源一致性 | Open-Meteo ERA5 vs CDS ERA5 | 同网格/同时间抽样后温度 MAE、风速 MAE、降水相关系数；差异图而非只报一个数字 |
| 本地化核验 | ERA5 vs CLDAS（2020/2022） | 小时 `T/W/R` 的相关、MAE、极端小时排名；解释格点尺度差异 |
| 事件合理性 | 2016 暴雨风险峰值 | 2016-07-05 至 07-06 的滚动降雨/风险曲线与官方暴雨事实窗口同向；不要求逐小时雨量完全相等 |
| 风险模型 | 校准/敏感性 | 保守/基准/恶劣先验下，故障数、EENS、柴油量、碳排的单调变化；有工单再报 AUC/Brier/Poisson deviance |
| 恢复价值 | 天气驱动 vs 无天气 baseline | 关键负荷恢复率、EENS、柴油量、碳排、绿电消纳；展示 Pareto 变化 |

**五分钟答辩证据链**：

1. 官方事件公告说明为什么选 2016/2020 窗口；
2. 一键展示 Open-Meteo 原始 URL、SHA-256 和 168 小时曲线；
3. 显示 ERA5 与 CLDAS（2020）对同一强降水过程的趋势核验；
4. 点击“基准/恶劣风险先验”，查看故障地图、成岛策略和低碳恢复 KPI；
5. 最后一页明确模型边界：天气真实、设备故障参数为可校准先验、停电工单到位后可学习化。

## 8. 许可、署名与引用

| 数据源 | 处理要求 |
|---|---|
| Open-Meteo | 记录 API URL 与其页面列出的底层 ERA5/ERA5-Land 来源；比赛展示页附 Open-Meteo 与 ECMWF/Copernicus 署名。调用/再发布条件以 Open-Meteo 当期 Usage licence / Terms 页面为准；建议提交固化的衍生特征和 manifest，而非依赖现场联网。 |
| Copernicus CDS ERA5/ERA5-Land | CDS 数据集页标明 ERA5-Land 使用 **CC BY** 许可；遵守 CDS 接受的具体 licence、署名、链接和“修改说明”。推荐引用相应 DOI：ERA5 `10.24381/cds.adbb2d47`；ERA5-Land `10.24381/cds.e2161bac`。 |
| 国家气象科学数据中心 / CLDAS | 产品页标注普通注册用户访问；下载、展示和二次分发按平台当期服务条款执行。保守做法：不把原始栅格随公开代码仓库分发，提交派生的风险指数、聚合 CSV 或截图，并保存下载凭据与引用信息。 |

## 9. 一页式资料来源（访问日期均为 2026-08-22）

1. [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)：历史 API、字段、ERA5/ERA5-Land 分辨率和数据可用性。  
2. [Copernicus CDS: ERA5 hourly data on single levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview)：ERA5 小时、0.25°、1940 年起、DOI。  
3. [Copernicus CDS: ERA5-Land hourly data](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=overview)：ERA5-Land 小时、0.1°、1950 年起、CC BY 与 DOI。  
4. [Copernicus CC BY 4.0 licence](https://cds.climate.copernicus.eu/licences/creative-commons-attribution-4-0-international-public-licence)。  
5. [国家气象科学数据中心：CLDAS-V2.0 近实时产品](https://k.data.cma.cn/mekb/?dataCode=NAFP_CLDAS2.0_NRT&r=data%2Fdetail)：0.0625°/小时、字段、数据来源和质量说明。  
6. [中国天气网湖北：2016 武汉暴雨过程](https://hubei.weather.com.cn/tpxw/07/2551191.shtml)：2016-06-30 至 07-06 过程的选窗依据。  
7. [湖北省水利厅：2020 年 7 月强降雨](https://slt.hubei.gov.cn/fbjd/dtyw/202007/t20200707_2500475.shtml)：2020-07-04 至 07-06 武汉暴雨预警的选窗依据。  
8. [湖北省应急管理厅：2022 年 8 月风险形势](https://yjt.hubei.gov.cn/yjgl/fzjz/202208/t20220802_4246236.shtml)：高温窗口的选窗依据。  
