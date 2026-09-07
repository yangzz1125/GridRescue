from copy import deepcopy
from pathlib import Path
import pickle

import numpy as np
import pandas as pd
import pytest

from gridrescue.carbon import calculate_carbon
from gridrescue.metrics import calculate_metrics
from gridrescue.powerflow import validate_dispatch

ROOT = Path(__file__).resolve().parents[1]


def test_physical_gate_rejects_both_signs_of_grid_imbalance():
    with (ROOT / 'artifacts/competition2026/baseline_current/flood/pipeline.pkl').open('rb') as handle:
        result = pickle.load(handle)
    reference = result.strategies['最小失供恢复']
    for delta in (-1000, 1000):
        dispatch = deepcopy(reference.dispatch)
        dispatch.frame.loc[0, 'grid_import_kw'] += delta
        flow = validate_dispatch(result.model, result.scenario, reference.plan, dispatch)
        assert not flow.components.query('hour == 0 and is_root_component').source_feasible.iloc[0]
        assert flow.hourly.loc[0, 'balance_violation']
        assert not flow.hourly.loc[0, 'is_feasible']
    valid = validate_dispatch(result.model, result.scenario, reference.plan, reference.dispatch)
    assert valid.hourly.is_feasible.all()
    above_capacity = deepcopy(reference.dispatch)
    above_capacity.frame.loc[0, 'grid_capacity_kw'] = above_capacity.frame.loc[0, 'grid_import_kw'] - 10
    flow = validate_dispatch(result.model, result.scenario, reference.plan, above_capacity)
    assert not flow.hourly.loc[0, 'is_feasible']


def test_experiment_output_is_new_and_sources_are_snapshotted(tmp_path):
    import hashlib
    import json
    from scripts.run_competition_validation import prepare_output

    output = tmp_path / 'run'
    manifest = prepare_output(output, 'test', {'stages': []})
    assert manifest['status'] == 'running'
    assert manifest['completed_stages'] == []
    for row in manifest['files']:
        assert hashlib.sha256((output / 'reproducibility' / row['path']).read_bytes()).hexdigest() == row['sha256']
    original = (output / 'experiment_manifest.json').read_bytes()
    with pytest.raises(FileExistsError):
        prepare_output(output, 'test', {'stages': []})
    assert (output / 'experiment_manifest.json').read_bytes() == original
    legacy = tmp_path / 'legacy'
    legacy.mkdir()
    (legacy / 'result.csv').write_text('preserve', encoding='utf-8')
    with pytest.raises(FileExistsError):
        prepare_output(legacy, 'test', {})
    assert json.loads(original)['code_sha256'] == manifest['code_sha256']


@pytest.mark.parametrize('unserved,first,sustained,completed', [
    ([0, 0, 10, 0, 0], 0, 3, True),
    ([10, 10, 0, 0, 0], 2, 2, True),
    ([0, 0, 0, 0, 0], 0, 0, True),
    ([0, 0, 0, 0, 10], 0, 5, False),
    ([10, 10, 10, 10, 10], 5, 5, False),
])
def test_restoration_requires_service_until_end_of_window(unserved, first, sustained, completed):
    frame = pd.DataFrame({
        'critical_load_kw': 20.0, 'served_critical_kw': 20.0,
        'unserved_critical_kw': 0.0, 'unserved_normal_kw': unserved,
        'pv_available_kw': 0.0, 'renewable_curtailment_kw': 0.0,
        'grid_import_kw': 100.0 - np.array(unserved),
        'grid_carbon_kg_per_kwh': 0.5, 'diesel_generation_kw': 0.0,
    })
    metrics = calculate_metrics(frame, calculate_carbon(frame, 0), 0)
    assert metrics.restoration_time_h == sustained
    assert metrics.first_full_supply_time_h == first
    assert metrics.restoration_completed is completed
