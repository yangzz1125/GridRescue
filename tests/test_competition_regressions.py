from dataclasses import replace
import numpy as np
import pandas as pd
from gridrescue.scenarios import SCENARIOS, hourly_profiles
from gridrescue.scenario_catalog import build_catalog
from gridrescue.experiments import scenario_from_dict, scenario_to_dict
from gridrescue.mrv_sensitivity import lhs_uniform, propagate_factor_uncertainty
from gridrescue.paired_stats import summarize_pairs, wilson_interval
from gridrescue.risk import cvar, summarize_risk


def test_heat_semantics_survive_rename_and_replay():
    original = SCENARIOS['极端高温']
    renamed = replace(original, name='case-id', disaster_type='极端高温')
    pd.testing.assert_frame_equal(hourly_profiles(original), hourly_profiles(scenario_from_dict(scenario_to_dict(renamed))))
    assert build_catalog()[-1].to_disaster_scenario().disaster_type == '极端高温'


def test_lhs_strata_are_shuffled_and_baseline_preserved():
    sample = lhs_uniform(100, seed=1)
    assert len(set(np.floor(sample * 100))) == 100
    assert not np.all(np.diff(sample) > 0)
    assert abs(np.corrcoef(sample, lhs_uniform(100, seed=2))[0, 1]) < .4
    inventory = pd.DataFrame([dict(strategy_id='a', activity_value=10, factor_id='f', factor_value=.9)])
    registry = pd.DataFrame([dict(factor_id='f', value=.5, uncertainty_pct=0)])
    frame, summaries = propagate_factor_uncertainty(inventory, registry)
    assert summaries[0].baseline_kgco2 == 9
    assert (frame.total_carbon_kg == 9).all()


def test_risk_and_paired_statistics_edges():
    assert np.isclose(cvar([0, 10, 20], alpha=.5), 50 / 3)
    summary = summarize_risk([dict(strategy='a', eens_kwh=1, solve_success=True, physical_pass=False)])[0]
    assert not summary.eligible and summary.failures == 1
    pairs = summarize_pairs([0, 0, 0], [1e-10, -1e-10, 1])
    assert pairs.wins + pairs.ties + pairs.losses == 3
    low = wilson_interval(5, 10, confidence=.8)
    high = wilson_interval(5, 10, confidence=.99)
    assert high[1] - high[0] > low[1] - low[0]


def test_spatial_storage_respects_energy_and_power():
    from gridrescue.pipeline import run_pipeline
    from gridrescue.dispatch import ResourceConfig
    result = run_pipeline()
    config = ResourceConfig()
    for strategy in result.strategies.values():
        for node, frame in strategy.dispatch.node_frame.groupby('node_id'):
            capacity = float(result.model.nodes.loc[node, 'storage_energy_kwh'])
            power = float(result.model.nodes.loc[node, 'storage_power_kw'])
            soc = frame.battery_soc_kwh.to_numpy()
            previous = np.r_[config.initial_soc * capacity, soc[:-1]]
            expected = previous + config.efficiency * frame.battery_charge_kw.to_numpy() - frame.battery_discharge_kw.to_numpy() / config.efficiency
            assert np.allclose(soc, expected, atol=1e-4)
            assert soc.min() >= config.min_soc * capacity - 1e-4
            assert soc.max() <= capacity + 1e-4
            assert frame.battery_discharge_kw.max() <= power + 1e-4
            assert frame.battery_charge_kw.max() <= power + 1e-4

