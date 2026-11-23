# Dashboard A: implementation guide

This guide is for someone with **Power BI Desktop on Windows** who wants to build the five-page report from this package in under an hour. It covers export, load, model, measures, theme, pages, publishing, refresh and privacy. It ends with a **validation checklist**: compare every DAX measure against the values below, which were computed from SQL against the warehouse.

> **Status.** No `.pbix` file is included: Power BI Desktop was not available in the build environment (macOS). The DAX (`measures.dax`) and Power Query M (`power_query.m`) were written to spec but **have not been executed in Power BI**. What *was* executed and tested:
>
> * the export script
> * row counts against PostgreSQL
> * KPI recomputation from the exported CSVs
> * relationship key integrity
> * DAX column and measure references against the exported schema
> * the Wilson CI formula against SciPy
>
> Details are in `tests/test_powerbi_export.py`. Run the checklist to confirm DAX = SQL in your build.

## Time budget

| Step | Minutes |
|---|---:|
| 1. Export datasets | 2 |
| 2. Load with Power Query | 10 |
| 3. Check data types and sort columns | 5 |
| 4. Build relationships | 5 |
| 5. Import measures | 5 |
| 6. Apply the theme | 1 |
| 7. Build the five pages | 25 |
| 8. Validate against the checklist | 5 |
| **Total** | **about 58** |

## Prerequisites

