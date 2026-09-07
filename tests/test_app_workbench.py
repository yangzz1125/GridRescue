from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "artifacts" / "v08_official" / "flood" / "mrv" / "run-7e495c4e6e73c188"


def test_decision_workbench_is_visible_and_has_three_gates(monkeypatch):
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(BUNDLE))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    assert not at.exception
    assert any("评委决策工作台" in item.value for item in at.header)
    metric_labels = {item.label for item in at.metric}
    assert {"推荐候选", "普通服务预算", "Care / 服务合同", "Physics / 物理校验", "MRV / 证据复算"}.issubset(metric_labels)
    assert any(item.label == "证据预设" for item in at.radio)


def test_workbench_no_gfm_preset_renders_blocked_state(monkeypatch):
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(BUNDLE))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    preset = next(item for item in at.radio if item.label == "证据预设")
    preset.set_value("NO_GFM反例 · BLOCKED").run(timeout=180)
    assert not at.exception
    assert any("NO_GFM" in item.value for item in at.error)
