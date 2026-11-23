"""Guardrails against committing restricted data or credentials."""

from __future__ import annotations

import subprocess

import pytest

from config.settings import PROJECT_ROOT

MUST_BE_IGNORED = [
    "data/raw/hosp/patients.csv.gz",
    "data/full/mimiciv/3.1/hosp/labevents.csv.gz",
    ".env",
    ".pgdata/base/1",
    "powerbi/datasets/fact_admissions.csv",
    "powerbi/datasets/fact_admissions.parquet",
    "reports/sql_results/q01.csv",
    "logs/ingestion_pipeline.jsonl",
    "notebooks/export.csv",
]


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True)


@pytest.fixture(scope="module", autouse=True)
def require_git():
    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        pytest.skip("not a git repository")


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_sensitive_paths_are_git_ignored(path):
    assert git("check-ignore", "-q", path).returncode == 0, f"{path} is NOT ignored"


def test_no_data_files_would_be_committed():
    candidates = git("ls-files", "--cached", "--others", "--exclude-standard").stdout.split()
    data_like = [p for p in candidates
                 if p.endswith((".csv", ".csv.gz", ".parquet", ".pbix", ".feather"))
                 and not p.startswith(("dbt_project/seeds/", "tests/fixtures/"))]
    assert data_like == [], f"data files would be committed: {data_like}"


def test_env_example_contains_no_secret_values():
    text = (PROJECT_ROOT / ".env.example").read_text()
    for line in text.splitlines():
        if line.startswith("HI_PG_PASSWORD="):
            assert line.strip() == "HI_PG_PASSWORD=", "example file must not hold a password"
