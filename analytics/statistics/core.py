"""Statistical primitives used by the analysis module (pure functions, unit-tested).

Conventions
* Proportion CIs use the Wilson score interval (good coverage for small n and
  rates near 0/1, unlike the Wald interval).
* Differences in proportions use Newcombe's hybrid score interval (method 10).
* Effect sizes are preferred to p-values: Cliff's delta for ordinal/skewed
  outcomes, risk difference and risk ratio for binary outcomes.
* Admissions are clustered within patients, so bootstrap CIs resample
  *patients* (cluster bootstrap), not admissions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

Z95 = 1.959963984540054


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float

    def fmt(self, pct: bool = False, digits: int = 1) -> str:
        k = 100.0 if pct else 1.0
        suffix = "%" if pct else ""
        return (f"{self.estimate * k:.{digits}f}{suffix} "
                f"(95% CI {self.low * k:.{digits}f}-{self.high * k:.{digits}f}{suffix})")


def wilson_ci(successes: int, n: int, z: float = Z95) -> Interval:
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and n")
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half))


def newcombe_diff_ci(x1: int, n1: int, x2: int, n2: int, z: float = Z95) -> Interval:
    """CI for p1 - p2 (Newcombe 1998, method 10: hybrid of Wilson score intervals)."""
    a, b = wilson_ci(x1, n1, z), wilson_ci(x2, n2, z)
    p1, p2 = x1 / n1, x2 / n2
    d = p1 - p2
    low = d - np.sqrt((p1 - a.low) ** 2 + (b.high - p2) ** 2)
    high = d + np.sqrt((a.high - p1) ** 2 + (p2 - b.low) ** 2)
    return Interval(d, low, high)


def risk_ratio_ci(x1: int, n1: int, x2: int, n2: int, z: float = Z95) -> Interval:
    """Risk ratio with a log-scale (Katz) interval; adds 0.5 to all cells if any is zero."""
    if 0 in (x1, x2, n1 - x1, n2 - x2):
        x1, x2, n1, n2 = x1 + 0.5, x2 + 0.5, n1 + 1, n2 + 1
    rr = (x1 / n1) / (x2 / n2)
    se = np.sqrt(1 / x1 - 1 / n1 + 1 / x2 - 1 / n2)
    return Interval(rr, float(np.exp(np.log(rr) - z * se)), float(np.exp(np.log(rr) + z * se)))


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """P(X > Y) - P(X < Y). |d| < 0.147 negligible, < 0.33 small, < 0.474 medium, else large."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) == 0 or len(y) == 0:
        raise ValueError("both samples must be non-empty")
    greater = (x[:, None] > y[None, :]).sum()
    less = (x[:, None] < y[None, :]).sum()
    return float((greater - less) / (len(x) * len(y)))


def cliffs_magnitude(d: float) -> str:
    a = abs(d)
    return "negligible" if a < 0.147 else "small" if a < 0.33 else "medium" if a < 0.474 else "large"


def describe(values: pd.Series) -> dict[str, float]:
    v = pd.Series(values, dtype=float).dropna()
    q = v.quantile([0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    return {
        "n": int(v.size), "mean": float(v.mean()), "sd": float(v.std(ddof=1)),
        "variance": float(v.var(ddof=1)), "min": float(v.min()), "p10": float(q[0.10]),
        "p25": float(q[0.25]), "median": float(q[0.50]), "p75": float(q[0.75]),
        "p90": float(q[0.90]), "p95": float(q[0.95]), "max": float(v.max()),
        "iqr": float(q[0.75] - q[0.25]), "skewness": float(stats.skew(v, bias=False)),
    }


def cluster_bootstrap(
    df: pd.DataFrame,
    cluster_col: str,
    statistic: Callable[[pd.DataFrame], float],
    n_boot: int = 2000,
    seed: int = 20261122,
    alpha: float = 0.05,
) -> Interval:
    """Percentile CI from resampling whole clusters (patients) with replacement."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in df.groupby(cluster_col, sort=True)}
    keys = np.array(list(groups))
    estimates = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(keys, size=keys.size, replace=True)
        estimates[i] = statistic(pd.concat([groups[k] for k in sample], ignore_index=True))
    estimates = estimates[~np.isnan(estimates)]
    return Interval(
        float(statistic(df)),
        float(np.quantile(estimates, alpha / 2)),
        float(np.quantile(estimates, 1 - alpha / 2)),
    )
