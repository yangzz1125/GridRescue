"""Archive NOAA station daily context; not a matched hourly validation."""
from pathlib import Path
import json
import hashlib
import urllib.request
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]/'data/public'
URL='https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/2022/57494099999.csv'
with urllib.request.urlopen(URL,timeout=40) as response:
    raw=response.read(2_000_000)
path=ROOT/'raw/noaa_tianhe_2022.csv'
path.write_bytes(raw)
frame=pd.read_csv(path)
row=frame.loc[frame.DATE=='2022-08-15'].iloc[0]
record={'id':'noaa-tianhe-2022','path':path.relative_to(ROOT).as_posix(),'url':URL,
        'sha256':hashlib.sha256(raw).hexdigest(),'source_type':'station_daily_summary',
        'station':str(row.STATION),'name':row.NAME,'latitude':float(row.LATITUDE),'longitude':float(row.LONGITUDE),
        'date':'2022-08-15','temperature_mean_c':(float(row.TEMP)-32)*5/9,
        'temperature_samples':int(row.TEMP_ATTRIBUTES),'temperature_max_c':(float(row.MAX)-32)*5/9,
        'temperature_min_c':(float(row.MIN)-32)*5/9,
        'meaning':'NOAA GSOD daily summary from station observations; UTC daily window differs from local ERA5 day, no direct bias/accuracy claim; no station precipitation inserted into hourly model'}
manifest_path=ROOT/'source_manifest.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
manifest['sources']=[x for x in manifest['sources'] if x['id']!=record['id']]+[record]
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'station_context.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=True))
