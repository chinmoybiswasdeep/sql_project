-- Case C2 optimized: one ordered pass with LAG() over the same partition
-- (subject_id, itemid), replacing one index probe + sort per row.
select
    labevent_id,
    valuenum - lag(valuenum) over (
        partition by subject_id, itemid order by charttime, labevent_id
    ) as delta_from_previous
from raw.labevents
where itemid in (50912, 50971, 50983, 51222)
  and valuenum is not null
