"""Reproducible SQL optimization benchmarks.

For each case:
  1. reset to a clean baseline (all benchmark indexes/views dropped)
  2. capture EXPLAIN (ANALYZE, BUFFERS) of the baseline query
  3. time N runs (after one warm-up) using EXPLAIN (ANALYZE, TIMING OFF), which
     reports server-side execution time without per-node timing overhead
  4. apply the optimization (index / materialized view) if the case has one
  5. capture the optimized plan and time N runs the same way
  6. verify both queries return identical results (order-independent hash of
     rows with floats rounded to 6 dp)
  7. record results in meta.query_benchmarks and reports/benchmarks/

Timings depend on hardware and cache state and are reported as measured;
nothing is extrapolated to the full dataset.

Usage:  python -m analytics.performance.benchmark [--runs 7] [--cases c1 c3]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import psycopg

from config.settings import PROJECT_ROOT, get_settings

SQL_DIR = PROJECT_ROOT / "sql" / "optimization"
OUT_DIR = PROJECT_ROOT / "reports" / "benchmarks"

RESET_SQL = """
DROP INDEX IF EXISTS raw.ix_perf_chartevents_item_stay_time;
DROP MATERIALIZED VIEW IF EXISTS perf.mv_lab_test_summary;
"""


@dataclass(frozen=True)
class Case:
    key: str
    title: str
    technique: str
    baseline: str
    optimized: str
    setup: str | None
    rationale: str


CASES = [
    Case("c1", "First-24h heart rate per ICU stay", "Covering composite index",
         "c1_vitals_first24h.sql", "c1_vitals_first24h.sql", "c1_setup_optimized.sql",
         "Filters chartevents (largest table) on itemid + stay_id + a charttime range. Without "
         "an index the planner must scan every chart event; a composite index in predicate "
         "order with INCLUDE(valuenum) allows an index-only range scan per stay."),
    Case("c2", "Lab delta check (change from previous result)",
         "Correlated subquery -> LAG() window",
         "c2_lab_delta_baseline.sql", "c2_lab_delta_optimized.sql", None,
         "The correlated subquery executes once per outer row (~10k), each doing an index "
         "probe plus top-1 sort over the patient's history. LAG() computes the same value "
         "in a single sorted pass."),
    Case("c3", "Lab test summary for dashboards", "Pre-aggregation (materialized view)",
         "c3_lab_summary_baseline.sql", "c3_lab_summary_optimized.sql",
         "c3_setup_optimized.sql",
         "The summary is requested repeatedly but changes only when data is reloaded. "
         "Materializing it moves the full scan, join and COUNT DISTINCT to refresh time."),
    Case("c4", "Vital-sign counts per ICU stay", "Many correlated scans -> one pass",
         "c4_vitals_counts_baseline.sql", "c4_vitals_counts_optimized.sql", None,
         "Five scalar subqueries per stay each scan chartevents (no index on stay_id), so "
         "the table is read hundreds of times. Conditional aggregation reads it once."),
    Case("c5", "Distinct ICU stays per charted item", "COUNT(DISTINCT) -> two-phase GROUP BY",
         "c5_distinct_stays_baseline.sql", "c5_distinct_stays_optimized.sql", None,
         "COUNT(DISTINCT) forces a sort-based aggregate per group and cannot use parallel "
         "or hash aggregation; de-duplicating with GROUP BY first can."),
]


def exec_script(cur: psycopg.Cursor, script: str) -> None:
    """Run statements one at a time (VACUUM cannot run inside a multi-statement block).
    Setup scripts are simple DDL with no semicolons inside literals."""
    body = "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("--"))
    for statement in (s.strip() for s in body.split(";")):
        if statement:
            cur.execute(statement)


def _normalise(value):
    if isinstance(value, float | Decimal):
        return round(float(value), 6)
    return value


def result_fingerprint(cur: psycopg.Cursor, query: str) -> tuple[str, int]:
    cur.execute(query)
    rows = sorted((tuple(_normalise(v) for v in row) for row in cur.fetchall()), key=repr)
    digest = hashlib.sha256(repr(rows).encode()).hexdigest()[:16]
    return digest, len(rows)


def execution_ms(cur: psycopg.Cursor, query: str) -> float:
    cur.execute(f"EXPLAIN (ANALYZE, TIMING OFF, SUMMARY ON, FORMAT JSON) {query}")
    plan = cur.fetchone()[0]
    plan = plan[0] if isinstance(plan, list) else json.loads(plan)[0]
    return float(plan["Execution Time"])


def plan_text(cur: psycopg.Cursor, query: str) -> str:
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, SETTINGS) {query}")
    return "\n".join(r[0] for r in cur.fetchall())


def time_query(cur: psycopg.Cursor, query: str, runs: int) -> list[float]:
    execution_ms(cur, query)  # warm-up (populates shared buffers / plan cache)
    return [execution_ms(cur, query) for _ in range(runs)]


def run_case(conn: psycopg.Connection, case: Case, runs: int, label: str) -> dict:
    base_sql = (SQL_DIR / case.baseline).read_text()
    opt_sql = (SQL_DIR / case.optimized).read_text()
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS perf")
        exec_script(cur, RESET_SQL)
        cur.execute("VACUUM (ANALYZE) raw.chartevents")
        cur.execute("ANALYZE raw.labevents")

        base_plan = plan_text(cur, base_sql)
        base_times = time_query(cur, base_sql, runs)
        base_hash, base_rows = result_fingerprint(cur, base_sql)

        setup_ms = None
        if case.setup:
            t0 = time.perf_counter()
            exec_script(cur, (SQL_DIR / case.setup).read_text())
            setup_ms = (time.perf_counter() - t0) * 1000
        opt_plan = plan_text(cur, opt_sql)
        opt_times = time_query(cur, opt_sql, runs)
        opt_hash, opt_rows = result_fingerprint(cur, opt_sql)

        for variant, times, h, n in (("baseline", base_times, base_hash, base_rows),
                                     ("optimized", opt_times, opt_hash, opt_rows)):
            cur.execute(
                """INSERT INTO meta.query_benchmarks
                   (dataset_label, case_name, variant, runs, median_ms, min_ms, max_ms,
                    result_hash, result_rows) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (label, case.key, variant, runs, statistics.median(times), min(times),
                 max(times), h, n))
        exec_script(cur, RESET_SQL)  # leave the database in its baseline state
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{case.key}_baseline_plan.txt").write_text(base_plan + "\n")
    (OUT_DIR / f"{case.key}_optimized_plan.txt").write_text(opt_plan + "\n")
    b, o = statistics.median(base_times), statistics.median(opt_times)
    return {"case": case.key, "title": case.title, "technique": case.technique,
            "rationale": case.rationale, "runs": runs, "setup_ms": setup_ms,
            "baseline_median_ms": b, "baseline_min_ms": min(base_times),
            "baseline_max_ms": max(base_times),
            "optimized_median_ms": o, "optimized_min_ms": min(opt_times),
            "optimized_max_ms": max(opt_times), "speedup": b / o if o else None,
            "baseline_rows": base_rows, "optimized_rows": opt_rows,
            "results_equivalent": base_hash == opt_hash and base_rows == opt_rows,
            "baseline_plan_root": base_plan.splitlines()[0],
            "optimized_plan_root": opt_plan.splitlines()[0]}


