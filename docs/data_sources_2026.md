# GridRescue 2026 数据来源与边界

## 数据分层

| 数据 | 来源与版本 | 进入模型 | 证据等级与限制 |
|---|---|---|---|
| 配电网 | MATPOWER `case33bw`，Baran & Wu 33节点算例，项目文件SHA `B40831...CCA95D` | P/Q负荷、支路R/X、拓扑 | 公开测试算例，不是中国实际馈线 |
| 高温天气 | Open-Meteo ERA5，武汉网格30.5/114.25，2022-08-15 | 逐时温度、辐射、雨量、风速 | 再分析，非站点直接实测 |
| 降雨天气 | Open-Meteo ERA5，武汉网格30.5/114.25，2020-07-06 | 同上 | 历史天气窗口，不证明实际停电 |
| 大风天气 | Open-Meteo ERA5，厦门网格24.5/118.0，2016-09-15 | 同上 | 历史天气窗口，不证明实际馈线故障 |
| 站点背景 | NOAA GSOD，武汉天河站57494099999，2022年度 | 仅高温日背景说明 | UTC日汇总与ERA5当地日不同，不用于逐时偏差校正 |
| 电力因子 | 国家能源局转载发布的2023全国电力平均因子 | 0.5306 kgCO2/kWh年度固定值 | 位置法年度平均，不是小时或边际因子 |
| 柴油/车辆因子 | 项目engineering_prior | 清单 | 工程假设，未升级为官方或实测 |
| DER、热限、故障、修复、CareTask | 项目配置 | 调度、潮流、服务门 | 合成工程假设 |

## 公开来源

1. 第五届中国研究生“双碳”创新与创意大赛通知：<https://www.icon.tsinghua.edu.cn/info/1080/2272.htm>。
2. 国家能源局《数据显示：我国发电能源结构持续优化》：<https://www.nea.gov.cn/20260116/b3867495909b4bf28f01c642d10e6345/c.html>。
3. Open-Meteo Historical Weather API：<https://open-meteo.com/en/docs/historical-weather-api>。
4. Copernicus ERA5 hourly data：<https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview>。
5. NOAA Global Surface Summary of the Day：<https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00516>。
6. MATPOWER case33bw：<https://github.com/MATPOWER/matpower/blob/master/data/case33bw.m>；模型论文DOI `10.1109/61.25627`。

## 本地冻结与完整性

`data/public/source_manifest.json`保存下载URL、时间、请求/实际坐标、时区、单位、用途和SHA256。气象原始JSON、官方网页HTML和站点CSV保存在`data/public/raw/`。MRV包复制每个实际使用的原始来源字节并再次校验SHA。

关键原文件SHA：

- 武汉高温：`c7acb1d6edb8b287376b918000ae7df7b79a51f1bddd788f0916e76bce9051e8`；
- 武汉降雨：`25b27cff9d5cf3b0d565c4d9a146fcb87b196e9b78a2e15d28f1b1f8fbe3ed42`；
- 厦门大风：`794e533d8e6d4d5413964da704992de508c571a68da754315eb9c08a1eb940f0`；
- 官方因子网页：`c25f5265f8fd7e018d9163e934a9c3394f85785b55abe46237a4ab213c0dd497`；
- NOAA武汉天河站年度文件：`9a456fdf452f33b206192aae31d335d38250ec0cf4a09d008cd23bb19a3942c2`。

## 许可与署名

Open-Meteo API数据按其页面说明提供CC BY 4.0署名使用，材料需注明Open-Meteo及底层Copernicus/ECMWF。NOAA数据需保留来源和数据集元数据。MATPOWER源码许可和论文引用需随提交包保留；商业部署前应重新核对所有来源的最新使用条件。

## 禁止推断

- “用了真实天气”不等于“用了真实馈线或真实停电工单”；
- ERA5不等于地面站逐时实测；
- 年平均因子不等于事件当天小时排放；
- 官方统计因子不使柴油、车辆、DER、医院任务等工程假设自动变成真实数据；
- 三个单日窗口不支持灾害概率、可靠性年景或全国推广结论。
