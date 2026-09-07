"""Run three fixed public-weather cases and seal actual source bytes with results."""
from pathlib import Path
import sys
import json
import hashlib
import pickle
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pandas as pd
from gridrescue.public_data import load_public_scenario
from gridrescue.pipeline import run_scenario
from gridrescue.mrv import write_mrv_bundle, STRATEGY_SLUGS
from gridrescue.care import default_care_tasks,evaluate_care_tasks
from gridrescue.mrv_sensitivity import propagate_factor_uncertainty
from gridrescue.scenarios import hourly_profiles

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/competition2026/public_replay'


def main():
    summary=[]
    for key in ('wuhan_heat','wuhan_rain','xiamen_wind'):
        path=OUT/key
        path.mkdir(parents=True,exist_ok=True)
        print(key,flush=True)
        scenario=load_public_scenario(key)
        hourly_profiles(scenario).to_csv(path/'input_profiles.csv',index_label='hour')
        result=run_scenario(scenario)
        result.comparison.to_csv(path/'strategy_comparison.csv',index=False)
        bundle=write_mrv_bundle(result,path/'mrv')
        assert bundle['verification']['verified'],bundle['verification']
        for name,value in result.strategies.items():
            slug=STRATEGY_SLUGS[name]
            validation=result.validations[name]
            value.dispatch.node_frame.to_csv(path/f'nodes_{slug}.csv',index=False)
            validation.hourly.to_csv(path/f'physics_{slug}.csv')
            validation.nodes.to_csv(path/f'voltages_{slug}.csv',index=False)
            care=evaluate_care_tasks(default_care_tasks(),value,validation)
            care.to_csv(path/f'care_{slug}.csv',index=False)
            summary.append(dict(case=key,strategy=name,**asdict(value.metrics),physical_pass=bool(validation.hourly.is_feasible.all()),care_pass=bool(care.task_complete.all()),feedback_converged=result.feedbacks[name].converged,mrv_verified=True))
        cache=path/'pipeline.pkl'
        cache.write_bytes(pickle.dumps(result))
        code=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'src').rglob('*.py')))).hexdigest()
        (path/'cache_manifest.json').write_text(json.dumps(dict(code_sha256=code,cache_sha256=hashlib.sha256(cache.read_bytes()).hexdigest())),encoding='utf-8')
        inventory=pd.read_csv(bundle['bundle']/'outputs/emission_inventory_hourly.csv')
        registry=pd.read_csv(bundle['bundle']/'inputs/factor_registry.csv')
        draws,sensitivity=propagate_factor_uncertainty(inventory,registry)
        draws.to_csv(path/'factor_draws.csv',index=False)
        (path/'sensitivity_report.json').write_text(json.dumps(dict(summaries=[asdict(x) for x in sensitivity],boundary='20% engineering sensitivity ranges, not official uncertainty'),ensure_ascii=False,indent=2),encoding='utf-8')
    pd.DataFrame(summary).to_csv(OUT/'summary.csv',index=False)
    print(pd.DataFrame(summary).to_string(index=False))


if __name__=='__main__': main()
