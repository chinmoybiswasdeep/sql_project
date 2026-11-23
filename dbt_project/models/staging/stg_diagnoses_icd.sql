select
    hadm_id,
    subject_id,
    seq_num,
    upper(trim(icd_code))                         as icd_code,
    icd_version,
    seq_num = 1                                   as is_primary
from {{ source('mimic_raw', 'diagnoses_icd') }}
