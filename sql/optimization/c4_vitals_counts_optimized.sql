-- Case C4 optimized: a single scan of chartevents with conditional
-- aggregation (FILTER), joined once to icustays. LEFT JOIN keeps stays with
-- no vitals (counts = 0), matching the baseline.
select
    i.stay_id,
    count(*) filter (where c.itemid = 220045) as heart_rate,
    count(*) filter (where c.itemid = 220179) as nibp_systolic,
    count(*) filter (where c.itemid = 220180) as nibp_diastolic,
    count(*) filter (where c.itemid = 220210) as resp_rate,
    count(*) filter (where c.itemid = 220277) as spo2
from raw.icustays i
left join raw.chartevents c
    on c.stay_id = i.stay_id
   and c.itemid in (220045, 220179, 220180, 220210, 220277)
group by i.stay_id
