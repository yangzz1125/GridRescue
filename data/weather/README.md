# Observed Weather Calibration Sample

This directory contains the first observed-data input: Open-Meteo Archive API for the Wuhan area grid (30.59N, 114.30E), 2024-07-01 through 2024-07-07, Asia/Shanghai timezone, hourly temperature, precipitation, wind speed, and shortwave radiation (168 rows).

Files:
- open_meteo_wuhan_20240701_20240707.csv: hourly weather records.
- open_meteo_wuhan_20240701_20240707.metadata.json: source, variables, retrieval time, and SHA-256.

Boundary: this is an observed historical weather calibration sample. It is not yet bound to a named feeder outage or hospital outage record, so it is not called a real-incident replay. The next step is a public outage/repair mapping from weather to failure and repair parameters.
