-- =============================================================================
-- Query 15: ICU mortality by patient group
-- Module: C. ICU analytics
-- Business question: How does mortality during ICU care vary by age group, sex and ICU type?
-- Metric: ICU stays, deaths during the ICU stay (death within intime and outtime + 6h), ICU mortality %, and hospital mortality % for the same stays; with Wilson 95% CI for ICU mortality.
-- Output grain: One row per grouping set: age group, sex, first ICU unit type... plus an overall row (GROUPING SETS).
-- Joins: None (demographics and death flags are carried onto fact_icu_stays).
-- Denominator and exclusions: All ICU stays. A patient with several stays contributes several denominators.
-- Potential biases: Unadjusted for severity (no illness-severity score is computed), so differences reflect case-mix. Very small groups.
-- Expected output: dimension, dimension_value, icu_stays, icu_deaths, icu_mortality_pct, ci95_low_pct, ci95_high_pct, hospital_mortality_pct.
-- Techniques: GROUPING SETS, GROUPING() labelling, FILTER, Wilson interval.
-- =============================================================================
with grouped as (
    select
        case
            when grouping(age_group) = 0 then 'Age group'
            when grouping(sex) = 0 then 'Sex'
            when grouping(first_careunit) = 0 then 'First ICU unit'
            else 'Overall'
        end                                                as dimension,
        coalesce(age_group, sex, first_careunit, 'All ICU stays') as dimension_value,
        count(*)                                           as n,
        count(*) filter (where died_in_icu)                as x,
        count(*) filter (where died_in_hospital)           as hosp_deaths
    from marts.fact_icu_stays
    group by grouping sets ((age_group), (sex), (first_careunit), ())
)
select
    dimension,
    dimension_value,
    n                                                      as icu_stays,
    x                                                      as icu_deaths,
    round(100.0 * x / n, 1)                                as icu_mortality_pct,
    round(100 * ((x::numeric / n + 1.920729 / n)
        - 1.959964 * sqrt((x::numeric / n) * (1 - x::numeric / n) / n + 0.960365 / (n * n)))
        / (1 + 3.841459 / n), 1)                           as ci95_low_pct,
    round(100 * ((x::numeric / n + 1.920729 / n)
        + 1.959964 * sqrt((x::numeric / n) * (1 - x::numeric / n) / n + 0.960365 / (n * n)))
        / (1 + 3.841459 / n), 1)                           as ci95_high_pct,
    round(100.0 * hosp_deaths / n, 1)                      as hospital_mortality_pct
from grouped
order by
    array_position(array['Overall', 'Age group', 'Sex', 'First ICU unit'], dimension),
    icu_stays desc;
