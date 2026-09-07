import copy
import json
from pathlib import Path
import numpy as np
import pytest
from gridrescue.public_data import load_public_scenario, validate_weather, PUBLIC
from gridrescue.scenarios import hourly_profiles
from gridrescue.experiments import scenario_from_dict, scenario_to_dict
from gridrescue.mrv import default_factor_registry


def test_public_weather_drives_actual_profiles():
    for name in ('wuhan_heat','wuhan_rain','xiamen_wind'):
        scenario = load_public_scenario(name)
        frame = hourly_profiles(scenario)
        assert len(frame) == 24
        assert (frame.grid_carbon_kg_per_kwh == .5306).all()
        assert scenario == scenario_from_dict(scenario_to_dict(scenario))
        factor = default_factor_registry(scenario).iloc[0]
        assert factor.value == .5306 and factor.source_class == 'official_statistics'
        assert factor.source_file_sha256


def test_weather_rejects_missing_wrong_units_and_hours():
    payload = json.loads((PUBLIC/'raw/wuhan_heat.json').read_text())
    for change in ('missing','unit','hour','timezone'):
        bad = copy.deepcopy(payload)
        if change == 'missing': bad['hourly']['precipitation'][0] = None
        if change == 'unit': bad['hourly_units']['wind_speed_10m'] = 'km/h'
        if change == 'hour': bad['hourly']['time'][1] = bad['hourly']['time'][0]
        if change == 'timezone': bad['utc_offset_seconds'] = 0
        with pytest.raises(ValueError): validate_weather(bad,'2022-08-15')
