select
    hadm_id,
    subject_id,
    admittime,
    dischtime,
    deathtime,
    trim(admission_type)                          as admission_type,
    admission_location,
    discharge_location,
    insurance,
    language,
    marital_status,
    race,
    {{ race_group('race') }}                      as race_group,
    edregtime,
    edouttime,
    hospital_expire_flag = 1                      as died_in_hospital,
    {{ hours_between('admittime', 'dischtime') }} as los_hours,
    case when edregtime is not null and edouttime >= edregtime
         then {{ hours_between('edregtime', 'edouttime') }} end as ed_los_hours
from {{ source('mimic_raw', 'admissions') }}
