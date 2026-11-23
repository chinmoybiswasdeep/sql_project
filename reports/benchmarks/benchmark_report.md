# SQL Performance Benchmarks

_Generated 2026-11-23 03:38 UTC by `python -m analytics.performance.benchmark` on `mimic-iv-demo-2.2`. Median of 7 timed runs after one warm-up; server-side execution time from `EXPLAIN (ANALYZE, TIMING OFF)`._

- **Engine:** PostgreSQL 16.16 on aarch64-apple-darwin20.0.0 on Darwin arm64
- **Settings:** shared_buffers=512MB, work_mem=64MB, jit=on, max_parallel_workers_per_gather=2
- **Table sizes:** raw.chartevents 668,862 rows, raw.labevents 107,727 rows

> These are **demo-scale** measurements (largest table 669k rows). They show that each optimization changes the plan in the expected way, and by how much at this scale. They are not projections: full MIMIC-IV chartevents holds hundreds of millions of rows and must be benchmarked separately on authorized data.

| Case | Technique | Baseline median (ms) | Optimized median (ms) | Speedup | One-off setup cost (ms) | Rows | Results identical |
|---|---|---:|---:|---:|---:|---:|---|
| C1: First-24h heart rate per ICU stay | Covering composite index | 11.29 | 0.65 | 17.5x | 226 | 140 | yes |
| C2: Lab delta check (change from previous result) | Correlated subquery -> LAG() window | 1051.72 | 4.52 | 232.6x | — | 11,814 | yes |
| C3: Lab test summary for dashboards | Pre-aggregation (materialized view) | 56.92 | 0.01 | 5692.1x | 62 | 498 | yes |
| C4: Vital-sign counts per ICU stay | Many correlated scans -> one pass | 13233.20 | 32.16 | 411.5x | — | 140 | yes |
| C5: Distinct ICU stays per charted item | COUNT(DISTINCT) -> two-phase GROUP BY | 119.37 | 49.05 | 2.4x | — | 1,318 | yes |

Setup cost is the measured time to build the index or materialized view (including VACUUM/ANALYZE). Query rewrites (C2, C4, C5) have no setup cost. Speedups for C3 are only meaningful when the view is read many times per refresh; the honest comparison is refresh cost vs. (requests x baseline time).

## C1: First-24h heart rate per ICU stay

**Technique:** Covering composite index  
**Why:** Filters chartevents (largest table) on itemid + stay_id + a charttime range. Without an index the planner must scan every chart event; a composite index in predicate order with INCLUDE(valuenum) allows an index-only range scan per stay.

- Baseline: median 11.29 ms (min 11.13, max 12.12)
- Optimized: median 0.65 ms (min 0.63, max 0.68)
- Baseline plan root: `GroupAggregate  (cost=13580.24..13655.88 rows=140 width=52) (actual time=10.739..11.572 rows=140 loops=1)`
- Optimized plan root: `GroupAggregate  (cost=764.27..774.63 rows=140 width=52) (actual time=0.620..0.968 rows=140 loops=1)`
- Full plans: [`c1_baseline_plan.txt`](c1_baseline_plan.txt), [`c1_optimized_plan.txt`](c1_optimized_plan.txt)

**Bottleneck observed in the plans:** Baseline: parallel Hash Join reading all of chartevents (2 workers), then filtering ~3.8k qualifying rows by the charttime join filter. Almost all work is scanning rows that are discarded. Optimized: Nested Loop over 140 stays, each doing an Index Only Scan on (itemid, stay_id, charttime) INCLUDE (valuenum), so only matching index entries are read and the heap is never visited.

## C2: Lab delta check (change from previous result)

**Technique:** Correlated subquery -> LAG() window  
**Why:** The correlated subquery executes once per outer row (~10k), each doing an index probe plus top-1 sort over the patient's history. LAG() computes the same value in a single sorted pass.

- Baseline: median 1051.72 ms (min 972.43, max 1057.28)
- Optimized: median 4.52 ms (min 4.42, max 4.90)
- Baseline plan root: `Bitmap Heap Scan on labevents l  (cost=138.21..236413.44 rows=10213 width=12) (actual time=0.558..1158.338 rows=11814 loops=1)`
- Optimized plan root: `WindowAgg  (cost=2927.31..3208.17 rows=10213 width=28) (actual time=3.221..4.967 rows=11814 loops=1)`
- Full plans: [`c2_baseline_plan.txt`](c2_baseline_plan.txt), [`c2_optimized_plan.txt`](c2_optimized_plan.txt)

