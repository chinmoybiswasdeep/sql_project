"""SQL explorer & metric definitions: the 25 catalogued analytical queries, their documented
headers, SQL text and live (aggregate) results."""

from __future__ import annotations

import html
import re

import pandas as pd
import streamlit as st

import components as ui
import data
from privacy import mask_table, suppression_enabled

ui.page_header(
    "SQL explorer & metric definitions",
    "The analytical query catalogue",
    "Each query documents its business question, metric, grain, joins, denominator and known "
    "biases in a structured header. Pick one to read the definition, the SQL and its live result.",
)

catalog = data.query_catalog()
if not catalog:
    st.error("No catalogued queries found under sql/<module>/q*.sql.")
    st.stop()

labels = {m["path"]: f"{m['query_id']} · {m['title']}" for m in catalog}
modules = sorted({m.get("module", "Other") for m in catalog})

c1, c2 = st.columns([1, 2], gap="medium")
with c1:
    module = st.selectbox("Module", ["All modules", *modules], key="sql_module")
with c2:
    paths = [m["path"] for m in catalog if module == "All modules" or m.get("module") == module]
    selected = st.selectbox("Query", paths, format_func=labels.get, key="sql_query")

meta = next(m for m in catalog if m["path"] == selected)

def _fmt(value: object) -> str:
    """Render whole-number floats (e.g. SUM over numeric -> 275.0) without a trailing .0."""
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    return str(value)


FIELDS = [
    ("business_question", "Business question"),
    ("metric", "Metric"),
    ("output_grain", "Output grain"),
    ("denominator_and_exclusions", "Denominator and exclusions"),
    ("joins", "Joins"),
    ("potential_biases", "Potential biases"),
    ("techniques", "SQL techniques"),
]

st.markdown(
    f'<span class="hi-pill">{html.escape(meta["query_id"])}</span>'
    f'<span class="hi-pill">{html.escape(meta.get("module", ""))}</span>'
    f'<span class="hi-pill">{html.escape(meta["path"])}</span>',
    unsafe_allow_html=True,
)
st.subheader(meta["title"])

left, right = st.columns(2, gap="large")
for i, (key, label) in enumerate(FIELDS):
    target = left if i % 2 == 0 else right
    value = meta.get(key)
    if value:
        target.markdown(
            f'<div class="hi-field-label">{label}</div>'
            f'<div class="hi-field-value">{html.escape(value)}</div>',
            unsafe_allow_html=True,
        )

if meta.get("interpretation"):
    with st.expander("Analyst interpretation (written against the demo dataset output)"):
        st.markdown(meta["interpretation"])

tab_result, tab_sql = st.tabs(["Live result", "SQL"])
with tab_sql:
    st.code(data.sql_text(selected), language="sql", line_numbers=True)
with tab_result:
    try:
        result = data.run_catalog_query(selected)
    except Exception as exc:  # noqa: BLE001 - shown to the user
        st.error(f"Query failed: {type(exc).__name__}: {str(exc).splitlines()[0]}")
    else:
        id_cols = [c for c in result.columns if re.fullmatch(r"(subject|hadm|stay)_id", c)]
        if id_cols:
            st.error("This query returns identifier columns; the result is withheld because the "
                     "dashboard shows aggregates only.")
        else:
            count_cols = [c for c in result.columns
                          if pd.api.types.is_integer_dtype(result[c])
                          and re.search(r"(^n_|patients|admissions|stays|count|_n$|^n$|numerator|"
                                        r"denominator|deaths|readmi)", c)]
            display, n_masked = mask_table(result, count_cols)
            if len(display) == 1 and display.shape[1] > 4:
                # A one-row summary reads better as a metric / value list.
                display = pd.DataFrame({"Metric": display.columns,
                                        "Value": [_fmt(display[c].iloc[0]) for c in display.columns]})
            st.dataframe(display, hide_index=True, width="stretch",
                         height=ui.table_height(len(display)))
            st.caption(
                f"{len(result)} row{'s' if len(result) != 1 else ''} · runs the catalogued SQL "
                "unchanged against the full warehouse (sidebar cohort filters do not apply here)."
                + (f" {n_masked} rows masked by small-cell suppression." if n_masked else "")
                + ("" if suppression_enabled() else
                   " Demo mode: small-cell suppression of count columns activates in full mode.")
            )
