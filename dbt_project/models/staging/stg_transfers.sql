select
    transfer_id,
    subject_id,
    hadm_id,
    eventtype                                     as event_type,
    careunit                                      as care_unit,
    intime,
    outtime,
    case when outtime is not null then {{ hours_between('intime', 'outtime') }} end as unit_hours
from {{ source('mimic_raw', 'transfers') }}
