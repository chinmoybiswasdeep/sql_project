"""Database helpers shared by analytics, tests, benchmarks and the dashboard."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import PROJECT_ROOT, get_settings

SQL_DIR = PROJECT_ROOT / "sql"
QUERY_MODULES = ["admissions", "readmissions", "icu", "clinical", "operations"]
_HEADER_FIELD = re.compile(r"^--\s*([A-Za-z][A-Za-z ()/&-]+):\s*(.+)$")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(get_settings().pg.sqlalchemy_url, pool_pre_ping=True)


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().pg.conninfo)


def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql_query(text(query), conn, params=params)


def run_sql_file(path: Path) -> pd.DataFrame:
    return read_sql(path.read_text())


def analytical_query_files() -> list[Path]:
    """The 25 catalogued queries, ordered by query number."""
    files = [p for m in QUERY_MODULES for p in (SQL_DIR / m).glob("q*.sql")]
    return sorted(files, key=lambda p: p.name)


def parse_header(path: Path) -> dict[str, str]:
    """Parse the structured '-- Field: value' documentation header of a query file."""
    meta: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.startswith("--"):
            break
        match = _HEADER_FIELD.match(line)
        if match:
            key = match.group(1).strip().lower().replace(" ", "_")
            meta[key] = match.group(2).strip()
    title = next((v for k, v in meta.items() if k.startswith("query_")), None)
    if title is None:
        for line in path.read_text().splitlines():
            if line.startswith("-- Query"):
                title = line.split(":", 1)[1].strip()
                break
    meta["title"] = title or path.stem
    meta["query_id"] = path.stem.split("_")[0].upper()
    return meta
