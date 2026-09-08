from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'release/GridRescue_Competition2026_Audit_Submission.zip'
MANIFEST='release_manifest_competition2026_audit.json'


def digest(data): return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',type=Path,default=DEFAULT)
    parser.add_argument('--run-tests',action='store_true')
    parser.add_argument('--run-smoke',action='store_true')
    parser.add_argument('--run-extracted-smoke',action='store_true')
    args=parser.parse_args()
    checks={}
    archive=args.archive.resolve()
    checks['archive_exists']=archive.is_file()
    if archive.is_file():
        with zipfile.ZipFile(archive) as z:
            names=z.namelist()
            checks['zip_integrity']=z.testzip() is None
            checks['paths_safe']=all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in names)
            checks['curated']=not any('__pycache__' in n or n.startswith('research_wave/') or n.endswith('.zip') for n in names)
            checks['single_manifest']=names.count(MANIFEST)==1
            manifest=json.loads(z.read(MANIFEST))
            listed={x['path']:x for x in manifest['files']}
            checks['manifest_complete']=set(listed)==set(names)-{MANIFEST}
            checks['manifest_hashes']=all(len(z.read(name))==item['bytes'] and digest(z.read(name))==item['sha256'] for name,item in listed.items())
            checks['required']=all(x in names for x in ('app.py','docs/submission_application_2026.md','data/public/source_manifest.json','artifacts/public_replay_audit_20260907/summary.csv', 'artifacts/independent_powerflow_20260907/verification.json', 'docs/team_defense_20260907.md'))
            checks['recorded_verification']=manifest.get('verification',{}).get('passed') is True
            if args.run_extracted_smoke:
                with tempfile.TemporaryDirectory() as tmp:
                    z.extractall(tmp)
                    result=subprocess.run([sys.executable,'scripts/smoke_demo.py'],cwd=tmp,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
                    checks['extracted_smoke']=result.returncode==0 and '"health": "ok"' in result.stdout
    if args.run_tests:
        checks['pytest']=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT).returncode==0
    if args.run_smoke:
        checks['smoke']=subprocess.run([sys.executable,'scripts/smoke_demo.py'],cwd=ROOT).returncode==0
    payload={'archive':str(archive),'checks':checks,'passed':bool(checks) and all(checks.values()),'failed':[k for k,v in checks.items() if not v]}
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    return int(not payload['passed'])


if __name__=='__main__': raise SystemExit(main())
