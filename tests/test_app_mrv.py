import shutil
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "artifacts" / "v08_official" / "flood" / "mrv" / "run-7e495c4e6e73c188"


@pytest.fixture(scope="module", autouse=True)
def official_bundle_exists():
    assert (BUNDLE / "run_manifest.json").exists()


def _run_app(monkeypatch, bundle: Path = BUNDLE) -> AppTest:
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(bundle))
    return AppTest.from_file(ROOT / "app.py", default_timeout=180).run()


def _metrics(at: AppTest) -> dict[str, str]:
    return {item.label: item.value for item in at.metric}


def test_mrv_tab_shows_live_verified_bundle(monkeypatch):
    at = _run_app(monkeypatch)

    assert not at.exception
    metrics = _metrics(at)
    assert metrics["Seal状态"] == "SEALED"
    assert metrics["Verification"] == "PASS"
    assert int(metrics["已校验文件"]) >= 17
    assert metrics["Factor data class"] == "E"
    assert metrics["Same-service gate"] == "未通过"
    assert metrics["Claim status"] == "受控服务预算下的清单差异"
    assert any("现场只读复核" in item.value for item in at.success)


def test_mrv_bundle_download_is_rendered(monkeypatch):
    at = _run_app(monkeypatch)

    labels = [item.proto.label for item in at.get("download_button")]
    assert "下载MRV证据包ZIP" in labels


def test_mismatched_scenario_does_not_reuse_flood_bundle(monkeypatch):
    at = _run_app(monkeypatch)
    scenario_box = next(item for item in at.selectbox if item.label == "灾害场景")
    scenario_box.select("台风").run(timeout=180)

    assert not at.exception
    assert any("没有匹配" in item.value for item in at.info)
    assert _metrics(at).get("Verification") != "PASS"


def test_tampered_bundle_is_visible_as_failed(monkeypatch, tmp_path):
    tampered = tmp_path / "tampered"
    shutil.copytree(BUNDLE, tampered)
    activity_path = tampered / "outputs" / "activity_energy_hourly.csv"
    activities = pd.read_csv(activity_path)
    activities.loc[0, "energy_kwh"] = float(activities.loc[0, "energy_kwh"]) + 1.0
    activities.to_csv(activity_path, index=False)

    at = _run_app(monkeypatch, tampered)

    assert not at.exception
    assert _metrics(at)["Verification"] == "FAIL"
    assert any("复核失败" in item.value for item in at.error)
    rendered_errors = [item.value for item in at.code]
    assert any("activity_energy_hourly.csv" in value for value in rendered_errors)
