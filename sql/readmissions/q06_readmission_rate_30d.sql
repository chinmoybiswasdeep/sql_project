-- =============================================================================
-- Query 06: 30-day all-cause readmission rate (with denominator funnel)
-- Module: B. Readmission analytics
-- Business question: What share of eligible discharges return to this hospital within 30 days, and how is the denominator built?
-- Metric: Readmission rate = eligible index discharges followed by any admission within 30 days / eligible index discharges. Also the unplanned rate (next admission not elective/same-day surgical) and returns within 24 hours.
-- Output grain: One row per funnel step, ending with the rate rows.
-- Joins: None. fact_readmissions pairs each admission with the patient's next admission using LEAD in int_readmission_pairs.
-- Denominator and exclusions: All admissions minus in-hospital deaths, transfers to another acute hospital, discharges against medical advice, overlapping next admissions and missing discharge times.
-- Potential biases: Only returns to this hospital are visible, so the true rate is understated. There is no per-patient follow-up end date, so late discharges cannot be censored. "Unplanned" is not "preventable": no validated preventability algorithm is applied. The ICU-only demo cohort inflates the rate relative to a general population.
-- Expected output: step, admissions, pct_of_all_admissions; final rows hold the numerator, rate and the unplanned and 24-hour counts.
-- Techniques: CTE, conditional aggregation (FILTER), UNION ALL funnel, ordering by step number.
-- =============================================================================
with base as (
    select * from marts.fact_readmissions
),
totals as (
    select count(*) as all_admissions from base
),
funnel as (
    select 1 as step_no, 'All admissions' as step, count(*) as admissions from base
    union all
    select 2, 'Excluded: ' || exclusion_reason, -count(*)
    from base where exclusion_reason is not null group by exclusion_reason
    union all
    select 3, 'Eligible index discharges (denominator)', count(*) filter (where is_eligible_index) from base
    union all
    select 4, 'Readmitted within 30 days, all-cause (numerator)', count(*) filter (where is_readmitted_30d) from base
    union all
    select 5, '  of which unplanned', count(*) filter (where is_unplanned_readmitted_30d) from base
    union all
    select 6, '  of which within 24 hours', count(*) filter (where is_readmitted_within_24h) from base
)
select
    f.step,
    f.admissions,
    round(100.0 * abs(f.admissions) / t.all_admissions, 1) as pct_of_all_admissions,
    case f.step_no
        when 4 then round(100.0 * f.admissions / nullif((select count(*) filter (where is_eligible_index) from base), 0), 1)
        when 5 then round(100.0 * f.admissions / nullif((select count(*) filter (where is_eligible_index) from base), 0), 1)
        when 6 then round(100.0 * f.admissions / nullif((select count(*) filter (where is_eligible_index) from base), 0), 1)
    end                                                    as rate_pct_of_eligible
from funnel f
cross join totals t
order by f.step_no, f.admissions;
