"""Reproduce a versioned experiment in a new directory, never overwrite evidence."""
from pathlib import Path
import argparse
import hashlib
import json
import pickle
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from gridrescue.pipeline import run_pipeline
from gridrescue.mrv import write_mrv_bundle, STRATEGY_SLUGS
from gridrescue.scenarios import SCENARIOS
from gridrescue.scenario_catalog import build_catalog, catalog_manifest
from gridrescue.experiments import run_single_scenario, summarize, write_failure_manifest
from gridrescue.pareto import scan_pareto, ParetoScanSpec
from gridrescue.care import default_care_tasks, evaluate_care_tasks
from gridrescue.islands import build_island_passports, write_island_passports
from gridrescue.risk import summarize_risk, choose_strategy
from gridrescue.mrv_sensitivity import propagate_factor_uncertainty
from gridrescue.paired_stats import bootstrap_mean_delta


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare_output(output, kind, settings):
    """Snapshot execution inputs before the first solve; existing runs are read-only."""
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Output is not empty: {output}. Choose a new --output directory.')
    sources = sorted((ROOT / 'src').rglob('*.py'))
    files = sources + [ROOT / name for name in (
        'pyproject.toml', 'requirements.txt', 'scripts/run_competition_validation.py',
        'scripts/run_public_replay.py', 'data/case33bw.m', 'data/factor_registry.csv',
    )] + sorted(p for p in (ROOT / 'data/public').rglob('*') if p.is_file())
    git_head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    git_dirty = subprocess.run(['git', 'status', '--porcelain', '--', 'src', 'scripts',
                                'pyproject.toml', 'requirements.txt', 'data'],
                               cwd=ROOT, capture_output=True, text=True)
    manifest = {
        'schema_version': 'gridrescue-reproducible-experiment-2.0', 'kind': kind,
        'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
        'code_sha256': hashlib.sha256(b''.join(p.read_bytes() for p in sources)).hexdigest(),
        'git_commit': git_head.stdout.strip() if git_head.returncode == 0 else None,
        'source_tree_dirty': bool(git_dirty.stdout.strip()) if git_dirty.returncode == 0 else None,
        'python': sys.version.split()[0],
        'dependencies': {p: version(p) for p in ('numpy', 'pandas', 'networkx', 'cvxpy', 'clarabel', 'streamlit', 'plotly')},
        'settings': settings, 'completed_stages': [], 'files': [],
        'metric_semantics': {'restoration_time_h': 'earliest hour with full service through the remaining window',
                             'first_full_supply_time_h': 'first full-service hour, may be followed by interruptions',
                             'restoration_completed': 'false means restoration_time_h=24 is a censoring sentinel, not completed recovery'},
        'boundary': 'public benchmark and engineering assumptions; not field outage reconstruction',
    }
    output.mkdir(parents=True, exist_ok=True)
    for source in files:
        relative = source.relative_to(ROOT)
        target = output / 'reproducibility' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest['files'].append({'path': relative.as_posix(), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    save_json(output / 'experiment_manifest.json', manifest)
    return manifest


def export_result(result, path, identity):
    path.mkdir(parents=True, exist_ok=True)
    result.comparison.to_csv(path / 'strategy_comparison.csv', index=False)
    summary = []
    for name, value in result.strategies.items():
        slug = STRATEGY_SLUGS[name]
        validation = result.validations[name]
        value.dispatch.frame.to_csv(path / f'dispatch_{slug}.csv', index_label='hour')
        value.dispatch.node_frame.to_csv(path / f'nodes_{slug}.csv', index=False)
        validation.hourly.to_csv(path / f'physics_{slug}.csv')
        validation.nodes.to_csv(path / f'voltages_{slug}.csv', index=False)
        validation.branches.to_csv(path / f'branches_{slug}.csv', index=False)
        validation.components.to_csv(path / f'components_{slug}.csv', index=False)
        value.plan.actions.to_csv(path / f'actions_{slug}.csv', index=False)
        (path / f'report_{slug}.md').write_text(value.report, encoding='utf-8')
        care = evaluate_care_tasks(default_care_tasks(), value, validation)
        care.to_csv(path / f'care_{slug}.csv', index=False)
        write_island_passports(build_island_passports(result.model, result.scenario, value, validation), path, slug)
        summary.append(dict(strategy=name, **asdict(value.metrics),
                            physical_pass=bool(validation.hourly.is_feasible.all()),
                            care_pass=bool(care.task_complete.all()), feedback_converged=bool(result.feedbacks[name].converged)))
    bundle = write_mrv_bundle(result, path / 'mrv', project_root=ROOT)
    if not bundle['verification']['verified']:
        raise RuntimeError(f'MRV verification failed: {bundle["verification"]}')
    for row in summary:
        row['mrv_verified'] = True
        row['run_id'] = bundle['verification']['run_id']
    cache = path / 'pipeline.pkl'
    cache.write_bytes(pickle.dumps(result))
    save_json(path / 'cache_manifest.json', {'code_sha256': identity, 'cache_sha256': hashlib.sha256(cache.read_bytes()).hexdigest()})
    inventory = pd.read_csv(bundle['bundle'] / 'outputs/emission_inventory_hourly.csv')
    registry = pd.read_csv(bundle['bundle'] / 'inputs/factor_registry.csv')
    draws, sensitivity = propagate_factor_uncertainty(inventory, registry)
    draws.to_csv(path / 'factor_draws.csv', index=False)
    save_json(path / 'sensitivity_report.json', {'summaries': [asdict(x) for x in sensitivity],
                                               'boundary': 'fixed activities; engineering uncertainty ranges, not official confidence intervals'})
    return summary


def run_batch(output):
    records = build_catalog()
    path = output / 'batch36'
    path.mkdir(parents=True, exist_ok=True)
    batches = []
    for i, record in enumerate(records, 1):
        print(f'BATCH {i}/{len(records)} {record.scenario_id}', flush=True)
        frame = run_single_scenario(record.to_disaster_scenario(), scenario_index=i, seed=record.seed)
        frame.to_csv(path / f'{record.scenario_id}.csv', index=False)
        batches.append(frame)
    frame = pd.concat(batches, ignore_index=True)
    frame.to_csv(path / 'experiment_runs.csv', index=False)
    summarize(frame).to_csv(path / 'validation_summary.csv', index=False)
    write_failure_manifest(frame, path / 'failure_manifest.json')
    save_json(path / 'catalog_manifest.json', catalog_manifest(records))
    risk = summarize_risk(frame.to_dict('records'))
    chosen = choose_strategy(risk)
    save_json(output / 'risk_report.json', {'metric': 'eens_kwh', 'failure_budget': 0,
                                          'chosen_strategy': asdict(chosen) if chosen else None,
                                          'summaries': [asdict(x) for x in risk]})
    paired = {}
    eligible = frame[frame.recommendation_eligible.fillna(False).astype(bool)]
    for metric in ('eens_kwh', 'critical_eens_kwh', 'total_carbon_kg'):
        pivot = eligible.pivot(index='scenario_id', columns='strategy', values=metric).reindex(columns=STRATEGY_SLUGS)
        delta = (pivot['碳韧协同恢复'] - pivot['最小失供恢复']).dropna()
        paired[metric] = {**bootstrap_mean_delta(delta), 'total_pairs': len(records), 'excluded_pairs': len(records) - len(delta)}
    save_json(path / 'paired_report.json', paired)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new empty experiment directory')
    parser.add_argument('--stages', nargs='+', choices=('baseline', 'batch', 'pareto'), default=['baseline', 'batch', 'pareto'])
    args = parser.parse_args()
    if len(set(args.stages)) != len(args.stages):
        parser.error('stages must not repeat')
    output = args.output.resolve()
    manifest = prepare_output(output, 'synthetic', {'stages': args.stages, 'normal_allowance_fractions': [0, .04, .05, .06]})
    try:
        for stage in args.stages:
            if stage == 'baseline':
                summary = []
                for name, slug in zip(SCENARIOS, ('flood', 'typhoon', 'heat')):
                    print(f'BASE {name}', flush=True)
                    rows = export_result(run_pipeline(name), output / 'baseline_current' / slug, manifest['code_sha256'])
                    summary.extend(dict(case=slug, **row) for row in rows)
                pd.DataFrame(summary).to_csv(output / 'baseline_summary.csv', index=False)
            elif stage == 'batch':
                run_batch(output)
            else:
                for name, slug in zip(SCENARIOS, ('flood', 'typhoon', 'heat')):
                    for mode, tasks in [('strict', default_care_tasks()), ('without_care', ())]:
                        print(f'PARETO {name} {mode}', flush=True)
                        scan_pareto(name, ParetoScanSpec(normal_allowance_fractions=(0, .04, .05, .06), care_tasks=tasks,
                                                       output_dir=output / 'pareto' / slug / mode),
                                    audit_tasks=default_care_tasks() if not tasks else ())
            manifest['completed_stages'].append(stage)
            save_json(output / 'experiment_manifest.json', manifest)
        manifest['status'] = 'completed'
    except Exception as exc:
        manifest['status'] = 'failed'
        manifest['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        save_json(output / 'experiment_manifest.json', manifest)
    print('EXPERIMENTS COMPLETE', flush=True)


if __name__ == '__main__':
    main()
