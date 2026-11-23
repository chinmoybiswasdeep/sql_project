# Dashboard A: report specification

This spec defines all five pages of the Power BI report: every visual's type, fields, measures, filters, sort order and formatting, plus a layout grid, the colour palette and accessibility rules. Measure names refer to `powerbi/measures/measures.dax`. Table and column names refer to `data_model.md`.

## Global settings

| Setting | Value |
|---|---|
| Canvas | 16:9, 1280 x 720 px. Page background `#F4F6F8`. Visuals on white cards (`#FFFFFF`) with 8 px rounded corners, a 1 px `#D9DEE3` border and no shadow. |
| Grid | 12 columns, each 96 px wide with a 8 px gutter and 24 px outer margins (24 + 12 x 96 + 11 x 8 + 24 = 1288; snap to 1280 and shave the last column to 88 px). Rows are 8 px. Turn on **View > Snap to grid**. |
| Theme | `documentation/theme.json` (View > Themes > Browse for themes). |
| Font | Segoe UI. Titles are 12 pt semibold. Card callouts are 28 pt. Labels are 10 pt. Never go below 9 pt. |
| Header band (every page) | 0 to 64 px: a text box with the page title (20 pt semibold, `#1F2933`) and a one-line subtitle (10 pt, `#52606D`). Page navigator buttons sit on the right (Insert > Buttons > Navigator > Page navigator). |
| Footer (every page) | 696 to 720 px: a 9 pt text box: "Source: MIMIC-IV Clinical Database Demo v2.2 (PhysioNet), de-identified and date-shifted. ICU-patient cohort. Small cells (<5) suppressed in labels." |
| Slicer sync | The five slicers on page 1 are synced (View > Sync slicers) to pages 1 to 4. They are visible on page 1 and hidden on pages 2 to 4, where a "Filters applied" text card shows the active selection. Page 5 is not synced: it is pipeline-level. |
| Tooltips | Every rate visual's tooltip shows the numerator, the denominator and the 95% CI, using the `(display)` measures where they exist. |
| Small cells | Any card or label that can show a count of 1 to 4 uses the `(display)` measure. Rates use `... % (display)`, which suppresses them when the numerator is a small cell or the denominator is under 5. |
| Number formats | Counts `#,0`. Rates `0.0%`. LOS `0.0` days (cards) or `0.00` (tables). Milliseconds `#,0.0`. |

### Field parameter (used on page 3)

Create it with **Modeling > New parameter > Fields** and name it `Outcome Group`. Add these fields in this order: age group, sex, admission group, insurance, race group. Power BI generates DAX equivalent to:

```dax
Outcome Group = {
    ("Age group",       NAMEOF ( 'dim_age_group'[age_group] ),             0),
    ("Sex",             NAMEOF ( 'dim_patient'[sex] ),                     1),
    ("Admission group", NAMEOF ( 'dim_admission_type'[admission_group] ),  2),
    ("Insurance",       NAMEOF ( 'dim_insurance'[insurance] ),             3),
    ("Race group",      NAMEOF ( 'dim_race_group'[race_group] ),           4)
}
```

Each of these columns filters both `fact_admissions` and `fact_readmissions`, so readmission and mortality measures stay correct whichever group is chosen.

---

## Page 1: Executive Overview

**Title:** Executive Overview
**Subtitle (required):** "MIMIC-IV demo v2.2: 100 patients, 275 admissions. **ICU-patient cohort:** every demo patient had at least one ICU stay, so rates are not hospital-wide."
**Footnote (required, above the footer):** "30-day readmission % = readmissions within 30 days of an eligible index discharge / eligible index admissions (255). In-hospital deaths, transfers to acute care, AMA discharges and overlapping stays are excluded from the denominator."

### Layout

```
 x:  24        232       440       648       856       1064     1256
    +---------------------------------------------------------------+ y=0
    | Executive Overview          subtitle (cohort caveat)  [nav]   |
    +---------------------------------------------------------------+ y=64
    |[Sex     ][Age group  ][Admission group][Insurance ][Race grp ]|  S1-S5
    +---------------------------------------------------------------+ y=120
    | K1      | K2      | K3      | K4      | K5      | K6          |
    | Patients| Admiss. | Med LOS | ICU %   | Readm % | Mortality % |
    +---------------------------------------------------------------+ y=248
    | V1 Admissions by admission    | V2 30-day readmission % by    |
    |    group (bar)                |    age group (column + CI)    |
    |                               |                               |
    +-------------------------------+---------------+---------------+ y=520
    | V3 Admissions by age group & sex (column)     | V4 Freshness  |
    |                                               |  & DQ status  |
    +-----------------------------------------------+---------------+ y=672
    | footnote (readmission definition)                             |
    +---------------------------------------------------------------+ y=696
    | footer                                                        |
    +---------------------------------------------------------------+ y=720
```

