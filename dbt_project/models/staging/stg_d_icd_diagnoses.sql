select
    upper(trim(icd_code))                         as icd_code,
    icd_version,
    long_title                                    as diagnosis_title
from {{ source('mimic_raw', 'd_icd_diagnoses') }}
