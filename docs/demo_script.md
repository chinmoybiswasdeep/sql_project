# Three-Minute Demo Script

Timing assumes about 150 words per minute. Have the README, the Streamlit app, and
`docs/sql_catalog.md` open in tabs.

---

**0:00 – 0:25 · The problem (README)**

> "Hospital operations teams need trustworthy answers to basic questions: how long patients
> stay, who comes back within 30 days, where ICU capacity goes. The data is messy: mixed ICD
> versions, shifted dates, events with no admission attached. I built Hospital Intelligence,
> an end-to-end analytics platform on MIMIC-IV, the de-identified EHR dataset from Beth
> Israel Deaconess, to turn that raw data into validated metrics."

**0:25 – 0:55 · Architecture (README diagram)**

> "Python streams the source files into PostgreSQL with type-safe parsing. Bad rows are
> quarantined, not dropped, and every table is row-count reconciled. dbt then builds staging,
> intermediate and a star schema of seven facts with declared grains, and 103 data tests plus
> unit tests guard it. On top sit 25 analytical SQL queries, a statistics module, a Streamlit
> dashboard and a Power BI package."

**0:55 – 1:40 · The SQL (open Q06 in the catalog, then the readmission model)**

> "Readmission is the metric people most often get wrong, so I made the definition explicit.
> The denominator excludes in-hospital deaths, transfers to other hospitals,
> against-advice discharges and overlapping stays. A LEAD window finds each patient's next
> admission. On the demo that gives 52 of 255 eligible discharges, 20.4%. I didn't trust my
> own SQL, so I verified it twice: once with a NOT EXISTS self-join on the raw tables, and
> once with an independent pandas implementation on the original CSVs. Both match exactly. A
> dbt unit test covers edge cases like 8-hour returns and the exact 30-day boundary."

**1:40 – 2:15 · Insights (Streamlit Overview → Outcomes)**

> "Three findings. First, 12 patients with seven or more admissions generate 44% of all
> admissions, so readmission work should target them. Second, the readmission rate swings
> from 15.8% to 23.7% depending on defensible definition choices, so any KPI must ship with
> its definition. Third, ICU stays of a week or longer are 14% of stays but 46% of ICU days.
> I'm careful about scope: the demo is 100 ICU patients, so these are hypotheses for the full
> dataset, and every rate is shown with its confidence interval."

**2:15 – 2:45 · Performance (benchmark report)**

> "I benchmarked five optimizations with EXPLAIN ANALYZE and verified each returns identical
> results. Replacing five correlated subqueries with one conditional aggregation took a
> vitals query from about 13 to 15 seconds down to about 33 milliseconds. A LAG window replaced a per-row
> subquery for lab delta checks, going from about 1 second to under 5 milliseconds."

**2:45 – 3:00 · Close**

> "Everything is reproducible: one script downloads the public data, builds the warehouse,
> runs 25 queries, regenerates every report and runs the tests. Patient-level data never
> leaves the machine. Happy to go deeper on any layer."

---

**If asked "what would you do next?"** Run it on the credentialed full dataset (546k
admissions), add severity adjustment for mortality comparisons, and map drugs to RxNorm.
