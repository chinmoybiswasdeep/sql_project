"""Reusable UI pieces: page header, banners, KPI cards, sidebar filters, chart frame,
cohort guard and privacy notes."""

from __future__ import annotations

import html
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import theme
from config.settings import get_settings
from data import Filters, filter_options
from privacy import min_cell_size, suppression_enabled

FILTER_KEY = "hi_filters"
SMALL_COHORT_WARN = 50  # admissions; below this rates get a stability warning
MIN_COHORT = 10  # admissions; below this (or below k in full mode) rates are withheld


# --------------------------------------------------------------------------------------
# Layout primitives
# --------------------------------------------------------------------------------------
def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""<div class="hi-header">
              <div class="hi-eyebrow">{html.escape(eyebrow)}</div>
              <h1 class="hi-title">{html.escape(title)}</h1>
              <div class="hi-subtitle">{html.escape(subtitle)}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def banner(body_html: str, kind: str = "note", icon: str = "i") -> None:
    """Callout box. ``body_html`` must be trusted markup built by this app (no user input)."""
    st.markdown(
        f'<div class="hi-banner {kind}" role="note"><span class="hi-banner-icon" '
        f'aria-hidden="true">{icon}</span><div>{body_html}</div></div>',
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(f'<div class="hi-section">{html.escape(title)}</div>', unsafe_allow_html=True)


def cohort_caveat_banner() -> None:
    banner(
        "<b>ICU-patient cohort, not a hospital-wide population.</b> Every one of the 100 "
        "patients in the public MIMIC-IV demo (v2.2) had at least one ICU stay, so volumes, "
        "length of stay, mortality and readmission rates describe critically ill patients and "
        "will be higher than a general hospital census. Rates come from small denominators; "
        "read them with their 95% confidence intervals.",
        kind="caveat",
        icon="&#9888;",
    )


def privacy_note() -> None:
    k = min_cell_size()
    if suppression_enabled():
        banner(
            f"<b>Small-cell suppression is on.</b> Aggregates representing fewer than {k} "
            "patients or admissions are hidden. Only aggregates are shown; no patient- or "
            "encounter-level rows are displayed.",
            kind="note", icon="&#128274;",
        )
    else:
        st.caption(
            f"Privacy: aggregates only. Demo data is open access (ODbL), so cells are shown in "
            f"full; small-cell suppression (< {k}) activates automatically in full-dataset mode."
        )


def suppressed_caption(n_hidden: int, what: str = "groups") -> None:
    if n_hidden:
        st.caption(f"{n_hidden} {what} hidden: fewer than {min_cell_size()} patients/admissions.")


# --------------------------------------------------------------------------------------
# KPI cards
# --------------------------------------------------------------------------------------
def kpi_card(label: str, value: str, unit: str = "", sub: str = "") -> str:
    unit_html = f'<span class="hi-kpi-unit">{html.escape(unit)}</span>' if unit else ""
    sub_html = f'<div class="hi-kpi-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="hi-kpi"><div class="hi-kpi-label">{html.escape(label)}</div>'
        f'<div class="hi-kpi-value">{html.escape(value)}{unit_html}</div>{sub_html}</div>'
    )


def kpi_row(cards: list[str]) -> None:
    cols = st.columns(len(cards), gap="small")
    for col, card in zip(cols, cards, strict=True):
        col.markdown(card, unsafe_allow_html=True)


