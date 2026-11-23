-- =============================================================================
-- Query 12: ICU length-of-stay distribution
-- Module: C. ICU analytics
-- Business question: How long do ICU stays last, and what share of ICU days comes from long stays?
-- Metric: ICU LOS bands: stays, % of stays, cumulative % of stays, ICU days, % of all ICU days; and overall percentiles.
-- Output grain: One row per ICU LOS band.
-- Joins: None.
-- Denominator and exclusions: All ICU stays (icustays). Stays that start before the formal admission time are kept (flagged in fact_icu_stays).
-- Potential biases: ICU LOS ends at ICU discharge or death. A few long stays dominate the total of ICU days.
-- Expected output: icu_los_band, stays, pct_stays, cumulative_pct_stays, icu_days, pct_icu_days, plus overall median/p90.
-- Techniques: CTE, window running SUM, share of total, ordered-set aggregates.
-- =============================================================================
with stays as (
    select
        icu_los_days,
        icu_los_band,
        case icu_los_band
            when '<1 day' then 1 when '1-2 days' then 2 when '3-6 days' then 3
            when '7-13 days' then 4 when '14+ days' then 5 else 6 end as band_order
    from marts.fact_icu_stays
),
overall as (
    select
        percentile_cont(0.5) within group (order by icu_los_days) as median_days,
        percentile_cont(0.9) within group (order by icu_los_days) as p90_days
    from stays
)
select
    s.icu_los_band,
    count(*)                                                               as stays,
    round(100.0 * count(*) / sum(count(*)) over (), 1)                     as pct_stays,
    round(100.0 * sum(count(*)) over (order by s.band_order) / sum(count(*)) over (), 1)
                                                                           as cumulative_pct_stays,
    round(sum(s.icu_los_days)::numeric, 1)                                 as icu_days,
    round((100.0 * sum(s.icu_los_days) / sum(sum(s.icu_los_days)) over ())::numeric, 1)
                                                                           as pct_icu_days,
    round(max(o.median_days)::numeric, 2)                                  as overall_median_icu_days,
    round(max(o.p90_days)::numeric, 2)                                     as overall_p90_icu_days
from stays s
cross join overall o
group by s.icu_los_band, s.band_order
order by s.band_order;
