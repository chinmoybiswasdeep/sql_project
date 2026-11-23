-- =============================================================================
-- Query 10: Patients with multiple hospitalizations and their admission patterns
-- Module: B. Readmission analytics
-- Business question: How concentrated is hospital use among frequent patients, and how do their patterns differ (spacing, readmissions, ICU use)?
-- Metric: Per admission-frequency band: patients, admissions, share of all admissions, median gap between consecutive admissions, 30-day readmissions per patient, % of admissions with ICU care.
-- Output grain: One row per admission-frequency band (1, 2-3, 4-6, 7+ admissions). Aggregated deliberately, so no patient-level rows are exposed.
-- Joins: Per-patient CTE built from fact_admissions using LAG to measure the gap between consecutive admissions; then grouped to bands.
-- Denominator and exclusions: All patients with at least one admission.
-- Potential biases: Frequency is measured within the observed (date-shifted) history only. Bands with few patients are unstable.
-- Expected output: frequency_band, patients, admissions, pct_of_admissions, median_gap_days, readmissions_30d_per_patient, pct_admissions_with_icu.
-- Techniques: LAG window function, multi-level CTE aggregation, percentile_cont, window share of total.
-- =============================================================================
with ordered as (
    select
        subject_id,
        hadm_id,
        admittime,
        had_icu_stay,
        is_readmitted_30d,
        extract(epoch from admittime - lag(dischtime) over (
            partition by subject_id order by admittime, hadm_id)) / 86400.0 as gap_days
    from marts.fact_admissions
),
per_patient as (
    select
        subject_id,
        count(*)                                        as n_admissions,
        count(*) filter (where had_icu_stay)            as n_icu_admissions,
        count(*) filter (where is_readmitted_30d)       as n_readmissions_30d,
        percentile_cont(0.5) within group (order by gap_days) as median_gap_days
    from ordered
    group by subject_id
),
banded as (
    select
        case
            when n_admissions = 1 then '1'
            when n_admissions <= 3 then '2-3'
            when n_admissions <= 6 then '4-6'
            else '7+'
        end as frequency_band,
        per_patient.*
    from per_patient
)
select
    frequency_band,
    count(*)                                                        as patients,
    sum(n_admissions)                                               as admissions,
    round(100.0 * sum(n_admissions) / sum(sum(n_admissions)) over (), 1) as pct_of_admissions,
    round(percentile_cont(0.5) within group (order by median_gap_days)::numeric, 1)
                                                                    as median_of_patient_median_gap_days,
    round(sum(n_readmissions_30d)::numeric / count(*), 2)           as readmissions_30d_per_patient,
    round(100.0 * sum(n_icu_admissions) / sum(n_admissions), 1)     as pct_admissions_with_icu
from banded
group by frequency_band
order by min(n_admissions);
