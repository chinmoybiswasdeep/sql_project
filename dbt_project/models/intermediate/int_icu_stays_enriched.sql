-- Grain: one row per ICU stay (stay_id).
--
-- ICU death: the admission's deathtime falls between ICU intime and
-- outtime + icu_death_grace_hours. In MIMIC the recorded outtime often lags
-- the death by a few hours (time until the patient physically leaves), and
-- occasionally precedes it slightly, hence the grace period. Hospital death
-- among ICU patients is reported separately (died_in_hospital).
--
-- ICU stays can begin before the formal admittime (ED/OR time recorded under
-- the stay); these are flagged, not removed.
with icu as (
    select * from {{ ref('stg_icustays') }}
),

admissions as (
    select * from {{ ref('int_admissions_enriched') }}
),

unit_types as (
    select * from {{ ref('care_unit_types') }}
)

select
    i.stay_id,
    i.hadm_id,
    i.subject_id,
    i.first_careunit,
    i.last_careunit,
    coalesce(ut.unit_type, 'Unclassified')         as first_unit_type,
    i.first_careunit <> i.last_careunit            as changed_icu_unit,
    i.intime,
    i.outtime,
    i.icu_los_hours,
    i.icu_los_hours / 24.0                         as icu_los_days,
    i.icu_los_days_source,
    row_number() over (partition by i.hadm_id order by i.intime, i.stay_id)
                                                   as icu_stay_seq,
    {{ hours_between(
        'lag(i.outtime) over (partition by i.hadm_id order by i.intime, i.stay_id)',
        'i.intime') }}                             as hours_since_prev_icu_discharge,
    {{ hours_between('a.admittime', 'i.intime') }} as hours_from_admit_to_icu,
    (i.intime < a.admittime or i.outtime > a.dischtime) as is_outside_admission_window,
    coalesce(
        a.deathtime >= i.intime
        and a.deathtime <= {{ add_hours('i.outtime', var('icu_death_grace_hours')) }},
        false)                                     as died_in_icu,
    a.died_in_hospital,
    a.age_at_admission,
    a.age_group,
    a.sex,
    a.admission_type,
    a.admission_group,
    a.patient_total_admissions
from icu i
inner join admissions a on a.hadm_id = i.hadm_id
left join unit_types ut on ut.careunit = i.first_careunit
