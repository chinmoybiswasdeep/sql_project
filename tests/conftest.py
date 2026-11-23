"""Shared fixtures. Integration tests skip cleanly when the warehouse is unavailable."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _warehouse_ready() -> tuple[bool, str]:
    try:
        import psycopg

        from config.settings import get_settings

        with psycopg.connect(get_settings().pg.conninfo, connect_timeout=3) as conn:
            cur = conn.execute("select to_regclass('marts.fact_admissions') is not null")
            if not cur.fetchone()[0]:
                return False, "warehouse not built (run dbt build)"
        return True, ""
    except Exception as exc:  # pragma: no cover - environment dependent
        return False, f"database unreachable: {exc}"


_READY, _REASON = _warehouse_ready()


def pytest_collection_modifyitems(config, items):
    if _READY:
        return
    skip = pytest.mark.skip(reason=_REASON)
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def db():
    import psycopg

    from config.settings import get_settings

    with psycopg.connect(get_settings().pg.conninfo) as conn:
        yield conn


@pytest.fixture(scope="session")
def scalar(db):
    def _scalar(query: str, params: tuple = ()):
        with db.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()[0]
    return _scalar
