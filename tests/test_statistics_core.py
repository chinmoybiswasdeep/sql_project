"""Unit tests for statistical primitives against published reference values."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.statistics.core import (
    cliffs_delta,
    cliffs_magnitude,
    cluster_bootstrap,
    describe,
    newcombe_diff_ci,
    risk_ratio_ci,
    wilson_ci,
)


def test_wilson_matches_reference_values():
    # Newcombe (1998) Table I examples: 81/263 -> 0.2553-0.3662; 0/10 -> 0-0.2775
    ci = wilson_ci(81, 263)
    assert ci.low == pytest.approx(0.2553, abs=5e-4)
    assert ci.high == pytest.approx(0.3662, abs=5e-4)
    zero = wilson_ci(0, 10)
    assert zero.low == 0.0
    assert zero.high == pytest.approx(0.2775, abs=5e-4)


def test_wilson_validates_input():
    with pytest.raises(ValueError):
        wilson_ci(5, 0)
    with pytest.raises(ValueError):
        wilson_ci(11, 10)


def test_newcombe_difference_matches_published_example():
    # Newcombe (1998) method 10, example 56/70 vs 48/80: 0.2000 (0.0524, 0.3339)
    ci = newcombe_diff_ci(56, 70, 48, 80)
    assert ci.estimate == pytest.approx(0.2)
    assert ci.low == pytest.approx(0.0524, abs=5e-4)
    assert ci.high == pytest.approx(0.3339, abs=5e-4)


def test_risk_ratio_handles_zero_cells_with_continuity_correction():
    ci = risk_ratio_ci(0, 10, 5, 10)
    assert 0 < ci.low < ci.estimate < ci.high


def test_cliffs_delta_extremes_and_symmetry():
    assert cliffs_delta(np.array([3, 4]), np.array([1, 2])) == 1.0
    assert cliffs_delta(np.array([1, 2]), np.array([3, 4])) == -1.0
    assert cliffs_delta(np.array([1, 2]), np.array([1, 2])) == 0.0
    assert cliffs_magnitude(0.1) == "negligible" and cliffs_magnitude(0.5) == "large"


def test_describe_basic_moments():
    d = describe(pd.Series([1.0, 2.0, 3.0, 4.0, 100.0]))
    assert d["n"] == 5 and d["median"] == 3.0
    assert d["variance"] == pytest.approx(np.var([1, 2, 3, 4, 100], ddof=1))
    assert d["skewness"] > 0


def test_cluster_bootstrap_is_deterministic_and_brackets_estimate():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"subject_id": np.repeat(np.arange(50), 3),
                       "y": rng.normal(10, 2, 150)})
    a = cluster_bootstrap(df, "subject_id", lambda d: d["y"].mean(), n_boot=300, seed=1)
    b = cluster_bootstrap(df, "subject_id", lambda d: d["y"].mean(), n_boot=300, seed=1)
    assert a == b
    assert a.low < a.estimate < a.high
