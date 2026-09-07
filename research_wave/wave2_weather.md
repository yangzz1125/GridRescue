# GridRescue Wave 2：武汉真实天气接入设计（Open-Meteo / ERA5）

**决策日期：2026-08-22；范围：设计说明，不改动当前代码。**

## 0. 结论与边界

采用“双层、冻结优先”路线：

1. **MVP 与演示回放：Open-Meteo Historical/Archive API，明确 `models=era5`。** 它提供武汉坐标、日期、小时字段的轻量 HTTP 获取，最适合十天内完成可视化与竞赛回放。
2. **科研复现锚点：Copernicus Climate Data Store (CDS) ERA5 hourly single levels。** 在正式实验冻结时保留原始 GRIB、CDS 请求 JSON、哈希与转换脚本；它是 Open-Meteo 演示路径的可审计底层参照。
3. **运行时规则：缓存优先；联网仅用于显式 refresh；离线永远能重放已冻结案例。** 当前 `scenarios.hourly_profiles()` 的合成曲线保留为最后一级回退，且输出中必须标为 `synthetic_fallback`，不与真实天气回放混报。

天气是真实的格点再分析/历史序列；**线路失效系数、修复时长和热额定降额是可配置工程先验，不是武汉配网工单拟合真值**。报告和 UI 要分别展示数据来源与模型假设。

武汉默认点为 `WH-CENTRE = (30.5928, 114.3055)`，WGS84；时区统一为 `Asia/Shanghai`（UTC+08:00，无 DST）。首版只做一个点，后续可增加汉口、武昌、蔡甸、江夏四点并以最近点/IDW 映射到线路天气区。

---

## 1. 数据来源、字段与许可证

| 层 | 来源 | 项目用途 | 最小字段 | 许可证/分发策略 |
|---|---|---|---|---|
| 默认获取 | Open-Meteo Historical Weather API，指定 ERA5 | 一键抓取与演示 | 2 m 气温、小时雨量/降水、10 m 风速/阵风、短波辐射、天气码 | 记录 API URL、响应和 Open-Meteo 条款快照；展示页署名 Open-Meteo 与底层 ECMWF/Copernicus。项目交付固化派生 CSV/manifest，而不是依赖现场网络。 |
| 复现基准 | CDS `reanalysis-era5-single-levels` | 原始再分析锚点及 Open-Meteo 抽样核验 | `2m_temperature`、`10m_u_component_of_wind`、`10m_v_component_of_wind`、`total_precipitation`、`surface_solar_radiation_downwards` | 以 CDS 数据集的当期许可、署名和接受条款为准；保存其许可快照与请求。ERA5 DOI：`10.24381/cds.adbb2d47`。 |
| 可选陆面敏感性 | CDS ERA5-Land | 土壤湿度/地表热状态，不单独承担风雨灾害主线 | `2m_temperature`、`volumetric_soil_water_layer_1` 等 | ERA5-Land 数据集页标示 CC BY 4.0；仍保存下载当期许可快照。DOI：`10.24381/cds.e2161bac`。 |
| 可选中国区域核验 | CMA/国家气象科学数据中心 CLDAS-V2.0 | 2017 年后武汉事件的本地化交叉检查 | 小时 2 m 气温、10 m 风、降水 | 原始栅格和再发布按平台当期条款处理；公开仓库默认只放允许分发的聚合派生物、元数据和哈希。 |

**推荐 API 请求（首版）：**

```text
GET https://archive-api.open-meteo.com/v1/archive
  ?latitude=30.5928
  &longitude=114.3055
  &start_date=2020-07-04
  &end_date=2020-07-06
  &hourly=temperature_2m,precipitation,rain,wind_speed_10m,wind_gusts_10m,shortwave_radiation,weather_code
  &timezone=Asia%2FShanghai
  &wind_speed_unit=ms
  &models=era5
```

- `precipitation` 保留为总降水；`rain` 优先作为降雨特征，`rain` 缺值才以 `precipitation` 回填。
- `shortwave_radiation` 用作 GHI proxy。其本质是格点短波辐射而非组件面辐照度，首版的 PV 转换必须注明这个限制。
- ERA5 的转换固定为：`t2m[°C] = t2m[K] - 273.15`、`wind = sqrt(u10² + v10²)`、`tp[mm] = tp[m] × 1000`、`ssrd_1h[Wh/m²] = ssrd[J/m²] / 3600`。对累计变量先依据 CDS 时间语义差分，再做非负和连续小时校验。

