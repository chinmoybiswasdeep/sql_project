"""Patient outcomes: 30-day readmission and in-hospital mortality with Wilson 95% CIs, and
length-of-stay comparisons."""

from __future__ import annotations

import streamlit as st

import charts
import components as ui
import data
import theme
from privacy import add_wilson, suppress_rows

f = ui.current_filters()
ui.page_header(
    "Patient outcomes",
    "Readmission, mortality and length of stay",
    "Rates are shown with Wilson score 95% confidence intervals. With a few hundred "
    "admissions the intervals are wide; overlapping intervals mean the data cannot "
    "distinguish the groups.",
)
ui.filter_summary(f)
k = data.kpis(f)
ui.cohort_guard(int(k["admissions"]))

readmit_den, readmit_num = int(k["readmit_den"]), int(k["readmit_num"])
overall_readmit = 100 * readmit_num / readmit_den if readmit_den else None
overall_mort = 100 * int(k["deaths"]) / int(k["admissions"])

READMIT_DEF = ("Numerator: any next admission within 30 days of discharge. Denominator: eligible "
               "index discharges (excludes in-hospital deaths, AMA, transfers to acute care, "
               "overlapping next admissions).")


def ci_frame(raw, label_col: str = "grp"):
    shown, hidden = suppress_rows(raw, ["numerator", "denominator", "patients"])
    return add_wilson(shown, "numerator", "denominator").rename(columns={label_col: "group"}), hidden


MORT_DEF = ("Numerator: admissions ending in death in hospital. Denominator: all filtered "
            "admissions in the group.")

# ---------------------------------------------------------------- By age group
ui.section("Outcomes by age group")
left, right = st.columns(2, gap="medium")
with left:
    if readmit_den == 0:
        ui.empty_card("30-day readmission by age group",
                      "No eligible index discharges in the filtered cohort.")
    else:
        df, hidden = ci_frame(data.readmission_by(f, "age_group"))
        fig = charts.rate_ci_dots(
            df, label="group", title="30-day readmission by age group",
            x_title="Readmitted within 30 days (%, 95% CI)", reference_pct=overall_readmit,
            order=[a for a in theme.AGE_ORDER if a in set(df["group"])],
        )
        ui.chart(fig, READMIT_DEF)
        ui.suppressed_caption(hidden)
with right:
    df, hidden = ci_frame(data.mortality_by(f, "age_group"))
    fig = charts.rate_ci_dots(
        df, label="group", title="In-hospital mortality by age group",
        x_title="Died during admission (%, 95% CI)", reference_pct=overall_mort,
        order=[a for a in theme.AGE_ORDER if a in set(df["group"])],
    )
    ui.chart(fig, MORT_DEF)
    ui.suppressed_caption(hidden)

# ---------------------------------------------------------------- Readmission by diagnosis
ui.section("30-day readmission by diagnosis")
if readmit_den == 0:
    st.info("No eligible index discharges in the filtered cohort.")
else:
    df, hidden = ci_frame(data.readmission_by(f, "primary_diagnosis_category"))
    df = df[df["denominator"] >= 5]
    fig = charts.rate_ci_dots(
        df, label="group", title="30-day readmission by primary diagnosis category",
        x_title="Readmitted within 30 days (%, 95% CI)", reference_pct=overall_readmit,
    )
    ui.chart(fig, READMIT_DEF + " Categories with fewer than 5 eligible discharges omitted.")
    ui.suppressed_caption(hidden)

# ---------------------------------------------------------------- Mortality & LOS
ui.section("Mortality and length of stay")
left, right = st.columns(2, gap="medium")
with left:
    df, hidden = ci_frame(data.mortality_by(f, "admission_group"))
    fig = charts.rate_ci_dots(
        df, label="group", title="In-hospital mortality by admission group",
        x_title="Died during admission (%, 95% CI)", reference_pct=overall_mort,
        order=[g for g in theme.ADMISSION_GROUP_ORDER if g in set(df["group"])],
    )
    fig.update_layout(height=300)
    ui.chart(fig, MORT_DEF)
    ui.suppressed_caption(hidden)
with right:
    out = data.los_by_outcome(f)
    shown, hidden = suppress_rows(out, ["admissions", "patients"])
    fig = charts.median_iqr(
        shown, label="outcome", title="Length of stay by discharge outcome",
        x_title="Hospital length of stay (days)",
        order=[o for o in ["Survived to discharge", "Died in hospital"]
               if o in set(shown["outcome"])],
    )
    fig.update_layout(height=300)
    ui.chart(fig, "Dot = median length of stay; bar = interquartile range. Denominator: "
                  "filtered admissions by whether the patient died before discharge.")
    ui.suppressed_caption(hidden)

los = data.los_by_age_icu(f)
shown, hidden = suppress_rows(los, ["admissions", "patients"])
fig = charts.median_iqr(
    shown, label="age_group", series="icu_group", series_colors=theme.ICU_COLORS,
    title="Length of stay by age group, with and without ICU care",
    x_title="Hospital length of stay (days)",
    order=[a for a in theme.AGE_ORDER if a in set(shown["age_group"])],
)
ui.chart(fig, "Dot = median hospital length of stay; bar = interquartile range. "
              "Denominator: filtered admissions in each age group and ICU stratum.")
ui.suppressed_caption(hidden)

ui.privacy_note()
