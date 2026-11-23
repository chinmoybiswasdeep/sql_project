-- Composite index matching the predicate order (equality on itemid, join on
-- stay_id, range on charttime) with valuenum INCLUDEd so the query can be
-- answered by an index-only scan without visiting the heap.
CREATE INDEX IF NOT EXISTS ix_perf_chartevents_item_stay_time
    ON raw.chartevents (itemid, stay_id, charttime) INCLUDE (valuenum);
VACUUM (ANALYZE) raw.chartevents;
