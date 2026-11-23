-- Case C1: heart rate (itemid 220045) during the first 24h of each ICU stay.
-- The SAME query text is used for baseline and optimized runs; the
-- optimization is a covering composite index (see c1_setup_optimized.sql).
select
    i.stay_id,
    count(*)                                                    as n_measurements,
    round(avg(c.valuenum)::numeric, 4)                          as mean_hr,
    percentile_cont(0.5) within group (order by c.valuenum)     as median_hr
from raw.icustays i
join raw.chartevents c on c.stay_id = i.stay_id
where c.itemid = 220045
  and c.valuenum is not null
  and c.charttime >= i.intime
  and c.charttime <  i.intime + interval '24 hours'
group by i.stay_id
