"""Executive overview: headline KPIs for the filtered cohort, cohort caveat, data freshness."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

import charts
import components as ui
import data
import theme
from privacy import is_small, min_cell_size, suppress_rows, suppression_enabled, wilson_interval

f = ui.current_filters()
ui.page_header(
    "Executive overview",
    "Hospital Intelligence",
    "Headline activity, utilisation and outcome indicators from the MIMIC-IV warehouse. "
    "Use the sidebar to restrict the cohort; every figure is recomputed live.",
)
ui.cohort_caveat_banner()
ui.filter_summary(f)

k = data.kpis(f)
n_adm = int(k["admissions"])
ui.cohort_guard(n_adm)

suppress = suppression_enabled()
kmin = min_cell_size()


def rate_card(label: str, num: int, den: int, definition: str) -> str:
    if den == 0:
        return ui.kpi_card(label, "-", sub="No eligible records in this cohort")
    if suppress and (is_small(num, kmin) or is_small(den, kmin)):
        return ui.kpi_card(label, "Suppressed", sub=f"Fewer than {kmin} records in a cell")
    lo, hi = wilson_interval(num, den)
    sub = f"{num:,} of {den:,} {definition}<br>95% CI {100 * lo:.1f}% to {100 * hi:.1f}%"
    return ui.kpi_card(label, f"{100 * num / den:.1f}", "%", sub)


median_los = float(k["median_los_days"]) if k["median_los_days"] is not None else math.nan
cards = [
    ui.kpi_card("Patients", ui.fmt_int(k["patients"]), sub="Distinct patients with ≥1 admission"),
    ui.kpi_card("Admissions", ui.fmt_int(n_adm),
                sub=f"{n_adm / max(int(k['patients']), 1):.2f} admissions per patient"),
    ui.kpi_card("Median length of stay", ui.fmt_num(median_los, 1), "days",
                sub="Admit to discharge, all admissions"),
    rate_card("ICU admission rate", int(k["icu_admissions"]), n_adm,
              "admissions had an ICU stay"),
    rate_card("30-day readmission", int(k["readmit_num"]), int(k["readmit_den"]),
              "eligible discharges"),
    rate_card("In-hospital mortality", int(k["deaths"]), n_adm, "admissions"),
]
ui.kpi_row(cards[:3])
st.write("")
ui.kpi_row(cards[3:])

# Reconciliation against the curated reporting table (only meaningful when unfiltered).
if not f.is_active:
    rpt = data.reporting_kpis()
    computed = {
        "total_admissions": n_adm,
        "readmission_denominator": int(k["readmit_den"]),
        "readmission_numerator": int(k["readmit_num"]),
        "icu_admission_pct": round(100 * int(k["icu_admissions"]) / n_adm, 1),
        "hospital_mortality_pct": round(100 * int(k["deaths"]) / n_adm, 1),
    }
    mismatches = [c for c, v in computed.items() if float(rpt[c]) != float(v)]
    if mismatches:
        st.warning("Live KPIs differ from reporting.rpt_executive_kpis for: " + ", ".join(mismatches))
    else:
        st.caption("✓ Unfiltered KPIs reconcile with `reporting.rpt_executive_kpis`.")

st.caption(
    "30-day readmission: denominator = eligible index discharges (excludes in-hospital deaths, "
    "discharges against medical advice, transfers to another acute hospital, overlapping next "
    "admissions and missing discharge times); numerator = any next admission within 30 days. "
    f"Unplanned-only rate: {100 * int(k['unplanned_num']) / max(int(k['readmit_den']), 1):.1f}%."
)

ui.section("Cohort composition")
left, right = st.columns([3, 2], gap="medium")
with left:
    age_sex = data.admissions_by_age_sex(f)
    shown, hidden = suppress_rows(age_sex, ["admissions", "patients"])
    fig = charts.grouped_vbar(
        shown, x="age_group", y="admissions", series="sex",
        series_colors=theme.SEX_COLORS, series_labels=theme.SEX_LABELS,
        title="Admissions by age group and sex", x_title="Age at admission (years)",
        y_title="Admissions", category_order=theme.AGE_ORDER,
        customdata=["patients"], hover_extra="<br>Patients: %{customdata[0]:,}",
    )
    fig.update_layout(bargap=0.5, bargroupgap=0.12, height=380)
    ui.chart(fig, "Count of hospital admissions in the filtered cohort; age is measured at each "
                  "admission, so one patient can appear in more than one band.")
    ui.suppressed_caption(hidden)
with right:
    cat = data.admissions_by_category(f)
    shown, hidden = suppress_rows(cat, ["admissions", "patients"])
    shown = shown.assign(share=100 * shown["admissions"] / n_adm)
    fig = charts.hbar(
        shown, y="admission_group", x="share", title="Admission mix",
        x_title="Share of admissions (%)", customdata=["admissions"],
        hover="<b>%{y}</b><br>%{x:.1f}% of admissions<br>%{customdata[0]:,} admissions",
        text_fmt="{:.0f}%",
    )
    fig.update_layout(height=380, bargap=0.62)
    fig.update_xaxes(ticksuffix="%", range=[0, max(10.0, float(shown["share"].max()) * 1.18)]
                     if not shown.empty else None)
    ui.chart(fig, "Share of filtered admissions by admission group (grouped from the MIMIC-IV "
                  "admission_type field).")
    ui.suppressed_caption(hidden)

ui.section("Data freshness")
runs = data.ingestion_runs()
if runs.empty:
    st.info("No ingestion runs have been recorded in meta.ingestion_runs yet.")
else:
    latest = runs.iloc[0]
    finished = pd.to_datetime(latest["finished_at"], utc=True)
    st.markdown(
        f"Latest ingestion run **#{int(latest['run_id'])}** finished "
        f"**{finished:%Y-%m-%d %H:%M} UTC** · status {ui.status_badge(str(latest['status']))} · "
        f"dataset `{latest['dataset_label']}` · {len(runs)} runs recorded.",
        unsafe_allow_html=True,
    )
ui.privacy_note()
