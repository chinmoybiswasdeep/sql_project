# Limitations

This page separates what the project demonstrates from what it cannot claim.

## Dataset

1. **Demo scale.** The public MIMIC-IV demo v2.2 has 100 patients, 275 admissions, 140 ICU
   stays, 107,727 lab events and 668,862 chart events. That is enough to build and verify
   every pipeline component, but subgroup rates have wide intervals.
2. **Selected cohort.** All 100 demo patients had at least one ICU stay. ICU admission share
   (46.5%), mortality and readmission describe an ICU-patient cohort, not a hospital. Any
   statement in this repository about "the hospital" means "this demo cohort".
3. **Single centre.** MIMIC comes from one academic medical centre (BIDMC, Boston).
   Readmissions to other hospitals are invisible, so readmission is understated.
4. **De-identified dates.** Dates are shifted per patient into 2110–2210, so calendar trends,
   seasonality, day-of-week and cross-patient time comparisons are impossible.
   `anchor_year_group` is the only real-time anchor.
5. **Top-coded age.** Patients older than 89 have `anchor_age = 91`; derived ages are floors.
6. **No financial, staffing or capacity data.** Charges, costs, nurse staffing and bed
   counts are absent. The project never reports cost or occupancy; utilisation proxies
   are event counts.

## Method

7. **No censoring of follow-up.** There is no per-patient end-of-observation date, so late
   index discharges may be under-counted as non-readmissions.
8. **Clustering.** Frequent patients (up to 20 admissions) contribute correlated
   observations. Cluster-bootstrap intervals address this for headline rates; other tests are
   labelled optimistic.
9. **No severity adjustment.** Mortality and readmission comparisons are crude. No acuity
   score (for example SOFA or APACHE) is computed, so differences mainly reflect case mix.
10. **Coding-based measures.** Diagnoses and Charlson come from billing codes assigned at
    discharge and reflect documentation practice.
11. **Chapter-level diagnosis grouping.** It is coarse, chosen so it works across ICD-9 and
    ICD-10. A CCSR mapping (ICD-10 only) would be finer for post-2015 data.
12. **Drug names are free text.** Brand/generic variants are not merged (no RxNorm mapping),
    and orders are not administrations (eMAR is not used).
13. **Unit classification.** The care-unit seed covers units seen in MIMIC-IV. New names in
    other data map to "Unclassified" (a dbt warn test reports them). The "Discharge Lounge"
    also works as pre-procedure holding for planned surgical admissions (25 of 26 lounge-first
    admissions in the demo), so "lounge → ICU" means a post-operative ICU admission.
14. **Observation status.** "OBSERVATION ADMIT" encounters include multi-week stays,
    suggesting status labels do not reflect later conversions. The services table could
    investigate this further.

## Engineering verification status

| Component | Status |
|---|---|
| Ingestion, dbt build, 25 queries, validation, statistics, benchmarks, pytest | Executed and passing locally (macOS arm64, PostgreSQL 16.16, Python 3.12) |
| Streamlit dashboard | Executed locally; see PROGRESS.md for screenshot and smoke-test status |
| Power BI | Import-ready package (exports, DAX, M, specs). **No .pbix**: Power BI Desktop was not available; DAX/M were not executed |
| Docker Compose / Dockerfile | Written, **not executed** (Docker unavailable in the build environment) |
| GitHub Actions CI | Written, YAML validated, **not executed** (no remote repository yet) |
| BigQuery backend | Profile and dispatch macros only; **not executed** (needs credentialed access) |
| Full MIMIC-IV v3.1 | **Not run.** No credentialed access was used. Scalability is designed for, not demonstrated |
