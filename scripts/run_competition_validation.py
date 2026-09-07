"""Reproduce competition experiments without overwriting historic evidence."""
from pathlib import Path
import sys
import json
import hashlib
import pickle
from dataclasses import asdict
from datetime import datetime, timezone
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gridrescue.pipeline import run_pipeline
from gridrescue.mrv import write_mrv_bundle
from gridrescue.scenarios import SCENARIOS
from gridrescue.scenario_catalog import build_catalog, catalog_manifest
from gridrescue.experiments import run_single_scenario, summarize, write_failure_manifest
from gridrescue.pareto import scan_pareto, ParetoScanSpec
from gridrescue.care import default_care_tasks, evaluate_care_tasks
from gridrescue.risk import summarize_risk, choose_strategy
from gridrescue.mrv_sensitivity import propagate_factor_uncertainty
from gridrescue.paired_stats import bootstrap_mean_delta

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/competition2026'


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT / 'src').rglob('*.py')))).hexdigest()
    manifest = OUT / 'experiment_manifest.json'
    if manifest.exists() and json.loads(manifest.read_text(encoding='utf-8'))['code_sha256'] != identity:
        raise RuntimeError('Code changed: use a new output version rather than mix results')
    save_json(manifest, {'code_sha256': identity, 'started_at': datetime.now(timezone.utc).isoformat(), 'boundary': 'synthetic benchmark; no observed outage claims'})
    for name, slug in zip(SCENARIOS, ('flood', 'typhoon', 'heat')):
        path = OUT / 'baseline' / slug
        path.mkdir(parents=True, exist_ok=True)
        print(f'BASE {name}', flush=True)
        result = run_pipeline(name)
        result.comparison.to_csv(path / 'strategy_comparison.csv', index=False)
        for strategy, value in result.strategies.items():
            key = {'传统顺序恢复':'traditional','最小失供恢复':'eens','碳韧协同恢复':'carbon_resilient'}[strategy]
            value.dispatch.frame.to_csv(path / f'dispatch_{key}.csv', index_label='hour')
            value.dispatch.node_frame.to_csv(path / f'nodes_{key}.csv', index=False)
            result.validations[strategy].hourly.to_csv(path / f'physics_{key}.csv')
            result.validations[strategy].nodes.to_csv(path / f'voltages_{key}.csv', index=False)
            result.validations[strategy].branches.to_csv(path / f'branches_{key}.csv', index=False)
            evaluate_care_tasks(default_care_tasks(), value, result.validations[strategy]).to_csv(path / f'care_{key}.csv', index=False)
        bundle = write_mrv_bundle(result, path / 'mrv')
        assert bundle['verification']['verified'], bundle['verification']
        cache = path / 'pipeline.pkl'
        cache.write_bytes(pickle.dumps(result))
        save_json(path / 'cache_manifest.json', {'code_sha256': identity, 'cache_sha256': hashlib.sha256(cache.read_bytes()).hexdigest()})
        inventory = pd.read_csv(bundle['bundle'] / 'outputs/emission_inventory_hourly.csv')
        registry = pd.read_csv(bundle['bundle'] / 'inputs/factor_registry.csv')
        draws, sensitivity = propagate_factor_uncertainty(inventory, registry)
        draws.to_csv(path / 'factor_draws.csv', index=False)
        save_json(path / 'sensitivity_report.json', {'summaries': [asdict(x) for x in sensitivity], 'boundary': 'fixed activity; factor ranges are engineering assumptions'})
        for mode, tasks in [('strict', default_care_tasks()), ('without_care', ())]:
            print(f'PARETO {name} {mode}', flush=True)
            scan_pareto(name, ParetoScanSpec(normal_allowance_fractions=(0,.04,.05,.06), care_tasks=tasks, output_dir=OUT / 'pareto' / slug / mode))
    records = build_catalog()
    batches = []
    for i, record in enumerate(records, 1):
        path = OUT / 'batch36' / f'{record.scenario_id}.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f'BATCH {i}/36 {record.scenario_id}', flush=True)
        if path.exists():
            frame = pd.read_csv(path)
        else:
            frame = run_single_scenario(record.to_disaster_scenario(), scenario_index=i, seed=record.seed)
            frame.to_csv(path, index=False)
        batches.append(frame)
    frame = pd.concat(batches, ignore_index=True)
    frame.to_csv(OUT / 'batch36/experiment_runs.csv', index=False)
    summarize(frame).to_csv(OUT / 'batch36/validation_summary.csv', index=False)
    write_failure_manifest(frame, OUT / 'batch36/failure_manifest.json')
    save_json(OUT / 'batch36/catalog_manifest.json', catalog_manifest(records))
    risk = summarize_risk(frame.to_dict('records'))
    chosen = choose_strategy(risk)
    save_json(OUT / 'risk_report.json', {'metric':'eens_kwh','failure_budget':0,'chosen_strategy':asdict(chosen) if chosen else None,'summaries':[asdict(x) for x in risk]})
    paired = {}
    for metric in ('eens_kwh','critical_eens_kwh','total_carbon_kg'):
        eligible = frame[frame.recommendation_eligible.fillna(False).astype(bool)]
        pivot = eligible.pivot(index='scenario_id', columns='strategy', values=metric)
        delta = (pivot['碳韧协同恢复'] - pivot['最小失供恢复']).dropna()
        paired[metric] = bootstrap_mean_delta(delta)
        paired[metric]['total_pairs'] = 36
        paired[metric]['excluded_pairs'] = 36 - len(delta)
    save_json(OUT / 'batch36/paired_report.json', paired)
    print('EXPERIMENTS COMPLETE', flush=True)


if __name__ == '__main__':
    main()