### Slicers

| ID | Field | Style | Notes |
|---|---|---|---|
| S1 | `dim_patient[sex]` | Tile (buttons), multi-select with Ctrl | Values F and M |
| S2 | `dim_age_group[age_group]` | Dropdown, "Select all" on | Sorted by `age_group_order` |
| S3 | `dim_admission_type[admission_group]` | Dropdown | Use this column, not `fact_admissions[admission_group]`, so readmissions filter too |
| S4 | `dim_insurance[insurance]` | Dropdown | |
| S5 | `dim_race_group[race_group]` | Dropdown | Add a tooltip that groups with fewer than 5 patients will show suppressed labels |

### KPI cards (Card (new), one callout each, 6 across)

| ID | Callout measure | Reference label (small text under the callout) | Format |
|---|---|---|---|
| K1 | `[Total Patients (display)]` | "Admissions per patient: " + `[Admissions per Patient]` | text |
| K2 | `[Total Admissions (display)]` | `[Emergency Admission %]` "emergency" | text |
| K3 | `[Median LOS (days)]` | "IQR " `[LOS P25 (days)]` "-" `[LOS P75 (days)]` | `0.0` "days" |
| K4 | `[ICU Admission %]` | `[ICU Admissions]` "of" `[Total Admissions]` | `0.0%` |
| K5 | `[Readmission 30d % (display)]` | `[Readmissions 30d (display)]` "/" `[Eligible Index Admissions]` "eligible"; CI in the tooltip: `[Readmission 30d % with CI (display)]` | text |
| K6 | `[Hospital Mortality % (display)]` | "95% CI " `[Hospital Mortality % CI Lower]` "-" `[Hospital Mortality % CI Upper]` | text |

Cards have no conditional colours: there is no target, so red or green would imply a judgement the data cannot support.

### Visuals

| ID | Visual | Fields / measures | Filters | Sort | Formatting |
|---|---|---|---|---|---|
| V1 | Clustered bar chart | Y axis: `dim_admission_type[admission_group]`. X axis: `[Total Admissions]`. Tooltips: `[Hospital Mortality %]`, `[Median LOS (days)]` | none | `[Total Admissions]` descending | Single colour `#005A8C`. Data labels on (`#,0`). X axis hidden. Title "Admissions by admission group". |
| V2 | Clustered column chart with error bars | X axis: `dim_age_group[age_group]`. Y axis: `[Readmission 30d %]`. Error bars (Analytics pane > Error bars): upper `[Readmission 30d % CI Upper]`, lower `[Readmission 30d % CI Lower]`. Tooltips: `[Readmission 30d % with CI (display)]`, `[Eligible Index Admissions]` | none | `age_group_order` ascending | Colour `#D97A00`. Y axis 0 to 50%. Constant line at the overall rate (Analytics > Constant line, value from `[Readmission 30d %]` via fx), dashed `#52606D`, labelled "Overall". Title "30-day readmission % by age group (95% Wilson CI)". |
| V3 | Clustered column chart | X axis: `dim_age_group[age_group]`. Legend: `dim_patient[sex]`. Y axis: `[Total Admissions]` | none | age order | Legend colours F `#B5528E`, M `#005A8C` (theme order). Data labels on. |
| V4 | Card (new), 3 rows | `[Last Successful Ingestion (UTC)]`, `[Freshness Status]`, `[DQ Status]` | none | n/a | 12 pt callouts. Clicking it navigates to page 5 (button action: Page navigation > SQL & Data Quality). |

---

## Page 2: Hospital Operations

**Subtitle:** "Throughput and resource use. ICU figures are utilisation (days consumed), not occupancy: no bed-capacity data exists."

### Layout

