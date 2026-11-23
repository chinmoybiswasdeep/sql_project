-- Grain: one row per hospital admission (hadm_id).
--
-- Charlson Comorbidity Index from billed ICD-9-CM / ICD-10-CM codes using the
-- Quan et al. (2005) coding algorithm, adapted from the MIT-LCP mimic-code
-- concept `mimic-iv/concepts/comorbidity/charlson.sql`.
--
-- Caveats
-- * Billed diagnoses are recorded at discharge, so they describe the whole
--   admission, not only conditions present on arrival. The index is used
--   here to *describe* case-mix, not as a pre-admission risk adjuster.
-- * Hierarchies: a severe form supersedes its mild form (liver disease,
--   diabetes, cancer) so each condition contributes once.
with dx as (
    select
        hadm_id,
        icd_version,
        icd_code,
        substr(icd_code, 1, 3) as c3,
        substr(icd_code, 1, 4) as c4,
        substr(icd_code, 1, 5) as c5
    from {{ ref('stg_diagnoses_icd') }}
),

flags as (
    select
        hadm_id,
        max(case when (icd_version = 9 and c3 in ('410', '412'))
                   or (icd_version = 10 and (c3 in ('I21', 'I22') or c4 = 'I252'))
                 then 1 else 0 end) as myocardial_infarct,
        max(case when (icd_version = 9 and (c3 = '428'
                        or c5 in ('39891', '40201', '40211', '40291', '40401', '40403',
                                  '40411', '40413', '40491', '40493')
                        or c4 between '4254' and '4259'))
                   or (icd_version = 10 and (c3 in ('I43', 'I50')
                        or c4 in ('I099', 'I110', 'I130', 'I132', 'I255', 'I420', 'I425',
                                  'I426', 'I427', 'I428', 'I429', 'P290')))
                 then 1 else 0 end) as congestive_heart_failure,
        max(case when (icd_version = 9 and (c3 in ('440', '441')
                        or c4 in ('0930', '4373', '4471', '5571', '5579', 'V434')
                        or c4 between '4431' and '4439'))
                   or (icd_version = 10 and (c3 in ('I70', 'I71')
                        or c4 in ('I731', 'I738', 'I739', 'I771', 'I790', 'I792', 'K551',
                                  'K558', 'K559', 'Z958', 'Z959')))
                 then 1 else 0 end) as peripheral_vascular_disease,
        max(case when (icd_version = 9 and (c3 between '430' and '438' or c5 = '36234'))
                   or (icd_version = 10 and (c3 in ('G45', 'G46')
                        or c3 between 'I60' and 'I69' or c4 = 'H340'))
                 then 1 else 0 end) as cerebrovascular_disease,
        max(case when (icd_version = 9 and (c3 = '290' or c4 in ('2941', '3312')))
                   or (icd_version = 10 and (c3 in ('F00', 'F01', 'F02', 'F03', 'G30')
                        or c4 in ('F051', 'G311')))
                 then 1 else 0 end) as dementia,
        max(case when (icd_version = 9 and (c3 between '490' and '505'
                        or c4 in ('4168', '4169', '5064', '5081', '5088')))
                   or (icd_version = 10 and (c3 between 'J40' and 'J47'
                        or c3 between 'J60' and 'J67'
                        or c4 in ('I278', 'I279', 'J684', 'J701', 'J703')))
                 then 1 else 0 end) as chronic_pulmonary_disease,
        max(case when (icd_version = 9 and (c3 = '725'
                        or c4 in ('4465', '7100', '7101', '7102', '7103', '7104', '7140',
                                  '7141', '7142', '7148')))
                   or (icd_version = 10 and (c3 in ('M05', 'M06', 'M32', 'M33', 'M34')
                        or c4 in ('M315', 'M351', 'M353', 'M360')))
                 then 1 else 0 end) as rheumatic_disease,
        max(case when (icd_version = 9 and c3 in ('531', '532', '533', '534'))
                   or (icd_version = 10 and c3 in ('K25', 'K26', 'K27', 'K28'))
                 then 1 else 0 end) as peptic_ulcer_disease,
        max(case when (icd_version = 9 and (c3 in ('570', '571')
                        or c4 in ('0706', '0709', '5733', '5734', '5738', '5739', 'V427')
                        or c5 in ('07022', '07023', '07032', '07033', '07044', '07054')))
                   or (icd_version = 10 and (c3 in ('B18', 'K73', 'K74')
                        or c4 in ('K700', 'K701', 'K702', 'K703', 'K709', 'K713', 'K714',
                                  'K715', 'K717', 'K760', 'K762', 'K763', 'K764', 'K768',
                                  'K769', 'Z944')))
                 then 1 else 0 end) as mild_liver_disease,
        max(case when (icd_version = 9 and c4 in ('2500', '2501', '2502', '2503', '2508', '2509'))
                   or (icd_version = 10 and c4 in ('E100', 'E101', 'E106', 'E108', 'E109',
                        'E110', 'E111', 'E116', 'E118', 'E119', 'E120', 'E121', 'E126',
                        'E128', 'E129', 'E130', 'E131', 'E136', 'E138', 'E139', 'E140',
                        'E141', 'E146', 'E148', 'E149'))
                 then 1 else 0 end) as diabetes_without_cc,
        max(case when (icd_version = 9 and c4 in ('2504', '2505', '2506', '2507'))
                   or (icd_version = 10 and c4 in ('E102', 'E103', 'E104', 'E105', 'E107',
                        'E112', 'E113', 'E114', 'E115', 'E117', 'E122', 'E123', 'E124',
                        'E125', 'E127', 'E132', 'E133', 'E134', 'E135', 'E137', 'E142',
                        'E143', 'E144', 'E145', 'E147'))
                 then 1 else 0 end) as diabetes_with_cc,
        max(case when (icd_version = 9 and (c3 in ('342', '343')
                        or c4 in ('3341', '3440', '3441', '3442', '3443', '3444', '3445',
                                  '3446', '3449')))
                   or (icd_version = 10 and (c3 in ('G81', 'G82')
                        or c4 in ('G041', 'G114', 'G801', 'G802', 'G830', 'G831', 'G832',
                                  'G833', 'G834', 'G839')))
                 then 1 else 0 end) as paraplegia,
        max(case when (icd_version = 9 and (c3 in ('582', '585', '586', 'V56')
                        or c4 in ('5880', 'V420', 'V451')
                        or c4 between '5830' and '5837'
                        or c5 in ('40301', '40311', '40391', '40402', '40403', '40412',
                                  '40413', '40492', '40493')))
                   or (icd_version = 10 and (c3 in ('N18', 'N19')
                        or c4 in ('I120', 'I131', 'N032', 'N033', 'N034', 'N035', 'N036',
                                  'N037', 'N052', 'N053', 'N054', 'N055', 'N056', 'N057',
                                  'N250', 'Z490', 'Z491', 'Z492', 'Z940', 'Z992')))
                 then 1 else 0 end) as renal_disease,
        max(case when (icd_version = 9 and (c3 between '140' and '172'
                        or c4 between '1740' and '1958'
                        or c3 between '200' and '208'
                        or c4 = '2386'))
                   or (icd_version = 10 and (c3 in ('C43', 'C88')
                        or c3 between 'C00' and 'C26' or c3 between 'C30' and 'C34'
                        or c3 between 'C37' and 'C41' or c3 between 'C45' and 'C58'
                        or c3 between 'C60' and 'C76' or c3 between 'C81' and 'C85'
                        or c3 between 'C90' and 'C97'))
                 then 1 else 0 end) as malignant_cancer,
        max(case when (icd_version = 9 and (c4 in ('4560', '4561', '4562')
                        or c4 between '5722' and '5728'))
                   or (icd_version = 10 and c4 in ('I850', 'I859', 'I864', 'I982', 'K704',
                        'K711', 'K721', 'K729', 'K765', 'K766', 'K767'))
                 then 1 else 0 end) as severe_liver_disease,
        max(case when (icd_version = 9 and c3 in ('196', '197', '198', '199'))
                   or (icd_version = 10 and c3 in ('C77', 'C78', 'C79', 'C80'))
                 then 1 else 0 end) as metastatic_solid_tumor,
        max(case when (icd_version = 9 and c3 in ('042', '043', '044'))
                   or (icd_version = 10 and c3 in ('B20', 'B21', 'B22', 'B24'))
                 then 1 else 0 end) as aids
    from dx
    group by hadm_id
),

