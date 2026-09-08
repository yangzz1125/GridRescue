"""Verify the current audit delivery and bind packaging to exact checked bytes."""
from pathlib import Path
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from gridrescue.mrv import verify_mrv_bundle
from scripts.build_submission import selected_files, sha256, VALIDATION as OUT

ART = ROOT / 'artifacts/competition2026_audit_20260907'
PUBLIC = ROOT / 'artifacts/public_replay_audit_20260907'
INDEPENDENT = ROOT / 'artifacts/independent_powerflow_20260907'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = {}
    with (OUT / 'final_pytest.log').open('w', encoding='utf-8') as log:
        test = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider'],
                              cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    match = re.search(r'(\d+) passed', (OUT / 'final_pytest.log').read_text(encoding='utf-8'))
    checks['pytest'] = {'pass': test.returncode == 0, 'count': int(match[1]) if match else None}
    with (OUT / 'final_smoke.log').open('w', encoding='utf-8') as log:
        smoke = subprocess.run([sys.executable, 'scripts/smoke_demo.py'], cwd=ROOT,
                               stdout=log, stderr=subprocess.STDOUT, timeout=60)
    checks['streamlit_health'] = {'pass': smoke.returncode == 0}
    bundles = []
    for directory in (ART / 'baseline_current', PUBLIC):
        for manifest in sorted(directory.glob('*/mrv/run-*/run_manifest.json')):
            verification = verify_mrv_bundle(manifest.parent)
            bundles.append({'path': manifest.parent.relative_to(ROOT).as_posix(),
                            'verified': verification['verified'], 'errors': verification['errors']})
    checks['mrv'] = {'pass': len(bundles) == 6 and all(x['verified'] for x in bundles), 'bundles': bundles}
    source = json.loads((ROOT / 'data/public/source_manifest.json').read_text(encoding='utf-8'))
    checks['public_sources'] = {'pass': bool(source['sources']) and all(
        sha256(ROOT / 'data/public' / row['path']) == row['sha256'] for row in source['sources'])}
    identity = hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT / 'src').rglob('*.py')))).hexdigest()
    for key, directory in [('synthetic_experiments', ART), ('public_replay', PUBLIC)]:
        manifest = json.loads((directory / 'experiment_manifest.json').read_text(encoding='utf-8'))
        checks[key] = {'pass': manifest['status'] == 'completed' and manifest['code_sha256'] == identity,
                       'completed_stages': manifest['completed_stages']}
    independent = json.loads((INDEPENDENT / 'verification.json').read_text(encoding='utf-8'))
    checks['independent_powerflow'] = {'pass': independent['passed'] is True
        and independent['code_sha256'] == identity
        and independent['script_sha256'] == sha256(ROOT / 'scripts/check_independent_powerflow.py')
        and all(sha256(ROOT / row['path']) == row['sha256'] for row in independent['inputs']),
        'checked': independent['checked'], 'not_applicable': independent['not_applicable']}
    browser = OUT / 'browser/checks.json'
    rows = json.loads(browser.read_text(encoding='utf-8')) if browser.is_file() else []
    checks['browser'] = {'pass': len(rows) >= 17 and len([x for x in rows if x.get('network_points') == 33]) == 4,
                         'records': len(rows)}
    required = ['docs/submission_application_2026.md', 'docs/submission_application_2026.html',
                'release/submission_application_2026.pdf', 'docs/team_defense_20260907.md',
                'artifacts/competition2026_audit_20260907/figures/figure_source_index.csv',
                'artifacts/submission_audit_20260907/browser/desktop.png',
                'artifacts/submission_audit_20260907/browser/mobile.png']
    checks['deliverables'] = {'pass': all((ROOT / x).is_file() and (ROOT / x).stat().st_size > 100 for x in required)}
    scan = []
    files = selected_files()
    for path in files:
        if path == Path(__file__) or path.suffix.lower() not in {'.py', '.md', '.html', '.txt', '.toml', '.json', '.csv'}:
            continue
        content = path.read_text(encoding='utf-8', errors='ignore')
        markers = ('C:' + chr(92) + 'Users' + chr(92) + 'ASUS', 'D:/' + '\u684c\u9762',
                   'D:' + chr(92) + '\u684c\u9762', 'Users/ASUS')
        if any(marker.lower() in content.lower() for marker in markers):
            scan.append(path.relative_to(ROOT).as_posix())
    checks['local_path_leaks'] = {'pass': not scan, 'matches': scan,
        'boundary': 'Automated local-path scan only; not institutional anonymity approval.'}
    payload = {'schema_version': 'gridrescue-final-verification-2.0',
               'created_at': datetime.now(timezone.utc).isoformat(), 'python': sys.version.split()[0],
               'platform': platform.platform(), 'code_sha256': identity, 'checks': checks,
               'passed': all(x['pass'] for x in checks.values()),
               'verified_files': {p.relative_to(ROOT).as_posix(): sha256(p) for p in files
                                  if p != OUT / 'final_verification.json'}}
    (OUT / 'final_verification.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': payload['passed'], 'pytest': checks['pytest'], 'mrv_bundles': len(bundles),
                      'failed': [k for k, v in checks.items() if not v['pass']]}, ensure_ascii=False))
    return int(not payload['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
