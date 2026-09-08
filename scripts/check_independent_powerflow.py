"""Independent AC load-flow comparison using optional PYPOWER==5.1.19.

Install PYPOWER in a validation environment, not as a runtime UI dependency.
This checks a frozen nodal dispatch, not protection, dynamics or optimizer optimality.
"""
from pathlib import Path
import argparse
import hashlib
import json
import pickle
import sys
from importlib.metadata import version

import numpy as np
import pandas as pd
from pypower.api import ppoption, runpf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def check_component(model, nodes, branches, component):
    ids = list(nodes.node_id.astype(int))
    bus = np.zeros((len(ids), 13))
    bus[:, 0] = np.array(ids) + 1
    bus[:, 1] = 1
    bus[:, 2] = nodes.net_load_kw.to_numpy() / 1000
    bus[:, 3] = nodes.net_reactive_kvar.to_numpy() / 1000
    bus[:, 6] = 1
    bus[:, 7] = 1
    bus[:, 9] = model.base_kv
    bus[:, 10] = 1
    bus[:, 11] = 1.05
    bus[:, 12] = .95
    slack = ids.index(int(component.slack_node))
    voltage = 1.05 if component.is_root_component else 1.0
    bus[slack, 1] = 3
    bus[slack, 7] = voltage
    gen = np.zeros((1, 21))
    gen[0, [0, 3, 4, 5, 6, 7, 8, 9]] = [ids[slack] + 1, 100, -100, voltage, model.base_mva, 1, 100, -100]
    lines = np.zeros((len(branches), 13))
    zbase = model.base_kv ** 2 / model.base_mva
    for i, row in enumerate(branches.itertuples()):
        source = model.branches.loc[int(row.branch_id)]
        lines[i, [0, 1, 2, 3, 5, 10, 11, 12]] = [
            row.from_node + 1, row.to_node + 1, source.resistance_ohm / zbase,
            source.reactance_ohm / zbase, source.capacity_kva / 1000, 1, -360, 360]
    solved, success = runpf({'version': '2', 'baseMVA': model.base_mva, 'bus': bus, 'gen': gen, 'branch': lines},
                           ppoption(VERBOSE=0, OUT_ALL=0, PF_ALG=1, PF_TOL=1e-10))
    if not success:
        raise RuntimeError('Independent Newton-Raphson did not converge')
    error_v = float(np.max(np.abs(solved['bus'][:, 7] - nodes.voltage_pu.to_numpy())))
    loss = float((solved['branch'][:, 13] + solved['branch'][:, 15]).sum() * 1000)
    error_loss = abs(loss - float(component.p_loss_kw))
    apparent = np.hypot(solved['branch'][:, 13], solved['branch'][:, 14]) * 1000
    error_flow = float(np.max(np.abs(apparent - branches.apparent_flow_kva.to_numpy())))
    return error_v, error_loss, error_flow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', nargs='+', type=Path, required=True, help='directories containing case/pipeline.pkl')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use a new empty validation output')
    caches = sorted(p for directory in args.inputs for p in directory.glob('*/pipeline.pkl'))
    if not caches:
        raise ValueError('No pipeline snapshots found')
    identity = hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT / 'src').rglob('*.py')))).hexdigest()
    rows, inputs = [], []
    for cache in caches:
        print(cache.parent.name, flush=True)
        data = cache.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        metadata = json.loads((cache.parent / 'cache_manifest.json').read_text(encoding='utf-8'))
        if metadata.get('cache_sha256') != digest or metadata.get('code_sha256') != identity:
            raise ValueError(f'Cache/code checksum mismatch: {cache}')
        result = pickle.loads(data)
        inputs.append({'path': cache.resolve().relative_to(ROOT).as_posix(), 'sha256': digest})
        for strategy, validation in result.validations.items():
            for component in validation.components.itertuples():
                nodes = validation.nodes.query('hour == @component.hour and component_id == @component.component_id').sort_values('node_id')
                branches = validation.branches.query('hour == @component.hour and component_id == @component.component_id')
                record = {'case': cache.parent.name, 'strategy': strategy, 'hour': int(component.hour),
                          'component_id': int(component.component_id), 'nodes': len(nodes)}
                if component.slack_node < 0 or branches.empty:
                    record.update(status='not_applicable', reason='deenergized or single-bus component')
                else:
                    try:
                        v, loss, flow = check_component(result.model, nodes, branches, component)
                        record.update(status='pass' if v <= 2e-5 and loss <= .05 and flow <= .1 else 'fail',
                                      voltage_error_pu=v, loss_error_kw=loss, branch_apparent_error_kva=flow)
                    except Exception as exc:
                        record.update(status='error', reason=f'{type(exc).__name__}: {exc}')
                rows.append(record)
    frame = pd.DataFrame(rows)
    tested = frame[frame.status != 'not_applicable']
    report = {'validator': 'PYPOWER Newton-Raphson AC power flow', 'version': version('PYPOWER'),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'code_sha256': identity,
              'cases': len(caches), 'component_hours': len(frame), 'checked': len(tested),
              'not_applicable': int((frame.status == 'not_applicable').sum()),
              'passed': bool(len(tested) and (tested.status == 'pass').all()),
              'max_voltage_error_pu': float(tested.get('voltage_error_pu', pd.Series(dtype=float)).max()),
              'max_loss_error_kw': float(tested.get('loss_error_kw', pd.Series(dtype=float)).max()),
              'max_branch_apparent_error_kva': float(tested.get('branch_apparent_error_kva', pd.Series(dtype=float)).max()),
              'tolerances': {'voltage_pu': 2e-5, 'loss_kw': .05, 'apparent_kva': .1}, 'inputs': inputs,
              'boundary': 'Independent solver on the same frozen modeled injections; not field validation, stability or independent data calibration.'}
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / 'component_checks.csv', index=False)
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