---

## 2. 标准化天气文件契约

### 2.1 规范化逐时表

每行是一个 `scenario_id × zone_id × timestamp_bjt`；不存在“默认时区”或隐式单位。

```csv
schema_version,scenario_id,zone_id,timestamp_bjt,temperature_2m_c,rain_1h_mm,precipitation_1h_mm,wind_speed_10m_ms,wind_gust_10m_ms,shortwave_radiation_wm2,weather_code,source,source_model,raw_sha256
weather.v1,WH_FLOOD_2020,WH-CENTRE,2020-07-04T00:00:00+08:00,26.4,0.0,0.0,2.8,5.1,0,3,openmeteo_archive,era5,<sha256>
```

**硬校验：**

- `timestamp_bjt` 必须解析为 `+08:00` 且严格逐小时；同一 `scenario_id/zone_id` 不许重复。
- `temperature_2m_c ∈ [-50, 60]`，所有降水、风速、短波辐射均 `>= 0`；异常值进入 reject report，不能静默截断。
- `rain_1h_mm` 缺失时才由 `precipitation_1h_mm` 回填；保留 `rain_imputed_from_precipitation=true`。
- 满窗小时数必须等于 `(end-start+1) × 24 × zone_count`。例如单点 7 日是 168 行。

### 2.2 目录与缓存格式

不用 Parquet 作为 MVP 强依赖，避免为读取缓存新增 `pyarrow`；原始 JSON 加 UTF-8 CSV 足够可移植。后续批量多点可并行写 Parquet，但 CSV 是发布冻结的规范副本。

```text
data/weather/
  raw/openmeteo_era5/WH_FLOOD_2020/WH-CENTRE/
    request.json                 # canonical JSON：完整 query、坐标、抓取时间
    response.json                # API 原始字节，UTF-8；绝不覆写
    response.sha256
  normalized/weather.v1_WH_FLOOD_2020_WH-CENTRE.csv
  derived/weather_effects.v1_WH_FLOOD_2020_WH-CENTRE.csv
  manifests/weather_manifest.v1.json
  fixtures/synthetic_weather.v1_24h.csv
```

`weather_manifest.v1.json` 是复现入口，最低包含：

```json
{
  "schema_version": "weather-manifest.v1",
  "scenario_id": "WH_FLOOD_2020",
  "zone_id": "WH-CENTRE",
  "coordinates_wgs84": {"latitude": 30.5928, "longitude": 114.3055},
  "timezone": "Asia/Shanghai",
  "source": "openmeteo_archive",
  "source_model": "era5",
  "request_canonical_json_sha256": "...",
  "raw_response_path": "data/weather/raw/.../response.json",
  "raw_response_sha256": "...",
  "normalized_path": "data/weather/normalized/...csv",
  "normalized_sha256": "...",
  "retrieved_utc": "2026-08-22T...Z",
  "licence_snapshot_path": "evidence/licenses/OPEN_METEO.txt",
  "derivation_version": "weather-effects.v1",
  "git_commit": "<commit>"
}
```

请求文件采用 canonical JSON（键排序、UTF-8、`\n` 统一），因此请求哈希和源响应哈希可审计；每次 `--refresh` 创建新 `retrieved_utc` 目录，而非覆盖冻结证据。

---

## 3. 天气字段 → 电网输入映射

所有系数放入版本化配置 `config/weather_effects.v1.json`；模型输出同时携带 `derivation_version` 和输入 `raw_sha256`。下面给出十天 MVP 的透明、可单调测试的映射，不宣称为设备制造商热定值或停电工单拟合结果。

