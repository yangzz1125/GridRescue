# 医院生命线负荷参数来源与边界

`data/hospital_load_profiles.csv` 是可替换的 **E 类 synthetic/engineering prior** 输入，不是某家医院的实测负荷，也不是临床运行标准。每一行都带 `source_id`、`source_url` 和 `assumption`；这些字段随 `CareTask` 定义和 MRV/CSV 输出保留，便于评委追溯。

## 公开参考

| source_id 前缀 | 公开参考 | 在模型中的用途 |
|---|---|---|
| `PUB-JGJ312-2CLASS-*` | 《医疗建筑电气设计规范》JGJ 312-2013 的公开条文页面（`https://www.waizi.org.cn/bz/89620.html`） | 支撑医疗建筑重要负荷、供电可靠性和备用电源应按功能分级考虑；不直接给出本项目四个服务块的实测 kW。 |
| `PUB-ICU-DEVICE-114W` | ICU 典型床位设备用电研究（PMC10119198，`https://pmc.ncbi.nlm.nih.gov/articles/PMC10119198/`） | 仅作为呼吸机、监护仪、输液泵等床旁插头负荷的公开量级锚点；本 CSV 的 28 kW 还包含辅助系统，不能把研究数值外推成医院总负荷。 |
| `PUB-GB51039-ICT` | 福建省卫健委转载的住建部公告：《综合医院建筑设计规范》GB 51039-2014 局部修订（`https://wjw.fujian.gov.cn/jggk/csxx/ghyxxc/gzdt/202412/t20241231_6600821.htm`） | 支撑综合医院功能分区、生命线设施和电气系统应按医院场景配置；ICT 聚合功率仍是本项目工程先验。 |
| `PUB-COLDCHAIN-EQUIPMENT` | 综合医院建筑设计规范公开文本（`https://www.jianbiaoku.com/webarbs/book/422.shtml`） | 支撑药品/血液冷链属于连续保障对象；冷链聚合 kW 采用设备数量×单位功率参数化，不冒充单台设备铭牌。 |

## 参数化规则

对每行，`min_kw = quantity × unit_kw × diversity_factor`。当前四行把 `diversity_factor` 冻结为 1.0，目的是让 Care 合同与潮流校验可复算；改成医院现场设备清单时，只需替换数量、单位功率和同时系数，不改 `care.py` 的校验逻辑。

推荐校准顺序：

1. 设备铭牌或厂家 datasheet（呼吸机、监护仪、手术灯、冷藏柜、UPS/机架）；
2. 分项电表/EMS 的 15 min 或 1 h 数据；
3. 医院电气设计图纸中的变压器、应急母线和末端回路容量；
4. 以 `source_id` 新建版本，不覆盖当前 E 类合成行。

## 竞赛口径

这些参数只用于“生命线服务合同”的压力场景和可复现实验。任何申报文字都应继续使用“受控服务预算下的运行碳清单差异”口径，不写成某医院实测、实时 SCADA 控制或第三方核证减排。
