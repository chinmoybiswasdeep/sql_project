# Interview Questions and Answers

Five likely questions about the technical decisions in this project, with answers grounded in
what the code actually does.

---

### 1. "How did you make sure your joins didn't inflate counts?"

The central fact table, `fact_admissions`, carries per-admission counts of labs, ICU stays,
diagnoses, prescriptions and transfers. Joining those child tables directly would multiply
rows: an admission with 300 lab results and 15 diagnoses would become 4,500 rows. Instead
each child table is aggregated to `hadm_id` in its own CTE and only then left-joined, so
every join is one-to-one.

Three controls enforce this:
- a dbt `row_count_equals` test: fact rows must equal source admissions (275)
- `unique` tests on every declared grain key
- `sql/validation/v03_fanout_reconciliation.sql`, which checks that the *sum* of the
  per-admission counts equals the raw event counts (79,307 admission-linked lab events,
  4,506 diagnoses, 18,087 prescriptions, 140 ICU stays, 515.11 ICU days, all exact).

### 2. "Walk me through your 30-day readmission definition. Why those exclusions?"

The denominator is *eligible index discharges*. I exclude in-hospital deaths (no chance to
be readmitted), transfers to another acute hospital (the episode continues elsewhere),
against-advice discharges (CMS practice) and overlapping next admissions (a data anomaly).
The numerator is any next admission within 30 days. A LEAD window over each patient's
admissions finds the next one; I only need the immediate next, because if it falls outside
the window every later one does too.

I report "unplanned" (the next admission isn't elective) but deliberately don't call
anything "preventable", because that needs a validated algorithm I didn't implement. I also
ran a sensitivity analysis: the rate is 20.4% under the primary definition, 23.7% excluding
observation stays and 15.8% counting one discharge per patient. That spread is itself a
finding: the KPI has to be published with its definition.

### 3. "How do you know your numbers are right?"

Defence in depth, using methods that don't share code:
1. **Ingestion reconciliation:** source rows = loaded + rejected for every table, and raw
   counts match an independent pyarrow count of each file.
2. **dbt tests:** 103 data tests (keys, relationships, accepted values, invariants such as
   `abnormal ≤ total labs`) and 2 unit tests on synthetic edge cases.
3. **Independent re-implementation:** the readmission metric is recomputed three ways (dbt
   `LEAD`, SQL `NOT EXISTS` self-join on raw tables, pandas on the original CSVs) and all
   agree exactly.
4. **Stale-narrative guard:** a test asserts the figures quoted in my written
   interpretations, so if the data changes, CI fails instead of the report quietly going
   wrong.

### 4. "Your sample is 100 patients. How do you handle uncertainty?"

First, I state the selection: every demo patient had an ICU stay, so it's an ICU cohort and
I never present its rates as hospital-wide. Second, every rate gets a Wilson 95% interval,
which behaves well for small n, unlike the Wald interval. Third, admissions are clustered:
one patient has 20. So for headline rates and medians I use a patient-level cluster
bootstrap, which gives a wider readmission interval (14.1–26.1% vs 15.9–25.8%). Fourth, I
lead with effect sizes (Cliff's delta, risk differences) rather than p-values, and I label
classical tests as optimistic under clustering. Findings are framed as hypotheses to test on
the full 546k-admission dataset.

### 5. "Tell me about a performance optimization and how you verified it."

The clearest one is vital-sign counts per ICU stay. The baseline used five correlated scalar
subqueries, a common reporting pattern. EXPLAIN ANALYZE showed each one doing a full
sequential scan of the 669k-row chartevents table once per stay: 700 full scans and about 13 to 15
seconds, depending on the run. Rewriting it as a single scan with `count(*) FILTER (WHERE itemid = …)` per vital
cut it to about 33 ms (exact timings vary run to run; see the benchmark report). The benchmark harness drops all optimization objects before each case, times
seven runs after a warm-up using `EXPLAIN (ANALYZE, TIMING OFF)`, and hashes both result
sets to prove they're identical.

I also report setup costs honestly. The materialized view case shows a huge read speedup,
but building the view costs about 60 ms, so it only pays off when it's read more than once
per refresh. These are demo-scale numbers; full-scale behaviour needs its own benchmark.
