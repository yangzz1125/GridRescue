import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def test_public_api_exposes_stable_model_entrypoint():
    from gridrescue.api import build_model, run_named_scenario

    model = build_model()
    assert len(model.nodes) == 33
    result = run_named_scenario()
    assert len(result.strategies) == 3

