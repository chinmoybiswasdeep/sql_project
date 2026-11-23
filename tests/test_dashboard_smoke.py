"""Smoke tests for the Streamlit dashboard (dashboard/streamlit).

The integration tests drive the real app with ``streamlit.testing.v1.AppTest`` against the
local warehouse and assert that every page renders without an exception. They are skipped
when PostgreSQL is unreachable. The unit tests cover the privacy/statistics helpers and the
parameterised filter clause and need no database.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "dashboard" / "streamlit"
APP_PATH = APP_DIR / "app.py"
for p in (str(APP_DIR), str(PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

PAGES = [
    "views/overview.py",
    "views/operations.py",
    "views/outcomes.py",
    "views/clinical.py",
    "views/data_quality.py",
    "views/sql_explorer.py",
]


def _db_reachable() -> bool:
    try:
        import psycopg

        from config.settings import get_settings

        with psycopg.connect(get_settings().pg.conninfo, connect_timeout=3) as conn:
            conn.execute("select 1 from marts.fact_admissions limit 1")
        return True
    except Exception:  # noqa: BLE001
        return False


requires_db = pytest.mark.skipif(not _db_reachable(), reason="warehouse database unreachable")


def _app():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


# ------------------------------------------------------------------ integration (AppTest)
@pytest.mark.integration
@requires_db
@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page: str) -> None:
    at = _app()
    at.switch_page(page)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


@pytest.mark.integration
@requires_db
def test_filters_apply_and_tiny_cohort_is_guarded() -> None:
    at = _app()
    at.switch_page("views/outcomes.py")
    at.run()
    at.multiselect(key="flt_age").set_value(["18-44"])
    at.multiselect(key="flt_adm").set_value(["Elective"])
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("too small" in w.value or "not shown" in w.value for w in at.warning)


@pytest.mark.integration
@requires_db
def test_every_catalogued_query_runs_in_explorer() -> None:
    at = _app()
    at.switch_page("views/sql_explorer.py")
    at.run()
    options = at.selectbox(key="sql_query").options
    assert len(options) == 25
    for option in at.selectbox(key="sql_query").options:
        at.selectbox(key="sql_query").set_value(_path_from_label(at, option))
        at.run()
        assert not at.exception, (option, [e.value for e in at.exception])
        assert not at.error, (option, [e.value for e in at.error])


def _path_from_label(at, label: str) -> str:
    import data

    for meta in data.query_catalog():
        if label in (meta["path"], f"{meta['query_id']} · {meta['title']}"):
            return meta["path"]
    raise AssertionError(f"unknown query option {label!r}")


# ------------------------------------------------------------------ unit (no database)
def test_wilson_interval_matches_reference_values() -> None:
    from privacy import wilson_interval

    lo, hi = wilson_interval(52, 255)
    assert lo == pytest.approx(0.1590, abs=5e-4)
    assert hi == pytest.approx(0.2580, abs=5e-4)
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and 0.0 < hi < 0.35


def test_suppression_hides_small_cells_only_when_enabled() -> None:
    from privacy import mask_table, suppress_rows

    df = pd.DataFrame({"grp": ["a", "b", "c"], "n": [3, 12, 0], "rate": [33.3, 8.3, 0.0]})
    kept, hidden = suppress_rows(df, ["n"], enabled=True, k=5)
    assert hidden == 1 and kept["grp"].tolist() == ["b", "c"]
    kept, hidden = suppress_rows(df, ["n"], enabled=False, k=5)
    assert hidden == 0 and len(kept) == 3
    masked, n = mask_table(df, ["n"], enabled=True, k=5)
    assert n == 1
    assert masked.loc[0, "grp"] == "a"
    assert "suppressed" in masked.loc[0, "n"] and "suppressed" in masked.loc[0, "rate"]


def test_filters_bind_values_as_parameters() -> None:
    from data import Filters

    hostile = "F'; drop table marts.fact_admissions; --"
    where, params = Filters(sexes=(hostile,), icu="ICU care").where_clause()
    assert hostile not in where
    assert params["f_sex"] == [hostile] and params["f_icu"] is True
    assert Filters().where_clause() == ("", {})
