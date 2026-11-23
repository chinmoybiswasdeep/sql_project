-- Pre-aggregate once into a materialized view (refreshed after each load).
-- Trade-off: storage plus a refresh step, in exchange for request-time reads
-- of ~1 row per test instead of every lab event.
CREATE SCHEMA IF NOT EXISTS perf;
DROP MATERIALIZED VIEW IF EXISTS perf.mv_lab_test_summary;
CREATE MATERIALIZED VIEW perf.mv_lab_test_summary AS
select
    d.itemid,
    d.label,
    d.fluid,
    count(*)                                         as results,
    count(*) filter (where l.flag = 'abnormal')      as abnormal_results,
    count(distinct l.hadm_id)                        as admissions_tested
from raw.labevents l
join raw.d_labitems d on d.itemid = l.itemid
group by d.itemid, d.label, d.fluid;
CREATE UNIQUE INDEX ON perf.mv_lab_test_summary (itemid);
ANALYZE perf.mv_lab_test_summary;
