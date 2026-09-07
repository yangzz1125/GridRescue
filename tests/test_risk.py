from gridrescue.risk import choose_strategy, cvar, summarize_risk


def test_cvar_upper_tail():
    assert cvar([1, 2, 3, 4], alpha=0.75) == 4.0


def test_failed_rows_stay_visible_and_are_not_zero():
    rows = [
        {"strategy": "A", "solve_success": "True", "eens_kwh": "1"},
        {"strategy": "A", "solve_success": "False", "eens_kwh": ""},
        {"strategy": "B", "solve_success": "True", "eens_kwh": "2"},
        {"strategy": "B", "solve_success": "True", "eens_kwh": "3"},
    ]
    summaries = summarize_risk(rows, failure_budget=0.0)
    a = next(item for item in summaries if item.strategy == "A")
    b = next(item for item in summaries if item.strategy == "B")
    assert a.failures == 1
    assert a.failure_rate == 0.5
    assert a.mean == 1.0
    assert not a.eligible
    assert b.eligible
    assert choose_strategy(summaries).strategy == "B"