def environment(conn: psycopg.Connection) -> dict:
    with conn.cursor() as cur:
        cur.execute("select version()")
        version = cur.fetchone()[0]
        settings = {}
        for name in ("shared_buffers", "work_mem", "jit", "max_parallel_workers_per_gather"):
            cur.execute(f"show {name}")
            settings[name] = cur.fetchone()[0]
        cur.execute("select count(*) from raw.chartevents")
        chart = cur.fetchone()[0]
        cur.execute("select count(*) from raw.labevents")
        labs = cur.fetchone()[0]
    return {"postgres": version.split(",")[0], "machine": f"{platform.system()} "
            f"{platform.machine()}", "settings": settings,
            "rows": {"raw.chartevents": chart, "raw.labevents": labs}}


def render(results: list[dict], env: dict, label: str, runs: int) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# SQL Performance Benchmarks", "",
        f"_Generated {generated} by `python -m analytics.performance.benchmark` on "
        f"`{label}`. Median of {runs} timed runs after one warm-up; server-side execution "
        "time from `EXPLAIN (ANALYZE, TIMING OFF)`._", "",
        f"- **Engine:** {env['postgres']} on {env['machine']}",
        "- **Settings:** " + ", ".join(f"{k}={v}" for k, v in env["settings"].items()),
        "- **Table sizes:** " + ", ".join(f"{k} {v:,} rows" for k, v in env["rows"].items()),
        "", "> These are **demo-scale** measurements (largest table 669k rows). They show "
        "that each optimization changes the plan in the expected way, and by how much at "
        "this scale. They are not projections: full MIMIC-IV chartevents holds hundreds of "
        "millions of rows and must be benchmarked separately on authorized data.", "",
        "| Case | Technique | Baseline median (ms) | Optimized median (ms) | Speedup | "
        "One-off setup cost (ms) | Rows | Results identical |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in results:
        lines.append(f"| {r['case'].upper()}: {r['title']} | {r['technique']} | "
                     f"{r['baseline_median_ms']:.2f} | {r['optimized_median_ms']:.2f} | "
                     f"{r['speedup']:.1f}x | "
                     f"{'—' if r['setup_ms'] is None else format(r['setup_ms'], '.0f')} | "
                     f"{r['baseline_rows']:,} | "
                     f"{'yes' if r['results_equivalent'] else '**NO**'} |")
    lines += ["", "Setup cost is the measured time to build the index or materialized view "
              "(including VACUUM/ANALYZE). Query rewrites (C2, C4, C5) have no setup cost. "
              "Speedups for C3 are only meaningful when the view is read many times per "
              "refresh; the honest comparison is refresh cost vs. (requests x baseline time)."]
    for r in results:
        lines += ["", f"## {r['case'].upper()}: {r['title']}", "",
                  f"**Technique:** {r['technique']}  ", f"**Why:** {r['rationale']}", "",
                  f"- Baseline: median {r['baseline_median_ms']:.2f} ms "
                  f"(min {r['baseline_min_ms']:.2f}, max {r['baseline_max_ms']:.2f})",
                  f"- Optimized: median {r['optimized_median_ms']:.2f} ms "
                  f"(min {r['optimized_min_ms']:.2f}, max {r['optimized_max_ms']:.2f})",
                  f"- Baseline plan root: `{r['baseline_plan_root'].strip()}`",
                  f"- Optimized plan root: `{r['optimized_plan_root'].strip()}`",
                  f"- Full plans: [`{r['case']}_baseline_plan.txt`]({r['case']}_baseline_plan.txt), "
                  f"[`{r['case']}_optimized_plan.txt`]({r['case']}_optimized_plan.txt)"]
        note = BOTTLENECK_NOTES.get(r["case"])
        if note:
            lines += ["", f"**Bottleneck observed in the plans:** {note}"]
    return "\n".join(lines) + "\n"


