-- Case C5 baseline: distinct ICU stays per charted item via COUNT(DISTINCT),
-- which PostgreSQL evaluates with a sort per group (no hash aggregation).
select itemid, count(distinct stay_id) as stays
from raw.chartevents
group by itemid
