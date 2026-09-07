import pandas as pd

from gridrescue.mrv_sensitivity import lhs_uniform, propagate_factor_uncertainty


def test_lhs_is_reproducible():
    assert (lhs_uniform(8, seed=3) == lhs_uniform(8, seed=3)).all()


def test_factor_uncertainty_preserves_strategy_rows():
    inventory = pd.DataFrame(
        [
            {"strategy_id": "a", "activity_value": 10.0, "factor_id": "f"},
            {"strategy_id": "b", "activity_value": 12.0, "factor_id": "f"},
        ]
    )
    registry = pd.DataFrame([{"factor_id": "f", "value": 2.0, "uncertainty_pct": 10.0}])
    draws, summaries = propagate_factor_uncertainty(inventory, registry, draws=20)
    assert len(draws) == 40
    assert {x.strategy_id for x in summaries} == {"a", "b"}
    assert abs(sum(x.winner_count for x in summaries) - 20) == 0

