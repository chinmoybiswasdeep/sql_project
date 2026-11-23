-- Independent validation of the 30-day readmission metric.
--
-- Recomputed from RAW tables (not the dbt models), using a different
-- technique: the "next admission" is found with a correlated NOT EXISTS
-- self-join instead of the LEAD() window used in int_readmission_pairs.
-- Each component (eligible discharges, numerator, gap calculation, rate)
-- is compared with the warehouse value.
with adm as (
    select subject_id, hadm_id, admittime, dischtime, discharge_location, hospital_expire_flag
    from raw.admissions
),
next_adm as (
    -- for each admission, the earliest later admission of the same patient
    select a.hadm_id, n.hadm_id as next_hadm_id, n.admittime as next_admittime, n.admission_type as next_type
    from adm a
    left join raw.admissions n
      on n.subject_id = a.subject_id
     and (n.admittime > a.admittime or (n.admittime = a.admittime and n.hadm_id > a.hadm_id))
     and not exists (
         select 1 from raw.admissions m
         where m.subject_id = a.subject_id
           and (m.admittime > a.admittime or (m.admittime = a.admittime and m.hadm_id > a.hadm_id))
           and (m.admittime < n.admittime or (m.admittime = n.admittime and m.hadm_id < n.hadm_id))
     )
),
classified as (
    select
        a.hadm_id,
        (a.dischtime is not null
         and a.hospital_expire_flag = 0
         and coalesce(a.discharge_location, '') not in ('DIED', 'ACUTE HOSPITAL', 'AGAINST ADVICE')
         and not coalesce(n.next_admittime < a.dischtime, false))         as eligible,
        n.next_admittime,
        a.dischtime,
        n.next_type
    from adm a
    left join next_adm n on n.hadm_id = a.hadm_id
),
independent as (
    select
        count(*) filter (where eligible)                                  as eligible,
        count(*) filter (where eligible and next_admittime >= dischtime
                         and next_admittime <= dischtime + interval '30 days') as readmitted,
        count(*) filter (where eligible and next_admittime >= dischtime
                         and next_admittime <= dischtime + interval '30 days'
                         and next_type not in ('ELECTIVE', 'SURGICAL SAME DAY ADMISSION')) as unplanned,
        round(sum(extract(epoch from next_admittime - dischtime) / 86400.0)
              filter (where next_admittime is not null)::numeric, 3)      as sum_gap_days
    from classified
),
warehouse as (
    select
        count(*) filter (where is_eligible_index)                         as eligible,
        count(*) filter (where is_readmitted_30d)                         as readmitted,
        count(*) filter (where is_unplanned_readmitted_30d)               as unplanned,
        round(sum(days_to_next_admission)::numeric, 3)                    as sum_gap_days
    from marts.fact_readmissions
)
select 'eligible_discharges' as component, w.eligible::numeric as warehouse_value, i.eligible::numeric as independent_value from warehouse w, independent i
union all select 'readmissions_30d', w.readmitted, i.readmitted from warehouse w, independent i
union all select 'unplanned_readmissions_30d', w.unplanned, i.unplanned from warehouse w, independent i
union all select 'sum_days_to_next_admission', w.sum_gap_days, i.sum_gap_days from warehouse w, independent i
union all select 'readmission_rate_pct',
    round(100.0 * w.readmitted / w.eligible, 4), round(100.0 * i.readmitted / i.eligible, 4)
    from warehouse w, independent i;
