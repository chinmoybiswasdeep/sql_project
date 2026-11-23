-- =============================================================================
-- Query 25: Cohort-level resource utilization (observable proxies)
-- Module: E. Operational analytics
-- Business question: How does use of observable hospital resources scale with comorbidity burden?
-- Metric: Per Charlson comorbidity band: admissions, and per admission: mean LOS days, ICU days, lab results, therapeutic medication orders, procedures, care-unit changes. Each mean is also shown as an index relative to the all-admission mean (1.00 = average).
-- Output grain: One row per Charlson band (0, 1-2, 3-4, 5+).
-- Joins: None. All proxies are pre-aggregated per hadm_id in fact_admissions.
-- Denominator and exclusions: All admissions. Proxies are COUNTS OF OBSERVED EVENTS, not costs: no charges, prices or staffing data exist in MIMIC, and an event count must not be read as a dollar amount.
-- Potential biases: Charlson is derived from discharge codes, so it partly reflects what happened during the stay (longer stays accumulate more codes), which inflates the association. Medication orders include all drug types here.
-- Expected output: charlson_band, admissions, mean_los_days, mean_icu_days, mean_lab_results, mean_med_orders, mean_procedures, mean_unit_changes, and *_index columns.
-- Techniques: CTE, CASE banding, cross join to overall means, ratio indexing.
-- =============================================================================
with banded as (
    select
        case
            when charlson_comorbidity_score = 0 then '0'
            when charlson_comorbidity_score <= 2 then '1-2'
            when charlson_comorbidity_score <= 4 then '3-4'
            else '5+'
        end                                         as charlson_band,
        los_days, icu_days_total, n_lab_events, n_prescriptions, n_procedures, n_unit_changes
    from marts.fact_admissions
),
overall as (
    select avg(los_days) as los, avg(icu_days_total) as icu, avg(n_lab_events) as lab,
           avg(n_prescriptions) as rx, avg(n_procedures) as px, avg(n_unit_changes) as moves
    from banded
)
select
    b.charlson_band,
    count(*)                                                  as admissions,
    round(avg(b.los_days)::numeric, 2)                        as mean_los_days,
    round(avg(b.icu_days_total)::numeric, 2)                  as mean_icu_days,
    round(avg(b.n_lab_events), 1)                             as mean_lab_results,
    round(avg(b.n_prescriptions), 1)                          as mean_med_orders,
    round(avg(b.n_procedures), 2)                             as mean_procedures,
    round(avg(b.n_unit_changes), 2)                           as mean_unit_changes,
    round((avg(b.los_days) / max(o.los))::numeric, 2)         as los_index,
    round((avg(b.icu_days_total) / max(o.icu))::numeric, 2)   as icu_index,
    round(avg(b.n_lab_events) / max(o.lab), 2)                as lab_index,
    round(avg(b.n_prescriptions) / max(o.rx), 2)              as med_index
from banded b
cross join overall o
group by b.charlson_band
order by b.charlson_band;
