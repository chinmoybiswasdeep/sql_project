-- =============================================================================
-- Query 20: Hospital mortality by diagnosis category
-- Module: D. Clinical analytics
-- Business question: Which principal-diagnosis groups carry the highest in-hospital mortality?
-- Metric: Per primary diagnosis category: admissions, in-hospital deaths, crude mortality %, Wilson 95% CI, and the median Charlson score as case-mix context. Categories with at least 10 admissions.
-- Output grain: One row per primary diagnosis category meeting the threshold.
-- Joins: None (primary category and Charlson score are pre-computed on fact_admissions).
-- Denominator and exclusions: All admissions in the category, including observation encounters.
-- Potential biases: Crude (unadjusted) rates; differences reflect severity and comorbidity, not quality of care. Very few deaths overall, so intervals are wide. The principal diagnosis is assigned at discharge.
-- Expected output: diagnosis_category, admissions, deaths, mortality_pct, ci95_low_pct, ci95_high_pct, median_charlson.
-- Techniques: Aggregation with HAVING, FILTER, Wilson interval, percentile_cont.
-- =============================================================================
with counts as (
    select
        primary_diagnosis_category                                   as diagnosis_category,
        count(*)                                                     as n,
        count(*) filter (where died_in_hospital)                     as x,
        percentile_cont(0.5) within group (order by charlson_comorbidity_score) as median_charlson
    from marts.fact_admissions
    group by primary_diagnosis_category
    having count(*) >= 10
),
s as (select *, x::numeric / n as p, 1.959964::numeric as z from counts)
select
    diagnosis_category,
    n                                                                as admissions,
    x                                                                as deaths,
    round(100 * p, 1)                                                as mortality_pct,
    round(100 * ((p + z * z / (2 * n)) - z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)))
          / (1 + z * z / n), 1)                                      as ci95_low_pct,
    round(100 * ((p + z * z / (2 * n)) + z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)))
          / (1 + z * z / n), 1)                                      as ci95_high_pct,
    median_charlson
from s
order by mortality_pct desc, admissions desc;
