-- Grain: one row per hospital admission (hadm_id).
--
-- The central fact for operational and outcome metrics. Every child table
-- (ICU stays, transfers, labs, diagnoses, procedures, prescriptions) is
-- aggregated to hadm_id in its own CTE *before* joining, so one-to-many joins
-- cannot inflate admission counts. The row_count_equals test enforces
-- rows(fact_admissions) = rows(stg_admissions).
with admissions as (
    select * from {{ ref('int_admissions_enriched') }}
),

icu as (
    select
        hadm_id,
        count(*)                                           as n_icu_stays,
        sum(icu_los_hours) / 24.0                          as icu_days_total,
        max(case when died_in_icu then 1 else 0 end) = 1   as died_in_icu
    from {{ ref('int_icu_stays_enriched') }}
    group by hadm_id
),

movements as (
    select
        hadm_id,
        sum(case when event_type = 'transfer' then 1 else 0 end) as n_transfer_events,
        sum(case when is_unit_change then 1 else 0 end)          as n_unit_changes,
        count(distinct care_unit)                                as n_distinct_care_units
    from {{ ref('int_transfers_sequenced') }}
    group by hadm_id
),

labs as (
    select
        hadm_id,
        count(*)                                           as n_lab_events,
        sum(case when flag_abnormal then 1 else 0 end)     as n_abnormal_lab_events,
        count(distinct itemid)                             as n_distinct_lab_tests
    from {{ ref('stg_labevents') }}
    where hadm_id is not null
    group by hadm_id
),

diagnoses as (
    select
        hadm_id,
        count(*)                                           as n_diagnoses,
        max(case when is_primary then diagnosis_category end) as primary_diagnosis_category,
        max(case when is_primary then icd_code end)        as primary_icd_code,
        max(case when is_primary then icd_version end)     as primary_icd_version
    from {{ ref('int_diagnoses_categorized') }}
    group by hadm_id
),

procedures as (
    select hadm_id, count(*) as n_procedures
    from {{ ref('stg_procedures_icd') }}
    group by hadm_id
),

prescriptions as (
    select
        hadm_id,
        count(*)                                           as n_prescriptions,
        count(distinct drug_name_normalized)               as n_distinct_drugs
    from {{ ref('stg_prescriptions') }}
    group by hadm_id
),

readmission as (
    select * from {{ ref('int_readmission_pairs') }}
),

-- admissions that *were* a 30-day readmission following an eligible index
was_readmission as (
    select next_hadm_id as hadm_id
    from readmission
    where is_readmitted_30d
)

select
    a.hadm_id,
    a.subject_id,
    a.admittime,
    a.dischtime,
    a.admission_type,
    a.admission_group,
    a.is_planned,
    a.is_observation,
    a.admission_location,
    a.discharge_location,
    a.insurance,
    a.race_group,
    a.sex,
    a.age_at_admission,
    a.age_group,
    a.is_age_top_coded,
    a.admission_seq,
    a.patient_total_admissions,
    a.los_hours,
    a.los_days,
    a.los_band,
    a.had_ed_visit,
    a.ed_los_hours,
    a.died_in_hospital,

    coalesce(icu.n_icu_stays, 0)                   as n_icu_stays,
    coalesce(icu.n_icu_stays, 0) > 0               as had_icu_stay,
    coalesce(icu.icu_days_total, 0)                as icu_days_total,
    coalesce(icu.died_in_icu, false)               as died_in_icu,

    coalesce(m.n_transfer_events, 0)               as n_transfer_events,
    coalesce(m.n_unit_changes, 0)                  as n_unit_changes,
    coalesce(m.n_distinct_care_units, 0)           as n_distinct_care_units,

    coalesce(l.n_lab_events, 0)                    as n_lab_events,
    coalesce(l.n_abnormal_lab_events, 0)           as n_abnormal_lab_events,
    coalesce(l.n_distinct_lab_tests, 0)            as n_distinct_lab_tests,

    coalesce(d.n_diagnoses, 0)                     as n_diagnoses,
    coalesce(d.primary_diagnosis_category, 'No coded diagnosis') as primary_diagnosis_category,
    d.primary_icd_code,
    d.primary_icd_version,
    coalesce(p.n_procedures, 0)                    as n_procedures,
    coalesce(rx.n_prescriptions, 0)                as n_prescriptions,
    coalesce(rx.n_distinct_drugs, 0)               as n_distinct_drugs,

    cci.charlson_comorbidity_score,
    cci.charlson_comorbidity_score + cci.charlson_age_score as charlson_age_adjusted_score,

    r.is_eligible_index                            as is_readmission_index_eligible,
    r.exclusion_reason                             as readmission_exclusion_reason,
    r.is_readmitted_30d,
    r.is_unplanned_readmitted_30d,
    r.days_to_next_admission,
    wr.hadm_id is not null                         as is_30d_readmission
from admissions a
left join icu                                 on icu.hadm_id = a.hadm_id
left join movements m                         on m.hadm_id = a.hadm_id
left join labs l                              on l.hadm_id = a.hadm_id
left join diagnoses d                         on d.hadm_id = a.hadm_id
left join procedures p                        on p.hadm_id = a.hadm_id
left join prescriptions rx                    on rx.hadm_id = a.hadm_id
left join {{ ref('int_charlson_comorbidity') }} cci on cci.hadm_id = a.hadm_id
left join readmission r                       on r.index_hadm_id = a.hadm_id
left join was_readmission wr                  on wr.hadm_id = a.hadm_id
