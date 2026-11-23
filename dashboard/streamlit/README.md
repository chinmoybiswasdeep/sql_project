# Hospital Intelligence dashboard (Streamlit + Plotly)

An interactive dashboard over the PostgreSQL warehouse (`marts`, `reporting`, `meta` schemas).
Every figure comes from a live, parameterised, aggregate-only query.

| Page | Contents |
|---|---|
| Executive overview | KPI cards (patients, admissions, median LOS, ICU admission %, 30-day readmission %, in-hospital mortality %, with Wilson 95% CIs), ICU-cohort caveat, cohort composition, data freshness |
| Hospital operations | LOS distribution and percentiles, LOS by admission group, ICU bed-days and median ICU LOS by unit, care-unit transition heatmap, resource-use proxies |
| Patient outcomes | Readmission and mortality by age group, diagnosis and admission group with Wilson 95% CI error bars, LOS comparisons |
| Clinical analytics | Primary diagnosis mix, top lab tests, abnormal-result rates, top therapeutic drugs |
| Data quality & pipeline | Latest ingestion run, per-table source → loaded → warehouse reconciliation, validation checks, missingness, query benchmarks (`meta.query_benchmarks`) |
| SQL explorer & metrics | The 25 catalogued queries: documented header fields, analyst interpretation, SQL text and live result |

## Run

Prerequisites: the warehouse is loaded and built (PostgreSQL on `localhost:5433`, database
`hospital_intel`; connection settings come from `.env` via `config/settings.py`).

From the project root:

```bash
.venv/bin/python -m streamlit run dashboard/streamlit/app.py
# headless on a fixed port:
.venv/bin/python -m streamlit run dashboard/streamlit/app.py --server.headless true --server.port 8599
curl -s localhost:8599/_stcore/health   # -> ok
```

The theme in `dashboard/streamlit/.streamlit/config.toml` is applied with either command above:
Streamlit reads the `.streamlit/config.toml` that sits next to the main script, as well as the
one in the current directory. Running `streamlit run app.py` from inside `dashboard/streamlit/`
also works.

If the database is unreachable, the app shows a connection error with the failing host and port
instead of a stack trace.

## Filters

The sidebar filters (sex, age group, admission group, ICU care yes/no) are applied server-side as
a parameterised `WHERE` clause on `marts.fact_admissions` (`sex = any(:f_sex)` and so on). Other
facts (ICU stays, transfers, labs, medications, diagnoses) are joined to that filtered cohort on
`hadm_id`. User input never reaches SQL text; grouping columns come from a fixed allow-list in
`data.py`. Query results are cached with `st.cache_data` (TTL 10 minutes).

The Data quality and SQL explorer pages show warehouse-wide metadata and catalogued queries, so the
cohort filters do not apply to them.

## Privacy

- Aggregates only. No subject-, admission- or stay-level rows are rendered. The SQL explorer refuses
  to display a result that contains identifier columns.
- Small-cell suppression: when `HI_DATASET_MODE=full`, any group or table row with between 1 and
  `HI_MIN_CELL_SIZE - 1` patients or admissions is hidden from charts and masked in tables, and KPI
  rates with small numerators are withheld. In demo mode (open-access MIMIC-IV demo, ODbL) cells
  are shown, and each page says that suppression switches on in full mode.
- Tiny cohorts: if filters leave fewer than 10 admissions (or fewer than `HI_MIN_CELL_SIZE` in full
  mode), the page shows a warning instead of rates. Below 50 admissions it adds a stability note.

## Cohort caveat

All 100 patients in the MIMIC-IV demo had at least one ICU stay. The dashboard describes an
ICU-patient cohort, not a hospital-wide population. The overview page shows this caveat in a banner.

## Code layout

| File | Purpose |
|---|---|
| `app.py` | Entry point: path setup, page config, `st.navigation`, DB check, sidebar filters |
| `views/*.py` | One module per page |
| `data.py` | `Filters` dataclass, parameterised cached queries |
| `components.py` | Page header, banners, KPI cards, sidebar filters, cohort guard, chart frame |
| `charts.py` | Plotly figure builders (ranked bars, CI dot plots, median/IQR, heatmap, dumbbell) |
| `theme.py` | Palette, Plotly template, page CSS (single source of truth for colour) |
| `privacy.py` | Small-cell suppression and Wilson score intervals |
| `capture_screenshots.py` | Playwright script that writes `docs/images/dashboard_<page>.png` |

## Tests and screenshots

```bash
.venv/bin/python -m pytest tests/test_dashboard_smoke.py -q

# screenshots (app must be running on port 8599)
.venv/bin/python -m pip install playwright && .venv/bin/python -m playwright install chromium
.venv/bin/python dashboard/streamlit/capture_screenshots.py --base-url http://localhost:8599
```