# Written after reading the captured plans (reports/benchmarks/*_plan.txt).
NOTES_FILE = SQL_DIR / "bottleneck_notes.json"
BOTTLENECK_NOTES: dict[str, str] = (
    json.loads(NOTES_FILE.read_text()) if NOTES_FILE.exists() else {}
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--cases", nargs="*", help="subset of case keys, e.g. c1 c3")
    args = parser.parse_args(argv)
    settings = get_settings()
    cases = [c for c in CASES if not args.cases or c.key in args.cases]
    with psycopg.connect(settings.pg.conninfo, autocommit=True) as conn:
        env = environment(conn)
        results = []
        for case in cases:
            print(f"running {case.key}: {case.title} ...", flush=True)
            r = run_case(conn, case, args.runs, settings.dataset_label)
            print(f"  baseline {r['baseline_median_ms']:.2f} ms | optimized "
                  f"{r['optimized_median_ms']:.2f} ms | {r['speedup']:.1f}x | "
                  f"equivalent={r['results_equivalent']}", flush=True)
            results.append(r)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "benchmark_results.json").write_text(
        json.dumps({"environment": env, "results": results}, indent=2, default=str))
    (OUT_DIR / "benchmark_report.md").write_text(render(results, env,
                                                        settings.dataset_label, args.runs))
    print(f"wrote {(OUT_DIR / 'benchmark_report.md').relative_to(PROJECT_ROOT)}")
    return 0 if all(r["results_equivalent"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
