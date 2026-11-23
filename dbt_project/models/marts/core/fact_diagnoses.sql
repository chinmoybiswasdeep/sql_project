-- Grain: one row per billed diagnosis (hadm_id, seq_num).
select
    hadm_id,
    subject_id,
    seq_num,
    icd_code,
    icd_version,
    is_primary,
    diagnosis_title,
    chapter_code,
    diagnosis_category
from {{ ref('int_diagnoses_categorized') }}
