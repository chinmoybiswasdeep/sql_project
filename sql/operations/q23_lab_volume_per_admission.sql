-- =============================================================================
-- Query 23: Laboratory test volume per admission
-- Module: E. Operational analytics
-- Business question: Where is laboratory workload concentrated: in which admission types, and with or without ICU care, once length of stay is taken into account?
-- Metric: Per (admission group, ICU yes/no): admissions, total lab results, share of all lab volume, median results per admission, and median results per inpatient day (results / max(LOS, 1 day)).
-- Output grain: One row per admission group x ICU flag.
-- Joins: None. n_lab_events is pre-aggregated to hadm_id in fact_admissions, so admission rows are not duplicated.
-- Denominator and exclusions: All admissions. Only admission-linked lab results count; outpatient draws are excluded. LOS is floored at 1 day for the per-day rate so very short stays do not explode it.
-- Potential biases: Results, not orders: panels inflate counts. Per-day normalisation assumes testing is spread evenly over the stay, but it is front-loaded.
-- Expected output: admission_group, icu_care, admissions, lab_results, pct_of_lab_volume, median_results_per_admission, median_results_per_day.
-- Techniques: CTE, GREATEST for the denominator floor, window share of total, percentile_cont.
-- =============================================================================
with per_adm as (
    select
        admission_group,
        case when had_icu_stay then 'ICU' else 'No ICU' end         as icu_care,
        n_lab_events,
        n_lab_events / greatest(los_days, 1.0)                       as results_per_day
    from marts.fact_admissions
)
select
    admission_group,
    icu_care,
    count(*)                                                         as admissions,
    sum(n_lab_events)                                                as lab_results,
    round(100.0 * sum(n_lab_events) / sum(sum(n_lab_events)) over (), 1) as pct_of_lab_volume,
    percentile_cont(0.5) within group (order by n_lab_events)        as median_results_per_admission,
    round(percentile_cont(0.5) within group (order by results_per_day)::numeric, 1)
                                                                     as median_results_per_day
from per_adm
group by admission_group, icu_care
order by lab_results desc;
