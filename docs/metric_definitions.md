# Metric Definitions

Every KPI in the dashboards, reports and Power BI package uses these definitions. The
implementing model or query is named for each one, so a number can be traced to code.

## Volume

| Metric | Definition | Implemented in |
|---|---|---|
| Total patients | Distinct `subject_id` with at least one admission | `rpt_executive_kpis`, Q01 |
| Total admissions | Rows in `fact_admissions` (one per `hadm_id`), including observation-status encounters | `rpt_executive_kpis`, Q01 |
| Admissions per patient | Total admissions ÷ total patients; the median is also reported because the distribution is skewed | Q01 |

## Length of stay

| Metric | Definition | Notes |
|---|---|---|
| Hospital LOS | `dischtime − admittime` in fractional days | Includes in-hospital deaths; Q04 splits survivors and deaths |
| Median LOS | 50th percentile (`percentile_cont`) of hospital LOS | Headline statistic: LOS is right-skewed |
| Long stay | LOS ≥ 14 days | Q21 |
| ICU LOS | `outtime − intime` of the ICU stay in fractional days | Matches the source `los` to within 1 hour (checked at ingestion) |

## ICU

| Metric | Definition | Notes |
|---|---|---|
| ICU admission proportion | Admissions with ≥ 1 linked ICU stay ÷ all admissions | **Inflated in the demo:** every demo patient had an ICU stay |
| ICU utilisation | ICU days consumed (sum of ICU LOS), by unit | **Not occupancy.** Occupancy needs bed capacity, which MIMIC does not contain |
| ICU readmission (same hospitalization) | ICU stay with `icu_stay_seq > 1` within one `hadm_id` | Q11 |
| ICU mortality | Death between ICU `intime` and `outtime + 6h` | The 6h grace covers documentation lag (`var icu_death_grace_hours`) |

## Mortality

| Metric | Definition | Notes |
|---|---|---|
| In-hospital mortality | `hospital_expire_flag = 1` ÷ admissions | Crude, unadjusted for severity |

## 30-day readmission

**Denominator: eligible index discharges.** Every admission is a candidate index, and
admissions are excluded in this priority order:

| Exclusion | Rule | Rationale |
|---|---|---|
| `missing_dischtime` | `dischtime IS NULL` | Window cannot be computed |
| `died_in_hospital` | `hospital_expire_flag = 1` or discharge location `DIED` | No opportunity to be readmitted |
| `transfer_to_acute_care` | discharge location `ACUTE HOSPITAL` | Episode continues elsewhere (CMS practice) |
| `left_against_medical_advice` | discharge location `AGAINST ADVICE` | CMS hospital-wide measure practice |
| `overlapping_next_admission` | next admission starts before this discharge | Data anomaly, not a readmission |

**Numerator:** eligible index whose **next** admission of the same patient (by `admittime`,
tie-broken by `hadm_id`) starts within `[dischtime, dischtime + 30 days]` (inclusive).

| Variant | Additional rule |
|---|---|
| All-cause (headline) | Any admission type |
| Unplanned | Next admission type is not `ELECTIVE` or `SURGICAL SAME DAY ADMISSION` |
| Within 24 hours | Next admission starts < 24h after discharge (flag only; counted in all-cause) |

**What it is not.** "Unplanned" is **not** "potentially preventable". No validated
preventability algorithm (for example 3M PPR or the CMS planned-readmission algorithm with
procedure-level logic) is applied, so no readmission is labelled preventable.

**Known limitations.** Only returns to this hospital are observed, so the rate is
understated. There is no per-patient end-of-follow-up date, so the last discharges cannot be
right-censored. Repeat patients contribute correlated index discharges (see the cluster
bootstrap in the statistics report).

**Edge cases tested** (dbt unit test `readmission_edge_cases`, 16 synthetic admissions):
single admission, a 10-day return, an 8-hour return, an exactly-30-day boundary and a
30-days-plus-1-minute gap, in-hospital death, overlapping admissions, missing discharge
time, a planned (elective) return and an against-advice discharge.

**Independent verification:** `sql/validation/v01` (NOT EXISTS self-join instead of `LEAD`)
and `tests/test_readmission_independent_pandas.py` (pandas on the original CSVs) both
reproduce eligible discharges, numerator, unplanned count, gap days and rate exactly.

## Clinical

| Metric | Definition | Notes |
|---|---|---|
| Lab result volume | Count of `labevents` rows linked to an admission | Results, not orders: panels yield several results per draw |
| Abnormal (lab flag) | Laboratory's own `flag = 'abnormal'` | Available even for some non-numeric results |
| Below/above range | `valuenum` vs the row's own `ref_range_lower/upper` | Null when the value or either bound is missing; ranges vary by assay and era |
| Diagnosis category | Harmonised ICD-9/ICD-10 chapter of the code (seed `icd_chapters`) | Chapter level only; V/Z codes = "Health status & services contact" |
| Primary diagnosis | `seq_num = 1` | Assigned at discharge |
| Charlson comorbidity score | Quan (2005) ICD coding, Charlson (1987) weights, with mild/severe hierarchies | Coded at discharge, so it describes the stay, not only pre-admission risk |
| Therapeutic medication orders | Prescriptions excluding `drug_type = 'BASE'` (diluents, IV bags) and line flushes | Orders, not administrations |

## Operations

| Metric | Definition | Notes |
|---|---|---|
| Care-unit change | Movement whose care unit differs from the previous movement's unit | Bed moves inside one unit are excluded; ED to ward counts |
| Labs per inpatient day | Lab results ÷ max(LOS, 1 day) | Floor avoids inflating very short stays |
| Resource-use index | Cohort mean ÷ all-admission mean for LOS, ICU days, lab results, medication orders | Event counts, **not costs** |

## Uncertainty conventions

- Proportions: Wilson score 95% interval (in SQL and Python).
- Differences in proportions: Newcombe hybrid score interval, plus a patient-cluster bootstrap.
- Medians and correlations: patient-cluster percentile bootstrap (2,000 replicates, fixed seed).
- Small cells: in full-dataset mode, aggregates describing fewer than `HI_MIN_CELL_SIZE`
  (default 5) patients or admissions are suppressed in published outputs.
