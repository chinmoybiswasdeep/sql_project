# Progress Log

Last updated: 2026-11-23 (UTC). Environment: macOS 26.6 arm64; PostgreSQL 16.16 and Python
3.12 from conda-forge (micromamba) in `.venv`; project-local cluster in `.pgdata` on port 5433.

## Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Local environment starts | ✅ | `scripts/setup_local.sh --with-postgres` path (initdb + pg_ctl) used for this build |
| Official demo dataset ingested | ✅ | 14 tables, 1,002,596 rows; SHA-256 verified against PhysioNet |
| PostgreSQL contains validated source data | ✅ | 0 rejects, 0 duplicate keys, 0 orphans; 17 plausibility checks (0 error-level fails) |
| dbt transformations execute | ✅ | `dbt build`: 143/143 (3 seeds, 35 models, 103 data tests, 2 unit tests) |
| Fact and dimension tables built | ✅ | 7 facts, 6 dims, 4 reporting views |
| ≥25 meaningful SQL queries execute | ✅ | 25 queries; `docs/sql_catalog.md` regenerated from live execution |
| Key metrics independently validated | ✅ | `sql/validation/v01–v03` (17 components, exact) + pandas re-implementation |
| Automated tests pass | ✅ | `pytest`: 133 passed; `ruff`: clean |
| Streamlit dashboard runs | ✅ | Started headless, health check ok, 6 real screenshots, AppTest smoke tests pass |
| Power BI-ready outputs and docs | ✅ (no .pbix) | Export + 105 DAX measures + M + spec + guide; DAX/M **not executed** (no Power BI Desktop) |
| Benchmarks reproducible | ✅ | `python -m analytics.performance.benchmark`; 5 cases, results identical, re-run twice |
| Real executive report generated | ✅ | `reports/executive_report.md`, numbers queried at generation time |
| README complete | ✅ | |
| Restricted data excluded from VCS | ✅ | `.gitignore` + `tests/test_privacy.py` |
| Reproducible from instructions | ✅ locally | `scripts/run_pipeline.sh` ran end to end in ~3 min (2026-11-23) |

**Full-dataset scalability (reported separately): not demonstrated.** No credentialed
MIMIC-IV access was used. The design for scale (streaming batches, restartable loads, sampled
profiling, incremental lab fact, benchmarked index/rewrite patterns) is implemented but has
not been run at full scale.

## Not executed (written only)

- `docker-compose.yml`, `Dockerfile`: Docker was not installed.
- `.github/workflows/ci.yml`: no remote repository; YAML validated only.
- BigQuery target: no credentialed access; porting notes in `docs/bigquery.md`.
- Power BI DAX / M / theme inside Power BI.

## Phase log

1. **Environment and data.** Found a bare macOS machine (system Python 3.9, no Docker, no
   PostgreSQL). Created `.venv` with micromamba (Python 3.12 + PostgreSQL 16) and pip-installed
   the stack. Downloaded demo v2.2 and verified checksums. Built a streaming ingestion with
   audit tables; the first load passed reconciliation and a rerun skipped unchanged tables.
   Fixed: missingness report empty on restart runs.
2. **Warehouse.** Seeds (ICD-9/10 chapters, care units, admission types), 12 staging, 6
   intermediate, 13 marts, 4 reporting models; generic tests written in-house (no package
   dependency). Fixed: NULL propagation in readmission flags; dbt `var()` resolution inside
   unit tests (wrapper macro).
3. **SQL analytics.** 25 queries plus 3 validation queries. Investigated "Discharge lounge →
   ICU" flows: they are pre-procedure holding for planned surgery (25/26), documented rather
   than "fixed". Excluded BASE diluents and flushes from medication patterns.
4. **Statistics.** Wilson/Newcombe intervals, patient-cluster bootstrap, Cliff's delta,
   sensitivity analysis (readmission 15.8–23.7% by definition).
5. **Dashboards.** Streamlit app and Power BI package (built by delegated agents, reviewed and
   tests re-run here).
6. **Optimization and testing.** 5 benchmark cases with plan-based bottleneck notes and setup
   costs; pytest suite (unit + integration + privacy).
7. **Portfolio.** Executive report with figures, README, architecture/metrics/limitations
   docs, data dictionary, demo script, interview Q&A.

## Commands executed (final verification)

```bash
scripts/run_pipeline.sh            # full rebuild: PASS=143 (dbt), 133 passed (pytest)
.venv/bin/ruff check config ingestion analytics tests powerbi dashboard
```

## Known limitations

See [docs/limitations.md](docs/limitations.md). Most important: the demo is a 100-patient
ICU cohort, so every finding is exploratory.

## Next tasks

1. Obtain credentialed PhysioNet access; run `HI_DATASET_MODE=full` ingestion and record
   load times, memory and dbt run times.
2. Re-run the benchmarks at full scale; evaluate partitioning `chartevents`.
3. Push to GitHub and confirm the CI workflow passes; try `docker compose` on a machine with
   Docker.
4. Build the `.pbix` from `powerbi/documentation/implementation_guide.md` on Windows and tick
   off its validation checklist.
5. Add severity adjustment and CCSR/RxNorm mappings.