admissions as (
    select hadm_id, age_at_admission from {{ ref('int_admissions_enriched') }}
)

select
    a.hadm_id,
    coalesce(f.myocardial_infarct, 0)          as myocardial_infarct,
    coalesce(f.congestive_heart_failure, 0)    as congestive_heart_failure,
    coalesce(f.peripheral_vascular_disease, 0) as peripheral_vascular_disease,
    coalesce(f.cerebrovascular_disease, 0)     as cerebrovascular_disease,
    coalesce(f.dementia, 0)                    as dementia,
    coalesce(f.chronic_pulmonary_disease, 0)   as chronic_pulmonary_disease,
    coalesce(f.rheumatic_disease, 0)           as rheumatic_disease,
    coalesce(f.peptic_ulcer_disease, 0)        as peptic_ulcer_disease,
    coalesce(f.mild_liver_disease, 0)          as mild_liver_disease,
    coalesce(f.diabetes_without_cc, 0)         as diabetes_without_cc,
    coalesce(f.diabetes_with_cc, 0)            as diabetes_with_cc,
    coalesce(f.paraplegia, 0)                  as paraplegia,
    coalesce(f.renal_disease, 0)               as renal_disease,
    coalesce(f.malignant_cancer, 0)            as malignant_cancer,
    coalesce(f.severe_liver_disease, 0)        as severe_liver_disease,
    coalesce(f.metastatic_solid_tumor, 0)      as metastatic_solid_tumor,
    coalesce(f.aids, 0)                        as aids,
    f.hadm_id is not null                      as has_coded_diagnoses,
    -- Comorbidity component (weights per Charlson 1987, hierarchies applied)
    coalesce(
        f.myocardial_infarct + f.congestive_heart_failure + f.peripheral_vascular_disease
        + f.cerebrovascular_disease + f.dementia + f.chronic_pulmonary_disease
        + f.rheumatic_disease + f.peptic_ulcer_disease
        + greatest(f.mild_liver_disease, 3 * f.severe_liver_disease)
        + greatest(2 * f.diabetes_with_cc, f.diabetes_without_cc)
        + greatest(2 * f.malignant_cancer, 6 * f.metastatic_solid_tumor)
        + 2 * f.paraplegia + 2 * f.renal_disease + 6 * f.aids,
        0)                                     as charlson_comorbidity_score,
    case
        when a.age_at_admission <= 50 then 0
        when a.age_at_admission <= 60 then 1
        when a.age_at_admission <= 70 then 2
        when a.age_at_admission <= 80 then 3
        else 4
    end                                        as charlson_age_score
from admissions a
left join flags f on f.hadm_id = a.hadm_id
