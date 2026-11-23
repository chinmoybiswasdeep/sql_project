with adm as (select * from {{ ref('fact_admissions') }}),
rd as (select * from {{ ref('fact_readmissions') }} where is_eligible_index)
select
    (select count(distinct subject_id) from adm)                           as total_patients,
    (select count(*) from adm)                                             as total_admissions,
    (select round(cast(count(*) as numeric) / count(distinct subject_id), 2) from adm)
                                                                           as admissions_per_patient,
    (select percentile_cont(0.5) within group (order by los_days) from adm) as median_los_days,
    (select round(100.0 * avg(case when had_icu_stay then 1 else 0 end), 1) from adm)
                                                                           as icu_admission_pct,
    (select round(100.0 * avg(case when died_in_hospital then 1 else 0 end), 1) from adm)
                                                                           as hospital_mortality_pct,
    (select count(*) from rd)                                              as readmission_denominator,
    (select sum(case when is_readmitted_30d then 1 else 0 end) from rd)    as readmission_numerator,
    (select round(100.0 * avg(case when is_readmitted_30d then 1 else 0 end), 1) from rd)
                                                                           as readmission_30d_pct,
    (select round(100.0 * avg(case when is_unplanned_readmitted_30d then 1 else 0 end), 1) from rd)
                                                                           as unplanned_readmission_30d_pct
