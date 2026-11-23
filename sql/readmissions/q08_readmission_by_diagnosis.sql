-- =============================================================================
-- Query 08: 30-day readmission rate by primary diagnosis category
-- Module: B. Readmission analytics
-- Business question: Which clinical areas (by principal diagnosis of the index stay) have the highest readmission rates?
-- Metric: Per primary diagnosis category of the index admission: eligible discharges, readmissions, rate, Wilson 95% CI, rank. Only categories with at least 10 eligible discharges are shown.
-- Output grain: One row per diagnosis category passing the volume threshold.
-- Joins: None (index_primary_diagnosis_category is carried onto fact_readmissions).
-- Denominator and exclusions: Eligible index discharges; categories below 10 discharges are suppressed by HAVING to avoid unstable rates.
-- Potential biases: Chapter-level categories are coarse. Small samples give wide CIs, so a high rank does not by itself show a real difference. Repeat patients cluster within categories.
-- Expected output: diagnosis_category, eligible_discharges, readmissions, rate_pct, ci95_low_pct, ci95_high_pct, rate_rank.
-- Techniques: CTE, GROUP BY with HAVING, RANK, Wilson interval.
-- =============================================================================
with counts as (
    select
        index_primary_diagnosis_category              as diagnosis_category,
        count(*)                                      as n,
        count(*) filter (where is_readmitted_30d)     as x
    from marts.fact_readmissions
    where is_eligible_index
    group by index_primary_diagnosis_category
    having count(*) >= 10
),
stats as (
    select *, x::numeric / n as p, 1.959964::numeric as z from counts
)
select
    diagnosis_category,
    n                                                 as eligible_discharges,
    x                                                 as readmissions,
    round(100 * p, 1)                                 as rate_pct,
    round(100 * ((p + z * z / (2 * n)) - z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)))
          / (1 + z * z / n), 1)                       as ci95_low_pct,
    round(100 * ((p + z * z / (2 * n)) + z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)))
          / (1 + z * z / n), 1)                       as ci95_high_pct,
    rank() over (order by p desc)                     as rate_rank
from stats
order by rate_rank, n desc;