def fmt_int(value: float | int | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{int(value):,}"


def fmt_num(value: float | None, digits: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{float(value):,.{digits}f}"


# --------------------------------------------------------------------------------------
# Sidebar filters
# --------------------------------------------------------------------------------------
def _ordered(values: list[str], order: list[str]) -> list[str]:
    known = [v for v in order if v in values]
    return known + sorted(v for v in values if v not in order)


def _reset_filters() -> None:
    for key in ("flt_sex", "flt_age", "flt_adm"):
        st.session_state[key] = []
    st.session_state["flt_icu"] = "All"


def sidebar_filters() -> Filters:
    opts = filter_options()
    with st.sidebar:
        st.markdown("**Cohort filters**")
        st.caption("Applied server-side to admissions on the analytics pages.")
        sexes = st.multiselect(
            "Sex", options=_ordered(opts.get("sex", []), ["F", "M"]),
            format_func=lambda s: theme.SEX_LABELS.get(s, s), key="flt_sex",
            placeholder="All",
        )
        ages = st.multiselect(
            "Age group (years)", options=_ordered(opts.get("age_group", []), theme.AGE_ORDER),
            key="flt_age", placeholder="All",
        )
        adm = st.multiselect(
            "Admission group",
            options=_ordered(opts.get("admission_group", []), theme.ADMISSION_GROUP_ORDER),
            key="flt_adm", placeholder="All",
        )
        icu = st.radio(
            "ICU care during admission", ["All", "ICU care", "No ICU care"],
            key="flt_icu", horizontal=False,
        )
        st.button("Reset filters", width="stretch", on_click=_reset_filters)

        settings = get_settings()
        st.divider()
        mode = "Full (credentialed)" if settings.dataset_mode == "full" else "Demo (open access)"
        st.caption(
            f"Dataset: **{settings.dataset_label}**  \nMode: {mode}  \n"
            f"Minimum reportable cell: {settings.min_cell_size}"
        )
    filters = Filters(tuple(sexes), tuple(ages), tuple(adm), icu)
    st.session_state[FILTER_KEY] = filters
    return filters


def current_filters() -> Filters:
    return st.session_state.get(FILTER_KEY, Filters())


def filter_summary(f: Filters) -> None:
    st.markdown(
        f'<span class="hi-pill">Cohort</span><span style="font-size:0.88rem;color:'
        f'{theme.INK_SECONDARY}">{html.escape(f.describe())}</span>',
        unsafe_allow_html=True,
    )


def cohort_guard(n_admissions: int) -> None:
    """Stop the page (with an explanation) when the filtered cohort is too small for rates."""
    k = min_cell_size()
    floor = max(MIN_COHORT, k if suppression_enabled() else 0)
    if n_admissions == 0:
        st.warning("No admissions match the current filters. Widen the cohort in the sidebar.")
        st.stop()
    if n_admissions < floor:
        shown = f"fewer than {floor}" if suppression_enabled() else f"{n_admissions}"
        st.warning(
            f"The filtered cohort has {shown} admissions. Rates and distributions on a cohort "
            f"this small are unstable or potentially identifying, so they are not shown. "
            "Widen the filters in the sidebar."
        )
        st.stop()
    if n_admissions < SMALL_COHORT_WARN:
        st.info(
            f"Small cohort ({n_admissions} admissions): percentages can swing widely. "
            "Use the confidence intervals, not the point estimates."
        )


# --------------------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------------------
def chart(fig: go.Figure, caption: str, *, key: str | None = None) -> None:
    """Render a Plotly figure in a bordered card with a one-line metric definition."""
    with st.container(border=True):
        st.plotly_chart(fig, width="stretch", config=theme.PLOTLY_CONFIG, key=key)
        st.caption(caption)


def empty_card(title: str, message: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{html.escape(title)}**")
        st.info(message)


def status_badge(status: str) -> str:
    mapping = {
        "pass": ("good", "Pass"), "succeeded": ("good", "Succeeded"),
        "loaded": ("good", "Loaded"), "skipped_unchanged": ("good", "Unchanged"),
        "flag": ("warning", "Flag"), "warn": ("warning", "Warn"),
        "fail": ("critical", "Fail"), "failed": ("critical", "Failed"),
    }
    tone, label = mapping.get(status, ("serious", status))
    return (
        f'<span class="hi-status" style="color:{theme.STATUS_TEXT[tone]}">'
        f'<span class="hi-dot" style="background:{theme.STATUS[tone]}"></span>'
        f"{html.escape(label)}</span>"
    )


def table_height(n_rows: int, row_px: int = 35, max_rows: int = 20) -> int:
    """Height that shows every row (up to ``max_rows``) without an inner scrollbar."""
    return row_px * (min(n_rows, max_rows) + 1) + 3


def to_display(df: pd.DataFrame, rename: dict[str, str]) -> pd.DataFrame:
    return df.rename(columns=rename)[list(rename.values())]
