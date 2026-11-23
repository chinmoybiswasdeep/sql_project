select
    stay_id,
    subject_id,
    hadm_id,
    first_careunit,
    last_careunit,
    intime,
    outtime,
    los                                           as icu_los_days_source,
    {{ hours_between('intime', 'outtime') }}      as icu_los_hours
from {{ source('mimic_raw', 'icustays') }}
