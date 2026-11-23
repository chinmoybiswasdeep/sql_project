"""Hospital Intelligence - Streamlit dashboard entry point.

Run from the project root:
    .venv/bin/python -m streamlit run dashboard/streamlit/app.py
The theme in dashboard/streamlit/.streamlit/config.toml is picked up automatically because
Streamlit reads the config file that sits next to the main script.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]
for path in (str(APP_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import streamlit as st  # noqa: E402

import theme  # noqa: E402
from components import sidebar_filters  # noqa: E402
from data import check_connection  # noqa: E402

st.set_page_config(
    page_title="Hospital Intelligence",
    page_icon=":material/local_hospital:",
    layout="wide",
    initial_sidebar_state="expanded",
)
theme.register_plotly_template()
st.markdown(theme.PAGE_CSS, unsafe_allow_html=True)

VIEWS = APP_DIR / "views"
PAGES = {
    "Analytics": [
        st.Page(VIEWS / "overview.py", title="Executive overview",
                icon=":material/monitoring:", default=True),
        st.Page(VIEWS / "operations.py", title="Hospital operations",
                icon=":material/local_hospital:"),
        st.Page(VIEWS / "outcomes.py", title="Patient outcomes", icon=":material/favorite:"),
        st.Page(VIEWS / "clinical.py", title="Clinical analytics", icon=":material/science:"),
    ],
    "Platform": [
        st.Page(VIEWS / "data_quality.py", title="Data quality & pipeline",
                icon=":material/fact_check:"),
        st.Page(VIEWS / "sql_explorer.py", title="SQL explorer & metrics",
                icon=":material/code:"),
    ],
}

navigation = st.navigation(PAGES)

error = check_connection()
if error is not None:
    st.error(
        "The warehouse database is unreachable, so the dashboard cannot load.\n\n"
        f"`{error}`\n\n"
        "Check that PostgreSQL is running and that the HI_PG_* settings in `.env` are correct "
        "(default: localhost:5433, database `hospital_intel`), and that `dbt build` has created "
        "the `marts` schema.",
        icon=":material/database:",
    )
    st.stop()

sidebar_filters()
navigation.run()
