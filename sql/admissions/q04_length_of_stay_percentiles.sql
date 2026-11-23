-- =============================================================================
-- Query 04: Hospital length-of-stay distribution
-- Module: A. Patient and admission analytics
-- Business question: What is a typical hospital stay, and how long is the tail of long stays?
-- Metric: LOS in days: mean, standard deviation, P10, P25, median, P75, P90, P95, IQR; for all admissions, survivors only, and in-hospital deaths.
-- Output grain: One row per cohort (all, survivors, died in hospital).
-- Joins: None.
-- Denominator and exclusions: All admissions with a discharge time (no missing values in the demo). Deaths are split out because death truncates LOS.
-- Potential biases: LOS is right-skewed, so the median is the headline statistic; the mean is shown for completeness. Observation encounters shorten the distribution.
-- Expected output: cohort, admissions, mean_los, sd_los, p10..p95, iqr.
-- Techniques: UNION ALL of cohorts via LATERAL VALUES, ordered-set aggregates.
-- =============================================================================
with cohorts as (
    select c.cohort, f.los_days
    from marts.fact_admissions f
    cross join lateral (
        values ('All admissions'),
               (case when f.died_in_hospital then 'Died in hospital' else 'Discharged alive' end)
    ) as c(cohort)
    where f.los_days is not null
)
select
    cohort,
    count(*)                                                              as admissions,
    round(avg(los_days)::numeric, 2)                                      as mean_los_days,
    round(stddev_samp(los_days)::numeric, 2)                              as sd_los_days,
    round(percentile_cont(0.10) within group (order by los_days)::numeric, 2) as p10,
    round(percentile_cont(0.25) within group (order by los_days)::numeric, 2) as p25,
    round(percentile_cont(0.50) within group (order by los_days)::numeric, 2) as median,
    round(percentile_cont(0.75) within group (order by los_days)::numeric, 2) as p75,
    round(percentile_cont(0.90) within group (order by los_days)::numeric, 2) as p90,
    round(percentile_cont(0.95) within group (order by los_days)::numeric, 2) as p95,
    round((percentile_cont(0.75) within group (order by los_days)
         - percentile_cont(0.25) within group (order by los_days))::numeric, 2) as iqr
from cohorts
group by cohort
order by admissions desc;
