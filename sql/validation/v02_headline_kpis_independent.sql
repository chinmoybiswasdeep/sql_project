-- Independent validation of headline KPIs: recomputed directly from raw tables
-- and compared with reporting.rpt_executive_kpis.
with k as (select * from reporting.rpt_executive_kpis)
select 'total_patients' as component, k.total_patients::numeric as warehouse_value,
       (select count(distinct subject_id) from raw.admissions)::numeric as independent_value from k
union all
select 'total_admissions', k.total_admissions, (select count(*) from raw.admissions) from k
union all
select 'median_los_days', round(k.median_los_days::numeric, 6),
       round((select percentile_cont(0.5) within group (
              order by extract(epoch from dischtime - admittime) / 86400.0) from raw.admissions)::numeric, 6)
from k
union all
select 'hospital_mortality_pct', k.hospital_mortality_pct,
       (select round(100.0 * avg(hospital_expire_flag), 1) from raw.admissions) from k
union all
select 'icu_admission_pct', k.icu_admission_pct,
       (select round(100.0 * count(*) filter (
                where exists (select 1 from raw.icustays i where i.hadm_id = a.hadm_id)) / count(*), 1)
        from raw.admissions a) from k;
