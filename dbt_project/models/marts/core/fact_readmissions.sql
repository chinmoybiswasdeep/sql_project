-- Grain: one row per hospital admission considered as a potential index
-- discharge (index_hadm_id). Filter is_eligible_index = true for the
-- readmission-rate denominator. Attributes describe the INDEX admission.
with pairs as (
    select * from {{ ref('int_readmission_pairs') }}
),

index_attributes as (
    select
        hadm_id, age_at_admission, age_group, sex, race_group, insurance,
        admission_group, los_days, primary_diagnosis_category,
        charlson_comorbidity_score, had_icu_stay, patient_total_admissions
    from {{ ref('fact_admissions') }}
)

select
    p.index_hadm_id,
    p.subject_id,
    p.index_admittime,
    p.index_dischtime,
    p.index_admission_type,
    p.index_is_observation,
    p.discharge_location,
    p.is_eligible_index,
    p.exclusion_reason,
    p.is_last_observed_admission,
    p.next_hadm_id,
    p.next_admittime,
    p.next_admission_type,
    p.next_is_planned,
    p.next_is_observation,
    p.days_to_next_admission,
    p.is_readmitted_30d,
    p.is_unplanned_readmitted_30d,
    p.is_readmitted_within_24h,
    ia.age_at_admission,
    ia.age_group,
    ia.sex,
    ia.race_group,
    ia.insurance,
    ia.admission_group                             as index_admission_group,
    ia.los_days                                    as index_los_days,
    ia.primary_diagnosis_category                  as index_primary_diagnosis_category,
    ia.charlson_comorbidity_score                  as index_charlson_score,
    ia.had_icu_stay                                as index_had_icu_stay,
    ia.patient_total_admissions
from pairs p
inner join index_attributes ia on ia.hadm_id = p.index_hadm_id
