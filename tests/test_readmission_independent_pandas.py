"""Third, fully independent implementation of the 30-day readmission metric.

Reads the ORIGINAL source CSV files with pandas (bypassing PostgreSQL, the
ingestion pipeline and dbt entirely), applies the documented definition, and
checks each component against the warehouse. If the SQL logic, the loader or
the type parsing were wrong, these numbers would diverge.
"""

from __future__ import annotations

import pandas as pd
import pytest

from config.settings import get_settings

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def independent() -> dict:
    path = get_settings().data_dir / "hosp" / "admissions.csv.gz"
    adm = pd.read_csv(path, parse_dates=["admittime", "dischtime"])
    adm = adm.sort_values(["subject_id", "admittime", "hadm_id"]).reset_index(drop=True)
    nxt = adm.groupby("subject_id")
    adm["next_admittime"] = nxt["admittime"].shift(-1)
    adm["next_type"] = nxt["admission_type"].shift(-1)

    excluded = (
        adm["dischtime"].isna()
        | (adm["hospital_expire_flag"] == 1)
        | adm["discharge_location"].isin(["DIED", "ACUTE HOSPITAL", "AGAINST ADVICE"])
        | (adm["next_admittime"] < adm["dischtime"])
    )
    eligible = adm[~excluded]
    gap = eligible["next_admittime"] - eligible["dischtime"]
    within = (gap >= pd.Timedelta(0)) & (gap <= pd.Timedelta(days=30))
    unplanned = within & ~eligible["next_type"].isin(["ELECTIVE", "SURGICAL SAME DAY ADMISSION"])
    return {"eligible": len(eligible), "readmitted": int(within.sum()),
            "unplanned": int(unplanned.sum()),
            "within_24h": int(((gap >= pd.Timedelta(0)) & (gap < pd.Timedelta(hours=24))).sum())}


def test_eligible_discharges_match(independent, scalar):
    assert scalar("select count(*) from marts.fact_readmissions where is_eligible_index") \
        == independent["eligible"]


def test_readmission_numerator_matches(independent, scalar):
    assert scalar("select count(*) from marts.fact_readmissions where is_readmitted_30d") \
        == independent["readmitted"]


def test_unplanned_and_24h_counts_match(independent, scalar):
    assert scalar("select count(*) from marts.fact_readmissions "
                  "where is_unplanned_readmitted_30d") == independent["unplanned"]
    assert scalar("select count(*) from marts.fact_readmissions "
                  "where is_readmitted_within_24h") == independent["within_24h"]


def test_rate_matches_reporting_kpi(independent, scalar):
    rate = round(100.0 * independent["readmitted"] / independent["eligible"], 1)
    assert float(scalar("select readmission_30d_pct from reporting.rpt_executive_kpis")) == rate