```
    +---------------------------------------------------------------+ y=0
    | Hospital Operations                       [filters applied]   |
    +---------------------------------------------------------------+ y=64
    | K1 Mean LOS | K2 P90 LOS | K3 Bed days | K4 ICU stays | K5 Unit changes/adm | K6 ICU days |
    +---------------------------------------------------------------+ y=168
    | V1 LOS distribution (column by LOS band)| V2 Admissions by    |
    |                                         | category (stacked)  |
    +-----------------------------------------+---------------------+ y=416
    | V3 ICU utilisation by first care unit   | V4 Transfer pattern |
    |    (bar: ICU days, tooltip stays/LOS)   |   matrix (from->to) |
    +-----------------------------------------+---------------------+ y=568
    | V5 Resource proxies by admission group (table)                |
    +---------------------------------------------------------------+ y=696
```

### KPI cards

| ID | Measure | Format |
|---|---|---|
| K1 | `[Mean LOS (days)]`, reference label `[Median LOS (days)]` "median" | `0.0` |
| K2 | `[LOS P90 (days)]` | `0.0` |
| K3 | `[Total Bed Days]` | `#,0` |
| K4 | `[ICU Stays]`, reference label `[ICU Stays per ICU Admission]` "per ICU admission" | `#,0` |
| K5 | `[Unit Changes per Admission]` | `0.00` |
| K6 | `[Total ICU Days]`, reference label `[Median ICU LOS (days)]` "median days per stay" | `#,0` |

### Visuals

| ID | Visual | Fields / measures | Filters | Sort | Formatting |
|---|---|---|---|---|---|
| V1 | Clustered column chart | X axis: `dim_los_band[los_band]`. Y axis: `[Total Admissions]`. Tooltips: `[Hospital Mortality %]`, `[ICU Admission %]` | none | `los_band_order` ascending | Colour `#005A8C`. Data labels on. Title "LOS distribution (admissions per LOS band)". Subtitle shows "Median " `[Median LOS (days)]` " days, P25 to P75 " `[LOS P25 (days)]` "-" `[LOS P75 (days)]` (subtitle fx with a text measure, or a text box). |
| V2 | Stacked bar chart | Y axis: `dim_admission_type[admission_group]`. Legend: `dim_admission_type[admission_type]`. X axis: `[Total Admissions]` | none | Total descending | Theme colours. Legend at the bottom. Data labels on the total only. |
| V3 | Clustered bar chart | Y axis: `dim_care_unit[care_unit]`. X axis: `[Total ICU Days]`. Tooltips: `[ICU Stays]`, `[ICU Patients]`, `[Median ICU LOS (days)]`, `[ICU Days Share]`, `[ICU Mortality %]` | Visual filter: `[ICU Stays]` is greater than 0 (keeps only units that appear as a first ICU unit) | `[Total ICU Days]` descending | Colour `#00876C`. Data labels `#,0.0`. Title "ICU days by first care unit". |
| V4 | Matrix (heatmap) | Rows: `fact_care_transfers[prev_unit_type]`. Columns: `fact_care_transfers[unit_type]`. Values: `[Unit Changes]` | Visual filter: `fact_care_transfers[is_unit_change]` = True; `prev_unit_type` is not blank | Rows by total descending | Cell elements > Background colour > gradient from `#FFFFFF` to `#005A8C`, font colour auto-contrast (white above the midpoint). Row and column subtotals on. Title "Care-unit transfers (from row to column)". Small cells: show "<5"-sized counts as they are, but do not publish this page externally without a review (see the implementation guide). |
| V5 | Table | `dim_admission_type[admission_group]`, `[Total Admissions]`, `[Median LOS (days)]`, `[Labs per Admission]`, `[Therapeutic Orders per Admission]`, `[Procedures per Admission]`, `[Unit Changes per Admission]`, `[ICU Admission %]` | none | `[Total Admissions]` descending | Data bars on `[Median LOS (days)]` (`#2F80B8`). Totals row on. Column headers wrap. Title "Resource-use proxies per admission". |

---

## Page 3: Patient Outcomes

**Subtitle:** "Readmission and mortality with 95% Wilson confidence intervals. Small groups give wide intervals, so read differences through the error bars."

### Layout

