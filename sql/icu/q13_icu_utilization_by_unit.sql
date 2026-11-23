-- =============================================================================
-- Query 13: ICU utilization by care unit
-- Module: C. ICU analytics
-- Business question: Which ICUs absorb the most ICU stays and ICU days, and how do their stay lengths compare?
-- Metric: Per first ICU care unit: stays, distinct patients, total ICU days, share of all ICU days, mean and median ICU LOS, % of stays that moved to a different ICU unit.
-- Output grain: One row per first ICU care unit.
-- Joins: None.
-- Denominator and exclusions: All ICU stays, attributed to their first care unit.
-- Potential biases: This is utilisation (ICU days consumed), NOT occupancy: no bed-capacity data exists, so no occupancy % is computed. Attribution to the first unit ignores later moves.
-- Expected output: first_careunit, stays, patients, icu_days, pct_icu_days, mean_los_days, median_los_days, pct_changed_unit, utilization_rank.
-- Techniques: Aggregation, window share, DENSE_RANK, FILTER, percentile_cont.
-- =============================================================================
select
    first_careunit,
    count(*)                                                               as stays,
    count(distinct subject_id)                                             as patients,
    round(sum(icu_los_days)::numeric, 1)                                   as icu_days,
    round((100.0 * sum(icu_los_days) / sum(sum(icu_los_days)) over ())::numeric, 1)
                                                                           as pct_icu_days,
    round(avg(icu_los_days)::numeric, 2)                                   as mean_los_days,
    round(percentile_cont(0.5) within group (order by icu_los_days)::numeric, 2)
                                                                           as median_los_days,
    round(100.0 * count(*) filter (where changed_icu_unit) / count(*), 1)  as pct_changed_unit,
    dense_rank() over (order by sum(icu_los_days) desc)                    as utilization_rank
from marts.fact_icu_stays
group by first_careunit
order by utilization_rank;
