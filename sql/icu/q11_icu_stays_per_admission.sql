-- =============================================================================
-- Query 11: ICU stays per hospital admission
-- Module: C. ICU analytics
-- Business question: How often does a hospitalization involve ICU care, and how often do patients return to the ICU within the same hospitalization?
-- Metric: Admissions by number of ICU stays (0, 1, 2, 3+); among ICU admissions, the share with a repeat ICU stay and the median hours between ICU discharge and readmission to ICU.
-- Output grain: One row per ICU-stay-count bucket, with ICU-bounce-back statistics repeated for reference.
-- Joins: fact_admissions (n_icu_stays pre-aggregated per hadm_id) and fact_icu_stays (hours_since_prev_icu_discharge from LAG within hadm_id).
-- Denominator and exclusions: All admissions for the distribution; ICU admissions for the bounce-back rate.
-- Potential biases: Every demo patient had at least one ICU stay at some point, so the ICU proportion is far above a general-hospital rate. Measures ICU episodes, not ICU occupancy.
-- Expected output: icu_stays_bucket, admissions, pct_of_admissions, pct_icu_admissions_with_repeat_icu_stay, median_hours_between_icu_stays.
-- Techniques: CTEs, CASE bucketing, window share, FILTER, percentile_cont.
-- =============================================================================
with dist as (
    select
        case when n_icu_stays >= 3 then '3+' else n_icu_stays::text end as icu_stays_bucket,
        least(n_icu_stays, 3)                                         as sort_key,
        count(*)                                                      as admissions
    from marts.fact_admissions
    group by 1, 2
),
bounce as (
    select
        round(100.0 * count(distinct hadm_id) filter (where is_repeat_icu_stay_same_admission)
              / count(distinct hadm_id), 1)                           as pct_icu_admissions_with_repeat_icu_stay,
        round(percentile_cont(0.5) within group (order by hours_since_prev_icu_discharge)
              filter (where hours_since_prev_icu_discharge is not null)::numeric, 1)
                                                                      as median_hours_between_icu_stays
    from marts.fact_icu_stays
)
select
    d.icu_stays_bucket,
    d.admissions,
    round(100.0 * d.admissions / sum(d.admissions) over (), 1)        as pct_of_admissions,
    b.pct_icu_admissions_with_repeat_icu_stay,
    b.median_hours_between_icu_stays
from dist d
cross join bounce b
order by d.sort_key;
