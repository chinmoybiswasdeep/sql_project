-- Case C4 baseline: one correlated scalar subquery per vital sign per stay
-- (a common reporting anti-pattern): 5 subqueries x 140 stays = 700 probes
-- of chartevents.
select
    i.stay_id,
    (select count(*) from raw.chartevents c where c.stay_id = i.stay_id and c.itemid = 220045) as heart_rate,
    (select count(*) from raw.chartevents c where c.stay_id = i.stay_id and c.itemid = 220179) as nibp_systolic,
    (select count(*) from raw.chartevents c where c.stay_id = i.stay_id and c.itemid = 220180) as nibp_diastolic,
    (select count(*) from raw.chartevents c where c.stay_id = i.stay_id and c.itemid = 220210) as resp_rate,
    (select count(*) from raw.chartevents c where c.stay_id = i.stay_id and c.itemid = 220277) as spo2
from raw.icustays i
