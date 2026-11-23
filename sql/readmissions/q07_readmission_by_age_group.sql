-- =============================================================================
-- Query 07: 30-day readmission rate by age group
-- Module: B. Readmission analytics
-- Business question: Do readmission rates differ across age groups, and are the differences larger than sampling noise?
-- Metric: Per age group (at index admission): eligible discharges, readmissions, rate, and Wilson score 95% confidence interval.
-- Output grain: One row per age group.
-- Joins: None (age_group is carried onto fact_readmissions from the index admission).
-- Denominator and exclusions: Eligible index discharges only (see Query 06).
-- Potential biases: Small cells give wide intervals, and overlapping intervals mean the data cannot distinguish the groups. Patients with many admissions contribute several index discharges, so observations are not independent and the CIs are optimistic.
-- Expected output: age_group, eligible_discharges, readmissions, rate_pct, ci95_low_pct, ci95_high_pct.
-- Techniques: CTE, FILTER, Wilson score interval computed in SQL.
-- =============================================================================
with counts as (
    select
        age_group,
        count(*)                                      as n,
        count(*) filter (where is_readmitted_30d)     as x
    from marts.fact_readmissions
    where is_eligible_index
    group by age_group
),
wilson as (
    select
        age_group, n, x,
        x::numeric / n                                as p,
        1.959964::numeric                             as z
    from counts
)
select
    age_group,
    n                                                 as eligible_discharges,
    x                                                 as readmissions,
    round(100 * p, 1)                                 as rate_pct,
    round(100 * ((p + z * z / (2 * n)) - z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)))
          / (1 + z * z / n), 1)                       as ci95_low_pct,
    round(100 * ((p + z * z / (2 * n)) + z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)))
          / (1 + z * z / n), 1)                       as ci95_high_pct
from wilson
order by age_group;
