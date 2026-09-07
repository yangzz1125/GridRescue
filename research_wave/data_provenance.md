# GridRescue 证据包

每个文件登记 `path,sha256,bytes,created_utc,source_id,license,git_commit`，manifest、日志、ZIP 均作 SHA-256 校验；受限原始数据只留许可快照、元数据、hash、重取脚本。

- **weather**：`data/raw/weather/*`；留 Open-Meteo Archive（`models=era5`）或 CDS ERA5 的 URL/JSON、坐标、时区、UTC、字段、hash；附 Open-Meteo/ECMWF/Copernicus 署名、条款快照、ERA5 DOI `10.24381/cds.adbb2d47`。
- **case33**：`data/case33bw.m` 留 MATPOWER case/版本、URL/commit、改动、hash、LICENSE/NOTICE；派生文件留转换脚本/hash。
- **碳因子**：`data/carbon/*.csv`：`factor_id,value,unit,region,year,method,source_url,retrieved_utc,license`；官方/文献/假设分列，假设 `assumption=true`，来源页/PDF 留 hash。
- **依赖、实验结果**：锁 Python/OS/CPU/solver、依赖、hash，SBOM 汇总许可；每 run 记录 seed、scenario、参数/输入 manifest hash、Git SHA、命令、UTC、输出 hash；天气回放与合成压力测试隔离。

## 必增文件
```text
evidence/manifest.json
evidence/sources/{weather,case33,carbon}.json
evidence/licenses/{OPEN-METEO,CDS,MATPOWER,THIRD_PARTY}.txt
evidence/notices/ATTRIBUTION.md; evidence/sbom/cyclonedx.json
evidence/runs/<id>/{run.json,stdout.log,metrics.json,output.sha256}
evidence/zip_audit/{ZIP_CONTENTS.sha256,ZIP_AUDIT.md}
scripts/{fetch_weather.py,build_manifest.py,make_sbom.py,reproduce.ps1,verify_bundle.py}
requirements-lock.txt
```
复算：`fetch_weather.py --manifest evidence/sources/weather.json`→`build_manifest.py`→`make_sbom.py`→`reproduce.ps1 -RunId <id> -Seed 20260822`→`verify_bundle.py evidence/manifest.json`。发布保存 Git SHA/状态；ZIP 固定排序和 UTC，审计清单逐项验路径、hash、LICENSE/NOTICE、SBOM、日志、结果、manifest。
