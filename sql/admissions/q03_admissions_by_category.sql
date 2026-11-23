-- =============================================================================
-- Query 03: Admission distribution by admission category
-- Module: A. Patient and admission analytics
-- Business question: What mix of emergency, urgent, elective and observation encounters does the hospital handle, and through which entry points?
-- Metric: Admissions and share by admission group and type; share within group; % arriving with an ED visit; most common admission location per type.
-- Output grain: One row per admission_type (with its admission_group).
-- Joins: None for counts; a ranked CTE finds the modal admission_location per type.
-- Denominator and exclusions: All admissions. Observation encounters are kept but labelled, because they are not inpatient admissions in billing terms.
-- Potential biases: admission_type reflects registration workflow, not clinical acuity.
-- Expected output: admission_group, admission_type, admissions, pct_of_total, pct_within_group, pct_with_ed_visit, top_admission_location.
-- Techniques: CTE, window functions (SUM OVER PARTITION, ROW_NUMBER), conditional aggregation.
-- =============================================================================
with by_type as (
    select
        admission_group,
        admission_type,
        count(*)                                                 as admissions,
        count(*) filter (where had_ed_visit)                     as with_ed_visit
    from marts.fact_admissions
    group by admission_group, admission_type
),
location_rank as (
    select
        admission_type,
        admission_location,
        row_number() over (partition by admission_type order by count(*) desc, admission_location) as rn
    from marts.fact_admissions
    group by admission_type, admission_location
)
select
    t.admission_group,
    t.admission_type,
    t.admissions,
    round(100.0 * t.admissions / sum(t.admissions) over (), 1)                          as pct_of_total,
    round(100.0 * t.admissions / sum(t.admissions) over (partition by t.admission_group), 1)
                                                                                         as pct_within_group,
    round(100.0 * t.with_ed_visit / t.admissions, 1)                                    as pct_with_ed_visit,
    l.admission_location                                                                as top_admission_location
from by_type t
left join location_rank l on l.admission_type = t.admission_type and l.rn = 1
order by sum(t.admissions) over (partition by t.admission_group) desc, t.admissions desc;
