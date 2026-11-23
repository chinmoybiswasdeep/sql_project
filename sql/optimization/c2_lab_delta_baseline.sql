-- Case C2 baseline: change from the previous result of the same test for the
-- same patient (a "delta check"), found with a correlated subquery that runs
-- once per outer row.
select
    l.labevent_id,
    l.valuenum - (
        select p.valuenum
        from raw.labevents p
        where p.subject_id = l.subject_id
          and p.itemid = l.itemid
          and p.valuenum is not null
          and (p.charttime < l.charttime
               or (p.charttime = l.charttime and p.labevent_id < l.labevent_id))
        order by p.charttime desc, p.labevent_id desc
        limit 1
    ) as delta_from_previous
from raw.labevents l
where l.itemid in (50912, 50971, 50983, 51222)   -- creatinine, potassium, sodium, hemoglobin
  and l.valuenum is not null
