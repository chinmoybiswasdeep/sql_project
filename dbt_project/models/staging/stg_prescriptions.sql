-- Prescriptions have no source primary key; the tested grain is
-- (hadm_id, pharmacy_id, drug, starttime). A deterministic surrogate key is
-- derived from it. drug_name_normalized collapses case/whitespace variants.
select
    md5(concat_ws('|', hadm_id, pharmacy_id, drug, starttime)) as prescription_key,
    subject_id,
    hadm_id,
    pharmacy_id,
    poe_id,
    starttime,
    stoptime,
    drug_type,
    drug                                          as drug_name_source,
    lower(regexp_replace(trim(drug), '\s+', ' ', 'g')) as drug_name_normalized,
    route,
    case when stoptime >= starttime then {{ hours_between('starttime', 'stoptime') }} end
                                                  as order_duration_hours,
    stoptime < starttime                          as has_inverted_times
from {{ source('mimic_raw', 'prescriptions') }}