```
    +---------------------------------------------------------------+ y=0
    | Patient Outcomes                         [Group by: ( ) ( ) ] |  P1 field parameter slicer
    +---------------------------------------------------------------+ y=64
    | K1 Readm%+CI | K2 Unplanned% | K3 Mortality% | K4 ICU mort% | K5 Readm <24h | K6 Median days to readm |
    +---------------------------------------------------------------+ y=168
    | V1 30-day readmission % by group  | V2 Hospital mortality %   |
    |    (column + CI error bars)       |    by group (column + CI) |
    +-----------------------------------+---------------------------+ y=432
    | V3 Median LOS by group with IQR   | V4 Readmission exclusions |
    |    (column + P25/P75 error bars)  |    (bar) + V5 table       |
    +-----------------------------------+---------------------------+ y=672
    | footnote: CI method and small-cell rule                        |
    +---------------------------------------------------------------+ y=696
```

### Controls

| ID | Visual | Field | Formatting |
|---|---|---|---|
| P1 | Slicer, tile style, single select | `Outcome Group[Outcome Group]` (field parameter) | Default selection "Age group". Horizontal tiles. Selected tile `#005A8C` with white text. |

### KPI cards

| ID | Measure | Format |
|---|---|---|
| K1 | `[Readmission 30d % (display)]`, reference label `[Readmission 30d % with CI (display)]` | text |
| K2 | `[Unplanned Readmission 30d %]`, reference label "CI " `[Unplanned Readmission 30d % CI Lower]` "-" `[Unplanned Readmission 30d % CI Upper]` | `0.0%` |
| K3 | `[Hospital Mortality % (display)]`, reference label `[Hospital Deaths (display)]` "deaths" | text |
| K4 | `[ICU Mortality %]`, reference label "CI " `[ICU Mortality % CI Lower]` "-" `[ICU Mortality % CI Upper]` | `0.0%` |
| K5 | `[Readmissions within 24h (display)]`. The current value is under 5, so the card shows "<5". | text |
| K6 | `[Median Days to Readmission]` | `0.0` "days" |

### Visuals

| ID | Visual | Fields / measures | Filters | Sort | Formatting |
|---|---|---|---|---|---|
| V1 | Clustered column chart with error bars | X axis: `Outcome Group` (field parameter). Y axis: `[Readmission 30d %]`. Error bars: upper `[Readmission 30d % CI Upper]`, lower `[Readmission 30d % CI Lower]`. Tooltips: `[Readmission 30d % with CI (display)]`, `[Eligible Index Admissions]`, `[Readmissions 30d (display)]` | Visual filter: `[Eligible Index Admissions]` is greater than or equal to 5 (visual-level filters take a constant; keep it equal to `[Min Cell Size]`) | Axis ascending. Age group sorts by its sort column automatically. | Colour `#D97A00`. Error bars `#1F2933`, 1.5 px, with caps. Y axis 0% to 60%, gridlines `#E4E7EB`. Constant line at the overall `[Readmission 30d %]` (calculated with `REMOVEFILTERS` if you want it fixed). Title "30-day readmission % by" + the selected group (dynamic title: `"30-day readmission % by " & SELECTEDVALUE('Outcome Group'[Outcome Group])`). |
| V2 | Clustered column chart with error bars | X axis: `Outcome Group`. Y axis: `[Hospital Mortality %]`. Error bars: `[Hospital Mortality % CI Upper]` and `[Hospital Mortality % CI Lower]`. Tooltips: `[Hospital Mortality % (display)]`, `[Total Admissions]` | Same denominator filter, using `[Total Admissions]` >= 5 | Axis ascending | Colour `#6B5B95`. Y axis 0% to 40%. A label inside the visual says "Groups with 1 to 4 deaths show suppressed labels." Set data labels to use the `(display)` measure, or turn them off and rely on the tooltip. |
| V3 | Clustered column chart with error bars | X axis: `Outcome Group`. Y axis: `[Median LOS (days)]`. Error bars: upper `[LOS P75 (days)]`, lower `[LOS P25 (days)]` (this is the IQR, not a CI; say so in the title). Tooltips: `[Mean LOS (days)]`, `[LOS P90 (days)]`, `[Total Admissions]` | none | Axis ascending | Colour `#005A8C`. Title "Median LOS (bars) and interquartile range (whiskers)". |
| V4 | Clustered bar chart | Y axis: `fact_readmissions[exclusion_reason]`. X axis: `[Excluded Index Admissions]`. Tooltip: `[Excluded Index Admissions (display)]` | Visual filter: `exclusion_reason` is not blank | Value descending | Colour `#5F6B73`. Title "Index admissions excluded from the readmission denominator". Data labels: turn on Format > Data labels > Value > fx and pick `[Excluded Index Admissions (display)]`, or turn labels off, because some reasons may have fewer than 5. |
| V5 | Table (under V4) | `fact_readmissions[index_primary_diagnosis_category]`, `[Eligible Index Admissions]`, `[Readmissions 30d (display)]`, `[Readmission 30d % (display)]` | `[Eligible Index Admissions]` >= 5 | Eligible descending | Compact table, 9 pt. Title "Readmission by index primary diagnosis". |

