"""Freeze a small public-source dataset; never substitute synthetic downloads."""
from pathlib import Path
import urllib.request
import urllib.parse
import hashlib
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/public'
CASES = {
    'wuhan_heat': (30.59,114.30,'2022-08-15','极端高温'),
    'wuhan_rain': (30.59,114.30,'2020-07-06','暴雨内涝'),
    'xiamen_wind': (24.48,118.08,'2016-09-15','台风'),
}
FACTOR_URL = 'https://www.nea.gov.cn/20260116/b3867495909b4bf28f01c642d10e6345/c.html'


def download(url):
    request = urllib.request.Request(url, headers={'User-Agent':'GridRescue-Research/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read(8_000_001)
    if len(raw) > 8_000_000:
        raise ValueError('response too large')
    return raw


def main():
    (OUT / 'raw').mkdir(parents=True, exist_ok=True)
    records = []
    for key, (lat, lon, date, disaster) in CASES.items():
        query = urllib.parse.urlencode(dict(latitude=lat,longitude=lon,start_date=date,end_date=date,hourly='temperature_2m,precipitation,wind_speed_10m,shortwave_radiation',models='era5',timezone='Asia/Shanghai',wind_speed_unit='ms'))
        url = 'https://archive-api.open-meteo.com/v1/archive?' + query
        raw = download(url)
        payload = json.loads(raw)
        if len(payload.get('hourly',{}).get('time',[])) != 24:
            raise ValueError(f'{key}: incomplete weather response')
        path = OUT / 'raw' / f'{key}.json'
        path.write_bytes(raw)
        records.append(dict(id=key,path=path.relative_to(OUT).as_posix(),url=url,sha256=hashlib.sha256(raw).hexdigest(),date=date,disaster_type=disaster,source_type='reanalysis',model='ERA5',timezone='Asia/Shanghai',requested_coordinates=[lat,lon],actual_coordinates=[payload['latitude'],payload['longitude']],license='Open-Meteo API data CC BY 4.0; credit Open-Meteo and Copernicus/ECMWF; verify API use conditions before commercial deployment',meaning='Historical weather window; feeder, faults and repairs remain synthetic assumptions'))
        print(key,flush=True)
    raw = download(FACTOR_URL)
    text = raw.decode('utf-8')
    if '0.5306' not in text or '2023' not in text:
        raise ValueError('official source does not substantiate selected factor')
    path = OUT / 'raw/electricity_factor_2023.html'
    path.write_bytes(raw)
    records.append(dict(id='china-electricity-2023',path=path.relative_to(OUT).as_posix(),url=FACTOR_URL,sha256=hashlib.sha256(raw).hexdigest(),source_type='official_statistics',value=.5306,unit='kgCO2/kWh',year=2023,geography='China national',uncertainty_pct=None,meaning='Annual location-based average, not hourly or marginal emissions; reference-year scenario, not historical event emission reconstruction'))
    (OUT / 'source_manifest.json').write_text(json.dumps({'downloaded_at':datetime.now(timezone.utc).isoformat(),'sources':records},ensure_ascii=False,indent=2),encoding='utf-8')
    print('PUBLIC DATA FROZEN')


if __name__ == '__main__':
    main()
