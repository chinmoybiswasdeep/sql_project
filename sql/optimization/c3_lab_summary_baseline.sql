-- Case C3 baseline: dashboard lab-test summary computed from the raw event
-- table on every request (full scan + join + COUNT DISTINCT).
select
    d.itemid,
    d.label,
    d.fluid,
    count(*)                                         as results,
    count(*) filter (where l.flag = 'abnormal')      as abnormal_results,
    count(distinct l.hadm_id)                        as admissions_tested
from raw.labevents l
join raw.d_labitems d on d.itemid = l.itemid
group by d.itemid, d.label, d.fluid
