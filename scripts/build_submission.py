"""Build the portable, anonymous Competition 2026 submission archive."""
from __future__ import annotations
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'release'
ARCHIVE=RELEASE/'GridRescue_Competition2026_Submission.zip'
MANIFEST=ROOT/'release_manifest_competition2026.json'
TOP_FILES=('app.py','ui.py','ui/styles.css','.streamlit/config.toml','README.md','requirements.txt','pyproject.toml')
DOCS=('submission_application_2026.md','submission_application_2026.html','technical_report_2026.md','competition2026_experiments.md','data_sources_2026.md','innovation_evidence_2026.md','presentation_materials_2026.md','submission_checklist_2026.md','claim_dictionary.md','contest_fit_2026.md')


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''): digest.update(chunk)
    return digest.hexdigest()


def _verified_artifact(path):
    parts=path.relative_to(ROOT).parts
    for index,part in enumerate(parts):
        if part.startswith('run-') and index and parts[index-1]=='mrv':
            verification=ROOT.joinpath(*parts[:index+1],'evidence','verification.json')
            return verification.is_file() and json.loads(verification.read_text(encoding='utf-8')).get('verified') is True
    return True


def selected_files():
    files=[ROOT/x for x in TOP_FILES]
    for directory,patterns in ((ROOT/'src',('*.py',)),(ROOT/'scripts',('*.py',)),(ROOT/'tests',('*.py',))):
        for pattern in patterns: files.extend(directory.rglob(pattern))
    files.extend(ROOT/'docs'/x for x in DOCS)
    files.extend([ROOT/'data/case33bw.m',ROOT/'data/factor_registry.csv'])
    files.extend(p for p in (ROOT/'data/public').rglob('*') if p.is_file())
    files.extend(p for p in (ROOT/'artifacts/competition2026').rglob('*') if p.is_file() and p.name not in {'server.json','streamlit.log'} and _verified_artifact(p))
    files.append(RELEASE/'submission_application_2026.pdf')
    return sorted(set(files),key=lambda p:p.relative_to(ROOT).as_posix())


def main():
    RELEASE.mkdir(exist_ok=True)
    verification=json.loads((ROOT/'artifacts/competition2026/validation/final_verification.json').read_text(encoding='utf-8'))
    if not verification.get('passed'):
        raise RuntimeError('Final verification has not passed')
    files=selected_files()
    missing=[p for p in files if not p.is_file()]
    if missing: raise FileNotFoundError(missing)
    payload={'schema_version':'gridrescue-competition2026-release-1.0','generated_at':datetime.now(timezone.utc).isoformat(),
             'project':'GridRescue 碳韧智网','release':'Competition2026','verification':verification,
             'claim_boundary':{'grid':'public benchmark, not observed feeder','weather':'ERA5 reanalysis','factor':'2023 China annual location-based average','faults_resources_care':'engineering assumptions','same_service_reduction':False,'third_party_assurance':False},
             'files':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha256(p)} for p in files]}
    MANIFEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    files.append(MANIFEST)
    with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files,key=lambda p:p.relative_to(ROOT).as_posix()):
            archive.write(path,path.relative_to(ROOT).as_posix())
    corrupt=zipfile.ZipFile(ARCHIVE).testzip()
    digest=sha256(ARCHIVE)
    (RELEASE/'GridRescue_Competition2026_Submission_SHA256.txt').write_text(f'{digest}  {ARCHIVE.name}\n',encoding='utf-8')
    print(json.dumps({'archive':str(ARCHIVE),'files':len(files),'bytes':ARCHIVE.stat().st_size,'sha256':digest,'testzip':corrupt},ensure_ascii=False))
    return int(corrupt is not None)


if __name__=='__main__': raise SystemExit(main())