| 电网输出 | 输入字段/派生特征 | MVP 映射 | 接入点 |
|---|---|---|---|
| **故障概率** `fault_probability_1h` | `rain_1h_mm`、`rain_6h_mm`、`rain_24h_mm`、`wind_speed_10m_ms`、`wind_gust_10m_ms`、`temperature_2m_c`、资产类别/暴露/老化因子 | 对每条支路生成小时 hazard `λ`，再用 `p=1-exp(-λ)`；雨、强风、高温对各资产类的系数可配置。 | 新的 `WeatherEffects.branch_effects`；随后由随机数种子采样为 `failed_branch_ids` 和 `repair_hours`。 |
| **PV 降额** `pv_multiplier` | `shortwave_radiation_wm2`、`temperature_2m_c` | 以 GHI proxy 计算辐照出力，再以温度系数做组件温升修正，输出 `[0,1]` 的可用容量比例。 | 取代 `hourly_profiles()` 中的合成 `daylight * scenario.pv_derating`。 |
| **负荷倍率** `load_multiplier` | `temperature_2m_c` + 原有小时负荷形状 | 保留当前日内基线负荷曲线；再叠加武汉制冷敏感因子。 | 取代/扩展 `hourly_profiles()` 的 `load_multiplier`。 |
| **线路热限额** `thermal_limit_multiplier` / `capacity_kva_t` | `temperature_2m_c`、`wind_speed_10m_ms`、`shortwave_radiation_wm2`、线路暴露参数 | 高温和太阳辐射降低保守载流裕度，风速增加对流冷却裕度；输出每小时每支路 kVA 上限。 | 扩展 `graph_from_state()` 和 `validate_dispatch()` 的每小时支路容量输入。 |
| **抢修时长** `repair_hours`（建议一起实现） | `rain_24h_mm`、阵风超阈、道路/区域可达性倍率 | `base_repair_h × weather_access_multiplier`，防止天气仅影响“坏几条线”而未影响恢复节奏。 | 生成 `DisasterScenario.repair_hours`。 |

### 3.1 故障概率：hazard 而不是黑箱分数

对于支路 `l`、小时 `t`：

\[
R_{6,t}=\sum_{k=0}^{5}r_{t-k},\qquad
R_{24,t}=\sum_{k=0}^{23}r_{t-k}
\]

\[
\lambda_{l,t}=\lambda_{0,c(l)}a_l\exp[
\beta_{r1,c}\ln(1+r_t)+
\beta_{r6,c}\ln(1+R_{6,t})+
\beta_{r24,c}\ln(1+R_{24,t})+
\beta_{w,c}(w_t-W_0)_+ +
\beta_{g,c}(g_t-G_0)_+ +
\beta_{T,c}(T_t-T_0)_+
]
\]

\[
p_{l,t}=1-\exp(-\lambda_{l,t}\Delta t), \quad \Delta t=1\ \mathrm{hour}
\]

首版配置建议：`T0=35°C`、`W0=10 m/s`、`G0=15 m/s`。`c(l)` 的最低资产类为 `overhead_line`、`underground_cable`、`switchgear`；`a_l` 由 `exposure_factor × condition_factor` 组成。架空线提高风/阵风系数，电缆与开关柜提高 `R6/R24` 系数，变压器提高高温系数。

为避免独立 Bernoulli 生成“不像灾害”的零散点，场景采样加一个区域共同冲击：

\[
 p'_{l,t}=\operatorname{logistic}(\operatorname{logit}(p_{l,t})+\rho_{zone(l)}Z_t),\quad Z_t\sim N(0,1)
\]

随机数种子固定为 `SHA256(run_seed | scenario_id | weather_raw_sha256 | model_version)` 的前 64 位。这样同一冻结天气、同一参数和同一种子必产生同一故障集。

建议修复时间：

\[
repair_{l}=baseRepair_{c(l)}\,[1+0.03R_{24,t}+0.05(g_t-G_0)_+]\times access_{zone(l)}
\]

再裁剪至配置的 `[min_h,max_h]`。所有参数表必须在结果页显示为“工程先验”。有武汉设备台账/工单后，再以按资产类分层的 Poisson 或 complementary-log-log GLM 拟合 `λ`，替换先验而非改变接口。

### 3.2 PV 降额

令 `G_t` 是短波辐射 W/m²（GHI proxy），`T_a` 是 2 m 气温，默认 `NOCT=45°C`、`γ=-0.004/°C`：

\[
T_{cell}=T_a+\frac{NOCT-20}{800}G_t
\]
\[
pvMultiplier_t=clip(\frac{G_t}{1000}[1+\gamma(T_{cell}-25)],0,1)
\]

