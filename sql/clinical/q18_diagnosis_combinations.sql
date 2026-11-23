-- =============================================================================
-- Query 18: Common diagnosis combinations (co-occurrence with lift)
-- Module: D. Clinical analytics
-- Business question: Which conditions are coded together on the same admission most often, and which pairs co-occur more than chance would predict?
-- Metric: For pairs of ICD codes on the same admission: admissions with both (support), support %, and lift = P(A and B) / (P(A) x P(B)). Pairs must co-occur on at least 15 admissions.
-- Output grain: One row per unordered code pair (top 15 by support).
-- Joins: Self-join of distinct (hadm_id, code) rows on hadm_id with a.code < b.code, so each unordered pair is counted once per admission.
-- Denominator and exclusions: All admissions with at least one coded diagnosis. ICD-9 and ICD-10 codes are kept separate (they are different code systems).
-- Potential biases: Common chronic codes (hypertension, hyperlipidemia) dominate support; lift corrects for base rates but is unstable for rare codes, hence the threshold. Co-occurrence is not causation or a clinical pathway.
-- Expected output: code_a, title_a, code_b, title_b, admissions_with_both, support_pct, lift.
-- Techniques: Self-join, DISTINCT pre-aggregation, CTE marginals, HAVING threshold.
-- =============================================================================
with dx as (
    select distinct hadm_id, icd_version || ':' || icd_code as code, diagnosis_title
    from marts.fact_diagnoses
),
n_adm as (
    select count(distinct hadm_id)::numeric as n from dx
),
marginal as (
    select code, max(diagnosis_title) as title, count(*) as n_code
    from dx group by code
),
pairs as (
    select a.code as code_a, b.code as code_b, count(*) as n_both
    from dx a
    join dx b on a.hadm_id = b.hadm_id and a.code < b.code
    group by a.code, b.code
    having count(*) >= 15
)
select
    p.code_a,
    left(ma.title, 60)                                               as title_a,
    p.code_b,
    left(mb.title, 60)                                               as title_b,
    p.n_both                                                         as admissions_with_both,
    round(100.0 * p.n_both / n.n, 1)                                 as support_pct,
    round((p.n_both / n.n) / ((ma.n_code / n.n) * (mb.n_code / n.n)), 2) as lift
from pairs p
join marginal ma on ma.code = p.code_a
join marginal mb on mb.code = p.code_b
cross join n_adm n
order by p.n_both desc, lift desc
limit 15;
