from pathlib import Path
import json
import zipfile
import pytest
import scripts.build_submission as release

ROOT=Path(__file__).resolve().parents[1]


def test_release_selection_is_portable_and_curated():
    files=release.selected_files()
    names=[p.relative_to(ROOT).as_posix() for p in files]
    assert len(names)==len(set(names))
    assert all(p.is_file() for p in files)
    assert 'app.py' in names and 'data/public/source_manifest.json' in names
    assert {'ui.py', 'ui_network.py', 'ui/styles.css', '.streamlit/config.toml',
            'ui/icons/LICENSE', 'ui/icons/sources.json', 'ui/icons/hospital.svg',
            'ui/icons/radio-tower.svg', 'ui/icons/battery-charging.svg', 'ui/icons/utility-pole.svg'}.issubset(names)
    assert {'requirements-validation.txt', 'docs/team_defense_20260907.md',
            'artifacts/public_replay_audit_20260907/summary.csv',
            'artifacts/independent_powerflow_20260907/verification.json',
            'artifacts/v08_official/flood/mrv/run-7e495c4e6e73c188/run_manifest.json',
            'artifacts/wave11/risk_report/risk_report.json'}.issubset(names)
    assert 'release/submission_application_2026.pdf' in names
    assert not any('__pycache__' in n or 'research_wave/' in n or n.endswith('.zip') for n in names)


def test_current_archive_when_present_has_one_manifest():
    archive=release.ARCHIVE
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            assert z.namelist().count(release.MANIFEST.name)==1


def test_packaging_rejects_changes_after_verification(tmp_path, monkeypatch):
    validation = tmp_path / 'validation'
    validation.mkdir()
    source = tmp_path / 'app.py'
    source.write_text('print(1)', encoding='utf-8')
    report = validation / 'final_verification.json'
    report.write_text(json.dumps({'passed': True, 'verified_files': {'app.py': release.sha256(source)}}), encoding='utf-8')
    monkeypatch.setattr(release, 'ROOT', tmp_path)
    monkeypatch.setattr(release, 'VALIDATION', validation)
    monkeypatch.setattr(release, 'RELEASE', tmp_path / 'release')
    monkeypatch.setattr(release, 'ARCHIVE', tmp_path / 'release/archive.zip')
    monkeypatch.setattr(release, 'MANIFEST', tmp_path / 'manifest.json')
    monkeypatch.setattr(release, 'selected_files', lambda: [source, report])
    assert release.main() == 0
    before = release.ARCHIVE.read_bytes()
    source.write_text('print(2)', encoding='utf-8')
    with pytest.raises(RuntimeError, match='changed since verification'):
        release.main()
    assert release.ARCHIVE.read_bytes() == before