`pv_available_kw = installed_pv_capacity_kw × pvMultiplier_t`。首版默认不尝试倾角、方位、遮挡和逆变器裁剪；它是透明的辐照-温度 proxy。若输入缺短波辐射，使用**冻结同日小时气候曲线**或当前合成日照曲线，但将 `pv_source_mode` 标成 `fallback_profile`，绝不伪装为真实辐照回放。

### 3.3 负荷倍率

保留当前 `base_hourly_multiplier[t]`（避免把温度解释为整个日负荷形状），在其上乘天气因子：

\[
loadMultiplier_t=clip(base_t[1+\alpha_{cool}(T_t-26)_+],0.55,1.50)
\]

MVP 推荐 `α_cool=0.018/°C`，并对 `0.01/0.018/0.03` 做敏感性扫描。该数值是园区/配电台区制冷敏感假设，非武汉电网公开负荷弹性估计。第二版可加入湿球温度或逐区域负荷曲线，但不应在十天版阻塞真实天气接入。

### 3.4 线路热限额

当前 `network.py` 的 `capacity_kva` 是明确工程假设；天气接入只将其变成逐时保守派生值，不伪造线路导线型号或 IEEE 738 精确评级：

\[
m_{l,t}=clip(1-0.012(T_t-25)_+ -0.020\frac{G_t}{1000}+0.008\min(w_t,10),0.70,1.10)\times exposure_l
\]
\[
capacityKVA_{l,t}=baseCapacityKVA_l\times m_{l,t}
\]

默认 `exposure_l=1.0`，以后可按走廊、导线/电缆、阴影和检修状态配置。雨水不直接提高热限额（虽然会影响冷却），首版把它只作用于故障与可达性，选择更保守且更容易解释的做法。

---

## 4. 拟引入的代码接口（设计契约）

不修改当前代码；下列是最小落地接口，保留现有合成场景的兼容路径。

```python
# src/gridrescue/weather.py
@dataclass(frozen=True)
class WeatherRequest:
    scenario_id: str
    zone_id: str
    latitude: float
    longitude: float
    start_date: date
    end_date: date
    timezone: str = "Asia/Shanghai"
    source: Literal["openmeteo_archive", "cds_era5"] = "openmeteo_archive"
    model: str = "era5"

@dataclass(frozen=True)
class WeatherDataset:
    frame: pd.DataFrame              # standardized weather.v1 schema
    manifest: dict[str, Any]
    cache_status: Literal["hit", "refreshed", "offline", "synthetic_fallback"]

@dataclass(frozen=True)
class WeatherEffects:
    hourly: pd.DataFrame             # hour/timestamp + load_multiplier, pv_multiplier
    branch_effects: pd.DataFrame     # MultiIndex(hour, branch_id), p_fault, capacity_kva
    manifest: dict[str, Any]

def load_or_fetch_weather(request: WeatherRequest, *, cache_root: Path,
                          refresh: bool = False, offline: bool = False) -> WeatherDataset: ...
def normalize_openmeteo(raw: Mapping[str, Any], request: WeatherRequest) -> pd.DataFrame: ...
def derive_weather_effects(weather: WeatherDataset, model: GridModel,
                           config: WeatherEffectConfig) -> WeatherEffects: ...
def sample_weather_scenario(effects: WeatherEffects, *, run_seed: int) -> DisasterScenario: ...
```

对现有模块的最小改造点：

```python
# scenarios.py：保持现有无参调用；新的可选实参覆盖合成曲线。
def hourly_profiles(scenario: DisasterScenario,
                    weather_effects: WeatherEffects | None = None,
                    seed: int = 2026) -> pd.DataFrame: ...

# network.py：按小时覆盖图边容量，默认继续用静态 capacity_kva。
def graph_from_state(model: GridModel, open_branch_ids=..., closed_tie_ids=...,
                     capacity_kva_by_branch: Mapping[int, float] | None = None) -> nx.Graph: ...

# powerflow.py：验证当前小时使用 effects 给出的支路容量。
def validate_dispatch(model, scenario, plan, dispatch,
                      branch_capacity_kva: pd.DataFrame | None = None) -> FlowValidation: ...

# pipeline.py：新入口，不影响 run_pipeline("暴雨内涝") 的既有演示。
def run_weather_replay(request: WeatherRequest, *, run_seed: int,
                       strategy_names: tuple[str, ...] = STRATEGIES) -> PipelineResult: ...
```

