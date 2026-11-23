-- Grain: one row per patient (subject_id). De-identified attributes only.
with admissions as (
    select
        subject_id,
        count(*)                                   as n_admissions,
        min(age_at_admission)                      as age_at_first_admission,
        max(case when died_in_hospital then 1 else 0 end) = 1 as died_in_hospital_ever
    from {{ ref('int_admissions_enriched') }}
    group by subject_id
),

icu as (
    select subject_id, count(*) as n_icu_stays
    from {{ ref('stg_icustays') }}
    group by subject_id
)

select
    p.subject_id,
    p.sex,
    p.anchor_age,
    p.anchor_year_group,
    p.is_age_top_coded,
    p.date_of_death is not null                    as has_recorded_death,
    coalesce(a.n_admissions, 0)                    as n_admissions,
    a.age_at_first_admission,
    coalesce(a.died_in_hospital_ever, false)       as died_in_hospital_ever,
    coalesce(i.n_icu_stays, 0)                     as n_icu_stays,
    case
        when coalesce(a.n_admissions, 0) = 0 then '0'
        when a.n_admissions = 1 then '1'
        when a.n_admissions <= 3 then '2-3'
        else '4+'
    end                                            as admission_frequency_band
from {{ ref('stg_patients') }} p
left join admissions a on a.subject_id = p.subject_id
left join icu i on i.subject_id = p.subject_id
