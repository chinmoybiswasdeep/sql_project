"""Small-cell suppression and interval statistics.

Suppression is active only when ``settings.dataset_mode == 'full'`` (credentialed MIMIC-IV).
The demo is open access (ODbL), so in demo mode cells are shown but the UI explains that
suppression switches on automatically in full mode.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd

from config.settings import get_settings

SUPPRESSED_LABEL = "suppressed"


def suppression_enabled() -> bool:
    return get_settings().dataset_mode == "full"


def min_cell_size() -> int:
    return get_settings().min_cell_size


def is_small(value: float | int | None, k: int) -> bool:
    """A cell is 'small' when it represents between 1 and k-1 people/encounters."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    return 0 < value < k


def small_mask(df: pd.DataFrame, count_cols: Iterable[str], k: int) -> pd.Series:
    """Boolean Series: True for rows where any of ``count_cols`` is a small cell."""
    cols = [c for c in count_cols if c in df.columns]
    if not cols or df.empty:
        return pd.Series(False, index=df.index)
    numeric = df[cols].apply(pd.to_numeric, errors="coerce")
    return ((numeric > 0) & (numeric < k)).any(axis=1)


def suppress_rows(
    df: pd.DataFrame, count_cols: Iterable[str], *, enabled: bool | None = None,
    k: int | None = None,
) -> tuple[pd.DataFrame, int]:
    """Drop rows containing small cells (for charts). Returns (kept rows, n hidden)."""
    enabled = suppression_enabled() if enabled is None else enabled
    if not enabled or df.empty:
        return df, 0
    k = min_cell_size() if k is None else k
    mask = small_mask(df, count_cols, k)
    return df.loc[~mask].copy(), int(mask.sum())


def mask_table(
    df: pd.DataFrame, count_cols: Iterable[str], *, enabled: bool | None = None,
    k: int | None = None,
) -> tuple[pd.DataFrame, int]:
    """Replace every value in rows containing small cells with a 'suppressed' marker
    (for tables). Non-key columns of a suppressed row are masked too, so a rate cannot be
    used to back out a hidden count. Returns (display frame, n rows masked)."""
    count_cols = list(count_cols)
    enabled = suppression_enabled() if enabled is None else enabled
    if not enabled or df.empty:
        return df, 0
    k = min_cell_size() if k is None else k
    mask = small_mask(df, count_cols, k)
    if not mask.any():
        return df, 0
    out = df.astype(object).copy()
    key_cols = [c for c in df.columns
                if not pd.api.types.is_numeric_dtype(df[c]) and c not in count_cols]
    value_cols = [c for c in out.columns if c not in key_cols]
    out.loc[mask, value_cols] = f"<{k} ({SUPPRESSED_LABEL})"
    # Masked columns now mix numbers and text; render them as text so Arrow serialises cleanly.
    for col in value_cols:
        out[col] = out[col].map(lambda v: "" if v is None or (isinstance(v, float)
                                                             and math.isnan(v)) else str(v))
    return out, int(mask.sum())


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% interval for a binomial proportion, returned as (low, high) in 0-1."""
    if n <= 0:
        return (math.nan, math.nan)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def add_wilson(df: pd.DataFrame, num_col: str, den_col: str) -> pd.DataFrame:
    """Append rate_pct, ci_low_pct and ci_high_pct columns (percent scale)."""
    out = df.copy()
    lows, highs, rates = [], [], []
    for k_, n_ in zip(out[num_col].astype(int), out[den_col].astype(int), strict=True):
        lo, hi = wilson_interval(k_, n_)
        rates.append(100.0 * k_ / n_ if n_ else math.nan)
        lows.append(100.0 * lo)
        highs.append(100.0 * hi)
    out["rate_pct"] = rates
    out["ci_low_pct"] = lows
    out["ci_high_pct"] = highs
    return out
