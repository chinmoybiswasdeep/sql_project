-- =============================================================================
-- Query 01: Patient and admission volume
-- Module: A. Patient and admission analytics
-- Business question: How many patients and admissions does the warehouse cover, and how concentrated are admissions among patients?
-- Metric: Distinct patients; admissions; admissions per patient (mean, median, max); share of patients and admissions from patients with 2+ admissions.
-- Output grain: One summary row.
-- Joins: None. fact_admissions is already one row per hadm_id; a per-patient CTE aggregates it to subject_id first.
-- Denominator and exclusions: All admissions and all patients with at least one admission. No exclusions.
-- Potential biases: The demo is a 100-patient subset in which every patient had an ICU stay, so admission frequency is higher than a general hospital population.
-- Expected output: total_patients, total_admissions, mean/median/max admissions per patient, repeat-patient shares.
-- Techniques: CTE, aggregate FILTER, ordered-set aggregate (percentile_cont).
-- =============================================================================
with per_patient as (
    select subject_id, count(*) as n_admissions
    from marts.fact_admissions
    group by subject_id
)
select
    count(*)                                                      as total_patients,
    sum(n_admissions)                                             as total_admissions,
    round(avg(n_admissions), 2)                                   as mean_admissions_per_patient,
    percentile_cont(0.5) within group (order by n_admissions)     as median_admissions_per_patient,
    max(n_admissions)                                             as max_admissions_one_patient,
    count(*) filter (where n_admissions = 1)                      as patients_single_admission,
    round(100.0 * count(*) filter (where n_admissions >= 2) / count(*), 1)
                                                                  as pct_patients_with_repeat_admissions,
    round(100.0 * sum(n_admissions) filter (where n_admissions >= 2) / sum(n_admissions), 1)
                                                                  as pct_admissions_from_repeat_patients
from per_patient;
