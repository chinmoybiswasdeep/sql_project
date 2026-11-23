-- =============================================================================
-- Query 17: Abnormal laboratory result frequency by test type
-- Module: D. Clinical analytics
-- Business question: Which high-volume tests most often return abnormal results, and in which direction?
-- Metric: For tests with at least 500 results: % flagged abnormal by the laboratory; % below and above the row's own reference range; agreement between the lab flag and the range comparison.
-- Output grain: One row per lab test meeting the volume threshold (top 20 by abnormal %).
-- Joins: fact_lab_events to dim_lab_test (many-to-one) after aggregation.
-- Denominator and exclusions: All results for the test (inpatient and outpatient) for the flag rate. The range-based rates use only results with a numeric value and both reference bounds.
-- Potential biases: Reference ranges vary by lab, assay, sex and era, and some tests have none (for example blood gases, where the flag may be absent). An abnormal value is a measurement property, NOT a diagnosis. Sick patients are tested more often, so results over-represent abnormal states.
-- Expected output: lab_test_name, fluid, results, pct_flag_abnormal, range_evaluable, pct_low, pct_high, pct_flag_range_agreement.
-- Techniques: Conditional aggregation (FILTER), HAVING, NULLIF-guarded ratios, ORDER BY with LIMIT.
-- =============================================================================
select
    d.lab_test_name,
    d.fluid,
    count(*)                                                                as results,
    round(100.0 * count(*) filter (where l.flag_abnormal) / count(*), 1)    as pct_flag_abnormal,
    count(l.range_direction)                                                as range_evaluable,
    round(100.0 * count(*) filter (where l.range_direction = 'low')
          / nullif(count(l.range_direction), 0), 1)                         as pct_low,
    round(100.0 * count(*) filter (where l.range_direction = 'high')
          / nullif(count(l.range_direction), 0), 1)                         as pct_high,
    round(100.0 * count(*) filter (
              where l.range_direction is not null
                and l.flag_abnormal = (l.range_direction <> 'normal'))
          / nullif(count(l.range_direction), 0), 1)                         as pct_flag_range_agreement
from marts.fact_lab_events l
join marts.dim_lab_test d on d.itemid = l.itemid
group by d.lab_test_name, d.fluid
having count(*) >= 500
order by pct_flag_abnormal desc, results desc
limit 20;
