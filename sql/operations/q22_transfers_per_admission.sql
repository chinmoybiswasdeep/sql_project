-- =============================================================================
-- Query 22: Transfer frequency per admission
-- Module: E. Operational analytics
-- Business question: How often are patients moved between care units during a stay, which admission types move most, and do more moves go with longer stays?
-- Metric: Per admission group: admissions, mean and median care-unit changes, % with 3+ changes, mean distinct units visited, and the Pearson and Spearman-style (rank) correlation between unit changes and LOS.
-- Output grain: One row per admission group, plus an overall row (GROUPING SETS).
-- Joins: None. n_unit_changes is pre-aggregated per hadm_id in fact_admissions from fact_care_transfers.
-- Denominator and exclusions: All admissions. A unit change means the care unit differs from the previous movement; bed moves within one unit do not count. ED to inpatient-unit moves count as a change.
-- Potential biases: Correlation with LOS is mechanical in part (longer stays give more chances to move) and does not show that transfers lengthen stays.
-- Expected output: admission_group, admissions, mean_unit_changes, median_unit_changes, pct_3plus_changes, mean_distinct_units, corr_changes_los, rank_corr_changes_los.
-- Techniques: GROUPING SETS, corr() aggregate, rank-transformed correlation via window RANK, FILTER.
-- =============================================================================
with ranked as (
    select
        admission_group,
        n_unit_changes,
        n_distinct_care_units,
        los_days,
        rank() over (order by n_unit_changes) as r_changes,
        rank() over (order by los_days)       as r_los
    from marts.fact_admissions
)
select
    coalesce(admission_group, 'All admissions')                          as admission_group,
    count(*)                                                             as admissions,
    round(avg(n_unit_changes), 2)                                        as mean_unit_changes,
    percentile_cont(0.5) within group (order by n_unit_changes)          as median_unit_changes,
    round(100.0 * count(*) filter (where n_unit_changes >= 3) / count(*), 1) as pct_3plus_changes,
    round(avg(n_distinct_care_units), 2)                                 as mean_distinct_units,
    round(corr(n_unit_changes, los_days)::numeric, 2)                    as corr_changes_los,
    round(corr(r_changes, r_los)::numeric, 2)                            as rank_corr_changes_los
from ranked
group by grouping sets ((admission_group), ())
order by grouping(admission_group), admissions desc;
