# 2023 电力二氧化碳排放因子接入说明

**维护日期：2026-08-27**  
**来源机构：** 中华人民共和国生态环境部  
**公告：**《关于发布 2023 年度电力平均二氧化碳排放因子的公告》  
**公告日期：** 2026-01-05  
**官方页面：** <https://www.mee.gov.cn/xxgk2018/xxgk/xxgk01/202512/t20251231_1139517.html>

## 1. 接入值

公告表格以 `tCO2/MWh` 发布。数值上 `1 tCO2/MWh = 1 kgCO2/kWh`，因此写入
`data/factor_registry.csv` 时只做单位换算，不改变数值。

| factor_id | registry activity | 地理范围 | 年份 | 公告值 | registry 值 | 适用说明 |
|---|---|---|---:|---:|---:|---|
| `mee-elec-2023-national` | `grid_import_national` | 全国 | 2023 | 0.5306 tCO2/MWh | 0.5306 kgCO2/kWh | 全国电力平均因子 |
| `mee-elec-2023-central-china` | `grid_import_central-china` | 华中区域 | 2023 | 0.5271 tCO2/MWh | 0.5271 kgCO2/kWh | 华中区域电力平均因子 |
| `mee-elec-2023-hubei` | `grid_import_hubei` | 湖北省 | 2023 | 0.4044 tCO2/MWh | 0.4044 kgCO2/kWh | 湖北省电力平均因子 |

同一公告还列出全国扣除市场化非化石能源电力后的因子 `0.6096 tCO2/MWh`，以及全国化石能源电力因子 `0.8273 tCO2/MWh`；本轮不将它们作为默认购电因子，避免把边界不同的因子混入普通电网购电活动。

## 2. 来源字段

三条记录共用以下 provenance：

```text
source_class=O
source_id=MEE-2026-01-05-2023-electricity-factor
source_title=生态环境部关于发布2023年度电力平均二氧化碳排放因子的公告
source_url=https://www.mee.gov.cn/xxgk2018/xxgk/xxgk01/202512/t20251231_1139517.html
method=MEE published average electricity CO2 emission factor; location-based
temporal_resolution=annual
gas_basis=CO2
unit=kgCO2/kWh
approval_status=official-source-reference
```

公告页面是 HTML 公告而非单独下载文件，因此 `source_file_sha256` 留空；公告 URL、发布日期和 `source_id` 是当前可复核来源锚点。

## 3. 边界与使用规则

1. **位置型年度平均因子。** 该值描述相应地理范围和年度的电力平均排放，不等于某一小时的边际排放因子，也不代表某个具体售电合同的市场化因子。
2. **活动边界。** 只用于 `grid_import`（上级电网购电）及“弃新能源的等效电网机会排放”敏感性；柴油和抢修车辆仍沿用项目已有独立因子，不能把电力因子套到柴油活动。
3. **时间边界。** 2023 年度因子不能自动改写 2026 场景的历史冻结结果。历史 V08/Wave10 bundle 继续使用其记录中的合成 E 类因子；新实验显式选择官方行并生成新的 manifest。
4. **地域选择。** 湖北项目优先使用 `湖北省` 行；若研究对象只知道区域而没有省级购电边界，使用 `华中区域` 行并在报告中写明。全国行用于跨区域基准或缺少区域信息的比较。
5. **主张边界。** 接入官方电力因子只提升因子来源质量，不改变 `same_service_pass=false`、`strict_eligible=0` 或“受控服务预算下运行碳清单差异”的服务比较边界；它也不构成现场实测或第三方核证。

## 4. 代码入口

保持历史默认行为：

```python
from gridrescue.carbon import DEFAULT_EMISSION_FACTORS
```

读取官方行：

```python
from gridrescue.carbon import EmissionFactors

factors = EmissionFactors.from_registry(
    "data/factor_registry.csv",
    geography="湖北省",
    year=2023,
)
assert factors.grid_base_kg_per_kwh == 0.4044
```

`DEFAULT_EMISSION_FACTORS` 仍是 `0.5366 / 0.72 / 0.23` 的历史合成演示默认值，确保已冻结 bundle 的结果和 hash 不被悄悄改写。官方行通过独立选择进入新实验。