`WeatherEffects.hourly` 至少提供：`timestamp_bjt, hour, load_multiplier, pv_multiplier, ambient_temperature_c, source, source_mode, raw_sha256`。`branch_effects` 至少提供：`hour, branch_id, fault_probability_1h, sampled_failed, repair_hours, thermal_limit_multiplier, capacity_kva`。结果 artifacts 把 `weather_manifest_sha256` 和 `weather_effects_sha256` 写入每个 run 的 `run.json`。

---

## 5. 缓存优先级与离线回退

1. `offline=True`：只读指定 manifest 的标准化 CSV；哈希、字段、时间窗通过才继续。
2. 默认：若 manifest 与原始响应/标准化文件哈希完整，直接 cache hit；不发网络请求。
3. `refresh=True`：显式请求 Open-Meteo 或 CDS，保留新原始证据到新的 `retrieved_utc` 版本目录；旧冻结版本不删除。
4. 网络失败、缓存不存在：读取 `data/weather/fixtures/synthetic_weather.v1_24h.csv`，运行仍可完成，但 `source_mode=synthetic_fallback`、UI badge、导出报告和比较表均强制标注；真实回放统计不接收该行。
5. 若真实缓存存在但缺 `shortwave_radiation`：允许只对 PV 使用冻结 fallback curve，并以 `pv_source_mode=fallback_profile` 标出；故障、负荷与热限额仍由真实字段派生。

**绝不做：**运行时无提示切换来源、覆盖原始 JSON、以当前 API 返回替换竞赛冻结数值、把合成 fallback 和真实天气回放放进同一均值/P90 结论。

---

## 6. 测试与验收

新增测试建议放入 `tests/test_weather.py`，网络测试全部使用录制 JSON fixture 或 mock，CI 不依赖外网。

| 测试 | 输入 | 断言 |
|---|---|---|
| Open-Meteo 规范化 | 固定 `response.json` fixture | 产生 v1 所有必需列、168 小时、`+08:00`、单位正确。 |
| ERA5 单位转换 | 小型 u/v/t/tp/ssrd fixture | 273.15 K→0°C、3/4 m/s→5 m/s、m→mm、J/m²→Wh/m²。 |
| 缓存命中 | 有效 manifest 与文件 | 第二次调用不触发 HTTP，frame 字节语义不变。 |
| 完整性失败 | 改动 raw/normalized 文件一个字节 | SHA-256 校验失败并停止真实回放。 |
| 离线回退 | 禁网络且无缓存/有 fixture | 产物标记 `synthetic_fallback`；有缓存时优先真实缓存。 |
| 特征窗口 | 已知连续雨量 | `R6`、`R24` 的滚动和与边界小时正确。 |
| 单调性 | 单一资产、逐步增大雨/风/温度 | `fault_probability_1h` 不下降；高温、低风、高辐照下 `capacity_kva` 不增加。 |
| PV/负荷边界 | 夜间、强日照、高温 | `0≤pv_multiplier≤1`、夜间为 0、`load_multiplier` 在配置裁剪区间内。 |
| 可重复采样 | 同 effects/seed | `failed_branch_ids`、repair hours 与 derived CSV hash 完全一致；换 seed 才允许改变。 |
| 管道兼容 | 旧 `run_pipeline()` 与新 replay | 旧测试保持通过；新 replay 的 24 h 输入进入 dispatch 与潮流校验，所有小时 `is_feasible`。 |
| 热限额接入 | 人工把一条线容量减到 70% | `loading_pct` 使用动态 `capacity_kva`；不能仍按静态额定值报告可行。 |

验收产物：`weather_manifest.v1.json`、一份原始 JSON、规范化 CSV、派生 effects CSV、图（降雨/风/温度、PV/负荷、故障风险、动态容量）、一条 `--offline` 成功运行日志及其 SHA-256。

---

## 7. 十天内最小实施排程

