-- Case C5 optimized: de-duplicate first with GROUP BY (eligible for hash
-- aggregation and parallelism), then count. Same result, different plan.
select itemid, count(*) as stays
from (
    select itemid, stay_id
    from raw.chartevents
    group by itemid, stay_id
) d
group by itemid
