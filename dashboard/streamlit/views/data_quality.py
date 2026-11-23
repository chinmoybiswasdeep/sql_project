"""Data quality & pipeline: freshness, load reconciliation, validation checks, missingness,
query benchmarks. Reads warehouse metadata only; cohort filters do not apply."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import charts
import components as ui
import data
import theme

ui.page_header(
    "Data quality & pipeline",
    "Can the numbers be trusted?",
    "Freshness, row-count reconciliation from source file to warehouse, automated validation "
    "checks and column completeness. Metadata only; the sidebar cohort filters do not apply here.",
)

# ---------------------------------------------------------------- Freshness
runs = data.ingestion_runs()
recon = data.reconciliation()
checks = data.quality_checks()

if runs.empty:
    st.info("No ingestion runs recorded in meta.ingestion_runs.")
    latest_txt, latest_time, latest_status = "-", "", "-"
else:
    latest = runs.iloc[0]
    finished = pd.to_datetime(latest["finished_at"], utc=True)
    latest_txt, latest_time = f"{finished:%Y-%m-%d}", f"{finished:%H:%M} UTC"
    latest_status = str(latest["status"])

n_tables = len(recon)
n_recon = int(recon["reconciled"].sum()) if not recon.empty else 0
n_fail = int((checks["status"] == "fail").sum()) if not checks.empty else 0
n_flag = int((checks["status"] == "flag").sum()) if not checks.empty else 0
n_pass = int((checks["status"] == "pass").sum()) if not checks.empty else 0

ui.kpi_row([
    ui.kpi_card("Data freshness", latest_txt,
                sub=f"Latest ingestion run finished {latest_time}<br>"
                    f"{ui.status_badge(latest_status)}"),
    ui.kpi_card("Tables reconciled", f"{n_recon}/{n_tables}",
                sub="Source rows = loaded rows = rows in raw schema"),
    ui.kpi_card("Validation checks", f"{n_pass}/{len(checks)}",
                sub=f"passing · {n_flag} flagged for review · {n_fail} failed"),
    ui.kpi_card("Ingestion runs", ui.fmt_int(len(runs)),
                sub=f"Dataset {runs.iloc[0]['dataset_label']}" if not runs.empty else ""),
])

# ---------------------------------------------------------------- Reconciliation
ui.section("Per-table reconciliation")
if recon.empty:
    st.info("No raw tables found.")
else:
    view = recon.sort_values("table_name").copy()
    view["Status"] = view["reconciled"].map({True: "✓ Reconciled", False: "✗ Mismatch"})
    view["Latest run"] = view["latest_status"].fillna("-").str.replace("_", " ")
    display = ui.to_display(view, {
        "table_name": "Raw table", "source_rows": "Source rows",
        "rejected_rows": "Rejected", "duplicate_key_rows": "Dup. keys",
        "loaded_rows": "Loaded", "current_raw_rows": "In warehouse",
        "Status": "Status", "Latest run": "Latest run",
    })
    count_fmt = st.column_config.NumberColumn(format="localized")
    with st.container(border=True):
        st.dataframe(
            display, hide_index=True, width="stretch", height=ui.table_height(len(display)),
            column_config={c: count_fmt for c in
                           ["Source rows", "Rejected", "Dup. keys", "Loaded", "In warehouse"]},
        )
        st.caption("Reconciled when loaded rows = source rows − rejected − duplicate-key rows "
                   "for the last run that actually loaded the file, and the raw table still holds "
                   "exactly that many rows. 'Unchanged' runs skip files whose SHA-256 is unchanged.")

# ---------------------------------------------------------------- Validation checks
ui.section("Validation checks")
if checks.empty:
    st.info("No validation results in reporting.rpt_data_quality_checks.")
else:
    with st.container():
        sev_order = ["error", "warn", "info"]
        status_meta = [("pass", "Pass", theme.STATUS["good"]),
                       ("flag", "Flagged", theme.STATUS["warning"]),
                       ("fail", "Failed", theme.STATUS["critical"])]
        counts = checks.groupby(["severity", "status"]).size().rename("n").reset_index()
        fig = go.Figure()
        for status, label, color in status_meta:
            d = counts[counts["status"] == status].set_index("severity").reindex(sev_order)
            if d["n"].fillna(0).sum() == 0:
                continue
            fig.add_trace(go.Bar(
                y=sev_order, x=d["n"].fillna(0), name=label, orientation="h", marker_color=color,
                marker_line=dict(color=theme.SURFACE, width=2),
                hovertemplate=f"<b>%{{y}}</b> severity<br>{label}: %{{x}}<extra></extra>",
            ))
        fig.update_layout(barmode="stack", title_text="Check outcomes by severity",
                          height=240, bargap=0.45, barcornerradius=0)
        fig.update_xaxes(title_text="Checks (count)", dtick=2)
        fig.update_yaxes(title_text="Severity", showgrid=False, autorange="reversed",
                         ticksuffix="  ")
        ui.chart(fig, "Automated checks from the latest validation run; 'flagged' = rows matched "
                      "an informational or warning rule and need review, not a pipeline failure.")
    with st.container():
        tbl = checks.copy()
        tbl["Result"] = tbl["status"].map({"pass": "✓ Pass", "flag": "⚑ Flag", "fail": "✗ Fail"})
        display = ui.to_display(tbl, {
            "Result": "Result", "check_name": "Check", "table_name": "Table",
            "severity": "Severity", "flagged_rows": "Flagged rows", "description": "Rule",
        })
        with st.container(border=True):
            st.dataframe(display, hide_index=True, width="stretch",
                         height=ui.table_height(len(display)))
            run_id = int(checks["run_id"].max())
            st.caption(f"reporting.rpt_data_quality_checks · validation run #{run_id}. Flagged "
                       "rows are counts of records matching a rule; record detail is not shown.")

# ---------------------------------------------------------------- Missingness
ui.section("Completeness")
miss = data.missingness()
if miss.empty:
    st.info("No column profile in reporting.rpt_missingness.")
else:
    with_nulls = miss[miss["null_pct"] > 0].copy()
    left, right = st.columns([11, 9], gap="medium")
    with left:
        top = with_nulls.head(15).assign(column=lambda d: d["table_name"] + "." + d["column_name"])
        if top.empty:
            ui.empty_card("Missingness", "No profiled column contains nulls.")
        else:
            fig = charts.hbar(
                top, y="column", x="null_pct", title="Columns with the most missing values",
                x_title="Null values (% of rows)", customdata=["null_count", "row_count"],
                hover="<b>%{y}</b><br>%{x:.1f}% null<br>%{customdata[0]:,} of "
                      "%{customdata[1]:,} rows",
                text_fmt="{:.0f}%",
            )
            fig.update_xaxes(range=[0, 115], ticksuffix="%", dtick=25)
            ui.chart(fig, "Share of rows with a NULL in each raw column (top 15). High values are "
                          "often structural, e.g. deathtime is null for survivors.")
    with right:
        summary = (miss.assign(has_nulls=miss["null_pct"] > 0)
                   .groupby("table_name")
                   .agg(columns=("column_name", "count"), with_nulls=("has_nulls", "sum"),
                        worst_pct=("null_pct", "max"))
                   .reset_index())
        display = ui.to_display(summary, {
            "table_name": "Table", "columns": "Columns",
            "with_nulls": "With nulls", "worst_pct": "Max null %",
        })
        with st.container(border=True):
            st.markdown("**Completeness by table**")
            st.dataframe(display, hide_index=True, width="stretch",
                         height=ui.table_height(len(display)),
                         column_config={"Max null %":
                                        st.column_config.NumberColumn(format="%.1f%%")})
            st.caption(f"{len(miss)} columns profiled across {summary.shape[0]} raw tables "
                       f"(reporting.rpt_missingness).")

# ---------------------------------------------------------------- Benchmarks
ui.section("Query benchmarks")
bench = data.benchmarks()
if bench.empty:
    st.info("No benchmark results yet: meta.query_benchmarks is empty. Run the benchmark suite "
            "to populate it; this section updates automatically (cache refreshes every 10 min).")
else:
    wide = bench.pivot_table(index="case_name", columns="variant", values="median_ms",
                             aggfunc="first").reset_index()
    if {"baseline", "optimized"} <= set(wide.columns):
        wide["case"] = wide["case_name"].map(data.benchmark_case_label)
        wide["speedup"] = wide["baseline"] / wide["optimized"]
        wide["note"] = [f"{v:,.0f}× faster" if v >= 10 else f"{v:,.1f}× faster"
                        for v in wide["speedup"]]
        fig = charts.dumbbell_log(
            wide, label="case", low="optimized", high="baseline", low_name="Optimized",
            high_name="Baseline", title="Query runtime before and after optimisation",
            x_title="Median runtime (ms, log scale)", note="note",
        )
        runs_n = int(bench["runs"].max())
        ui.chart(fig, f"Median wall-clock time over {runs_n} runs per variant (latest measurement "
                      "per case, meta.query_benchmarks, dataset "
                      f"{bench['dataset_label'].iloc[0]}). Log scale: each gridline is 10×.")
    display = ui.to_display(bench.sort_values(["case_name", "variant"]), {
        "case_name": "Case", "variant": "Variant", "runs": "Runs", "median_ms": "Median ms",
        "min_ms": "Min ms", "max_ms": "Max ms", "result_rows": "Result rows",
    })
    with st.expander("Benchmark measurements"):
        st.dataframe(display, hide_index=True, width="stretch")