* Power BI Desktop (any 2024 or later release; DAX query view needs the November 2023 release or later).
* Optional but recommended: [Tabular Editor 2](https://github.com/TabularEditor/TabularEditor) (free) or Tabular Editor 3, registered as an External Tool.
* One of:
  * **CSV route**: the folder `powerbi/datasets/` produced by step 1, copied to the Windows machine.
  * **PostgreSQL route**: network access to the warehouse. Recent Power BI Desktop releases include the Npgsql provider for PostgreSQL. Older releases need the Npgsql installer with the GAC option.

## 1. Export the datasets

On the machine that hosts the warehouse, from the project root:

```bash
.venv/bin/python -m powerbi.export_powerbi_datasets
# options: --output-dir DIR  --no-parquet  --full-diagnosis-dictionary  --tables fact_admissions dim_patient
```

This writes 23 tables to `powerbi/datasets/` as `<table>.csv` (UTF-8, ISO-8601 timestamps, booleans `true`/`false`, empty field = null) and `<table>.parquet`, plus `manifest.json`. The manifest holds the row count, source row count, columns and Power Query type of each table, the export time and the dataset label. The script opens a **read-only** session and checks that the CSV and Parquet row counts equal the query count. It fails loudly if they differ.

Reference run (2026-11-22, `mimic-iv-demo-2.2`), with the row counts verified against `select count(*)` on each source:

| Table | Rows | Table | Rows |
|---|---:|---|---:|
| fact_admissions | 275 | dim_patient | 100 |
| fact_readmissions | 275 | dim_admission_type | 9 |
| fact_icu_stays | 140 | dim_care_unit | 42 |
| fact_care_transfers | 861 | dim_diagnosis (codes in use; 109,775 in the full dictionary) | 1,474 |
| fact_diagnoses | 4,506 | dim_lab_test | 1,622 |
| fact_lab_events | 107,727 | dim_medication | 598 |
| fact_medication_orders | 18,087 | dim_age_group / dim_insurance / dim_race_group / dim_los_band | 4 / 3 / 5 / 5 |
| rpt_executive_kpis | 1 | rpt_pipeline_status | 14 |
| rpt_data_quality_checks | 17 | rpt_missingness | 120 |
| ingestion_runs | 3 | query_benchmarks | changing during the build (see the checklist) |

> The files are patient-level. Never commit them (git ignores `powerbi/datasets/*`) and never share them when the credentialed dataset is loaded. See [Privacy](#11-privacy-row-level-security-and-the-mimic-dua).

## 2. Load with Power Query

1. Open Power BI Desktop and start a blank report. Go to **File > Options and settings > Options > Current file > Data load** and turn off **Autodetect new relationships after data is loaded**. Also turn off **Auto date/time** (MIMIC dates are shifted, so automatic date hierarchies would only add noise).
2. Open **Home > Transform data**.
3. Open `documentation/power_query.m`. It is a set of queries separated by `// Query: <name>` lines. For each one, go to **Home > New Source > Blank Query > Advanced Editor**, paste the body (everything up to the next `// Query:` line), click **Done**, and rename the query to `<name>`:
   1. The four parameters: `SourceMode` (`CSV` or `PostgreSQL`), `DataFolder` (for example `C:\HospitalIntel\powerbi\datasets`), `PgServer` (for example `dbhost:5433`) and `PgDatabase` (`hospital_intel`). Set their values under **Home > Manage Parameters**.
   2. The function `fnLoadTable`.
   3. `_Measures`.
   4. The 23 table queries. The query names must match exactly (`fact_admissions`, `dim_patient`, ...), because the DAX uses them.
4. **CSV route:** set `SourceMode = "CSV"` and point `DataFolder` at the exported folder. Under **File > Options > Privacy**, either set the level to Organizational for the folder, or choose "Ignore privacy levels" for this local file.
5. **PostgreSQL route:** set `SourceMode = "PostgreSQL"`. On the first refresh, Power BI asks for credentials (Database: user name and password) and asks you to approve each native query. The queries are the same `SELECT` statements the export script runs, which also derive `diagnosis_key` and the slicer dimensions. Use a **read-only** database role.
6. Put the parameters and `fnLoadTable` in a "Parameters" group and turn off **Enable load** for them (right-click > uncheck Enable load). `_Measures` and the 23 tables stay loaded.
7. Click **Close & Apply**.

If you would rather load the Parquet files (Power BI supports `Parquet.Document`), replace the CSV branch in `fnLoadTable` with `Parquet.Document(File.Contents(DataFolder & "\" & tableName & ".parquet"))`. The types are already correct in Parquet. Keep the UTC conversion step.

## 3. Check data types and sort columns

`fnLoadTable` sets an explicit type on every column (generated from `manifest.json`). After loading, confirm in Table view:

| Check | Expected |
|---|---|
| IDs (`hadm_id`, `subject_id`, `stay_id`, `transfer_id`, `labevent_id`, `itemid`) | Whole number. Set **Summarization: Don't summarize**. |
| `los_days`, `icu_los_days`, `unit_hours`, `days_to_next_admission`, `median_ms` | Decimal number |
| Flags (`had_icu_stay`, `died_in_hospital`, `is_eligible_index`, `is_readmitted_30d`, ...) | True/False |
| Clinical timestamps (`admittime`, `intime`, `charttime`, ...) | Date/time (date-shifted; do not build calendar trends) |
| Audit timestamps (`finished_at`, `last_successful_load_at`, `benchmarked_at`, `checked_at`) | Date/time in **UTC** (converted from timestamptz) |
| `dim_age_group[age_group]` | Column tools > **Sort by column** = `age_group_order` |
| `dim_los_band[los_band]` | **Sort by column** = `los_band_order` |
| `_Measures[Measure Holder]` | Hidden |

## 4. Build the relationships

Use Model view. Create the 21 relationships in `data_model.md` (R1 to R21): all many-to-one, **single** cross-filter direction, all active. Then:

* Make sure Power BI did not create anything else, especially any relationship between `fact_readmissions` and `fact_admissions`, or between a child fact and `dim_patient`.
* Hide the foreign-key columns and the snapshot columns listed at the end of `data_model.md`.

Quick check: in Model view, `fact_admissions` should have 6 dimension relationships and 5 child facts. `fact_readmissions` should have exactly 5 relationships, all to dimensions.

## 5. Import the measures (105 measures, 7 display folders)

`powerbi/measures/measures.dax` is the source of truth. Each measure carries a comment stating its definition and denominator, plus a `// @folder=... @format=...` annotation. Choose one option:

**Option A: Tabular Editor (recommended, about 1 minute).**
1. Start Tabular Editor from **External Tools** while the report is open.
2. Open the **C# Script** tab, paste `powerbi/measures/measures_tabular_editor.csx` and run it (F5). It creates or updates all 105 measures in `_Measures`, with their expressions, display folders (Volume, LOS, ICU, Outcomes, Readmission, Clinical, Data Quality, plus `\Display` sub-folders), format strings and descriptions.
3. Save (Ctrl+S) to write the changes back to Power BI Desktop.

The `.csx` file is generated from `measures.dax`. If you change a measure, edit the `.dax` file and run `.venv/bin/python -m powerbi.measures.generate_tabular_editor_script`. A test fails if the two drift apart.

**Option B: DAX query view (no extra tools).**
1. Open **DAX query view**, paste the whole of `measures.dax`, and run it (F5). The result grid shows the validation row.
2. Click **Update model with changes** (the CodeLens above `DEFINE`) to add every measure to `_Measures`.
3. Display folders and format strings are not set this way. Set them in Model view > Properties, following the annotations, or run Option A afterwards.

**Option C: copy and paste.** In Report view, select `_Measures` and choose **New measure**. Paste `Name = expression` for each measure. This is the slowest option.

## 6. Apply the theme

**View > Themes > Browse for themes** > `documentation/theme.json`. The palette and its contrast ratios are listed in `dashboard_spec.md`. Then set the page background to `#F4F6F8` (Format page > Canvas background) on each page, or set it once and duplicate the page.

## 7. Build the five pages

Follow `documentation/dashboard_spec.md`, which gives the layout grid, visuals, fields, filters, sort order and formatting for each page. Suggested order:

1. Build page 1 (Executive Overview) completely, including the header, footer and slicers. **Duplicate it** four times so the header, footer and background carry over. Rename the copies, and delete the visuals and slicers you do not need on each.
2. **View > Sync slicers**: sync S1 to S5 across pages 1 to 4. They are visible only on page 1, and page 5 is excluded.
3. Page 3: create the `Outcome Group` field parameter (Modeling > New parameter > Fields) before adding V1 to V3.
4. Error bars: select the column chart, open **Analytics pane > Error bars**, choose **By field**, and set Upper bound = `... CI Upper` and Lower bound = `... CI Lower`. Error bars need a recent Desktop release. In older releases, use a line chart with markers only and add the bounds as extra lines.
5. Page 5: use the reporting tables directly. They need no relationships.
6. Fill in alt text and tab order (see the accessibility notes in the spec).

## 8. Publish considerations

* **Demo data only.** The public MIMIC-IV demo (Open Data Commons ODbL) can be shown in a portfolio. Even so, publish only aggregates: use the `(display)` measures for labels, keep the visual-level `>= 5` denominator filters, and do not add table visuals with patient-level rows (`subject_id`, `hadm_id`). Hide those columns before publishing.
* **Never use "Publish to web"** for any build that holds credentialed data. For demo data, prefer screenshots, a PDF export, or a workspace shared with named users.
* Turn off **Export data** (File > Options > Current file > Report settings > Export data: "None", or "Summarized data only") so that viewers cannot download rows.
* Leave the subtitle and footer caveats in place: ICU-patient cohort, de-identified, date-shifted, demo-scale.

## 9. Refresh strategy

| Scenario | Recommendation |
|---|---|
| Portfolio / demo (static extract) | Import mode, CSV route. Re-run the export and click **Refresh** in Desktop. The freshness card shows "Stale" over time. That is expected and shows that the indicator works. |
| Internal deployment on PostgreSQL | Import mode, PostgreSQL route, with an **on-premises data gateway** registered for `PgServer`/`PgDatabase` and a read-only role. Schedule the refresh **after** the nightly `ingestion -> dbt build -> validation` job finishes (for example, the job at 02:00 and the refresh at 03:00). |
| Full MIMIC-IV (hundreds of millions of lab rows) | Do not import `fact_lab_events` at row grain. Either (a) add an aggregated table (lab events per `hadm_id` x `itemid`) in dbt and import that, or (b) put `fact_lab_events` in **DirectQuery** (composite model) and import the rest. Incremental refresh on `charttime` is possible, but the date shifting makes the partitions synthetic. |
| CSV route in the Power BI Service | `File.Contents` with a path built from a parameter inside a function can be reported as a *dynamic data source*, which the Service will not refresh. Refresh in Desktop and republish, or switch to the PostgreSQL route for scheduled refresh. |

`[Hours Since Last Ingestion]` uses `UTCNOW()`, which is evaluated when a query runs, so the card stays current between refreshes. The underlying `ingestion_runs` timestamp changes only on refresh.

## 10. Measure design notes

* **Readmission denominator**: `fact_readmissions` rows with `is_eligible_index = TRUE` (255). It is not all admissions (275).
* **Median and percentiles**: `PERCENTILE.INC`, which equals PostgreSQL `percentile_cont` (linear interpolation).
* **Wilson 95% CI**: written out in DAX with z = 1.959964, and checked against `scipy.stats.binomtest(...).proportion_ci(method="wilson")` in the tests.
* **Therapeutic medications**: `drug_type <> "BASE"` and `NOT CONTAINSSTRING(drug_name_normalized, "flush")`. This is the same filter as SQL query 19. CONTAINSSTRING is case-insensitive; the drug names are already lower-case, so it matches SQL `like`.
* **Small cells**: `[Min Cell Size] = 5` matches `HI_MIN_CELL_SIZE`. Measures in the `\Display` folders return text such as "<5" or "Suppressed (n<5)".
* **Safe division**: every ratio uses `DIVIDE`. The test suite rejects a bare `/` in measure code.

## 11. Privacy, row-level security and the MIMIC DUA

* **No patient-level data is published by this package.** The exports in `powerbi/datasets/` are generated locally, are git-ignored, and must never be committed. See `powerbi/datasets/README.md`.
* **Credentialed MIMIC-IV** (the full dataset) is covered by the PhysioNet Credentialed Health Data Use Agreement. That data, and any report or `.pbix` that contains it, **must not be shared publicly or with anyone who is not credentialed** and covered by the agreement. Do not upload it to a Power BI tenant that people without credentials can reach. The DUA also forbids sending the data to third-party services that are not covered. Treat a `.pbix` built on credentialed data as the data itself, because it holds an imported copy.
* **Row-level security** is not needed for the demo. If a credentialed build must be shared inside a covered team, RLS does **not** make it publishable, because imported data remains in the file. Restrict access at the workspace level, and publish only aggregated screenshots that follow the small-cell rule.
* `.pbix` files are git-ignored in this repository (`*.pbix` in `.gitignore`).

## 12. Validation checklist

Run the `EVALUATE` query at the bottom of `measures.dax` in DAX query view, or put each measure on a card **with no slicers applied**. Each DAX value must match the expected value. The expected values were computed on **2026-11-22** by running SQL directly against `hospital_intel` (dataset `mimic-iv-demo-2.2`). Percentages are shown as displayed (format `0.0%`) and as the raw ratio. Tolerances: exact for counts; ±0.001 for decimals; ±0.0005 for ratios.

The page 5 card **`[KPI Reconciliation Status]`** runs ten of these checks automatically against `rpt_executive_kpis`. It should read "DAX = SQL for all 10 headline KPIs".

### Headline KPIs (also in `reporting.rpt_executive_kpis`)

| # | Measure | Expected | SQL used |
|---|---|---|---|
| 1 | Total Patients | **100** | `count(distinct subject_id)` from `fact_admissions` |
| 2 | Total Admissions | **275** | `count(*)` from `fact_admissions` |
| 3 | Admissions per Patient | **2.75** | 275 / 100 |
| 4 | Median LOS (days) | **4.853** (4.852778) | `percentile_cont(0.5)` of `los_days` |
| 5 | ICU Admission % | **46.5%** (0.4655) | 128 / 275 |
| 6 | Hospital Mortality % | **5.5%** (0.0545) | 15 / 275 |
| 7 | Eligible Index Admissions | **255** | `count(*) filter (where is_eligible_index)` |
| 8 | Readmissions 30d | **52** | `count(*) filter (where is_readmitted_30d)` |
| 9 | Readmission 30d % | **20.4%** (0.2039) | 52 / 255 (eligible index admissions, NOT 275) |
| 10 | Unplanned Readmission 30d % | **18.8%** (0.1882) | 48 / 255 |

### Confidence intervals (Wilson 95%, z = 1.959964)

| # | Measure | Expected |
|---|---|---|
| 11 | Readmission 30d % CI Lower / Upper | **15.9% / 25.8%** (0.1590 / 0.2576) |
| 12 | Unplanned Readmission 30d % CI Lower / Upper | **14.5% / 24.1%** (0.1450 / 0.2407) |
| 13 | Hospital Mortality % CI Lower / Upper | **3.3% / 8.8%** (0.0333 / 0.0880) |
| 14 | ICU Mortality % CI Lower / Upper | **5.0% / 14.4%** (0.0497 / 0.1438) |

### Volume and LOS

| # | Measure | Expected |
|---|---|---|
| 15 | Repeat Patients / Repeat Patient % | **48** / **48.0%** |
| 16 | Emergency Admission % | **43.3%** (0.4327) |
| 17 | ED Visit % | **66.2%** (0.6618) |
| 18 | Mean LOS (days) | **6.876** |
| 19 | LOS P25 / P75 / P90 (days) | **2.692 / 8.768 / 14.503** |
| 20 | LOS IQR (days) | **6.076** |
| 21 | Total Bed Days | **1,890.8** |
| 22 | Long Stay % (14+ days) / Short Stay % (<1 day) | **11.3% / 10.9%** |

### ICU and operations

| # | Measure | Expected |
|---|---|---|
| 23 | ICU Admissions | **128** |
| 24 | ICU Stays / ICU Patients | **140 / 100** |
| 25 | ICU Stays per ICU Admission | **1.09** (1.09375) |
| 26 | Total ICU Days | **515.1** |
| 27 | Median / Mean ICU LOS (days) | **2.155 / 3.679** |
| 28 | ICU Deaths / ICU Mortality % | **12 / 8.6%** (0.0857) |
| 29 | ICU Unit Change % | **7.9%** (0.0786) |
| 30 | Repeat ICU Stays (same admission) | **12** |
| 31 | Median Hours Admit to ICU | **2.1** (2.0608) |
| 32 | Care Unit Movements | **861** |
| 33 | Unit Changes / Unit Changes per Admission | **450 / 1.64** |
| 34 | Care Unit Hours | **46,548.2** |
| 35 | Procedures per Admission | **2.63** |

### Outcomes and readmission detail

| # | Measure | Expected |
|---|---|---|
| 36 | Hospital Deaths | **15** |
| 37 | Mean Charlson Score | **2.77** |
| 38 | Excluded Index Admissions | **20** (died_in_hospital 15, left_against_medical_advice 4, transfer_to_acute_care 1) |
| 39 | Unplanned Readmissions 30d | **48** |
| 40 | Readmissions within 24h | **4**; the display measure shows **"<5"** |
| 41 | Median Days to Readmission | **10.9** (10.9156) |

### Clinical

| # | Measure | Expected |
|---|---|---|
| 42 | Diagnoses / Diagnoses per Admission | **4,506 / 16.4** |
| 43 | Admissions with Diagnosis | **275** |
| 44 | Distinct ICD Codes | **1,474** |
| 45 | Lab Events (all) / Admission-Linked Lab Events | **107,727 / 79,307** |
| 46 | Labs per Admission | **288.4** (288.389) |
| 47 | Abnormal Lab Events / Abnormal Lab % | **40,275 / 37.4%** (0.3739) |
| 48 | Low Result % / High Result % | **19.9% / 24.6%** (0.1989 / 0.2458) |
| 49 | Medication Orders (all) / Therapeutic Orders | **18,087 / 13,671** |
| 50 | Distinct Therapeutic Drugs | **548** |
| 51 | Admissions Exposed / % Admissions Exposed | **250 / 90.9%** |
| 52 | Therapeutic Orders per Admission | **49.7** |
| 53 | Median Order Hours | **32.0** |

### Sliced spot checks (one slicer value at a time)

| # | Filter | Measure | Expected |
|---|---|---|---|
| 54 | `dim_age_group` = 80+ | Readmission 30d % | **11.9%** (5 / 42) |
| 55 | `dim_age_group` = 45-64 | Readmission 30d % | **22.0%** (27 / 123) |
| 56 | `dim_patient[sex]` = F | Total Admissions / Total Patients / Readmissions 30d / Eligible | **133 / 43 / 32 / 128** |
| 57 | `dim_admission_type[admission_group]` = Urgent | Total Admissions / Hospital Mortality % / Median LOS | **38 / 13.2% / 7.856** |
| 58 | `dim_admission_type[admission_group]` = Elective | Hospital Deaths | **0** |
| 59 | `dim_care_unit[care_unit]` = Medical Intensive Care Unit (MICU) | ICU Stays / Total ICU Days | **29 / 116.7** |

### Data quality (pipeline state at build time; changes when the pipeline re-runs)

| # | Measure | Expected at build time |
|---|---|---|
| 60 | DQ Checks / Passed / Flagged | **17 / 12 / 5** |
| 61 | DQ Error Flags | **0** |
| 62 | DQ Pass Rate | **70.6%** (0.7059) |
| 63 | DQ Flagged Rows | **30,544** |
| 64 | Tables Monitored / Rejected Rows / Duplicate Key Rows | **14 / 0 / 0** |
| 65 | Last Successful Ingestion (UTC) | **2026-11-23 02:54:35** (`max(finished_at)` of runs with status `succeeded`) |
| 66 | Last Successful Table Load (UTC) | **2026-11-23 02:54:19** |
| 67 | Avg Column Null % / Columns Over 50% Null | **10.7%** (0.1068) / **12** |
| 68 | Benchmark Runs, Latest Median ms, Benchmark Speedup | **Volatile.** `meta.query_benchmarks` was being filled by another process during the build (0, then 6, then 16 rows). Check these against `query_benchmarks.csv` in your own export: Benchmark Runs = its row count. If the table is empty, `[Benchmark Status]` reads "No query benchmarks recorded yet ...". |
| 69 | KPI Reconciliation Mismatches | **0** |

If a value does not match, check in this order:

1. A slicer or page filter is still applied.
2. A relationship is missing or has the wrong direction (compare with R1 to R21).
3. A boolean column loaded as text (the `= TRUE ()` filters then return blank).
4. A source column was renamed or retyped in Power Query.

All four can be confirmed with the `EVALUATE` validation query.