**Footnote:** "Error bars: 95% Wilson score interval, z = 1.96. Counts of 1 to 4 are shown as '<5', and rates built on them are suppressed. The demo cohort is small (255 eligible index admissions), so most group differences are not statistically distinguishable."

---

## Page 4: Clinical Analytics

**Subtitle:** "Diagnoses (ICD-9/10 harmonised chapters), laboratory utilisation and abnormal results, and therapeutic medication orders (diluents, base solutions and flushes excluded)."

### Layout

```
    +---------------------------------------------------------------+ y=0
    | Clinical Analytics                    [Lab category slicer]   |
    +---------------------------------------------------------------+ y=64
    | K1 Dx/adm | K2 Labs/adm | K3 Abnormal % | K4 Ther. orders/adm | K5 Distinct drugs | K6 Mean Charlson |
    +---------------------------------------------------------------+ y=168
    | V1 Diagnosis categories      | V2 Primary diagnosis category  |
    |    (% admissions coded)      |    admissions + mortality      |
    +------------------------------+--------------------------------+ y=416
    | V3 Top 15 lab tests by       | V4 Abnormal % by test          |
    |    volume (bar)              |    (low/high stacked, >=500)   |
    +------------------------------+--------------------------------+ y=560
    | V5 Top 20 therapeutic medications (table)                     |
    +---------------------------------------------------------------+ y=696
```

### KPI cards

| ID | Measure | Format |
|---|---|---|
| K1 | `[Diagnoses per Admission]` | `0.0` |
| K2 | `[Labs per Admission]`, reference label `[Admission-Linked Lab Events]` "admission-linked results" | `#,0` |
| K3 | `[Abnormal Lab %]`, reference label `[Abnormal Lab Events]` "of" `[Lab Events]` | `0.0%` |
| K4 | `[Therapeutic Orders per Admission]` | `0.0` |
| K5 | `[Distinct Therapeutic Drugs]` | `#,0` |
| K6 | `[Mean Charlson Score]` | `0.00` |

### Controls

| ID | Visual | Field | Notes |
|---|---|---|---|
| S6 | Slicer, dropdown | `dim_lab_test[lab_category]` | Interactions: filters V3 and V4 only (Format > Edit interactions; set "None" on V1, V2, V5 and the KPIs other than K2 and K3). |

### Visuals

| ID | Visual | Fields / measures | Filters | Sort | Formatting |
|---|---|---|---|---|---|
| V1 | Clustered bar chart | Y axis: `dim_diagnosis[diagnosis_category]`. X axis: `[% Admissions with Diagnosis]`. Tooltips: `[Admissions with Diagnosis]`, `[Diagnoses]`, `[Distinct ICD Codes]` | Top N: 15 by `[Admissions with Diagnosis]` | X descending | Colour `#005A8C`. Labels `0%`. Title "Share of admissions with at least one diagnosis in each ICD chapter". |
| V2 | Line and clustered column chart | X axis: `fact_admissions[primary_diagnosis_category]`. Column: `[Total Admissions]`. Line: `[Hospital Mortality %]` (secondary axis, markers only, no line) | Top N: 10 by `[Total Admissions]` | Columns descending | Columns `#2F80B8`, markers `#B2182B`, 8 px. Tooltip `[Hospital Mortality % (display)]`. Title "Primary diagnosis category: admissions and in-hospital mortality". Mortality uses the primary diagnosis (one per admission), so there is no fan-out. |
| V3 | Clustered bar chart | Y axis: `dim_lab_test[lab_test_name]`. X axis: `[Lab Events]`. Tooltips: `dim_lab_test[fluid]`, `[Abnormal Lab %]`, `[Admission-Linked Lab Events]` | Top N: 15 by `[Lab Events]` | X descending | Colour `#00876C`. Labels `#,0`. Title "Most frequent lab tests (all results, inpatient and outpatient)". |
| V4 | Stacked bar chart | Y axis: `dim_lab_test[lab_test_name]`. X axis: `[Low Result %]`, `[High Result %]`. Tooltips: `[Abnormal Lab %]`, `[Lab Events]` | Visual filter: `[Lab Events]` >= 500 (same threshold as SQL query 17); Top N: 20 by `[Abnormal Lab %]` | `[Abnormal Lab %]` descending | Low `#2F80B8`, High `#C04A00`. Legend at the top. Title "Results outside the reference range (tests with 500+ results)". Caption: "An abnormal value is a measurement property, not a diagnosis." |
| V5 | Table | `dim_medication[drug_name]`, `[Admissions Exposed]`, `[% Admissions Exposed]`, `[Therapeutic Orders]`, `[Median Order Hours]`, `dim_medication[most_common_route]` | Top N: 20 by `[Admissions Exposed]`; `[Therapeutic Orders]` is not blank | `[Admissions Exposed]` descending | Data bars on `[% Admissions Exposed]` (`#005A8C`). 9 pt. Title "Top 20 therapeutic medications by admissions exposed (orders, not administrations)". |

