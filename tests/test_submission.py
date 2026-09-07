from pathlib import Path
import json
import zipfile
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
    assert 'release/submission_application_2026.pdf' in names
    assert not any('__pycache__' in n or 'research_wave/' in n or n.endswith('.zip') for n in names)


def test_current_archive_when_present_has_one_manifest():
    archive=ROOT/'release/GridRescue_Competition2026_Submission.zip'
    if archive.exists():
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            assert z.namelist().count('release_manifest_competition2026.json')==1
