"""Validated public snapshots adapted to an explicitly synthetic feeder scenario."""
from dataclasses import replace
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from .scenarios import SCENARIOS

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'data/public'


def load_public_scenario(case_id, root=PUBLIC):
    root = Path(root)
    manifest = json.loads((root / 'source_manifest.json').read_text(encoding='utf-8'))
    sources = {row['id']: row for row in manifest['sources']}
    weather = sources[case_id]
    factor = sources['china-electricity-2023']
    for source in (weather, factor):
        path = (root / source['path']).resolve()
        if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('public source path/hash mismatch')
    payload = json.loads((root / weather['path']).read_text(encoding='utf-8'))
    frame = validate_weather(payload, weather['date'])
    base = SCENARIOS[weather['disaster_type']]
    hour = np.arange(24)
    # Engineering transfer function, not measured hospital demand or PV output.
    load = .78 + .14 * np.sin(2 * np.pi * (hour - 8) / 24) + .23 * np.exp(-.5 * ((hour - 19) / 2.7) ** 2)
    load += .012 * np.maximum(frame.temperature_2m.to_numpy() - 26, 0)
    pv = np.clip(frame.shortwave_radiation.to_numpy() / 1000 * .85, 0, 1)
    provenance = {'weather':weather, 'grid_factor':factor, 'model_version':'weather-transfer-v1',
                  'load_temperature_coefficient_per_c':.012, 'load_temperature_threshold_c':26,
                  'pv_performance_ratio':.85, 'pv_reference_w_m2':1000,
                  'data_boundary':'ERA5 reanalysis + official annual statistics + benchmark feeder + synthetic faults/repairs/resources',
                  'factor_uncertainty':'20 percent scenario range assumed for sensitivity; not official uncertainty'}
    return replace(base, name=case_id, disaster_type=weather['disaster_type'],
                   description=f'Historical weather window {weather["date"]}; synthetic feeder and outage assumptions',
                   load_profile=tuple(np.clip(load,.55,1.6)), pv_profile=tuple(pv),
                   grid_factor=float(factor['value']), grid_carbon_multiplier=1,
                   ambient_temperature_c=float(frame.temperature_2m.mean()), provenance_json=json.dumps(provenance, ensure_ascii=False))


def validate_weather(payload, date):
    expected = {'temperature_2m':'°C', 'precipitation':'mm', 'wind_speed_10m':'m/s', 'shortwave_radiation':'W/m²'}
    if payload.get('timezone') != 'Asia/Shanghai' or payload.get('utc_offset_seconds') != 28800:
        raise ValueError('weather timezone mismatch')
    if any(payload.get('hourly_units',{}).get(k) != unit for k, unit in expected.items()):
        raise ValueError('weather units mismatch')
    frame = pd.DataFrame(payload['hourly'])
    if len(frame) != 24 or frame.time.tolist() != pd.date_range(date, periods=24, freq='h').strftime('%Y-%m-%dT%H:%M').tolist():
        raise ValueError('weather requires 24 unique consecutive local hours')
    values = frame[list(expected)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('weather missing/nonfinite values')
    if not frame.temperature_2m.between(-60,60).all() or (frame[['precipitation','wind_speed_10m','shortwave_radiation']] < 0).any().any():
        raise ValueError('weather outside physical range')
    return frame
