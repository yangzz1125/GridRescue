from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "artifacts" / "v08_official" / "flood" / "mrv" / "run-7e495c4e6e73c188"


def test_decision_workbench_is_visible_and_has_three_gates(monkeypatch):
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(BUNDLE))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    assert not at.exception
    assert any("方案评估" in item.value for item in at.header)
    assert any('碳韧智网 <span>GridRescue</span>' in item.value for item in at.markdown)
    metric_labels = {item.label for item in at.metric}
    assert {"推荐候选", "普通服务预算", "服务合同", "物理校验", "证据复算"}.issubset(metric_labels)
    assert any(item.label == "证据预设" for item in at.radio)


def test_workbench_presets_update_qualification_and_restore_evidence(monkeypatch):
    bundle = ROOT / "artifacts/competition2026/baseline_current/flood/mrv/run-3d4fa009bfe41047"
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(bundle))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    assert not at.exception
    assert next(x.value for x in at.metric if x.label == "推荐资格") == "PASS"
    gate_labels = {"服务合同", "物理校验", "证据复算"}
    evidence = {x.label: x.value for x in at.metric if x.label in gate_labels}
    for mode, expected in (
        ("NO_GFM反例 · BLOCKED", "BLOCKED"),
        ("受控预算候选 · CLAIM GATED", "CLAIM GATED"),
        ("主推荐 · PASS", "PASS"),
    ):
        next(x for x in at.radio if x.label == "证据预设").set_value(mode).run(timeout=180)
        assert not at.exception
        assert next(x.value for x in at.metric if x.label == "推荐资格") == expected
        assert {x.label: x.value for x in at.metric if x.label in gate_labels} == evidence
        if mode.startswith("NO_GFM"):
            assert any("NO_GFM" in x.value for x in at.error)
        if expected != "PASS":
            assert not any("主推荐通过" in x.value for x in at.success)


def test_missing_bundle_never_claims_success(monkeypatch, tmp_path):
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(tmp_path / "missing"))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    assert not at.exception
    assert next(x.value for x in at.metric if x.label == "推荐资格") == "BLOCKED"
    assert not any("主推荐通过" in x.value for x in at.success)
    for mode in ("受控预算候选 · CLAIM GATED", "NO_GFM反例 · BLOCKED", "主推荐 · PASS"):
        next(x for x in at.radio if x.label == "证据预设").set_value(mode).run(timeout=180)
        assert not at.exception
        assert next(x.value for x in at.metric if x.label == "推荐资格") == "BLOCKED"
        assert not any("主推荐通过" in x.value for x in at.success)


def test_risk_report_is_visible(monkeypatch):
    monkeypatch.setenv("GRIDRESCUE_RISK_REPORT", str(ROOT / "artifacts/wave11/risk_report/risk_report.json"))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    assert not at.exception
    assert any(x.label == "CVaR95" for x in at.metric)


def test_invalid_risk_report_is_unavailable(monkeypatch, tmp_path):
    report = tmp_path / "risk.json"
    monkeypatch.setenv("GRIDRESCUE_RISK_REPORT", str(report))
    for content in (None, "{broken", '{}'):
        if content is not None:
            report.write_text(content, encoding="utf-8")
        at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
        assert not at.exception
        assert any("尾部风险报告不可用" in x.value for x in at.info)


def test_mismatched_archived_dispatch_blocks_recommendation(monkeypatch, tmp_path):
    import shutil
    import pandas as pd
    bundle = tmp_path / "different-result"
    shutil.copytree(BUNDLE, bundle)
    path = bundle / "outputs/dispatch_eens.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "grid_import_kw"] += 10
    frame.to_csv(path, index=False)
    monkeypatch.setenv("GRIDRESCUE_MRV_BUNDLE", str(bundle))
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    assert not at.exception
    assert next(x.value for x in at.metric if x.label == "推荐资格") == "BLOCKED"
    assert any("不对应当前推演" in x.value for x in at.caption)


def test_public_heat_shows_sources_and_care_block(monkeypatch):
    monkeypatch.delenv("GRIDRESCUE_MRV_BUNDLE", raising=False)
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    next(x for x in at.selectbox if x.label == "灾害场景").select("武汉高温 · 2022-08-15").run(timeout=180)
    assert not at.exception
    assert any("官方年度电力因子" in x.value for x in at.markdown)
    assert next(x.value for x in at.metric if x.label == "推荐资格") == "BLOCKED"
    assert next(x.value for x in at.metric if x.label == "Verification") == "PASS"


def test_redesigned_overview_keeps_controls_and_updates_time():
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    assert not at.exception
    assert at.tabs[0].label == "决策总览"
    assert len(at.tabs) == 9
    assert any('class="kpi-strip"' in x.value for x in at.markdown)
    slider = next(x for x in at.slider if x.label == "恢复进程 / 小时")
    slider.set_value(12).run()
    assert not at.exception
    assert any("T+12:00" in x.value for x in at.caption)
    labels = {x.label for x in at.metric}
    assert {"活跃故障", "联络开关闭合", "非根孤岛", "推荐资格"}.issubset(labels)
    assert any('class="strategy-results"' in x.value for x in at.markdown)
    next(x for x in at.button if x.key == "hour-next").click().run()
    assert next(x.value for x in at.slider if x.label == "恢复进程 / 小时") == 13
    next(x for x in at.slider if x.label == "恢复进程 / 小时").set_value(23).run()
    assert next(x.disabled for x in at.button if x.key == "hour-next")
    next(x for x in at.slider if x.label == "恢复进程 / 小时").set_value(0).run()
    assert next(x.disabled for x in at.button if x.key == "hour-previous")
    assert not at.exception




