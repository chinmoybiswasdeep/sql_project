-- Abnormality has two independent signals, both kept:
--   * flag_abnormal: the laboratory's own 'abnormal' flag (available for
--     numeric and some non-numeric results)
--   * range_direction: numeric value compared with the row's own reference
--     range (null when either the value or the range is missing)
select
    labevent_id,
    subject_id,
    hadm_id,
    specimen_id,
    itemid,
    charttime,
    storetime,
    value                                         as value_text,
    valuenum                                      as value_numeric,
    valueuom                                      as value_unit,
    ref_range_lower,
    ref_range_upper,
    coalesce(flag = 'abnormal', false)            as flag_abnormal,
    case
        when valuenum is null or ref_range_lower is null or ref_range_upper is null then null
        when valuenum < ref_range_lower then 'low'
        when valuenum > ref_range_upper then 'high'
        else 'normal'
    end                                           as range_direction,
    priority
from {{ source('mimic_raw', 'labevents') }}
