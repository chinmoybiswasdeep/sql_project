-- Grain: one row per ICD code and version (full ICD-9-CM + ICD-10-CM dictionary).
select
    d.icd_code,
    d.icd_version,
    d.diagnosis_title,
    coalesce(c.chapter_code, 'unmapped')           as chapter_code,
    coalesce(c.harmonized_category, 'Unclassified') as diagnosis_category
from {{ ref('stg_d_icd_diagnoses') }} d
left join {{ ref('icd_chapters') }} c
    on c.icd_version = d.icd_version
   and substr(d.icd_code, 1, 3) between c.range_start and c.range_end
