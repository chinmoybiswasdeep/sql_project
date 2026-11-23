-- Case C3 optimized: read the pre-aggregated materialized view.
select itemid, label, fluid, results, abnormal_results, admissions_tested
from perf.mv_lab_test_summary