| 天 | 可交付实施 | 验收线 |
|---|---|---|
| D1 | 固定 `WeatherRequest`/weather.v1/manifest schema；建 `data/weather` 和 `evidence/licenses` 目录。 | schema 文档与空 manifest 通过 JSON schema/字段测试。 |
| D2 | 实现 Open-Meteo query 构造、raw JSON 落盘、canonical request 与 SHA-256。 | mock 请求含 `models=era5`、`timezone=Asia/Shanghai`、`wind_speed_unit=ms`。 |
| D3 | 实现 normalize、小时连续性/单位/缺失 QA；录制武汉 2020-07-04~06 冻结样本。 | 单点 72 行，无缺失；输出 normalized CSV + manifest。 |
| D4 | 实现 cache-first、`--offline` 与 synthetic fixture 回退。 | CI 禁网也能完成 replay；报告正确标识数据模式。 |
| D5 | 实现 `derive_weather_effects()`：雨窗、故障 hazard、PV、负荷、维修倍率。 | 单调性和边界测试通过；输出 effects CSV。 |
| D6 | 以可选参数把 effects 接入 `hourly_profiles()`、`build_demand_frame()`、`build_node_demand_frame()`，不破坏旧场景。 | 现有 `pytest` 全绿，weather replay 改变 PV/负荷。 |
| D7 | 接入逐时支路热限额至图/PF 验证；保存热约束证据。 | 定向容量降额用例确实改变 loading/feasibility。 |
| D8 | 以固定 seed 从支路风险生成 `DisasterScenario` 与 repair hours；共同冲击可开关。 | 相同 seed 与 hash 结果逐字一致。 |
| D9 | 可选 CDS ERA5 取样脚本、转换器和 Open-Meteo 对照 notebook/CSV；补许可证 notice。 | 同日期/点位的 T、风、降水趋势对照和误差统计可复算。 |
| D10 | 冻结 `WH_FLOOD_2020`，生成一键离线命令、artifact manifest、答辩图及 README。 | 新环境 `python -m gridrescue.cli replay-weather --manifest ... --offline` 重现同一输出 hash/核心 KPI。 |

若时间不足，保留 D1-D6 与 D10：真实天气、缓存、PV/负荷/故障概率已闭环；D7 的动态热限额先以 effects 文件导出和报告呈现，避免未接入 PF 却宣称已约束。D9/多点空间化均是扩展项。

---

## 8. 推荐最小案例与命令形状

首发案例建议冻结为 `WH_FLOOD_2020`，北京时间 **2020-07-04 00:00 至 2020-07-06 23:00**（72 小时），后续运行取其中连续 24 小时窗口或做滚动恢复。选择其原因是它适合真实降雨连续过程与后续 CLDAS 核验；最终强度判断以固化的 ERA5 序列而不是事件新闻文字为准。

```powershell
# 一次性抓取/冻结；实际实现后执行
python -m gridrescue.weather fetch `
  --scenario WH_FLOOD_2020 --zone WH-CENTRE `
  --lat 30.5928 --lon 114.3055 `
  --start 2020-07-04 --end 2020-07-06 `
  --source openmeteo_archive --model era5

# 永远可复现的竞赛命令；实际实现后执行
python -m gridrescue.cli replay-weather `
  --manifest data/weather/manifests/weather_manifest.v1.json `
  --offline --run-seed 20260822
```

---

## 9. 一手资料与引用（访问日期：2026-08-22）

1. [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)：历史 API、小时字段、模型选择和单位参数。
2. [Copernicus CDS: ERA5 hourly data on single levels](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview)：ERA5 单层小时产品、字段和 DOI。
3. [Copernicus CDS: ERA5-Land hourly data](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=overview)：ERA5-Land 产品、空间分辨率、DOI 与许可说明。
4. [Copernicus CC BY 4.0 licence](https://cds.climate.copernicus.eu/licences/creative-commons-attribution-4-0-international-public-licence)。
5. [国家气象科学数据中心：CLDAS-V2.0 近实时产品](https://k.data.cma.cn/mekb/?dataCode=NAFP_CLDAS2.0_NRT&r=data%2Fdetail)：中国区域小时产品和字段说明。
6. [湖北省水利厅：2020 年 7 月强降雨信息](https://slt.hubei.gov.cn/fbjd/dtyw/202007/t20200707_2500475.shtml)：`WH_FLOOD_2020` 选窗的事件背景；不替代实际天气数据本体。
