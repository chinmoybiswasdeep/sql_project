-- =============================================================================
-- Query 09: Time between discharge and next hospital admission
-- Module: B. Readmission analytics
-- Business question: When patients come back, how soon do they return? Is the 30-day window capturing most early returns?
-- Metric: Distribution of days from discharge to the next admission, in clinically meaningful buckets, with cumulative share; plus percentiles.
-- Output grain: One row per time bucket.
-- Joins: None. days_to_next_admission comes from the LEAD-based pairing in int_readmission_pairs.
-- Denominator and exclusions: Admissions discharged alive that have a later admission (any eligibility status except in-hospital death). Last-observed admissions have no next admission and are excluded.
-- Potential biases: Returns to other hospitals are invisible. Long gaps are truncated by the end of each patient's observable history.
-- Expected output: gap_bucket, next_admissions, pct, cumulative_pct, plus median and p25/p75 repeated on each row for reference.
-- Techniques: CASE bucketing, window SUM for the cumulative distribution, ordered-set aggregates in a CTE.
-- =============================================================================
with gaps as (
    select days_to_next_admission as d
    from marts.fact_readmissions
    where next_hadm_id is not null
      and coalesce(exclusion_reason, '') <> 'died_in_hospital'
      and days_to_next_admission >= 0
),
bucketed as (
    select
        case
            when d < 1   then 1
            when d <= 7  then 2
            when d <= 14 then 3
            when d <= 30 then 4
            when d <= 90 then 5
            when d <= 180 then 6
            when d <= 365 then 7
            else 8
        end as bucket_no,
        d
    from gaps
),
pctl as (
    select
        percentile_cont(0.25) within group (order by d) as p25,
        percentile_cont(0.50) within group (order by d) as p50,
        percentile_cont(0.75) within group (order by d) as p75
    from gaps
)
select
    (array['<1 day', '1-7 days', '8-14 days', '15-30 days', '31-90 days',
           '91-180 days', '181-365 days', '>365 days'])[bucket_no] as gap_bucket,
    count(*)                                                   as next_admissions,
    round(100.0 * count(*) / sum(count(*)) over (), 1)         as pct,
    round(100.0 * sum(count(*)) over (order by bucket_no) / sum(count(*)) over (), 1)
                                                               as cumulative_pct,
    round(max(p.p25)::numeric, 1)                              as overall_p25_days,
    round(max(p.p50)::numeric, 1)                              as overall_median_days,
    round(max(p.p75)::numeric, 1)                              as overall_p75_days
from bucketed
cross join pctl p
group by bucket_no
order by bucket_no;
