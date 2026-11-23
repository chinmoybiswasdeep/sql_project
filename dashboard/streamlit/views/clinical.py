"""Clinical analytics: diagnosis mix, laboratory workload and abnormality, medications."""

from __future__ import annotations

import streamlit as st

import charts
import components as ui
import data
from privacy import add_wilson, suppress_rows

f = ui.current_filters()
ui.page_header(
    "Clinical analytics",
    "Diagnoses, laboratory testing and medications",
    "What patients are admitted with, which tests drive laboratory workload, how often results "
    "fall outside the reference range, and which therapeutic drugs are prescribed most.",
)
ui.filter_summary(f)
k = data.kpis(f)
n_adm = int(k["admissions"])
ui.cohort_guard(n_adm)

# ---------------------------------------------------------------- Diagnoses
ui.section("Diagnosis mix")
dx = data.diagnosis_categories(f)
shown, hidden = suppress_rows(dx, ["admissions", "patients"])
shown = shown.assign(
    share=100 * shown["admissions"] / n_adm,
    any_share=100 * shown["admissions_any_position"].fillna(0) / n_adm,
)
fig = charts.hbar(
    shown, y="category", x="share", title="Primary diagnosis category",
    x_title="Share of admissions (%)", customdata=["admissions", "any_share"],
    hover="<b>%{y}</b><br>Primary diagnosis in %{x:.1f}% of admissions (%{customdata[0]:,})"
          "<br>Recorded in any position: %{customdata[1]:.1f}%",
    text_fmt="{:.1f}%",
)
fig.update_xaxes(ticksuffix="%", range=[0, float(shown["share"].max()) * 1.15]
                 if not shown.empty else None)
ui.chart(fig, "Share of filtered admissions whose sequence-1 ICD diagnosis falls in each "
              "ICD chapter-based category (ICD-9 and ICD-10 harmonised). Hover shows how often "
              "the category is coded in any position.")
ui.suppressed_caption(hidden, "categories")

# ---------------------------------------------------------------- Labs
ui.section("Laboratory testing")
labs = data.top_lab_tests(f, limit=15)
if labs.empty:
    ui.empty_card("Laboratory testing", "No admission-linked lab results for this cohort.")
else:
    shown, hidden = suppress_rows(labs, ["admissions", "patients"])
    left, right = st.columns(2, gap="medium")
    with left:
        fig = charts.hbar(
            shown, y="lab_test", x="results", title="Most frequent lab tests",
            x_title="Lab results (count)", customdata=["admissions", "lab_category"],
            hover="<b>%{y}</b><br>Results: %{x:,}<br>Admissions tested: %{customdata[0]:,}"
                  "<br>Category: %{customdata[1]}",
            text_fmt="{:,}",
        )
        fig.update_layout(height=max(240, 120 + 34 * len(shown)))
        fig.update_xaxes(range=[0, float(shown["results"].max()) * 1.15]
                         if not shown.empty else None)
        ui.chart(fig, "Count of lab results linked to a filtered admission (outpatient results "
                      "without an hadm_id are excluded), top 15 tests by volume.")
    with right:
        ab = add_wilson(shown, "abnormal_results", "results").rename(
            columns={"abnormal_results": "numerator", "results": "denominator"})
        fig = charts.rate_ci_dots(
            ab, label="lab_test", title="Abnormal result rate (same 15 tests)",
            x_title="Results flagged abnormal (%, 95% CI)",
        )
        ui.chart(fig, "Numerator: results with the MIMIC-IV abnormal flag set. Denominator: all "
                      "admission-linked results for that test. Repeated draws on the same patient "
                      "are not independent, so intervals are optimistic.")
    ui.suppressed_caption(hidden, "tests")

# ---------------------------------------------------------------- Medications
ui.section("Medications")
meds = data.top_medications(f, limit=15)
if meds.empty:
    ui.empty_card("Medications", "No therapeutic prescriptions for this cohort.")
else:
    shown, hidden = suppress_rows(meds, ["admissions", "patients"])
    shown = shown.assign(share=100 * shown["admissions"] / shown["cohort_admissions"])
    fig = charts.hbar(
        shown, y="drug", x="share", title="Most widely prescribed therapeutic drugs",
        x_title="Admissions with ≥1 order (%)", customdata=["admissions", "orders", "patients"],
        hover="<b>%{y}</b><br>%{x:.1f}% of admissions (%{customdata[0]:,})"
              "<br>Orders: %{customdata[1]:,}<br>Patients: %{customdata[2]:,}",
        text_fmt="{:.0f}%",
    )
    fig.update_xaxes(ticksuffix="%", range=[0, min(100.0, float(shown["share"].max()) * 1.15)])
    ui.chart(fig, "Share of filtered admissions with at least one order for the drug. Base "
                  "solutions (drug_type = BASE) and line flushes are excluded as non-therapeutic.")
    ui.suppressed_caption(hidden, "drugs")

ui.privacy_note()
