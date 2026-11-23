select
    hadm_id,
    subject_id,
    seq_num,
    chartdate                                     as procedure_date,
    upper(trim(icd_code))                         as icd_code,
    icd_version
from {{ source('mimic_raw', 'procedures_icd') }}