---

## Page 5: SQL & Data Quality

**Subtitle:** "Pipeline health, freshness, validation results, source-column missingness and query benchmark timings. These figures describe the pipeline, not patients."

This page is **not** synced to the patient slicers. The reporting tables have no relationships.

### Layout

```
    +---------------------------------------------------------------+ y=0
    | SQL & Data Quality                                            |
    +---------------------------------------------------------------+ y=64
    | K1 Last ingestion | K2 Freshness | K3 DQ pass rate | K4 Error flags | K5 Rejected rows | K6 DAX=SQL |
    +---------------------------------------------------------------+ y=168
    | V1 Pipeline status by source table (table)                    |
    +-------------------------------+-------------------------------+ y=352
    | V2 Validation checks (table)  | V3 Missingness: top 15 columns|
    |                               |    by null % (bar)            |
    +-------------------------------+-------------------------------+ y=536
    | V4 Benchmarks: latest median  | V5 Benchmark speedup table    |
    |    ms baseline vs optimized   |    + K7 status text           |
    +-------------------------------+-------------------------------+ y=696
```

### KPI cards

| ID | Measure | Format / rule |
|---|---|---|
| K1 | `[Last Successful Ingestion (UTC)]`, reference label `[Hours Since Last Ingestion]` "h ago" | `yyyy-mm-dd hh:nn "UTC"` |
| K2 | `[Freshness Status]` | Text. Callout colour via fx rule: contains "Fresh" = good `#1A7F4B`; contains "Stale" = neutral `#A87400`; otherwise bad `#B2182B`. Always paired with the words, never colour alone. |
| K3 | `[DQ Pass Rate]`, reference label `[DQ Checks Passed]` "/" `[DQ Checks]` "checks pass" | `0.0%` |
| K4 | `[DQ Error Flags]`, reference label `[DQ Status]` | `#,0`. Callout colour bad when > 0, good when 0. |
| K5 | `[Rejected Rows]`, reference label `[Duplicate Key Rows]` "duplicate keys" | `#,0` |
| K6 | `[KPI Reconciliation Status]` | Text. Good colour when `[KPI Reconciliation Mismatches]` = 0. |

### Visuals

| ID | Visual | Fields / measures | Filters | Sort | Formatting |
|---|---|---|---|---|---|
| V1 | Table | `rpt_pipeline_status[table_name]`, `[latest_status]`, `[loaded_rows]`, `[rejected_rows]`, `[duplicate_key_rows]`, `[duration_seconds]`, `[last_successful_load_at]` (all columns set to "Don't summarize") | none | `loaded_rows` descending | Conditional formatting: `rejected_rows` and `duplicate_key_rows` font colour bad when > 0. Icons on `latest_status` (loaded or skipped_unchanged = check, failed = cross). `loaded_rows` `#,0`. Title "Ingestion status by source table". |
| V2 | Table | `rpt_data_quality_checks[check_name]`, `[table_name]`, `[severity]`, `[status]`, `[flagged_rows]`, `[description]` | none | `status` ascending (flag before pass), then `flagged_rows` descending | Icons on `status` (pass = green check, flag = amber triangle; with severity error = red cross), text kept beside the icon. `description` wraps. `flagged_rows` `#,0`. Title "Validation checks (latest run)" with a subtitle showing `[DQ Checks Flagged]` "flagged". |
| V3 | Clustered bar chart | Y axis: `rpt_missingness[column_name]`. Tooltip: `rpt_missingness[table_name]`, `[null_count]`, `[row_count]`. X axis: Average of `rpt_missingness[null_pct]` (implicit average is fine at column grain), or `[Avg Column Null %]` | Top N: 15 by null % ; `null_pct` > 0 | X descending | Colour `#5F6B73`. X axis 0 to 100. Labels `0.0`. Title "Most incomplete source columns (% null)". Note in the subtitle: "High missingness in optional source fields (for example deathtime) is expected." |
| V4 | Clustered bar chart | Y axis: `query_benchmarks[case_name]`. Legend: `query_benchmarks[variant]`. X axis: `[Latest Median ms]` | none | case_name ascending | X axis **logarithmic** (timings range from 0.01 ms to over 14,000 ms). Baseline `#5F6B73`, optimized `#00876C`. Labels `#,0.0`. If the table is empty the visual shows no data: put K7 above it. |
| V5 | Table | `query_benchmarks[case_name]`, `[Benchmark Speedup]`, `[Latest Median ms]` | none | Speedup descending | Speedup format `#,0.0"x"`, with data bars. |
| K7 | Card (text) | `[Benchmark Status]` | none | n/a | 10 pt. Shows "No query benchmarks recorded yet ..." when `meta.query_benchmarks` is empty. |

