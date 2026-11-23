-- =============================================================================
-- Query 24: ICU utilization among patients with repeated admissions
-- Module: E. Operational analytics
-- Business question: Do frequently admitted patients use the ICU more per admission, and does ICU use change across a patient's successive admissions?
-- Metric: Per patient admission-frequency band and admission sequence position (1st, 2nd-3rd, 4th+): admissions, % with ICU care, ICU days per admission, ICU days per ICU admission.
-- Output grain: One row per (frequency band, sequence position).
-- Joins: fact_admissions to dim_patient on subject_id (many-to-one) for the frequency band.
-- Denominator and exclusions: All admissions.
-- Potential biases: Strong selection effect: every demo patient had at least one ICU stay, so a single-admission patient's only admission includes ICU care by construction. This query mainly shows how that selection dilutes across repeat admissions; full-dataset validation is needed before drawing operational conclusions.
-- Expected output: admission_frequency_band, sequence_position, admissions, pct_with_icu, icu_days_per_admission, icu_days_per_icu_admission.
-- Techniques: Join to dimension, CASE bucketing of a window-derived sequence (admission_seq from ROW_NUMBER upstream), FILTER, NULLIF.
-- =============================================================================
select
    p.admission_frequency_band,
    case
        when f.admission_seq = 1 then '1st admission'
        when f.admission_seq <= 3 then '2nd-3rd admission'
        else '4th+ admission'
    end                                                                    as sequence_position,
    count(*)                                                               as admissions,
    round(100.0 * count(*) filter (where f.had_icu_stay) / count(*), 1)    as pct_with_icu,
    round((sum(f.icu_days_total) / count(*))::numeric, 2)                  as icu_days_per_admission,
    round((sum(f.icu_days_total) / nullif(count(*) filter (where f.had_icu_stay), 0))::numeric, 2)
                                                                           as icu_days_per_icu_admission
from marts.fact_admissions f
join marts.dim_patient p on p.subject_id = f.subject_id
group by p.admission_frequency_band, 2
order by p.admission_frequency_band, min(f.admission_seq);
