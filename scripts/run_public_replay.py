"""Run the three public-weather snapshots in a fresh, independently sealed output."""
from pathlib import Path
import argparse
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

import pandas as pd
from gridrescue.public_data import load_public_scenario
from gridrescue.pipeline import run_scenario
from gridrescue.scenarios import hourly_profiles
from scripts.run_competition_validation import prepare_output, export_result, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new empty public replay directory')
    args = parser.parse_args()
    output = args.output.resolve()
    cases = ('wuhan_heat', 'wuhan_rain', 'xiamen_wind')
    manifest = prepare_output(output, 'public_weather', {'cases': list(cases)})
    summary = []
    try:
        for case in cases:
            print(case, flush=True)
            scenario = load_public_scenario(case)
            rows = export_result(run_scenario(scenario), output / case, manifest['code_sha256'])
            hourly_profiles(scenario).to_csv(output / case / 'input_profiles.csv', index_label='hour')
            summary.extend(dict(case=case, **row) for row in rows)
            pd.DataFrame(summary).to_csv(output / 'summary.csv', index=False)
            manifest['completed_stages'].append(case)
            save_json(output / 'experiment_manifest.json', manifest)
        manifest['status'] = 'completed'
    except Exception as exc:
        manifest['status'] = 'failed'
        manifest['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        save_json(output / 'experiment_manifest.json', manifest)
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == '__main__':
    main()
