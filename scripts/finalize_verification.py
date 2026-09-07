"""Create machine-readable final verification before packaging."""
from pathlib import Path
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'src'))
from gridrescue.mrv import verify_mrv_bundle
from scripts.build_submission import selected_files

OUT=ROOT/'artifacts/competition2026/validation'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    checks={}
    with (OUT/'final_pytest.log').open('w',encoding='utf-8') as log:
        test=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    text=(OUT/'final_pytest.log').read_text(encoding='utf-8')
    match=re.search(r'(\d+) passed',text)
    checks['pytest']={'pass':test.returncode==0,'count':int(match.group(1)) if match else None,'command':'python -m pytest -q'}
    with (OUT/'final_smoke.log').open('w',encoding='utf-8') as log:
        smoke=subprocess.run([sys.executable,'scripts/smoke_demo.py'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    checks['streamlit_health']={'pass':smoke.returncode==0,'command':'python scripts/smoke_demo.py'}
    bundles=[]
    excluded_bundles=[]
    for manifest in sorted((ROOT/'artifacts/competition2026').glob('**/mrv/run-*/run_manifest.json')):
        verification=verify_mrv_bundle(manifest.parent)
        record={'path':manifest.parent.relative_to(ROOT).as_posix(),'verified':verification['verified'],'checked_files':verification['checked_files'],'errors':verification['errors']}
        if verification['verified']:
            bundles.append(record)
        else:
            excluded_bundles.append(record)
    checks['mrv']={'pass':len(bundles)>=9 and all(x['verified'] for x in bundles),'bundles':bundles,'excluded_intermediate_bundles':excluded_bundles}
    source=json.loads((ROOT/'data/public/source_manifest.json').read_text(encoding='utf-8'))
    source_checks=[]
    for row in source['sources']:
        path=ROOT/'data/public'/row['path']
        source_checks.append({'id':row['id'],'pass':path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']})
    checks['public_sources']={'pass':all(x['pass'] for x in source_checks),'files':source_checks}
    required=['docs/submission_application_2026.md','docs/submission_application_2026.html','release/submission_application_2026.pdf','docs/technical_report_2026.md','docs/competition2026_experiments.md','docs/data_sources_2026.md','docs/innovation_evidence_2026.md','docs/presentation_materials_2026.md','artifacts/competition2026/figures/figure_source_index.csv','artifacts/competition2026/validation/desktop.png','artifacts/competition2026/validation/mobile.png']
    checks['deliverables']={'pass':all((ROOT/x).is_file() and (ROOT/x).stat().st_size>100 for x in required),'required':required}
    scan=[]
    for path in selected_files():
        if path == Path(__file__) or path.suffix.lower() not in {'.py','.md','.html','.txt','.toml','.json','.csv'}:
            continue
        content=path.read_text(encoding='utf-8',errors='ignore')
        markers=('C:'+chr(92)+'Users'+chr(92)+'ASUS','D:/桌面','D:'+chr(92)+'桌面','Users/ASUS')
        if any(marker.lower() in content.lower() for marker in markers):
            scan.append(path.relative_to(ROOT).as_posix())
    checks['anonymous_paths']={'pass':not scan,'matches':scan}
    payload={'schema_version':'gridrescue-final-verification-1.0','created_at':datetime.now(timezone.utc).isoformat(),'python':sys.version.split()[0],'platform':platform.platform(),'checks':checks,'passed':all(x['pass'] for x in checks.values())}
    (OUT/'final_verification.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':payload['passed'],'pytest':checks['pytest'],'mrv_bundles':len(bundles),'excluded_intermediate_mrv':len(excluded_bundles),'failed':[k for k,v in checks.items() if not v['pass']]},ensure_ascii=False))
    return int(not payload['passed'])


if __name__=='__main__': raise SystemExit(main())