**Bottleneck observed in the plans:** Baseline: SubPlan 1 executes once per outer row (loops = 11,814). Each loop builds a BitmapAnd of two indexes, fetches about 44 heap rows and runs a top-N heapsort. Optimized: a single Bitmap Heap Scan, one in-memory quicksort (about 1 MB) and a WindowAgg. The per-row repeated work disappears.

## C3: Lab test summary for dashboards

**Technique:** Pre-aggregation (materialized view)  
**Why:** The summary is requested repeatedly but changes only when data is reloaded. Materializing it moves the full scan, join and COUNT DISTINCT to refresh time.

- Baseline: median 56.92 ms (min 56.59, max 57.91)
- Optimized: median 0.01 ms (min 0.01, max 0.01)
- Baseline plan root: `GroupAggregate  (cost=13552.38..15723.14 rows=1622 width=49) (actual time=53.823..60.700 rows=498 loops=1)`
- Optimized plan root: `Seq Scan on mv_lab_test_summary  (cost=0.00..12.98 rows=498 width=49) (actual time=0.001..0.012 rows=498 loops=1)`
- Full plans: [`c3_baseline_plan.txt`](c3_baseline_plan.txt), [`c3_optimized_plan.txt`](c3_optimized_plan.txt)

**Bottleneck observed in the plans:** Baseline: Seq Scan of all 107,727 lab events, Hash Join to d_labitems, then a full Sort (about 8.9 MB in memory) to evaluate COUNT(DISTINCT hadm_id) per group. Optimized: Seq Scan of 498 pre-aggregated rows. The cost moves to view creation and refresh (see setup cost); the view pays off only when it is read more than once per refresh.

## C4: Vital-sign counts per ICU stay

**Technique:** Many correlated scans -> one pass  
**Why:** Five scalar subqueries per stay each scan chartevents (no index on stay_id), so the table is read hundreds of times. Conditional aggregation reads it once.

- Baseline: median 13233.20 ms (min 13174.51, max 13315.22)
- Optimized: median 32.16 ms (min 31.02, max 32.65)
- Baseline plan root: `Seq Scan on icustays i  (cost=0.00..13347706.25 rows=140 width=44) (actual time=99.578..13500.491 rows=140 loops=1)`
- Optimized plan root: `HashAggregate  (cost=22282.03..22283.43 rows=140 width=44) (actual time=36.166..36.174 rows=140 loops=1)`
- Full plans: [`c4_baseline_plan.txt`](c4_baseline_plan.txt), [`c4_optimized_plan.txt`](c4_optimized_plan.txt)

**Bottleneck observed in the plans:** Baseline: five SubPlans, each a full Seq Scan of chartevents executed once per ICU stay (loops = 140), removing about 668,800 rows per scan. That is 700 full scans of the table. Optimized: one Seq Scan with the itemid IN-list filter, a Hash Right Join to icustays and one HashAggregate.

## C5: Distinct ICU stays per charted item

**Technique:** COUNT(DISTINCT) -> two-phase GROUP BY  
**Why:** COUNT(DISTINCT) forces a sort-based aggregate per group and cannot use parallel or hash aggregation; de-duplicating with GROUP BY first can.

- Baseline: median 119.37 ms (min 117.99, max 124.54)
- Optimized: median 49.05 ms (min 48.22, max 50.80)
- Baseline plan root: `GroupAggregate  (cost=80440.53..85467.10 rows=1010 width=12) (actual time=107.470..139.549 rows=1318 loops=1)`
- Optimized plan root: `HashAggregate  (cost=20740.08..20742.08 rows=200 width=12) (actual time=56.830..56.869 rows=1318 loops=1)`
- Full plans: [`c5_baseline_plan.txt`](c5_baseline_plan.txt), [`c5_optimized_plan.txt`](c5_optimized_plan.txt)

**Bottleneck observed in the plans:** Baseline: COUNT(DISTINCT) forces a GroupAggregate fed by a full Sort of 668,862 rows on (itemid, stay_id) using about 45 MB of memory. Optimized: two HashAggregates (first de-duplicating to 40,587 pairs, then counting), with no sort. The gain is real but modest (about 2-3x) because both plans still scan the whole table.
