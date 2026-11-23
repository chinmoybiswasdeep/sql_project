-- Grain: one row per hospital admission (hadm_id).
-- Adds patient demographics, derived age, admission grouping and the
-- admission's position in the patient's history.
--
-- Age: MIMIC shifts dates per patient and publishes anchor_age at anchor_year.
-- Age at admission = anchor_age + (year(admittime) - anchor_year). Patients
-- older than 89 are top-coded (anchor_age = 91), so their derived age is a
-- floor, not an exact value; they all fall in the 80+ band.
with admissions as (
    select * from {{ ref('stg_admissions') }}
),

patients as (
    select * from {{ ref('stg_patients') }}
),

admission_types as (
    select * from {{ ref('admission_type_groups') }}
),

joined as (
    select
        a.hadm_id,
        a.subject_id,
        a.admittime,
        a.dischtime,
        a.deathtime,
        a.admission_type,
        coalesce(t.admission_group, 'Unmapped')    as admission_group,
        coalesce(t.is_planned, false)              as is_planned,
        coalesce(t.is_observation, false)          as is_observation,
        a.admission_location,
        a.discharge_location,
        a.insurance,
        a.race_group,
        a.marital_status,
        a.language,
        p.sex,
        p.anchor_age + ({{ year_of('a.admittime') }} - p.anchor_year) as age_at_admission,
        p.is_age_top_coded,
        p.date_of_death,
        a.died_in_hospital,
        a.los_hours,
        a.los_hours / 24.0                         as los_days,
        a.edregtime is not null                    as had_ed_visit,
        a.ed_los_hours
    from admissions a
    inner join patients p on p.subject_id = a.subject_id
    left join admission_types t on t.admission_type = a.admission_type
)

select
    joined.*,
    {{ age_group('age_at_admission') }}            as age_group,
    {{ los_band('los_days') }}                     as los_band,
    row_number() over (
        partition by subject_id order by admittime, hadm_id
    )                                              as admission_seq,
    count(*) over (partition by subject_id)        as patient_total_admissions
from joined
