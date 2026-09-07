from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_real_event_replay_panel_is_visible():
    at = AppTest.from_file(ROOT / "app.py", default_timeout=180).run()
    assert not at.exception
    assert any("Real event replay" in item.value for item in at.subheader)
    assert any("Texas-1" in item.value for item in at.caption)
    assert any(item.label == "Peak customers" for item in at.metric)
    assert any("E_external_aggregate" in item.value for item in at.info)

