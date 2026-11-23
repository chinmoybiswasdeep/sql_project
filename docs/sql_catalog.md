# SQL Query Catalog

_Generated 2026-11-23 03:35 UTC by `python -m analytics.reporting.sql_catalog` against `mimic-iv-demo-2.2` (demo mode). Results are pasted from that execution and nothing is hand-edited._

> **Read results with the cohort in mind.** The public demo has 100 patients, and every one had at least one ICU stay, so it is an ICU-patient cohort, not a hospital-wide population. Rates are descriptive of this sample; confidence intervals are wide. See [limitations](limitations.md).

All queries target the dbt marts (`marts.*`) in PostgreSQL. Each file has a structured header documenting the question, metric, grain, joins, denominator, exclusions and biases; this catalog is rendered from those headers.

| ID | Query | Module | Rows | ms |
|---|---|---|---:|---:|
| [Q01](#q01) | Patient and admission volume | A. Patient and admission analytics | 1 | 18 |
| [Q02](#q02) | Admission distribution by age group and sex | A. Patient and admission analytics | 13 | 1 |
| [Q03](#q03) | Admission distribution by admission category | A. Patient and admission analytics | 9 | 1 |
| [Q04](#q04) | Hospital length-of-stay distribution | A. Patient and admission analytics | 3 | 1 |
| [Q05](#q05) | Top diagnosis categories associated with admissions | A. Patient and admission analytics | 17 | 2 |
| [Q06](#q06) | 30-day all-cause readmission rate (with denominator funnel) | B. Readmission analytics | 8 | 1 |
| [Q07](#q07) | 30-day readmission rate by age group | B. Readmission analytics | 4 | 1 |
| [Q08](#q08) | 30-day readmission rate by primary diagnosis category | B. Readmission analytics | 10 | 1 |
| [Q09](#q09) | Time between discharge and next hospital admission | B. Readmission analytics | 8 | 1 |
| [Q10](#q10) | Patients with multiple hospitalizations and their admission patterns | B. Readmission analytics | 4 | 1 |
| [Q11](#q11) | ICU stays per hospital admission | C. ICU analytics | 4 | 1 |
| [Q12](#q12) | ICU length-of-stay distribution | C. ICU analytics | 5 | 1 |
| [Q13](#q13) | ICU utilization by care unit | C. ICU analytics | 9 | 1 |
| [Q14](#q14) | Frequency and duration of ICU care-unit transfers | C. ICU analytics | 15 | 1 |
| [Q15](#q15) | ICU mortality by patient group | C. ICU analytics | 16 | 1 |
| [Q16](#q16) | Most frequent laboratory tests | D. Clinical analytics | 20 | 19 |
| [Q17](#q17) | Abnormal laboratory result frequency by test type | D. Clinical analytics | 20 | 12 |
| [Q18](#q18) | Common diagnosis combinations (co-occurrence with lift) | D. Clinical analytics | 15 | 13 |
| [Q19](#q19) | Medication prescribing patterns | D. Clinical analytics | 20 | 9 |
| [Q20](#q20) | Hospital mortality by diagnosis category | D. Clinical analytics | 10 | 1 |
| [Q21](#q21) | Hospital length of stay by admission category | E. Operational analytics | 9 | 1 |
| [Q22](#q22) | Transfer frequency per admission | E. Operational analytics | 5 | 1 |
| [Q23](#q23) | Laboratory test volume per admission | E. Operational analytics | 8 | 1 |
| [Q24](#q24) | ICU utilization among patients with repeated admissions | E. Operational analytics | 6 | 1 |
| [Q25](#q25) | Cohort-level resource utilization (observable proxies) | E. Operational analytics | 4 | 1 |


## A. Patient and admission analytics

<a id="q01"></a>
### Q01: Patient and admission volume

**File:** [`sql/admissions/q01_patient_admission_volume.sql`](../sql/admissions/q01_patient_admission_volume.sql)  
**Execution:** 1 rows in 18 ms (includes client round-trip)

- **Business question:** How many patients and admissions does the warehouse cover, and how concentrated are admissions among patients?
- **Metric:** Distinct patients; admissions; admissions per patient (mean, median, max); share of patients and admissions from patients with 2+ admissions.
- **Output grain:** One summary row.
- **Join logic:** None. fact_admissions is already one row per hadm_id; a per-patient CTE aggregates it to subject_id first.
- **Denominator and exclusions:** All admissions and all patients with at least one admission. No exclusions.
- **Potential biases:** The demo is a 100-patient subset in which every patient had an ICU stay, so admission frequency is higher than a general hospital population.
- **Expected output:** total_patients, total_admissions, mean/median/max admissions per patient, repeat-patient shares.
- **SQL techniques:** CTE, aggregate FILTER, ordered-set aggregate (percentile_cont).

**Result (actual output):**

|   total_patients |   total_admissions |   mean_admissions_per_patient |   median_admissions_per_patient |   max_admissions_one_patient |   patients_single_admission |   pct_patients_with_repeat_admissions |   pct_admissions_from_repeat_patients |
|-----------------:|-------------------:|------------------------------:|--------------------------------:|-----------------------------:|----------------------------:|--------------------------------------:|--------------------------------------:|
|           100.00 |             275.00 |                          2.75 |                            1.00 |                        20.00 |                       52.00 |                                 48.00 |                                 81.10 |

**Interpretation:** 100 patients account for 275 admissions (2.75 per patient), but the median patient has only 1 admission. Use is highly concentrated: the 48% of patients with repeat admissions generate 81.1% of all admissions, and one patient has 20. Mean-based "per patient" figures are therefore driven by a small group of frequent patients.

<a id="q02"></a>
### Q02: Admission distribution by age group and sex

**File:** [`sql/admissions/q02_admissions_by_age_sex.sql`](../sql/admissions/q02_admissions_by_age_sex.sql)  
**Execution:** 13 rows in 1 ms (includes client round-trip)

- **Business question:** Which demographic segments generate the most admissions, and how does the mix compare with the patient mix?
- **Metric:** Admissions, distinct patients, share of all admissions, admissions per patient, per age group x sex with subtotals.
- **Output grain:** One row per (age_group, sex), plus ROLLUP subtotals per age group and a grand total.
- **Join logic:** None (age and sex are denormalised onto fact_admissions from int_admissions_enriched).
- **Denominator and exclusions:** All admissions. Age is age at admission, so one patient can appear in two age groups across admissions.
- **Potential biases:** Ages above 89 are top-coded by MIMIC (all in 80+). The demo's ICU-only sampling skews older.
- **Expected output:** age_group, sex, admissions, patients, pct_of_admissions, admissions_per_patient; subtotal rows labelled 'All'.
- **SQL techniques:** GROUP BY ROLLUP, GROUPING(), scalar subquery for the grand-total denominator.

**Result (actual output):**

| age_group   | sex   |   admissions |   patients |   pct_of_admissions |   admissions_per_patient |
|:------------|:------|-------------:|-----------:|--------------------:|-------------------------:|
| 18-44       | F     |           13 |          7 |                4.70 |                     1.86 |
| 18-44       | M     |           13 |          7 |                4.70 |                     1.86 |
| 18-44       | All   |           26 |         14 |                9.50 |                     1.86 |
| 45-64       | F     |           54 |         19 |               19.60 |                     2.84 |
| 45-64       | M     |           79 |         23 |               28.70 |                     3.43 |
| 45-64       | All   |          133 |         42 |               48.40 |                     3.17 |
| 65-79       | F     |           35 |         10 |               12.70 |                     3.50 |
| 65-79       | M     |           36 |         20 |               13.10 |                     1.80 |
| 65-79       | All   |           71 |         30 |               25.80 |                     2.37 |
| 80+         | F     |           31 |         10 |               11.30 |                     3.10 |
| 80+         | M     |           14 |          9 |                5.10 |                     1.56 |
| 80+         | All   |           45 |         19 |               16.40 |                     2.37 |
| All         | All   |          275 |        100 |              100.00 |                     2.75 |

**Interpretation:** The 45-64 band generates 48.4% of admissions; men in that band alone account for 28.7%. Admissions per patient are highest for women aged 65-79 (3.50) and men aged 45-64 (3.43), which means a few frequent patients in each segment. Patient counts across age bands add up to more than 100 because age is measured per admission and patients age across stays.

<a id="q03"></a>
### Q03: Admission distribution by admission category

**File:** [`sql/admissions/q03_admissions_by_category.sql`](../sql/admissions/q03_admissions_by_category.sql)  
**Execution:** 9 rows in 1 ms (includes client round-trip)

- **Business question:** What mix of emergency, urgent, elective and observation encounters does the hospital handle, and through which entry points?
- **Metric:** Admissions and share by admission group and type; share within group; % arriving with an ED visit; most common admission location per type.
- **Output grain:** One row per admission_type (with its admission_group).
- **Join logic:** None for counts; a ranked CTE finds the modal admission_location per type.
- **Denominator and exclusions:** All admissions. Observation encounters are kept but labelled, because they are not inpatient admissions in billing terms.
- **Potential biases:** admission_type reflects registration workflow, not clinical acuity.
- **Expected output:** admission_group, admission_type, admissions, pct_of_total, pct_within_group, pct_with_ed_visit, top_admission_location.
- **SQL techniques:** CTE, window functions (SUM OVER PARTITION, ROW_NUMBER), conditional aggregation.

**Result (actual output):**

| admission_group   | admission_type              |   admissions |   pct_of_total |   pct_within_group |   pct_with_ed_visit | top_admission_location   |
|:------------------|:----------------------------|-------------:|---------------:|-------------------:|--------------------:|:-------------------------|
| Emergency         | EW EMER.                    |          104 |          37.80 |              87.40 |               94.20 | EMERGENCY ROOM           |
| Emergency         | DIRECT EMER.                |           15 |           5.50 |              12.60 |               26.70 | PHYSICIAN REFERRAL       |
| Observation       | OBSERVATION ADMIT           |           45 |          16.40 |              51.70 |               91.10 | EMERGENCY ROOM           |
| Observation       | EU OBSERVATION              |           30 |          10.90 |              34.50 |              100.00 | EMERGENCY ROOM           |
| Observation       | DIRECT OBSERVATION          |            7 |           2.50 |               8.00 |               14.30 | PHYSICIAN REFERRAL       |
| Observation       | AMBULATORY OBSERVATION      |            5 |           1.80 |               5.70 |                0.00 | PROCEDURE SITE           |
| Urgent            | URGENT                      |           38 |          13.80 |             100.00 |               21.10 | TRANSFER FROM HOSPITAL   |
| Elective          | SURGICAL SAME DAY ADMISSION |           18 |           6.50 |              58.10 |                0.00 | PHYSICIAN REFERRAL       |
| Elective          | ELECTIVE                    |           13 |           4.70 |              41.90 |                0.00 | PHYSICIAN REFERRAL       |

**Interpretation:** Emergency admissions (EW EMER. + DIRECT EMER.) are 43.3% of encounters. Observation-status encounters are a large 31.6%, and most arrive through the emergency room. Elective and same-day surgical admissions come entirely through physician referral, with no ED contact.

<a id="q04"></a>
### Q04: Hospital length-of-stay distribution

**File:** [`sql/admissions/q04_length_of_stay_percentiles.sql`](../sql/admissions/q04_length_of_stay_percentiles.sql)  
**Execution:** 3 rows in 1 ms (includes client round-trip)

- **Business question:** What is a typical hospital stay, and how long is the tail of long stays?
- **Metric:** LOS in days: mean, standard deviation, P10, P25, median, P75, P90, P95, IQR; for all admissions, survivors only, and in-hospital deaths.
- **Output grain:** One row per cohort (all, survivors, died in hospital).
- **Join logic:** None.
- **Denominator and exclusions:** All admissions with a discharge time (no missing values in the demo). Deaths are split out because death truncates LOS.
- **Potential biases:** LOS is right-skewed, so the median is the headline statistic; the mean is shown for completeness. Observation encounters shorten the distribution.
- **Expected output:** cohort, admissions, mean_los, sd_los, p10..p95, iqr.
- **SQL techniques:** UNION ALL of cohorts via LATERAL VALUES, ordered-set aggregates.

**Result (actual output):**

| cohort           |   admissions |   mean_los_days |   sd_los_days |   p10 |   p25 |   median |   p75 |   p90 |   p95 |   iqr |
|:-----------------|-------------:|----------------:|--------------:|------:|------:|---------:|------:|------:|------:|------:|
| All admissions   |          275 |            6.88 |          6.73 |  0.97 |  2.69 |     4.85 |  8.77 | 14.50 | 22.94 |  6.08 |
| Discharged alive |          260 |            6.64 |          6.51 |  0.97 |  2.61 |     4.72 |  8.30 | 14.06 | 21.89 |  5.69 |
| Died in hospital |           15 |           10.92 |          9.19 |  2.92 |  4.82 |     8.57 | 13.80 | 24.17 | 30.19 |  8.98 |

**Interpretation:** The median hospital stay is 4.85 days (IQR 2.69-8.77), but the mean is 6.88 days. That gap shows a right-skewed distribution: 10% of stays exceed 14.5 days. Patients who died in hospital stayed longer (median 8.57 days, n = 15) than survivors (4.72 days).

<a id="q05"></a>
### Q05: Top diagnosis categories associated with admissions

**File:** [`sql/admissions/q05_top_diagnosis_categories.sql`](../sql/admissions/q05_top_diagnosis_categories.sql)  
**Execution:** 17 rows in 2 ms (includes client round-trip)

- **Business question:** Which clinical areas drive admissions, both as the principal reason and as any coded condition?
- **Metric:** Per harmonised ICD chapter: admissions where it is the primary (seq_num = 1) diagnosis, admissions with it anywhere, and each as a % of all admissions.
- **Output grain:** One row per diagnosis category.
- **Join logic:** fact_diagnoses aggregated to (category, hadm_id) with DISTINCT before counting, so an admission with several codes in one chapter counts once.
- **Denominator and exclusions:** All admissions (a few may have no coded diagnosis).
- **Potential biases:** Billing codes reflect documentation and reimbursement practice. ICD-9 and ICD-10 eras are pooled at chapter level, which hides code-level changes. 'Health status & services contact' (V/Z codes) captures history and status, not acute reasons.
- **Expected output:** diagnosis_category, primary_admissions, pct_primary, rank_primary, any_admissions, pct_any.
- **SQL techniques:** CTEs, COUNT DISTINCT, DENSE_RANK, FULL OUTER JOIN.

**Result (actual output):**

| diagnosis_category                 |   primary_admissions |   pct_primary |   rank_primary |   any_admissions |   pct_any |
|:-----------------------------------|---------------------:|--------------:|---------------:|-----------------:|----------:|
| Circulatory                        |                   67 |         24.40 |              1 |              223 |     81.10 |
| Injury & poisoning                 |                   35 |         12.70 |              2 |               96 |     34.90 |
| Digestive                          |                   33 |         12.00 |              3 |              122 |     44.40 |
| Neoplasms                          |                   24 |          8.70 |              4 |               75 |     27.30 |
| Infectious & parasitic             |                   22 |          8.00 |              5 |               89 |     32.40 |
| Symptoms, signs & ill-defined      |                   18 |          6.50 |              6 |              146 |     53.10 |
| Respiratory                        |                   18 |          6.50 |              6 |              116 |     42.20 |
| Mental & behavioral                |                   15 |          5.50 |              7 |              168 |     61.10 |
| Endocrine, nutritional & metabolic |                   13 |          4.70 |              8 |              220 |     80.00 |
| Genitourinary                      |                   10 |          3.60 |              9 |              126 |     45.80 |
| Nervous system & sense organs      |                    8 |          2.90 |             10 |              115 |     41.80 |
| Health status & services contact   |                    5 |          1.80 |             11 |              240 |     87.30 |
| Blood & immune                     |                    3 |          1.10 |             12 |              129 |     46.90 |
| Skin                               |                    3 |          1.10 |             12 |               37 |     13.50 |
| Musculoskeletal                    |                    1 |          0.40 |             13 |               87 |     31.60 |
| External causes                    |                    0 |          0.00 |             14 |               96 |     34.90 |
| Congenital                         |                    0 |          0.00 |             14 |                9 |      3.30 |

**Interpretation:** Circulatory disease is the leading principal diagnosis (24.4% of admissions), followed by injury/poisoning (12.7%) and digestive disease (12.0%). Chronic conditions are much more common as secondary codes: endocrine/metabolic codes appear on 80.0% of admissions but are the principal reason for only 4.7%. This is the comorbidity burden that the Charlson analysis (Q25) quantifies.


## B. Readmission analytics

<a id="q06"></a>
### Q06: 30-day all-cause readmission rate (with denominator funnel)

**File:** [`sql/readmissions/q06_readmission_rate_30d.sql`](../sql/readmissions/q06_readmission_rate_30d.sql)  
**Execution:** 8 rows in 1 ms (includes client round-trip)

- **Business question:** What share of eligible discharges return to this hospital within 30 days, and how is the denominator built?
- **Metric:** Readmission rate = eligible index discharges followed by any admission within 30 days / eligible index discharges. Also the unplanned rate (next admission not elective/same-day surgical) and returns within 24 hours.
- **Output grain:** One row per funnel step, ending with the rate rows.
- **Join logic:** None. fact_readmissions pairs each admission with the patient's next admission using LEAD in int_readmission_pairs.
- **Denominator and exclusions:** All admissions minus in-hospital deaths, transfers to another acute hospital, discharges against medical advice, overlapping next admissions and missing discharge times.
- **Potential biases:** Only returns to this hospital are visible, so the true rate is understated. There is no per-patient follow-up end date, so late discharges cannot be censored. "Unplanned" is not "preventable": no validated preventability algorithm is applied. The ICU-only demo cohort inflates the rate relative to a general population.
- **Expected output:** step, admissions, pct_of_all_admissions; final rows hold the numerator, rate and the unplanned and 24-hour counts.
- **SQL techniques:** CTE, conditional aggregation (FILTER), UNION ALL funnel, ordering by step number.

**Result (actual output):**

| step                                             |   admissions |   pct_of_all_admissions |   rate_pct_of_eligible |
|:-------------------------------------------------|-------------:|------------------------:|-----------------------:|
| All admissions                                   |          275 |                  100.00 |                 nan    |
| Excluded: died_in_hospital                       |          -15 |                    5.50 |                 nan    |
| Excluded: left_against_medical_advice            |           -4 |                    1.50 |                 nan    |
| Excluded: transfer_to_acute_care                 |           -1 |                    0.40 |                 nan    |
| Eligible index discharges (denominator)          |          255 |                   92.70 |                 nan    |
| Readmitted within 30 days, all-cause (numerator) |           52 |                   18.90 |                  20.40 |
| of which unplanned                               |           48 |                   17.50 |                  18.80 |
| of which within 24 hours                         |            4 |                    1.50 |                   1.60 |

**Interpretation:** Of 275 admissions, 20 are excluded (15 in-hospital deaths, 4 against-advice discharges, 1 transfer to another acute hospital). That leaves 255 eligible index discharges, of which 52 were followed by an admission within 30 days: a 20.4% all-cause rate. 48 of those (18.8%) were unplanned and 4 occurred within 24 hours. This is a selected ICU-patient sample and only same-hospital returns are visible, so this figure must not be compared with national benchmarks.

<a id="q07"></a>
### Q07: 30-day readmission rate by age group

**File:** [`sql/readmissions/q07_readmission_by_age_group.sql`](../sql/readmissions/q07_readmission_by_age_group.sql)  
**Execution:** 4 rows in 1 ms (includes client round-trip)

- **Business question:** Do readmission rates differ across age groups, and are the differences larger than sampling noise?
- **Metric:** Per age group (at index admission): eligible discharges, readmissions, rate, and Wilson score 95% confidence interval.
- **Output grain:** One row per age group.
- **Join logic:** None (age_group is carried onto fact_readmissions from the index admission).
- **Denominator and exclusions:** Eligible index discharges only (see Query 06).
- **Potential biases:** Small cells give wide intervals, and overlapping intervals mean the data cannot distinguish the groups. Patients with many admissions contribute several index discharges, so observations are not independent and the CIs are optimistic.
- **Expected output:** age_group, eligible_discharges, readmissions, rate_pct, ci95_low_pct, ci95_high_pct.
- **SQL techniques:** CTE, FILTER, Wilson score interval computed in SQL.

**Result (actual output):**

| age_group   |   eligible_discharges |   readmissions |   rate_pct |   ci95_low_pct |   ci95_high_pct |
|:------------|----------------------:|---------------:|-----------:|---------------:|----------------:|
| 18-44       |                    26 |              6 |      23.10 |          11.00 |           42.10 |
| 45-64       |                   123 |             27 |      22.00 |          15.50 |           30.10 |
| 65-79       |                    64 |             14 |      21.90 |          13.50 |           33.40 |
| 80+         |                    42 |              5 |      11.90 |           5.20 |           25.00 |

**Interpretation:** Rates are similar for ages 18-79 (21.9-23.1%) and lower for 80+ (11.9%, 95% CI 5.2-25.0%). Every interval overlaps the others, so the demo cannot show a real age difference. The lower 80+ rate could also reflect competing mortality or discharge to hospice/facilities, which this metric does not adjust for.

<a id="q08"></a>
### Q08: 30-day readmission rate by primary diagnosis category

**File:** [`sql/readmissions/q08_readmission_by_diagnosis.sql`](../sql/readmissions/q08_readmission_by_diagnosis.sql)  
**Execution:** 10 rows in 1 ms (includes client round-trip)

- **Business question:** Which clinical areas (by principal diagnosis of the index stay) have the highest readmission rates?
- **Metric:** Per primary diagnosis category of the index admission: eligible discharges, readmissions, rate, Wilson 95% CI, rank. Only categories with at least 10 eligible discharges are shown.
- **Output grain:** One row per diagnosis category passing the volume threshold.
- **Join logic:** None (index_primary_diagnosis_category is carried onto fact_readmissions).
- **Denominator and exclusions:** Eligible index discharges; categories below 10 discharges are suppressed by HAVING to avoid unstable rates.
- **Potential biases:** Chapter-level categories are coarse. Small samples give wide CIs, so a high rank does not by itself show a real difference. Repeat patients cluster within categories.
- **Expected output:** diagnosis_category, eligible_discharges, readmissions, rate_pct, ci95_low_pct, ci95_high_pct, rate_rank.
- **SQL techniques:** CTE, GROUP BY with HAVING, RANK, Wilson interval.

**Result (actual output):**

| diagnosis_category                 |   eligible_discharges |   readmissions |   rate_pct |   ci95_low_pct |   ci95_high_pct |   rate_rank |
|:-----------------------------------|----------------------:|---------------:|-----------:|---------------:|----------------:|------------:|
| Respiratory                        |                    13 |              5 |      38.50 |          17.70 |           64.50 |           1 |
| Mental & behavioral                |                    13 |              4 |      30.80 |          12.70 |           57.60 |           2 |
| Digestive                          |                    29 |              8 |      27.60 |          14.70 |           45.70 |           3 |
| Neoplasms                          |                    23 |              6 |      26.10 |          12.50 |           46.50 |           4 |
| Genitourinary                      |                    10 |              2 |      20.00 |           5.70 |           51.00 |           5 |
| Endocrine, nutritional & metabolic |                    12 |              2 |      16.70 |           4.70 |           44.80 |           6 |
| Injury & poisoning                 |                    32 |              5 |      15.60 |           6.90 |           31.80 |           7 |
| Infectious & parasitic             |                    21 |              3 |      14.30 |           5.00 |           34.60 |           8 |
| Circulatory                        |                    64 |              8 |      12.50 |           6.50 |           22.80 |           9 |
| Symptoms, signs & ill-defined      |                    18 |              2 |      11.10 |           3.10 |           32.80 |          10 |

**Interpretation:** Respiratory (38.5%, n = 13) and mental/behavioral (30.8%, n = 13) index stays rank highest, and circulatory ranks lowest (12.5%, n = 64). With 10-64 discharges per category the intervals are wide and largely overlapping. Treat this as a hypothesis-generating ranking to re-test on the full dataset, not as a finding.

<a id="q09"></a>
### Q09: Time between discharge and next hospital admission

**File:** [`sql/readmissions/q09_time_to_next_admission.sql`](../sql/readmissions/q09_time_to_next_admission.sql)  
**Execution:** 8 rows in 1 ms (includes client round-trip)

- **Business question:** When patients come back, how soon do they return? Is the 30-day window capturing most early returns?
- **Metric:** Distribution of days from discharge to the next admission, in clinically meaningful buckets, with cumulative share; plus percentiles.
- **Output grain:** One row per time bucket.
- **Join logic:** None. days_to_next_admission comes from the LEAD-based pairing in int_readmission_pairs.
- **Denominator and exclusions:** Admissions discharged alive that have a later admission (any eligibility status except in-hospital death). Last-observed admissions have no next admission and are excluded.
- **Potential biases:** Returns to other hospitals are invisible. Long gaps are truncated by the end of each patient's observable history.
- **Expected output:** gap_bucket, next_admissions, pct, cumulative_pct, plus median and p25/p75 repeated on each row for reference.
- **SQL techniques:** CASE bucketing, window SUM for the cumulative distribution, ordered-set aggregates in a CTE.

**Result (actual output):**

| gap_bucket   |   next_admissions |   pct |   cumulative_pct |   overall_p25_days |   overall_median_days |   overall_p75_days |
|:-------------|------------------:|------:|-----------------:|-------------------:|----------------------:|-------------------:|
| <1 day       |                 4 |  2.30 |             2.30 |              20.50 |                 89.40 |             327.60 |
| 1-7 days     |                18 | 10.30 |            12.60 |              20.50 |                 89.40 |             327.60 |
| 8-14 days    |                14 |  8.00 |            20.60 |              20.50 |                 89.40 |             327.60 |
| 15-30 days   |                17 |  9.70 |            30.30 |              20.50 |                 89.40 |             327.60 |
| 31-90 days   |                35 | 20.00 |            50.30 |              20.50 |                 89.40 |             327.60 |
| 91-180 days  |                26 | 14.90 |            65.10 |              20.50 |                 89.40 |             327.60 |
| 181-365 days |                23 | 13.10 |            78.30 |              20.50 |                 89.40 |             327.60 |
| >365 days    |                38 | 21.70 |           100.00 |              20.50 |                 89.40 |             327.60 |

**Interpretation:** Among returns after a live discharge, 30.3% happen within 30 days and half within about 3 months (median 89 days). A further 20% return in days 31-90. That suggests a 90-day view would capture substantially more early returns than the standard 30-day window.

<a id="q10"></a>
### Q10: Patients with multiple hospitalizations and their admission patterns

**File:** [`sql/readmissions/q10_repeat_hospitalization_patterns.sql`](../sql/readmissions/q10_repeat_hospitalization_patterns.sql)  
**Execution:** 4 rows in 1 ms (includes client round-trip)

- **Business question:** How concentrated is hospital use among frequent patients, and how do their patterns differ (spacing, readmissions, ICU use)?
- **Metric:** Per admission-frequency band: patients, admissions, share of all admissions, median gap between consecutive admissions, 30-day readmissions per patient, % of admissions with ICU care.
- **Output grain:** One row per admission-frequency band (1, 2-3, 4-6, 7+ admissions). Aggregated deliberately, so no patient-level rows are exposed.
- **Join logic:** Per-patient CTE built from fact_admissions using LAG to measure the gap between consecutive admissions; then grouped to bands.
- **Denominator and exclusions:** All patients with at least one admission.
- **Potential biases:** Frequency is measured within the observed (date-shifted) history only. Bands with few patients are unstable.
- **Expected output:** frequency_band, patients, admissions, pct_of_admissions, median_gap_days, readmissions_30d_per_patient, pct_admissions_with_icu.
- **SQL techniques:** LAG window function, multi-level CTE aggregation, percentile_cont, window share of total.

**Result (actual output):**

| frequency_band   |   patients |   admissions |   pct_of_admissions |   median_of_patient_median_gap_days |   readmissions_30d_per_patient |   pct_admissions_with_icu |
|:-----------------|-----------:|-------------:|--------------------:|------------------------------------:|-------------------------------:|--------------------------:|
| 1                |         52 |        52.00 |               18.90 |                              nan    |                           0.00 |                    100.00 |
| 2-3              |         29 |        67.00 |               24.40 |                              206.00 |                           0.48 |                     59.70 |
| 4-6              |          7 |        36.00 |               13.10 |                               35.10 |                           1.00 |                     27.80 |
| 7+               |         12 |       120.00 |               43.60 |                              106.80 |                           2.58 |                     21.70 |

**Interpretation:** 12 patients with 7+ admissions generate 43.6% of all admissions and average 2.58 30-day readmissions each. The frequent-admission group is where readmission activity concentrates. Their admissions involve ICU care less often (21.7%) than single-admission patients' (100%, a sampling artefact: every demo patient had an ICU stay).


## C. ICU analytics

<a id="q11"></a>
### Q11: ICU stays per hospital admission

**File:** [`sql/icu/q11_icu_stays_per_admission.sql`](../sql/icu/q11_icu_stays_per_admission.sql)  
**Execution:** 4 rows in 1 ms (includes client round-trip)

- **Business question:** How often does a hospitalization involve ICU care, and how often do patients return to the ICU within the same hospitalization?
- **Metric:** Admissions by number of ICU stays (0, 1, 2, 3+); among ICU admissions, the share with a repeat ICU stay and the median hours between ICU discharge and readmission to ICU.
- **Output grain:** One row per ICU-stay-count bucket, with ICU-bounce-back statistics repeated for reference.
- **Join logic:** fact_admissions (n_icu_stays pre-aggregated per hadm_id) and fact_icu_stays (hours_since_prev_icu_discharge from LAG within hadm_id).
- **Denominator and exclusions:** All admissions for the distribution; ICU admissions for the bounce-back rate.
- **Potential biases:** Every demo patient had at least one ICU stay at some point, so the ICU proportion is far above a general-hospital rate. Measures ICU episodes, not ICU occupancy.
- **Expected output:** icu_stays_bucket, admissions, pct_of_admissions, pct_icu_admissions_with_repeat_icu_stay, median_hours_between_icu_stays.
- **SQL techniques:** CTEs, CASE bucketing, window share, FILTER, percentile_cont.

**Result (actual output):**

| icu_stays_bucket   |   admissions |   pct_of_admissions |   pct_icu_admissions_with_repeat_icu_stay |   median_hours_between_icu_stays |
|:-------------------|-------------:|--------------------:|------------------------------------------:|---------------------------------:|
| 0                  |          147 |               53.50 |                                      7.00 |                            38.00 |
| 1                  |          119 |               43.30 |                                      7.00 |                            38.00 |
| 2                  |            7 |                2.50 |                                      7.00 |                            38.00 |
| 3+                 |            2 |                0.70 |                                      7.00 |                            38.00 |

**Interpretation:** 46.5% of admissions include ICU care: 43.3% have one ICU stay and 3.2% have two or more. 7.0% of ICU admissions involve a return to ICU within the same hospitalization, with a median of 38 hours between ICU discharge and readmission to ICU. The ICU share reflects the demo's ICU-only sampling, not hospital-wide practice.

<a id="q12"></a>
### Q12: ICU length-of-stay distribution

**File:** [`sql/icu/q12_icu_los_distribution.sql`](../sql/icu/q12_icu_los_distribution.sql)  
**Execution:** 5 rows in 1 ms (includes client round-trip)

- **Business question:** How long do ICU stays last, and what share of ICU days comes from long stays?
- **Metric:** ICU LOS bands: stays, % of stays, cumulative % of stays, ICU days, % of all ICU days; and overall percentiles.
- **Output grain:** One row per ICU LOS band.
- **Join logic:** None.
- **Denominator and exclusions:** All ICU stays (icustays). Stays that start before the formal admission time are kept (flagged in fact_icu_stays).
- **Potential biases:** ICU LOS ends at ICU discharge or death. A few long stays dominate the total of ICU days.
- **Expected output:** icu_los_band, stays, pct_stays, cumulative_pct_stays, icu_days, pct_icu_days, plus overall median/p90.
- **SQL techniques:** CTE, window running SUM, share of total, ordered-set aggregates.

**Result (actual output):**

| icu_los_band   |   stays |   pct_stays |   cumulative_pct_stays |   icu_days |   pct_icu_days |   overall_median_icu_days |   overall_p90_icu_days |
|:---------------|--------:|------------:|-----------------------:|-----------:|---------------:|--------------------------:|-----------------------:|
| <1 day         |      23 |       16.40 |                  16.40 |      14.60 |           2.80 |                      2.16 |                   8.86 |
| 1-2 days       |      62 |       44.30 |                  60.70 |     106.60 |          20.70 |                      2.16 |                   8.86 |
| 3-6 days       |      35 |       25.00 |                  85.70 |     159.30 |          30.90 |                      2.16 |                   8.86 |
| 7-13 days      |      15 |       10.70 |                  96.40 |     150.10 |          29.10 |                      2.16 |                   8.86 |
| 14+ days       |       5 |        3.60 |                 100.00 |      84.40 |          16.40 |                      2.16 |                   8.86 |

**Interpretation:** The median ICU stay is 2.16 days and 60.7% of stays end within 3 days. The long tail dominates resource use: the 14.3% of stays lasting 7+ days account for 45.5% of all ICU days.

<a id="q13"></a>
### Q13: ICU utilization by care unit

**File:** [`sql/icu/q13_icu_utilization_by_unit.sql`](../sql/icu/q13_icu_utilization_by_unit.sql)  
**Execution:** 9 rows in 1 ms (includes client round-trip)

- **Business question:** Which ICUs absorb the most ICU stays and ICU days, and how do their stay lengths compare?
- **Metric:** Per first ICU care unit: stays, distinct patients, total ICU days, share of all ICU days, mean and median ICU LOS, % of stays that moved to a different ICU unit.
- **Output grain:** One row per first ICU care unit.
- **Join logic:** None.
- **Denominator and exclusions:** All ICU stays, attributed to their first care unit.
- **Potential biases:** This is utilisation (ICU days consumed), NOT occupancy: no bed-capacity data exists, so no occupancy % is computed. Attribution to the first unit ignores later moves.
- **Expected output:** first_careunit, stays, patients, icu_days, pct_icu_days, mean_los_days, median_los_days, pct_changed_unit, utilization_rank.
- **SQL techniques:** Aggregation, window share, DENSE_RANK, FILTER, percentile_cont.

**Result (actual output):**

| first_careunit                                   |   stays |   patients |   icu_days |   pct_icu_days |   mean_los_days |   median_los_days |   pct_changed_unit |   utilization_rank |
|:-------------------------------------------------|--------:|-----------:|-----------:|---------------:|----------------:|------------------:|-------------------:|-------------------:|
| Medical Intensive Care Unit (MICU)               |      29 |         23 |     116.70 |          22.70 |            4.02 |              2.86 |               6.90 |                  1 |
| Medical/Surgical Intensive Care Unit (MICU/SICU) |      23 |         16 |      97.70 |          19.00 |            4.25 |              2.89 |               0.00 |                  2 |
| Surgical Intensive Care Unit (SICU)              |      29 |         26 |      81.90 |          15.90 |            2.83 |              1.79 |               6.90 |                  3 |
| Coronary Care Unit (CCU)                         |      13 |         12 |      70.60 |          13.70 |            5.43 |              4.95 |              15.40 |                  4 |
| Trauma SICU (TSICU)                              |      16 |         14 |      65.10 |          12.60 |            4.07 |              2.04 |               6.30 |                  5 |
| Cardiac Vascular Intensive Care Unit (CVICU)     |      25 |         25 |      55.50 |          10.80 |            2.22 |              2.00 |               8.00 |                  6 |
| Neuro Surgical Intensive Care Unit (Neuro SICU)  |       3 |          3 |      19.00 |           3.70 |            6.33 |              5.45 |              66.70 |                  7 |
| Neuro Stepdown                                   |       1 |          1 |       7.70 |           1.50 |            7.70 |              7.70 |               0.00 |                  8 |
| Neuro Intermediate                               |       1 |          1 |       0.90 |           0.20 |            0.87 |              0.87 |               0.00 |                  9 |

**Interpretation:** The MICU consumes the most ICU days (22.7%), followed by the combined MICU/SICU (19.0%) and SICU (15.9%). The CCU has the longest median stay (4.95 days) and the CVICU the shortest (2.00 days), consistent with a planned post-cardiac-surgery pathway. These are utilisation shares, not occupancy rates: bed capacity is not in MIMIC.

<a id="q14"></a>
### Q14: Frequency and duration of ICU care-unit transfers

**File:** [`sql/icu/q14_icu_transfer_patterns.sql`](../sql/icu/q14_icu_transfer_patterns.sql)  
**Execution:** 15 rows in 1 ms (includes client round-trip)

- **Business question:** How do patients flow into, out of and between ICUs, and how long do they stay in the unit they leave?
- **Metric:** Unit-type transitions that involve an ICU (ward to ICU, ICU to ward, ICU to ICU, ED to ICU, ...): count, share, distinct admissions, and median hours in the origin unit before the move.
- **Output grain:** One row per (from_unit_type, to_unit_type) transition involving an ICU.
- **Join logic:** fact_care_transfers with LAG over movements within each hadm_id to recover the origin unit and its duration.
- **Denominator and exclusions:** Unit changes only (is_unit_change); bed moves within the same unit are excluded. Admission-linked movements only.
- **Potential biases:** Unit types come from a reference seed; Unclassified units would be pooled. Short origin durations can reflect documentation timing. 'Discharge lounge -> ICU' is NOT a reversed discharge: in this data 25 of 26 admissions whose first unit is the Discharge Lounge are elective/same-day surgical admissions, so the lounge works as pre-procedure holding and the move is a planned post-operative ICU admission.
- **Expected output:** from_unit_type, to_unit_type, transitions, pct_of_icu_transitions, admissions, median_hours_in_origin_unit.
- **SQL techniques:** LAG window function, CTE, FILTER, window share, percentile_cont.

**Result (actual output):**

| from_unit_type           | to_unit_type             |   transitions |   pct_of_icu_transitions |   admissions |   median_hours_in_origin_unit |
|:-------------------------|:-------------------------|--------------:|-------------------------:|-------------:|------------------------------:|
| ICU                      | Medical ward             |            56 |                    21.80 |           52 |                         48.60 |
| Emergency                | ICU                      |            55 |                    21.40 |           55 |                          4.30 |
| ICU                      | Surgical ward            |            30 |                    11.70 |           29 |                         34.70 |
| ICU                      | Mixed med-surg ward      |            22 |                     8.60 |           22 |                         49.00 |
| Medical ward             | ICU                      |            21 |                     8.20 |           19 |                         45.60 |
| Discharge lounge         | ICU                      |            18 |                     7.00 |           18 |                          7.30 |
| Perioperative            | ICU                      |            14 |                     5.40 |           14 |                          2.70 |
| ICU                      | ICU                      |            11 |                     4.30 |           10 |                         27.80 |
| Surgical ward            | ICU                      |             7 |                     2.70 |            7 |                         40.80 |
| Mixed med-surg ward      | ICU                      |             7 |                     2.70 |            7 |                         19.30 |
| ICU                      | Intermediate / step-down |             6 |                     2.30 |            6 |                         61.30 |
| ICU                      | Perioperative            |             4 |                     1.60 |            4 |                         18.60 |
| Observation              | ICU                      |             3 |                     1.20 |            3 |                          0.40 |
| Intermediate / step-down | ICU                      |             2 |                     0.80 |            2 |                         31.70 |
| ICU                      | Discharge lounge         |             1 |                     0.40 |            1 |                          0.60 |

**Interpretation:** The most frequent ICU-related flows are ICU to medical ward (56) and ED to ICU (55). Patients spend a median 4.3 hours in the ED before moving to ICU and about 35-49 hours in ICU before stepping down to a ward. "Discharge lounge to ICU" (18) is a pre-procedure holding pattern for planned surgical admissions, not a discharge reversal, and is documented as such.

<a id="q15"></a>
### Q15: ICU mortality by patient group

**File:** [`sql/icu/q15_icu_mortality_by_group.sql`](../sql/icu/q15_icu_mortality_by_group.sql)  
**Execution:** 16 rows in 1 ms (includes client round-trip)

- **Business question:** How does mortality during ICU care vary by age group, sex and ICU type?
- **Metric:** ICU stays, deaths during the ICU stay (death within intime and outtime + 6h), ICU mortality %, and hospital mortality % for the same stays; with Wilson 95% CI for ICU mortality.
- **Output grain:** One row per grouping set: age group, sex, first ICU unit type... plus an overall row (GROUPING SETS).
- **Join logic:** None (demographics and death flags are carried onto fact_icu_stays).
- **Denominator and exclusions:** All ICU stays. A patient with several stays contributes several denominators.
- **Potential biases:** Unadjusted for severity (no illness-severity score is computed), so differences reflect case-mix. Very small groups.
- **Expected output:** dimension, dimension_value, icu_stays, icu_deaths, icu_mortality_pct, ci95_low_pct, ci95_high_pct, hospital_mortality_pct.
- **SQL techniques:** GROUPING SETS, GROUPING() labelling, FILTER, Wilson interval.

**Result (actual output):**

| dimension      | dimension_value                                  |   icu_stays |   icu_deaths |   icu_mortality_pct |   ci95_low_pct |   ci95_high_pct |   hospital_mortality_pct |
|:---------------|:-------------------------------------------------|------------:|-------------:|--------------------:|---------------:|----------------:|-------------------------:|
| Overall        | All ICU stays                                    |         140 |           12 |                8.60 |           5.00 |           14.40 |                    14.30 |
| Age group      | 45-64                                            |          60 |            4 |                6.70 |           2.60 |           15.90 |                    10.00 |
| Age group      | 65-79                                            |          37 |            5 |               13.50 |           5.90 |           28.00 |                    24.30 |
| Age group      | 80+                                              |          27 |            3 |               11.10 |           3.90 |           28.10 |                    18.50 |
| Age group      | 18-44                                            |          16 |            0 |                0.00 |           0.00 |           19.40 |                     0.00 |
| Sex            | M                                                |          77 |            9 |               11.70 |           6.30 |           20.70 |                    20.80 |
| Sex            | F                                                |          63 |            3 |                4.80 |           1.60 |           13.10 |                     6.30 |
| First ICU unit | Medical Intensive Care Unit (MICU)               |          29 |            5 |               17.20 |           7.60 |           34.50 |                    20.70 |
| First ICU unit | Surgical Intensive Care Unit (SICU)              |          29 |            2 |                6.90 |           1.90 |           22.00 |                    10.30 |
| First ICU unit | Cardiac Vascular Intensive Care Unit (CVICU)     |          25 |            0 |                0.00 |           0.00 |           13.30 |                     0.00 |
| First ICU unit | Medical/Surgical Intensive Care Unit (MICU/SICU) |          23 |            1 |                4.30 |           0.80 |           21.00 |                    13.00 |
| First ICU unit | Trauma SICU (TSICU)                              |          16 |            0 |                0.00 |           0.00 |           19.40 |                    12.50 |
| First ICU unit | Coronary Care Unit (CCU)                         |          13 |            3 |               23.10 |           8.20 |           50.30 |                    38.50 |
| First ICU unit | Neuro Surgical Intensive Care Unit (Neuro SICU)  |           3 |            1 |               33.30 |           6.10 |           79.20 |                    33.30 |
| First ICU unit | Neuro Stepdown                                   |           1 |            0 |                0.00 |           0.00 |           79.30 |                     0.00 |
| First ICU unit | Neuro Intermediate                               |           1 |            0 |                0.00 |           0.00 |           79.30 |                     0.00 |

**Interpretation:** ICU mortality (death during the stay + 6h) is 8.6% (12/140, CI 5.0-14.4%); hospital mortality for the same stays is 14.3%, so some deaths occur after ICU discharge. Rates are numerically higher for men (11.7% vs 4.8%) and in the CCU (23.1%) and MICU (17.2%), but the rates are unadjusted for severity and the CIs overlap.


## D. Clinical analytics

<a id="q16"></a>
### Q16: Most frequent laboratory tests

**File:** [`sql/clinical/q16_most_frequent_lab_tests.sql`](../sql/clinical/q16_most_frequent_lab_tests.sql)  
**Execution:** 20 rows in 19 ms (includes client round-trip)

- **Business question:** Which laboratory tests account for most lab volume, and how widely are they used across admissions?
- **Metric:** Per lab test (itemid): measurements, share of admission-linked lab volume, cumulative share, admissions with at least one result, % of all admissions. Top 20 by volume.
- **Output grain:** One row per lab test (top 20).
- **Join logic:** fact_lab_events to dim_lab_test on itemid (many-to-one; volumes are counted before the join, so no inflation).
- **Denominator and exclusions:** Admission-linked measurements only (hadm_id not null); outpatient draws are excluded. % of admissions uses all admissions.
- **Potential biases:** Panels (for example a basic metabolic panel) produce several itemids per draw, so counts are results, not orders or blood draws.
- **Expected output:** volume_rank, lab_test_name, fluid, lab_category, measurements, pct_of_volume, cumulative_pct, admissions_tested, pct_admissions_tested.
- **SQL techniques:** CTE pre-aggregation, ROW_NUMBER, running window SUM, COUNT DISTINCT.

**Result (actual output):**

|   volume_rank | lab_test_name     | fluid   | lab_category   |   measurements |   pct_of_volume |   cumulative_pct |   admissions_tested |   pct_admissions_tested |
|--------------:|:------------------|:--------|:---------------|---------------:|----------------:|-----------------:|--------------------:|------------------------:|
|             1 | Potassium         | Blood   | Chemistry      |           2461 |            3.10 |             3.10 |                 250 |                   90.90 |
|             2 | Sodium            | Blood   | Chemistry      |           2449 |            3.09 |             6.20 |                 250 |                   90.90 |
|             3 | Chloride          | Blood   | Chemistry      |           2443 |            3.08 |             9.30 |                 250 |                   90.90 |
|             4 | Creatinine        | Blood   | Chemistry      |           2366 |            2.98 |            12.30 |                 250 |                   90.90 |
|             5 | Urea Nitrogen     | Blood   | Chemistry      |           2349 |            2.96 |            15.20 |                 250 |                   90.90 |
|             6 | Bicarbonate       | Blood   | Chemistry      |           2339 |            2.95 |            18.20 |                 246 |                   89.50 |
|             7 | Anion Gap         | Blood   | Chemistry      |           2336 |            2.95 |            21.10 |                 246 |                   89.50 |
|             8 | Glucose           | Blood   | Chemistry      |           2304 |            2.91 |            24.00 |                 246 |                   89.50 |
|             9 | Hematocrit        | Blood   | Hematology     |           2298 |            2.90 |            26.90 |                 248 |                   90.20 |
|            10 | Magnesium         | Blood   | Chemistry      |           2237 |            2.82 |            29.70 |                 240 |                   87.30 |
|            11 | Platelet Count    | Blood   | Hematology     |           2208 |            2.78 |            32.50 |                 248 |                   90.20 |
|            12 | Hemoglobin        | Blood   | Hematology     |           2173 |            2.74 |            35.30 |                 246 |                   89.50 |
|            13 | MCH               | Blood   | Hematology     |           2149 |            2.71 |            38.00 |                 245 |                   89.10 |
|            14 | MCHC              | Blood   | Hematology     |           2149 |            2.71 |            40.70 |                 245 |                   89.10 |
|            15 | MCV               | Blood   | Hematology     |           2149 |            2.71 |            43.40 |                 245 |                   89.10 |
|            16 | RDW               | Blood   | Hematology     |           2149 |            2.71 |            46.10 |                 245 |                   89.10 |
|            17 | Red Blood Cells   | Blood   | Hematology     |           2149 |            2.71 |            48.80 |                 245 |                   89.10 |
|            18 | White Blood Cells | Blood   | Hematology     |           2149 |            2.71 |            51.50 |                 245 |                   89.10 |
|            19 | Phosphate         | Blood   | Chemistry      |           2114 |            2.67 |            54.20 |                 236 |                   85.80 |
|            20 | Calcium, Total    | Blood   | Chemistry      |           2099 |            2.65 |            56.80 |                 236 |                   85.80 |

**Interpretation:** Basic chemistry and complete blood count components make up the top 20 tests. Each is measured on 86-91% of admissions, and together the top 20 account for 56.8% of admission-linked lab results. Most volume comes from routine repeated panels, not specialised tests.

<a id="q17"></a>
### Q17: Abnormal laboratory result frequency by test type

**File:** [`sql/clinical/q17_abnormal_lab_frequency.sql`](../sql/clinical/q17_abnormal_lab_frequency.sql)  
**Execution:** 20 rows in 12 ms (includes client round-trip)

- **Business question:** Which high-volume tests most often return abnormal results, and in which direction?
- **Metric:** For tests with at least 500 results: % flagged abnormal by the laboratory; % below and above the row's own reference range; agreement between the lab flag and the range comparison.
- **Output grain:** One row per lab test meeting the volume threshold (top 20 by abnormal %).
- **Join logic:** fact_lab_events to dim_lab_test (many-to-one) after aggregation.
- **Denominator and exclusions:** All results for the test (inpatient and outpatient) for the flag rate. The range-based rates use only results with a numeric value and both reference bounds.
- **Potential biases:** Reference ranges vary by lab, assay, sex and era, and some tests have none (for example blood gases, where the flag may be absent). An abnormal value is a measurement property, NOT a diagnosis. Sick patients are tested more often, so results over-represent abnormal states.
- **Expected output:** lab_test_name, fluid, results, pct_flag_abnormal, range_evaluable, pct_low, pct_high, pct_flag_range_agreement.
- **SQL techniques:** Conditional aggregation (FILTER), HAVING, NULLIF-guarded ratios, ORDER BY with LIMIT.

**Result (actual output):**

| lab_test_name              | fluid   |   results |   pct_flag_abnormal |   range_evaluable |   pct_low |   pct_high |   pct_flag_range_agreement |
|:---------------------------|:--------|----------:|--------------------:|------------------:|----------:|-----------:|---------------------------:|
| Red Blood Cells            | Blood   |      2760 |               86.80 |              2748 |     86.80 |       0.40 |                     100.00 |
| Hemoglobin                 | Blood   |      2930 |               85.90 |              2928 |     85.70 |       0.20 |                     100.00 |
| Hematocrit                 | Blood   |      2913 |               83.30 |              2908 |     82.80 |       0.60 |                     100.00 |
| pO2                        | Blood   |       889 |               79.80 |               889 |     35.00 |      44.80 |                     100.00 |
| Glucose                    | Blood   |      2973 |               76.90 |              2971 |      2.30 |      74.70 |                     100.00 |
| RDW-SD                     | Blood   |      1555 |               74.50 |              1542 |      0.00 |      75.10 |                     100.00 |
| INR(PT)                    | Blood   |      1481 |               69.90 |              1464 |      0.10 |      70.60 |                     100.00 |
| PT                         | Blood   |      1481 |               68.60 |              1464 |      0.10 |      69.10 |                     100.00 |
| Absolute Monocyte Count    | Blood   |       569 |               63.60 |               565 |     14.20 |      50.30 |                      99.60 |
| Lymphocytes                | Blood   |       943 |               63.00 |               939 |     51.30 |      12.20 |                      99.70 |
| Absolute Neutrophil Count  | Blood   |       569 |               62.20 |               565 |     13.80 |      49.40 |                      99.50 |
| Absolute Lymphocyte Count  | Blood   |       585 |               61.20 |               565 |     35.00 |      28.70 |                      99.60 |
| Absolute Basophil Count    | Blood   |       569 |               57.60 |               565 |     35.60 |      23.00 |                      99.50 |
| Lactate Dehydrogenase (LD) | Blood   |       663 |               57.30 |               663 |      0.00 |      57.30 |                     100.00 |
| Absolute Eosinophil Count  | Blood   |       569 |               53.10 |               565 |     37.70 |      16.10 |                      99.60 |
| pCO2                       | Blood   |       889 |               53.00 |               889 |     25.60 |      27.30 |                     100.00 |
| Free Calcium               | Blood   |       509 |               52.30 |               509 |     49.50 |       2.80 |                     100.00 |
| White Blood Cells          | Blood   |      2760 |               50.70 |              2759 |      9.10 |      41.60 |                     100.00 |
| pH                         | Blood   |       966 |               50.60 |               966 |     37.30 |      13.40 |                     100.00 |
| Urea Nitrogen              | Blood   |      2974 |               49.30 |              2973 |      3.70 |      45.60 |                     100.00 |

**Interpretation:** Red cell indices (RBC 86.8%, hemoglobin 85.9%, hematocrit 83.3% flagged abnormal), almost all LOW, are the most frequently abnormal high-volume tests. That is consistent with anaemia being common in a hospitalised ICU cohort. Glucose is abnormal on 76.9% of results, mostly HIGH. The lab flag agrees with the row's reference range on 99.5-100% of evaluable results. These are measurement frequencies, not diagnoses.

<a id="q18"></a>
### Q18: Common diagnosis combinations (co-occurrence with lift)

**File:** [`sql/clinical/q18_diagnosis_combinations.sql`](../sql/clinical/q18_diagnosis_combinations.sql)  
**Execution:** 15 rows in 13 ms (includes client round-trip)

- **Business question:** Which conditions are coded together on the same admission most often, and which pairs co-occur more than chance would predict?
- **Metric:** For pairs of ICD codes on the same admission: admissions with both (support), support %, and lift = P(A and B) / (P(A) x P(B)). Pairs must co-occur on at least 15 admissions.
- **Output grain:** One row per unordered code pair (top 15 by support).
- **Join logic:** Self-join of distinct (hadm_id, code) rows on hadm_id with a.code < b.code, so each unordered pair is counted once per admission.
- **Denominator and exclusions:** All admissions with at least one coded diagnosis. ICD-9 and ICD-10 codes are kept separate (they are different code systems).
- **Potential biases:** Common chronic codes (hypertension, hyperlipidemia) dominate support; lift corrects for base rates but is unstable for rare codes, hence the threshold. Co-occurrence is not causation or a clinical pathway.
- **Expected output:** code_a, title_a, code_b, title_b, admissions_with_both, support_pct, lift.
- **SQL techniques:** Self-join, DISTINCT pre-aggregation, CTE marginals, HAVING threshold.

**Result (actual output):**

| code_a   | title_a                                                      | code_b    | title_b                                                      |   admissions_with_both |   support_pct |   lift |
|:---------|:-------------------------------------------------------------|:----------|:-------------------------------------------------------------|-----------------------:|--------------:|-------:|
| 9:2724   | Other and unspecified hyperlipidemia                         | 9:4019    | Unspecified essential hypertension                           |                     31 |         11.30 |   2.28 |
| 10:E039  | Hypothyroidism, unspecified                                  | 10:E785   | Hyperlipidemia, unspecified                                  |                     27 |          9.80 |   2.77 |
| 10:E785  | Hyperlipidemia, unspecified                                  | 10:Z794   | Long term (current) use of insulin                           |                     26 |          9.50 |   3.39 |
| 10:E785  | Hyperlipidemia, unspecified                                  | 10:I2510  | Atherosclerotic heart disease of native coronary artery with |                     25 |          9.10 |   3.65 |
| 10:E785  | Hyperlipidemia, unspecified                                  | 10:F329   | Major depressive disorder, single episode, unspecified       |                     23 |          8.40 |   3.47 |
| 10:E785  | Hyperlipidemia, unspecified                                  | 10:Z87891 | Personal history of nicotine dependence                      |                     23 |          8.40 |   3.17 |
| 10:E785  | Hyperlipidemia, unspecified                                  | 10:Z955   | Presence of coronary angioplasty implant and graft           |                     22 |          8.00 |   4.42 |
| 10:E039  | Hypothyroidism, unspecified                                  | 10:I2510  | Atherosclerotic heart disease of native coronary artery with |                     22 |          8.00 |   3.90 |
| 10:E039  | Hypothyroidism, unspecified                                  | 10:F329   | Major depressive disorder, single episode, unspecified       |                     21 |          7.60 |   3.84 |
| 10:E039  | Hypothyroidism, unspecified                                  | 10:Z794   | Long term (current) use of insulin                           |                     21 |          7.60 |   3.32 |
| 10:I2510 | Atherosclerotic heart disease of native coronary artery with | 10:Z955   | Presence of coronary angioplasty implant and graft           |                     20 |          7.30 |   6.94 |
| 9:42731  | Atrial fibrillation                                          | 9:V5861   | Long-term (current) use of anticoagulants                    |                     20 |          7.30 |   6.47 |
| 9:2724   | Other and unspecified hyperlipidemia                         | 9:41401   | Coronary atherosclerosis of native coronary artery           |                     20 |          7.30 |   3.57 |
| 10:E785  | Hyperlipidemia, unspecified                                  | 10:I10    | Essential (primary) hypertension                             |                     20 |          7.30 |   3.02 |
| 10:E039  | Hypothyroidism, unspecified                                  | 10:N179   | Acute kidney failure, unspecified                            |                     19 |          6.90 |   3.59 |

**Interpretation:** The most frequent pair is ICD-9 hyperlipidemia with hypertension (31 admissions). The strongest associations among frequent pairs are coronary atherosclerosis with a coronary stent (lift 6.94) and atrial fibrillation with long-term anticoagulant use (lift 6.47). These are clinically coherent condition-treatment pairs, which supports the integrity of the coding data.

<a id="q19"></a>
### Q19: Medication prescribing patterns

**File:** [`sql/clinical/q19_medication_prescribing_patterns.sql`](../sql/clinical/q19_medication_prescribing_patterns.sql)  
**Execution:** 20 rows in 9 ms (includes client round-trip)

- **Business question:** Which medications are ordered most, how widely across admissions, by which route, and for how long?
- **Metric:** Per normalised drug name: orders, admissions with an order, % of admissions, orders per exposed admission, most common route, median order duration (hours). Top 20 by admissions exposed.
- **Output grain:** One row per drug (top 20).
- **Join logic:** fact_medication_orders aggregated by drug; modal route from dim_medication (one row per drug, so no fan-out).
- **Denominator and exclusions:** Therapeutic orders only: drug_type = 'BASE' (diluents and IV base solutions such as '0.9% sodium chloride' and 'bag', 20% of orders) and line flushes are excluded because they are carriers, not therapies. % of admissions uses all admissions. Order durations with stop before start are left out of the duration median (flagged has_inverted_times).
- **Potential biases:** Orders are not administrations (use emar for administration). Free-text drug names: brand and generic names, and different strengths, are not merged (no RxNorm mapping). PRN protocol orders (for example dextrose 50%, glucagon for hypoglycaemia) count as exposure even if never given.
- **Expected output:** exposure_rank, drug_name, orders, admissions_exposed, pct_admissions_exposed, orders_per_exposed_admission, most_common_route, median_order_hours.
- **SQL techniques:** CTE aggregation, DENSE_RANK, percentile_cont with FILTER, join to dimension.

**Result (actual output):**

|   exposure_rank | drug_name                     |   orders |   admissions_exposed |   pct_admissions_exposed |   orders_per_exposed_admission | most_common_route   |   median_order_hours |
|----------------:|:------------------------------|---------:|---------------------:|-------------------------:|-------------------------------:|:--------------------|---------------------:|
|               1 | acetaminophen                 |      344 |                  176 |                    64.00 |                           1.95 | PO/NG               |                52.00 |
|               2 | heparin                       |      287 |                  173 |                    62.90 |                           1.66 | SC                  |                70.00 |
|               3 | docusate sodium               |      250 |                  155 |                    56.40 |                           1.61 | PO/NG               |                79.50 |
|               4 | senna                         |      217 |                  148 |                    53.80 |                           1.47 | PO/NG               |                89.00 |
|               5 | magnesium sulfate             |      402 |                  138 |                    50.20 |                           2.91 | IV                  |                24.00 |
|               6 | dextrose 50%                  |      182 |                  137 |                    49.80 |                           1.33 | IV                  |                91.00 |
|               7 | potassium chloride            |      610 |                  133 |                    48.40 |                           4.59 | PO                  |                23.00 |
|               8 | insulin                       |      915 |                  130 |                    47.30 |                           7.04 | SC                  |                26.00 |
|               8 | glucagon                      |      145 |                  130 |                    47.30 |                           1.12 | IM                  |               112.50 |
|               9 | ondansetron                   |      173 |                  116 |                    42.20 |                           1.49 | IV                  |                59.00 |
|              10 | furosemide                    |      510 |                  103 |                    37.50 |                           4.95 | IV                  |                23.00 |
|              10 | glucose gel                   |      116 |                  103 |                    37.50 |                           1.13 | PO                  |               113.00 |
|              11 | aspirin                       |      129 |                  100 |                    36.40 |                           1.29 | PO/NG               |                67.00 |
|              12 | oxycodone (immediate release) |      215 |                   99 |                    36.00 |                           2.17 | PO/NG               |                32.00 |
|              13 | calcium gluconate             |      271 |                   90 |                    32.70 |                           3.01 | IV                  |                53.00 |
|              14 | bisacodyl                     |      159 |                   89 |                    32.40 |                           1.79 | PR                  |                74.00 |
|              15 | metoprolol tartrate           |      371 |                   88 |                    32.00 |                           4.22 | PO/NG               |                21.00 |
|              16 | vancomycin                    |      272 |                   82 |                    29.80 |                           3.32 | IV                  |                24.00 |
|              17 | hydromorphone (dilaudid)      |      326 |                   79 |                    28.70 |                           4.13 | IV                  |                23.00 |
|              17 | lorazepam                     |      225 |                   79 |                    28.70 |                           2.85 | IV                  |                24.00 |

**Interpretation:** Excluding diluents and line flushes, the most widely ordered therapeutic drugs are acetaminophen (64.0% of admissions), heparin (62.9%, mostly subcutaneous, consistent with VTE prophylaxis) and bowel regimen agents (docusate 56.4%, senna 53.8%). Insulin has the most orders per exposed admission (7.04), reflecting sliding-scale reordering. Hypoglycaemia rescue orders (dextrose 50%, glucagon) appear on about half of admissions as PRN protocol orders.

<a id="q20"></a>
### Q20: Hospital mortality by diagnosis category

**File:** [`sql/clinical/q20_mortality_by_diagnosis.sql`](../sql/clinical/q20_mortality_by_diagnosis.sql)  
**Execution:** 10 rows in 1 ms (includes client round-trip)

- **Business question:** Which principal-diagnosis groups carry the highest in-hospital mortality?
- **Metric:** Per primary diagnosis category: admissions, in-hospital deaths, crude mortality %, Wilson 95% CI, and the median Charlson score as case-mix context. Categories with at least 10 admissions.
- **Output grain:** One row per primary diagnosis category meeting the threshold.
- **Join logic:** None (primary category and Charlson score are pre-computed on fact_admissions).
- **Denominator and exclusions:** All admissions in the category, including observation encounters.
- **Potential biases:** Crude (unadjusted) rates; differences reflect severity and comorbidity, not quality of care. Very few deaths overall, so intervals are wide. The principal diagnosis is assigned at discharge.
- **Expected output:** diagnosis_category, admissions, deaths, mortality_pct, ci95_low_pct, ci95_high_pct, median_charlson.
- **SQL techniques:** Aggregation with HAVING, FILTER, Wilson interval, percentile_cont.

**Result (actual output):**

| diagnosis_category                 |   admissions |   deaths |   mortality_pct |   ci95_low_pct |   ci95_high_pct |   median_charlson |
|:-----------------------------------|-------------:|---------:|----------------:|---------------:|----------------:|------------------:|
| Respiratory                        |           18 |        3 |           16.70 |           5.80 |           39.20 |              2.00 |
| Digestive                          |           33 |        4 |           12.10 |           4.80 |           27.30 |              3.00 |
| Injury & poisoning                 |           35 |        3 |            8.60 |           3.00 |           22.40 |              1.00 |
| Circulatory                        |           67 |        3 |            4.50 |           1.50 |           12.40 |              2.00 |
| Infectious & parasitic             |           22 |        1 |            4.50 |           0.80 |           21.80 |              2.50 |
| Neoplasms                          |           24 |        1 |            4.20 |           0.70 |           20.20 |              4.00 |
| Symptoms, signs & ill-defined      |           18 |        0 |            0.00 |           0.00 |           17.60 |              2.00 |
| Mental & behavioral                |           15 |        0 |            0.00 |           0.00 |           20.40 |              0.00 |
| Endocrine, nutritional & metabolic |           13 |        0 |            0.00 |           0.00 |           22.80 |              3.00 |
| Genitourinary                      |           10 |        0 |            0.00 |           0.00 |           27.80 |              3.50 |

**Interpretation:** Crude in-hospital mortality is highest for respiratory (16.7%, 3/18) and digestive (12.1%, 4/33) principal diagnoses. With 15 deaths in total, every interval is wide (e.g. respiratory 5.8-39.2%) and the rates are unadjusted for severity. No conclusions about care quality are possible.


## E. Operational analytics

<a id="q21"></a>
### Q21: Hospital length of stay by admission category

**File:** [`sql/operations/q21_los_by_admission_category.sql`](../sql/operations/q21_los_by_admission_category.sql)  
**Execution:** 9 rows in 1 ms (includes client round-trip)

- **Business question:** Which admission categories have unusually long stays relative to the hospital-wide median?
- **Metric:** Per admission group and type: admissions, mean/median/P75/P90 LOS, % of stays of 14+ days, and median LOS relative to the overall median (index = 1.0).
- **Output grain:** One row per admission type, ordered within its admission group.
- **Join logic:** None; the overall median comes from a separate CTE that is cross-joined.
- **Denominator and exclusions:** All admissions, including in-hospital deaths (which truncate LOS; see Query 04 for the survivor split).
- **Potential biases:** Observation encounters are short by definition. Small types (n < 10) give unstable medians. LOS is influenced by discharge-destination availability, which this data does not capture.
- **Expected output:** admission_group, admission_type, admissions, mean_los, median_los, p75_los, p90_los, pct_long_stay_14d, median_vs_overall.
- **SQL techniques:** CTE, ordered-set aggregates, FILTER, ratio to an overall benchmark, window ordering.

**Result (actual output):**

| admission_group   | admission_type              |   admissions |   mean_los_days |   median_los_days |   p75_los_days |   p90_los_days |   pct_long_stay_14d |   median_vs_overall |
|:------------------|:----------------------------|-------------:|----------------:|------------------:|---------------:|---------------:|--------------------:|--------------------:|
| Urgent            | URGENT                      |           38 |            9.85 |              7.86 |          11.11 |          22.22 |               18.40 |                1.62 |
| Elective          | ELECTIVE                    |           13 |            8.19 |              6.19 |           9.22 |          15.78 |               15.40 |                1.28 |
| Emergency         | EW EMER.                    |          104 |            7.28 |              5.55 |           9.41 |          14.07 |               11.50 |                1.14 |
| Elective          | SURGICAL SAME DAY ADMISSION |           18 |            5.70 |              5.48 |           7.27 |           8.58 |                0.00 |                1.13 |
| Observation       | OBSERVATION ADMIT           |           45 |            8.15 |              4.85 |          12.66 |          15.77 |               15.60 |                1.00 |
| Emergency         | DIRECT EMER.                |           15 |            9.39 |              4.09 |          10.90 |          27.17 |               20.00 |                0.84 |
| Observation       | DIRECT OBSERVATION          |            7 |            1.45 |              1.23 |           2.10 |           2.85 |                0.00 |                0.25 |
| Observation       | AMBULATORY OBSERVATION      |            5 |            1.02 |              0.98 |           1.02 |           1.14 |                0.00 |                0.20 |
| Observation       | EU OBSERVATION              |           30 |            0.92 |              0.64 |           1.27 |           2.01 |                0.00 |                0.13 |

**Interpretation:** URGENT admissions have the longest stays (median 7.86 days, 1.62x the hospital median; 18.4% stay 14+ days), followed by ELECTIVE (6.19 days). "OBSERVATION ADMIT" encounters have a median of 4.85 days, with 15.6% lasting 14+ days, which is long for observation status and suggests the label includes encounters that became full inpatient stays. Worth reviewing against status-change data on the full dataset.

<a id="q22"></a>
### Q22: Transfer frequency per admission

**File:** [`sql/operations/q22_transfers_per_admission.sql`](../sql/operations/q22_transfers_per_admission.sql)  
**Execution:** 5 rows in 1 ms (includes client round-trip)

- **Business question:** How often are patients moved between care units during a stay, which admission types move most, and do more moves go with longer stays?
- **Metric:** Per admission group: admissions, mean and median care-unit changes, % with 3+ changes, mean distinct units visited, and the Pearson and Spearman-style (rank) correlation between unit changes and LOS.
- **Output grain:** One row per admission group, plus an overall row (GROUPING SETS).
- **Join logic:** None. n_unit_changes is pre-aggregated per hadm_id in fact_admissions from fact_care_transfers.
- **Denominator and exclusions:** All admissions. A unit change means the care unit differs from the previous movement; bed moves within one unit do not count. ED to inpatient-unit moves count as a change.
- **Potential biases:** Correlation with LOS is mechanical in part (longer stays give more chances to move) and does not show that transfers lengthen stays.
- **Expected output:** admission_group, admissions, mean_unit_changes, median_unit_changes, pct_3plus_changes, mean_distinct_units, corr_changes_los, rank_corr_changes_los.
- **SQL techniques:** GROUPING SETS, corr() aggregate, rank-transformed correlation via window RANK, FILTER.

**Result (actual output):**

| admission_group   |   admissions |   mean_unit_changes |   median_unit_changes |   pct_3plus_changes |   mean_distinct_units |   corr_changes_los |   rank_corr_changes_los |
|:------------------|-------------:|--------------------:|----------------------:|--------------------:|----------------------:|-------------------:|------------------------:|
| Emergency         |          119 |                1.81 |                  2.00 |               17.60 |                  2.66 |               0.25 |                    0.41 |
| Observation       |           87 |                1.28 |                  1.00 |               14.90 |                  2.18 |               0.42 |                    0.48 |
| Urgent            |           38 |                1.84 |                  1.50 |               26.30 |                  2.47 |               0.69 |                    0.49 |
| Elective          |           31 |                1.74 |                  2.00 |               16.10 |                  2.61 |              -0.19 |                    0.11 |
| All admissions    |          275 |                1.64 |                  1.00 |               17.80 |                  2.48 |               0.40 |                    0.46 |

**Interpretation:** Admissions average 1.64 care-unit changes and 17.8% have three or more. URGENT admissions move most (26.3% with 3+ changes). Unit changes correlate moderately with LOS overall (Pearson 0.40, rank 0.46); this is partly mechanical, because longer stays give more chances to move.

<a id="q23"></a>
### Q23: Laboratory test volume per admission

**File:** [`sql/operations/q23_lab_volume_per_admission.sql`](../sql/operations/q23_lab_volume_per_admission.sql)  
**Execution:** 8 rows in 1 ms (includes client round-trip)

- **Business question:** Where is laboratory workload concentrated: in which admission types, and with or without ICU care, once length of stay is taken into account?
- **Metric:** Per (admission group, ICU yes/no): admissions, total lab results, share of all lab volume, median results per admission, and median results per inpatient day (results / max(LOS, 1 day)).
- **Output grain:** One row per admission group x ICU flag.
- **Join logic:** None. n_lab_events is pre-aggregated to hadm_id in fact_admissions, so admission rows are not duplicated.
- **Denominator and exclusions:** All admissions. Only admission-linked lab results count; outpatient draws are excluded. LOS is floored at 1 day for the per-day rate so very short stays do not explode it.
- **Potential biases:** Results, not orders: panels inflate counts. Per-day normalisation assumes testing is spread evenly over the stay, but it is front-loaded.
- **Expected output:** admission_group, icu_care, admissions, lab_results, pct_of_lab_volume, median_results_per_admission, median_results_per_day.
- **SQL techniques:** CTE, GREATEST for the denominator floor, window share of total, percentile_cont.

**Result (actual output):**

| admission_group   | icu_care   |   admissions |   lab_results |   pct_of_lab_volume |   median_results_per_admission |   median_results_per_day |
|:------------------|:-----------|-------------:|--------------:|--------------------:|-------------------------------:|-------------------------:|
| Emergency         | ICU        |           66 |      25928.00 |               32.70 |                         261.00 |                    38.40 |
| Urgent            | ICU        |           25 |      13289.00 |               16.80 |                         391.00 |                    46.10 |
| Observation       | No ICU     |           70 |      10329.00 |               13.00 |                          43.50 |                    24.60 |
| Observation       | ICU        |           17 |      10213.00 |               12.90 |                         486.00 |                    48.50 |
| Emergency         | No ICU     |           53 |       9533.00 |               12.00 |                         131.00 |                    28.40 |
| Elective          | ICU        |           20 |       4448.00 |                5.60 |                         213.00 |                    39.20 |
| Elective          | No ICU     |           11 |       3059.00 |                3.90 |                         175.00 |                    26.80 |
| Urgent            | No ICU     |           13 |       2508.00 |                3.20 |                          97.00 |                    27.50 |

**Interpretation:** Emergency admissions with ICU care generate 32.7% of all admission-linked lab results. ICU admissions run about 38-49 results per inpatient day versus about 25-28 without ICU, so lab workload follows ICU exposure more than admission type.

<a id="q24"></a>
### Q24: ICU utilization among patients with repeated admissions

**File:** [`sql/operations/q24_icu_use_repeat_patients.sql`](../sql/operations/q24_icu_use_repeat_patients.sql)  
**Execution:** 6 rows in 1 ms (includes client round-trip)

- **Business question:** Do frequently admitted patients use the ICU more per admission, and does ICU use change across a patient's successive admissions?
- **Metric:** Per patient admission-frequency band and admission sequence position (1st, 2nd-3rd, 4th+): admissions, % with ICU care, ICU days per admission, ICU days per ICU admission.
- **Output grain:** One row per (frequency band, sequence position).
- **Join logic:** fact_admissions to dim_patient on subject_id (many-to-one) for the frequency band.
- **Denominator and exclusions:** All admissions.
- **Potential biases:** Strong selection effect: every demo patient had at least one ICU stay, so a single-admission patient's only admission includes ICU care by construction. This query mainly shows how that selection dilutes across repeat admissions; full-dataset validation is needed before drawing operational conclusions.
- **Expected output:** admission_frequency_band, sequence_position, admissions, pct_with_icu, icu_days_per_admission, icu_days_per_icu_admission.
- **SQL techniques:** Join to dimension, CASE bucketing of a window-derived sequence (admission_seq from ROW_NUMBER upstream), FILTER, NULLIF.

**Result (actual output):**

| admission_frequency_band   | sequence_position   |   admissions |   pct_with_icu |   icu_days_per_admission |   icu_days_per_icu_admission |
|:---------------------------|:--------------------|-------------:|---------------:|-------------------------:|-----------------------------:|
| 1                          | 1st admission       |           52 |         100.00 |                     3.21 |                         3.21 |
| 2-3                        | 1st admission       |           29 |          55.20 |                     2.25 |                         4.07 |
| 2-3                        | 2nd-3rd admission   |           38 |          63.20 |                     2.14 |                         3.38 |
| 4+                         | 1st admission       |           19 |          31.60 |                     2.77 |                         8.77 |
| 4+                         | 2nd-3rd admission   |           38 |          36.80 |                     1.36 |                         3.69 |
| 4+                         | 4th+ admission      |           99 |          16.20 |                     0.99 |                         6.11 |

**Interpretation:** Among frequently admitted patients (4+ admissions), ICU use falls from 31.6% of first admissions to 16.2% of 4th+ admissions. Single-admission patients show 100% ICU use, which is an artefact of the demo's ICU-only selection, not a clinical pattern. Full-dataset validation is required before drawing operational conclusions.

<a id="q25"></a>
### Q25: Cohort-level resource utilization (observable proxies)

**File:** [`sql/operations/q25_cohort_resource_utilization.sql`](../sql/operations/q25_cohort_resource_utilization.sql)  
**Execution:** 4 rows in 1 ms (includes client round-trip)

- **Business question:** How does use of observable hospital resources scale with comorbidity burden?
- **Metric:** Per Charlson comorbidity band: admissions, and per admission: mean LOS days, ICU days, lab results, therapeutic medication orders, procedures, care-unit changes. Each mean is also shown as an index relative to the all-admission mean (1.00 = average).
- **Output grain:** One row per Charlson band (0, 1-2, 3-4, 5+).
- **Join logic:** None. All proxies are pre-aggregated per hadm_id in fact_admissions.
- **Denominator and exclusions:** All admissions. Proxies are COUNTS OF OBSERVED EVENTS, not costs: no charges, prices or staffing data exist in MIMIC, and an event count must not be read as a dollar amount.
- **Potential biases:** Charlson is derived from discharge codes, so it partly reflects what happened during the stay (longer stays accumulate more codes), which inflates the association. Medication orders include all drug types here.
- **Expected output:** charlson_band, admissions, mean_los_days, mean_icu_days, mean_lab_results, mean_med_orders, mean_procedures, mean_unit_changes, and *_index columns.
- **SQL techniques:** CTE, CASE banding, cross join to overall means, ratio indexing.

**Result (actual output):**

| charlson_band   |   admissions |   mean_los_days |   mean_icu_days |   mean_lab_results |   mean_med_orders |   mean_procedures |   mean_unit_changes |   los_index |   icu_index |   lab_index |   med_index |
|:----------------|-------------:|----------------:|----------------:|-------------------:|------------------:|------------------:|--------------------:|------------:|------------:|------------:|------------:|
| 0               |           47 |            5.11 |            1.21 |             141.60 |             49.70 |              2.11 |                1.68 |        0.74 |        0.65 |        0.49 |        0.76 |
| 1-2             |           98 |            6.29 |            1.90 |             245.60 |             58.20 |              2.74 |                1.64 |        0.91 |        1.01 |        0.85 |        0.89 |
| 3-4             |           65 |            6.33 |            1.26 |             307.30 |             58.80 |              1.95 |                1.48 |        0.92 |        0.67 |        1.07 |        0.89 |
| 5+              |           65 |            9.58 |            2.93 |             440.20 |             95.60 |              3.49 |                1.75 |        1.39 |        1.56 |        1.53 |        1.45 |

**Interpretation:** Resource proxies rise with comorbidity burden. Admissions with Charlson 5+ use 1.39x the average LOS, 1.56x ICU days, 1.53x lab results and 1.45x medication orders; Charlson 0 admissions use 0.49-0.76x. These are event counts, not costs, and the association is inflated because Charlson is coded at discharge.

