-- Fan-out reconciliation: totals of the per-admission counts in fact_admissions
-- must equal raw event counts. Any one-to-many join error would inflate these.
select 'lab_events (admission-linked)' as component,
       (select sum(n_lab_events) from marts.fact_admissions)::numeric as warehouse_value,
       (select count(*) from raw.labevents where hadm_id is not null)::numeric as independent_value
union all
select 'diagnoses', (select sum(n_diagnoses) from marts.fact_admissions),
       (select count(*) from raw.diagnoses_icd)
union all
select 'procedures', (select sum(n_procedures) from marts.fact_admissions),
       (select count(*) from raw.procedures_icd)
union all
select 'prescriptions', (select sum(n_prescriptions) from marts.fact_admissions),
       (select count(*) from raw.prescriptions)
union all
select 'icu_stays', (select sum(n_icu_stays) from marts.fact_admissions),
       (select count(*) from raw.icustays)
union all
select 'icu_days', (select round(sum(icu_days_total)::numeric, 4) from marts.fact_admissions),
       (select round(sum(extract(epoch from outtime - intime) / 86400.0)::numeric, 4) from raw.icustays)
union all
select 'abnormal_lab_events (admission-linked)', (select sum(n_abnormal_lab_events) from marts.fact_admissions),
       (select count(*) from raw.labevents where hadm_id is not null and flag = 'abnormal');
