-- =============================================================================
-- Query 21: Hospital length of stay by admission category
-- Module: E. Operational analytics
-- Business question: Which admission categories have unusually long stays relative to the hospital-wide median?
-- Metric: Per admission group and type: admissions, mean/median/P75/P90 LOS, % of stays of 14+ days, and median LOS relative to the overall median (index = 1.0).
-- Output grain: One row per admission type, ordered within its admission group.
-- Joins: None; the overall median comes from a separate CTE that is cross-joined.
-- Denominator and exclusions: All admissions, including in-hospital deaths (which truncate LOS; see Query 04 for the survivor split).
-- Potential biases: Observation encounters are short by definition. Small types (n < 10) give unstable medians. LOS is influenced by discharge-destination availability, which this data does not capture.
-- Expected output: admission_group, admission_type, admissions, mean_los, median_los, p75_los, p90_los, pct_long_stay_14d, median_vs_overall.
-- Techniques: CTE, ordered-set aggregates, FILTER, ratio to an overall benchmark, window ordering.
-- =============================================================================
with overall as (
    select percentile_cont(0.5) within group (order by los_days) as overall_median
    from marts.fact_admissions
)
select
    f.admission_group,
    f.admission_type,
    count(*)                                                                as admissions,
    round(avg(f.los_days)::numeric, 2)                                      as mean_los_days,
    round(percentile_cont(0.5) within group (order by f.los_days)::numeric, 2) as median_los_days,
    round(percentile_cont(0.75) within group (order by f.los_days)::numeric, 2) as p75_los_days,
    round(percentile_cont(0.9) within group (order by f.los_days)::numeric, 2)  as p90_los_days,
    round(100.0 * count(*) filter (where f.los_days >= 14) / count(*), 1)   as pct_long_stay_14d,
    round((percentile_cont(0.5) within group (order by f.los_days) / max(o.overall_median))::numeric, 2)
                                                                            as median_vs_overall
from marts.fact_admissions f
cross join overall o
group by f.admission_group, f.admission_type
order by median_vs_overall desc;
