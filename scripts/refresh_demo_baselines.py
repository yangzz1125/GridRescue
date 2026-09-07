"""Refresh only the final UI baselines; preserve the earlier experiment records."""
from pathlib import Path
import sys,json,pickle,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from gridrescue.pipeline import run_pipeline
from gridrescue.mrv import write_mrv_bundle
ROOT=Path(__file__).resolve().parents[1]
for name,slug in [('暴雨内涝','flood'),('台风','typhoon'),('极端高温','heat')]:
    print(slug,flush=True)
    out=ROOT/'artifacts/competition2026/baseline_current'/slug
    out.mkdir(parents=True,exist_ok=True)
    result=run_pipeline(name)
    bundle=write_mrv_bundle(result,out/'mrv')
    assert bundle['verification']['verified']
    cache=out/'pipeline.pkl'
    cache.write_bytes(pickle.dumps(result))
    code=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'src').rglob('*.py')))).hexdigest()
    (out/'cache_manifest.json').write_text(json.dumps(dict(code_sha256=code,cache_sha256=hashlib.sha256(cache.read_bytes()).hexdigest())),encoding='utf-8')
