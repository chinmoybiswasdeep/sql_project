-- =============================================================================
-- Query 05: Top diagnosis categories associated with admissions
-- Module: A. Patient and admission analytics
-- Business question: Which clinical areas drive admissions, both as the principal reason and as any coded condition?
-- Metric: Per harmonised ICD chapter: admissions where it is the primary (seq_num = 1) diagnosis, admissions with it anywhere, and each as a % of all admissions.
-- Output grain: One row per diagnosis category.
-- Joins: fact_diagnoses aggregated to (category, hadm_id) with DISTINCT before counting, so an admission with several codes in one chapter counts once.
-- Denominator and exclusions: All admissions (a few may have no coded diagnosis).
-- Potential biases: Billing codes reflect documentation and reimbursement practice. ICD-9 and ICD-10 eras are pooled at chapter level, which hides code-level changes. 'Health status & services contact' (V/Z codes) captures history and status, not acute reasons.
-- Expected output: diagnosis_category, primary_admissions, pct_primary, rank_primary, any_admissions, pct_any.
-- Techniques: CTEs, COUNT DISTINCT, DENSE_RANK, FULL OUTER JOIN.
-- =============================================================================
with total as (
    select count(*) as n from marts.fact_admissions
),
primary_dx as (
    select diagnosis_category, count(*) as primary_admissions
    from marts.fact_diagnoses
    where is_primary
    group by diagnosis_category
),
any_dx as (
    select diagnosis_category, count(distinct hadm_id) as any_admissions
    from marts.fact_diagnoses
    group by diagnosis_category
)
select
    coalesce(p.diagnosis_category, a.diagnosis_category)               as diagnosis_category,
    coalesce(p.primary_admissions, 0)                                  as primary_admissions,
    round(100.0 * coalesce(p.primary_admissions, 0) / t.n, 1)          as pct_primary,
    dense_rank() over (order by coalesce(p.primary_admissions, 0) desc) as rank_primary,
    a.any_admissions,
    round(100.0 * a.any_admissions / t.n, 1)                           as pct_any
from primary_dx p
full outer join any_dx a on a.diagnosis_category = p.diagnosis_category
cross join total t
order by primary_admissions desc, any_admissions desc;
