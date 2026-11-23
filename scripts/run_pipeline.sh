#!/usr/bin/env bash
# End-to-end pipeline: download (demo) -> ingest -> dbt build -> analytics -> tests.
# Usage: scripts/run_pipeline.sh [--skip-download] [--skip-benchmarks]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
DBT="${DBT:-$(dirname "$PY")/dbt}"
[[ -f .env ]] || cp .env.example .env
set -a; source .env; set +a

SKIP_DOWNLOAD=0; SKIP_BENCH=0
for arg in "$@"; do
  case "$arg" in
    --skip-download) SKIP_DOWNLOAD=1 ;;
    --skip-benchmarks) SKIP_BENCH=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

if [[ "${HI_DATASET_MODE:-demo}" == "demo" && $SKIP_DOWNLOAD -eq 0 ]]; then
  step "Download public MIMIC-IV demo (checksum-verified)"
  "$PY" -m ingestion.download_demo
fi

step "Ingest raw tables into PostgreSQL"
"$PY" -m ingestion.pipelines.run_ingestion

step "dbt seed + build (models and tests)"
( cd dbt_project && "$DBT" deps --profiles-dir . >/dev/null 2>&1 || true
  "$DBT" build --profiles-dir . )

step "Execute the 25 analytical queries and render docs/sql_catalog.md"
"$PY" -m analytics.reporting.sql_catalog

step "Statistical analysis"
"$PY" -m analytics.statistics.run_statistics

if [[ $SKIP_BENCH -eq 0 ]]; then
  step "SQL optimization benchmarks"
  "$PY" -m analytics.performance.benchmark
fi

step "Executive report and data dictionary"
"$PY" -m analytics.reporting.executive_report
"$PY" -m analytics.reporting.data_dictionary

step "Automated tests"
"$PY" -m pytest -q

step "Done"