---

## Colour palette

| Role | Hex | Contrast on white | Use |
|---|---|---:|---|
| Primary / data 1 | `#005A8C` | 7.39:1 | Volume and LOS bars, table accent, selected slicer |
| Data 2 | `#D97A00` | 3.12:1 | Readmission series (graphics only, never body text) |
| Data 3 | `#00876C` | 4.49:1 | ICU and lab series, "optimized" benchmarks |
| Data 4 | `#B5528E` | 4.60:1 | Female series |
| Data 5 | `#2F80B8` | 4.29:1 | Secondary bars, "low" results |
| Data 6 | `#C04A00` | 4.98:1 | "High" results |
| Data 7 | `#6B5B95` | 5.91:1 | Mortality series |
| Data 8 | `#5F6B73` | 5.47:1 | Neutral or reference series |
| Good | `#1A7F4B` | 5.02:1 | Pipeline OK states only |
| Neutral | `#A87400` | 4.07:1 | Warnings and stale data |
| Bad | `#B2182B` | 6.87:1 | Errors, mortality marker |
| Text | `#1F2933` | 14.76:1 | Titles and callouts |
| Secondary text | `#52606D` | 6.46:1 | Labels and subtitles |
| Page background | `#F4F6F8` | n/a | Canvas behind the white cards |

The contrast ratios were computed with the WCAG 2.1 relative-luminance formula. Every data colour reaches at least the 3:1 minimum for graphical objects (WCAG 1.4.11). All text colours reach at least 4.5:1 (WCAG 1.4.3).

## Accessibility notes

1. **Colour is never the only signal.** Status cards say "Fresh", "Stale" or "Attention" in words. DQ tables use icons and the status text. Good and bad are used only on page 5 (pipeline states), never for clinical rates, which have no target.
2. **Colour-vision deficiency.** The palette avoids red-green pairs within the same visual: the readmission series is orange and the mortality series is purple. Check it with a CVD simulator, for example the "Colorblind" option in Windows Settings > Accessibility > Colour filters.
3. **Alt text.** Fill in Format > General > Alt text on every visual. Use a sentence with the takeaway built from a measure, for example `"30-day readmission rate by age group. Overall " & FORMAT([Readmission 30d %], "0.0%")`.
4. **Tab order.** Set View > Selection > Tab order: header, slicers, KPI cards left to right, then visuals top-left to bottom-right. Hide decorative shapes from tab order.
5. **Titles and labels.** Every visual has a descriptive title that states the measure and the denominator. Axis titles are on wherever the unit is not obvious (days, %, ms).
6. **Font size.** Minimum 9 pt (footers and dense tables), 10 pt for labels, 12 pt for titles.
7. **Keyboard and screen readers.** Use Power BI's built-in "Show as a table" (Alt+Shift+F11) for chart data. Do not put key numbers only inside images or shapes.
8. **Uncertainty.** Show CIs whenever groups are compared (page 3), and write the method in the footnote. Do not rank groups by point estimate alone.
9. **Small cells.** The `(display)` measures suppress counts of 1 to 4 and the rates built on them. Visual-level filters drop groups with denominators under 5 from the rate charts.
