"""Hospital operations: length of stay, admission mix, ICU utilisation, transfer flows and
resource-use proxies."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import charts
import components as ui
import data
import theme
from privacy import mask_table, suppress_rows

f = ui.current_filters()
ui.page_header(
    "Hospital operations",
    "Throughput and utilisation",
    "How long patients stay, how they arrive, which ICUs carry the load and how patients "
    "move between care units.",
)
ui.filter_summary(f)
summary = data.los_summary(f)
ui.cohort_guard(int(summary["admissions"]))

cards = [
    ui.kpi_card("Median LOS", ui.fmt_num(summary["p50"]), "days", "Hospital length of stay"),
    ui.kpi_card("Interquartile range", f"{summary['p25']:.1f}–{summary['p75']:.1f}", "days",
                "25th to 75th percentile"),
    ui.kpi_card("Mean LOS", ui.fmt_num(summary["mean"]), "days",
                "Above the median: right-skewed stays"),
    ui.kpi_card("90th percentile", ui.fmt_num(summary["p90"]), "days", "Long-stay threshold"),
]
ui.kpi_row(cards)

# ---------------------------------------------------------------- LOS + admission category
ui.section("Length of stay")
left, right = st.columns([3, 2], gap="medium")
with left:
    hist = data.los_histogram(f)
    shown, hidden = suppress_rows(hist, ["admissions", "patients"])
    shown = shown.assign(label=[f"{d}+" if d == 30 else str(d) for d in shown["los_day"]])
    fig = charts.vbar(
        shown, x="los_day", y="admissions", title="Length-of-stay distribution",
        x_title="Length of stay (whole days; 30 = 30 or more)", y_title="Admissions",
        customdata=["label", "patients"], bargap=0.12,
        hover="<b>%{customdata[0]} days</b><br>Admissions: %{y:,}"
              "<br>Patients: %{customdata[1]:,}",
    )
    fig.add_vline(x=float(summary["p50"]), line_width=1, line_color=theme.INK_SECONDARY,
                  annotation_text=f"Median {summary['p50']:.1f} d", annotation_position="top right",
                  annotation_font=dict(size=11, color=theme.INK_SECONDARY))
    fig.update_xaxes(dtick=5)
    ui.chart(fig, "Admissions per completed day of stay (discharge minus admission time); "
                  "stays of 30+ days are pooled in the last bar.")
    ui.suppressed_caption(hidden, "bins")
with right:
    cat = data.admissions_by_category(f)
    shown, hidden = suppress_rows(cat, ["admissions", "patients"])
    shown = shown.rename(columns={"los_p25": "p25", "los_p50": "p50", "los_p75": "p75"})
    fig = charts.median_iqr(
        shown, label="admission_group", title="Length of stay by admission group",
        x_title="Length of stay (days)",
        order=[g for g in theme.ADMISSION_GROUP_ORDER if g in set(shown["admission_group"])],
    )
    ui.chart(fig, "Dot = median length of stay; bar = interquartile range (25th–75th "
                  "percentile). Denominator: all filtered admissions in each group.")
    ui.suppressed_caption(hidden)

# ---------------------------------------------------------------- ICU utilisation
ui.section("ICU utilisation")
icu = data.icu_by_unit(f)
if icu.empty:
    ui.empty_card("ICU utilisation by unit", "No ICU stays in the filtered cohort.")
else:
    shown, hidden = suppress_rows(icu, ["icu_stays", "patients"])
    # Display the unit's own abbreviation, e.g. "Medical Intensive Care Unit (MICU)" -> "MICU".
    shown["unit"] = shown["care_unit"].str.extract(r"\(([^)]+)\)\s*$", expand=False).fillna(
        shown["care_unit"])
    left, right = st.columns(2, gap="medium")
    with left:
        fig = charts.hbar(
            shown, y="unit", x="icu_days", title="ICU bed-days by first care unit",
            x_title="ICU bed-days",
            customdata=["icu_stays", "patients", "median_icu_los_days", "care_unit"],
            hover="<b>%{customdata[3]}</b><br>ICU bed-days: %{x:,.1f}<br>Stays: %{customdata[0]:,}"
                  "<br>Patients: %{customdata[1]:,}<br>Median stay: %{customdata[2]:.1f} days",
            text_fmt="{:,.0f}",
        )
        fig.update_xaxes(range=[0, float(shown["icu_days"].max()) * 1.15] if not shown.empty
                         else None)
        ui.chart(fig, "Sum of ICU length of stay (days) for stays starting in each unit, "
                      "restricted to admissions in the filtered cohort. Hover for full unit names.")
    with right:
        fig = charts.hbar(
            shown, y="unit", x="median_icu_los_days",
            title="Median ICU length of stay by unit", x_title="Median ICU stay (days)",
            customdata=["icu_stays", "care_unit"],
            hover="<b>%{customdata[1]}</b><br>Median ICU stay: %{x:.1f} days<br>Stays: %{customdata[0]:,}",
            text_fmt="{:.1f}",
        )
        fig.update_xaxes(range=[0, float(shown["median_icu_los_days"].max()) * 1.18]
                         if not shown.empty else None)
        ui.chart(fig, "Median ICU intime-to-outtime duration per stay; units with few stays "
                      "(see hover) give unstable medians.")
    ui.suppressed_caption(hidden, "units")

# ---------------------------------------------------------------- Transfer flows
ui.section("Patient flow between care units")
flows = data.transfer_flows(f)
if flows.empty:
    ui.empty_card("Care-unit transitions", "No unit changes recorded for the filtered cohort.")
else:
    shown, hidden = suppress_rows(flows, ["admissions", "patients"])
    unit_order = ["Emergency", "Observation", "Perioperative", "ICU", "Intermediate / step-down",
                  "Medical ward", "Surgical ward", "Mixed med-surg ward", "Discharge lounge",
                  "Unknown"]
    present = set(shown["from_unit_type"]) | set(shown["to_unit_type"])
    order = [u for u in unit_order if u in present] + sorted(present - set(unit_order))
    matrix = (shown.pivot_table(index="from_unit_type", columns="to_unit_type",
                                values="transitions", aggfunc="sum")
              .reindex(index=[u for u in order if u in set(shown["from_unit_type"])],
                       columns=[u for u in order if u in set(shown["to_unit_type"])]))
    fig = charts.heatmap(matrix, title="Care-unit transitions (from → to)",
                         x_title="Destination unit type", y_title="Origin unit type",
                         hover_value="Transitions")
    ui.chart(fig, "Count of transfer events where the patient moved to a different care unit "
                  "(is_unit_change), by origin and destination unit type. Empty cells: none "
                  "recorded" + (" or suppressed." if hidden else "."))
    ui.suppressed_caption(hidden, "unit pairs")

# ---------------------------------------------------------------- Resource proxies
ui.section("Resource-use proxies")
res = data.resource_by_category(f)
res["admission_group"] = pd.Categorical(res["admission_group"],
                                        categories=theme.ADMISSION_GROUP_ORDER, ordered=True)
res = res.sort_values("admission_group")
display = ui.to_display(res, {
    "admission_group": "Admission group", "admissions": "Admissions", "patients": "Patients",
    "median_lab_events": "Lab results", "median_prescriptions": "Rx orders",
    "median_procedures": "Procedures", "median_diagnoses": "Diagnoses",
    "mean_unit_changes": "Unit moves", "icu_days_total": "ICU bed-days",
})
display["Admission group"] = display["Admission group"].astype(str)
display, n_masked = mask_table(display, ["Admissions", "Patients"])
with st.container(border=True):
    st.markdown("**Resource use per admission, by admission group**")
    st.dataframe(display, hide_index=True, width="stretch",
                 height=ui.table_height(len(display)))
    st.caption("Lab results, Rx orders, procedures, diagnoses: median count per admission. "
               "Unit moves: mean care-unit changes per admission. ICU bed-days: group total. "
               "Observable proxies only: no cost or staffing data exist in MIMIC-IV.")
ui.suppressed_caption(n_masked, "rows")

labs = data.labs_by_los_band(f)
shown, hidden = suppress_rows(labs, ["admissions", "patients"])
band_order = [b for b in theme.LOS_BAND_ORDER if b in set(shown["los_band"])]
band_ticks = [b.replace(" days", "<br>days").replace(" day", "<br>day") for b in band_order]
left, right = st.columns(2, gap="medium")
for col, measure, title, y_title, noun in (
    (left, "median_lab_events", "Lab workload rises with length of stay",
     "Median lab results per admission", "lab results"),
    (right, "median_prescriptions", "Prescribing rises with length of stay",
     "Median prescription orders per admission", "prescription orders"),
):
    with col:
        fig = charts.vbar(
            shown, x="los_band", y=measure, title=title, x_title="Length-of-stay band",
            y_title=y_title, customdata=["admissions"], category_order=band_order,
            hover=f"<b>%{{x}}</b><br>Median {noun}: %{{y:,.0f}}<br>Admissions: "
                  "%{customdata[0]:,}",
            bargap=0.55, height=360,
        )
        fig.update_xaxes(tickvals=band_order, ticktext=band_ticks)
        ui.chart(fig, f"Median count of admission-linked {noun} per admission, by "
                      "length-of-stay band. Denominator: filtered admissions in each band.")
ui.suppressed_caption(hidden, "bands")

ui.privacy_note()
