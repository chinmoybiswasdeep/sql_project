-- =============================================================================
-- Query 16: Most frequent laboratory tests
-- Module: D. Clinical analytics
-- Business question: Which laboratory tests account for most lab volume, and how widely are they used across admissions?
-- Metric: Per lab test (itemid): measurements, share of admission-linked lab volume, cumulative share, admissions with at least one result, % of all admissions. Top 20 by volume.
-- Output grain: One row per lab test (top 20).
-- Joins: fact_lab_events to dim_lab_test on itemid (many-to-one; volumes are counted before the join, so no inflation).
-- Denominator and exclusions: Admission-linked measurements only (hadm_id not null); outpatient draws are excluded. % of admissions uses all admissions.
-- Potential biases: Panels (for example a basic metabolic panel) produce several itemids per draw, so counts are results, not orders or blood draws.
-- Expected output: volume_rank, lab_test_name, fluid, lab_category, measurements, pct_of_volume, cumulative_pct, admissions_tested, pct_admissions_tested.
-- Techniques: CTE pre-aggregation, ROW_NUMBER, running window SUM, COUNT DISTINCT.
-- =============================================================================
with volume as (
    select
        itemid,
        count(*)                     as measurements,
        count(distinct hadm_id)      as admissions_tested
    from marts.fact_lab_events
    where is_admission_linked
    group by itemid
),
ranked as (
    select
        v.*,
        row_number() over (order by v.measurements desc, v.itemid)                     as volume_rank,
        100.0 * v.measurements / sum(v.measurements) over ()                          as pct_of_volume,
        100.0 * sum(v.measurements) over (order by v.measurements desc, v.itemid
                                          rows between unbounded preceding and current row)
              / sum(v.measurements) over ()                                           as cumulative_pct
    from volume v
)
select
    r.volume_rank,
    d.lab_test_name,
    d.fluid,
    d.lab_category,
    r.measurements,
    round(r.pct_of_volume, 2)                                                         as pct_of_volume,
    round(r.cumulative_pct, 1)                                                        as cumulative_pct,
    r.admissions_tested,
    round(100.0 * r.admissions_tested / (select count(*) from marts.fact_admissions), 1)
                                                                                      as pct_admissions_tested
from ranked r
join marts.dim_lab_test d on d.itemid = r.itemid
where r.volume_rank <= 20
order by r.volume_rank;
