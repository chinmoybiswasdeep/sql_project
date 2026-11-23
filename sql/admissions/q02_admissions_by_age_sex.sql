-- =============================================================================
-- Query 02: Admission distribution by age group and sex
-- Module: A. Patient and admission analytics
-- Business question: Which demographic segments generate the most admissions, and how does the mix compare with the patient mix?
-- Metric: Admissions, distinct patients, share of all admissions, admissions per patient, per age group x sex with subtotals.
-- Output grain: One row per (age_group, sex), plus ROLLUP subtotals per age group and a grand total.
-- Joins: None (age and sex are denormalised onto fact_admissions from int_admissions_enriched).
-- Denominator and exclusions: All admissions. Age is age at admission, so one patient can appear in two age groups across admissions.
-- Potential biases: Ages above 89 are top-coded by MIMIC (all in 80+). The demo's ICU-only sampling skews older.
-- Expected output: age_group, sex, admissions, patients, pct_of_admissions, admissions_per_patient; subtotal rows labelled 'All'.
-- Techniques: GROUP BY ROLLUP, GROUPING(), scalar subquery for the grand-total denominator.
-- =============================================================================
select
    case when grouping(age_group) = 1 then 'All' else age_group end   as age_group,
    case when grouping(sex) = 1 then 'All' else sex end               as sex,
    count(*)                                                          as admissions,
    count(distinct subject_id)                                        as patients,
    round(100.0 * count(*) / (select count(*) from marts.fact_admissions), 1)
                                                                      as pct_of_admissions,
    round(count(*)::numeric / count(distinct subject_id), 2)          as admissions_per_patient
from marts.fact_admissions
group by rollup (age_group, sex)
order by grouping(age_group), age_group, grouping(sex), sex;
