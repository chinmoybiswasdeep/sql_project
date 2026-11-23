-- Grain: one row per billed diagnosis (hadm_id, seq_num).
-- Maps ICD-9-CM and ICD-10-CM codes to a harmonised chapter-level category so
-- the mixed-version history can be analysed together. Chapter ranges are
-- matched on the first three characters of the (dot-less) code.
--
-- Fan-out guard: the seed's ranges must not overlap within a version. The
-- unique_combination test on (hadm_id, seq_num) fails if they ever do.
with diagnoses as (
    select * from {{ ref('stg_diagnoses_icd') }}
),

dictionary as (
    select * from {{ ref('stg_d_icd_diagnoses') }}
),

chapters as (
    select * from {{ ref('icd_chapters') }}
)

select
    d.hadm_id,
    d.subject_id,
    d.seq_num,
    d.icd_code,
    d.icd_version,
    d.is_primary,
    coalesce(dict.diagnosis_title, '(code not in dictionary)') as diagnosis_title,
    coalesce(c.chapter_code, 'unmapped')                       as chapter_code,
    coalesce(c.harmonized_category, 'Unclassified')            as diagnosis_category
from diagnoses d
left join dictionary dict
    on dict.icd_code = d.icd_code
   and dict.icd_version = d.icd_version
left join chapters c
    on c.icd_version = d.icd_version
   and substr(d.icd_code, 1, 3) between c.range_start and c.range_end
