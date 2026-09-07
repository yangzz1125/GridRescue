import numpy as np
import pytest

from gridrescue.paired_stats import bootstrap_mean_delta, paired_deltas, summarize_pairs, wilson_interval


def test_failed_pairs_are_excluded_but_counted():
    summary = summarize_pairs([10, 20, None, 40], [8, 21, 30, None], [True, True, False, False])
    assert summary.total_pairs == 4
    assert summary.eligible_pairs == 2
    assert summary.failed_pairs == 2
    assert summary.wins == 1
    assert summary.losses == 1


def test_paired_delta_and_bootstrap_are_deterministic():
    deltas = paired_deltas([10, 20, 30], [8, 25, 27])
    assert np.allclose(deltas, [-2, 5, -3])
    a = bootstrap_mean_delta(deltas, n_resamples=500, seed=7)
    b = bootstrap_mean_delta(deltas, n_resamples=500, seed=7)
    assert a == b
    assert a["n"] == 3


def test_wilson_interval_and_validation():
    lo, hi = wilson_interval(9, 10)
    assert 0 <= lo < hi <= 1
    with pytest.raises(ValueError):
        wilson_interval(11, 10)

