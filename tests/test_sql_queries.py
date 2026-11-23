"""Execute all 25 analytical queries; assert structure, invariants and the key figures
quoted in sql/interpretations.yml (so stale interpretations fail loudly)."""

from __future__ import annotations

import pandas as pd
import pytest
import yaml

from analytics.metrics.db import analytical_query_files, parse_header, run_sql_file
from config.settings import PROJECT_ROOT, get_settings

pytestmark = pytest.mark.integration
FILES = analytical_query_files()
REQUIRED_HEADER_FIELDS = ["module", "business_question", "metric", "output_grain", "joins",
                          "denominator_and_exclusions", "potential_biases", "expected_output"]


@pytest.fixture(scope="module")
def results() -> dict[str, pd.DataFrame]:
    return {parse_header(p)["query_id"]: run_sql_file(p) for p in FILES}


def test_there_are_25_queries():
    assert len(FILES) == 25
    assert [parse_header(p)["query_id"] for p in FILES] == [f"Q{i:02d}" for i in range(1, 26)]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_header_documents_every_required_field(path):
    meta = parse_header(path)
    missing = [f for f in REQUIRED_HEADER_FIELDS if not meta.get(f)]
    assert not missing, f"{path.name} header missing {missing}"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_query_executes_and_returns_rows(results, path):
    assert len(results[parse_header(path)["query_id"]]) > 0


def test_every_query_has_an_interpretation():
    notes = yaml.safe_load((PROJECT_ROOT / "sql" / "interpretations.yml").read_text())
    assert set(notes) == {f"Q{i:02d}" for i in range(1, 26)}


def test_cross_query_consistency(results, scalar):
    kpi = scalar("select readmission_30d_pct from reporting.rpt_executive_kpis")
    q06 = results["Q06"]
    numerator = q06[q06["step"].str.contains("numerator")].iloc[0]
    assert float(numerator["rate_pct_of_eligible"]) == float(kpi)
    assert results["Q11"]["pct_of_admissions"].sum() == pytest.approx(100.0, abs=0.2)
    q02_total = results["Q02"].query("age_group == 'All' and sex == 'All'").iloc[0]
    assert q02_total["admissions"] == results["Q01"].iloc[0]["total_admissions"]
    assert results["Q10"]["admissions"].sum() == results["Q01"].iloc[0]["total_admissions"]


def row(df: pd.DataFrame, col: str, value) -> pd.Series:
    match = df[df[col] == value]
    assert len(match) == 1, f"expected one row where {col} == {value!r}"
    return match.iloc[0]


# Figures quoted in sql/interpretations.yml for the demo dataset.
@pytest.mark.skipif(get_settings().dataset_mode != "demo",
                    reason="interpretations quote demo-dataset figures")
def test_interpretation_figures_are_current(results):
    r = results
    q01 = r["Q01"].iloc[0]
    assert (q01.total_patients, q01.total_admissions) == (100, 275)
    assert float(q01.pct_admissions_from_repeat_patients) == 81.1
    assert float(row(r["Q02"].query("sex == 'All'"), "age_group", "45-64").pct_of_admissions) == 48.4
    assert float(row(r["Q04"], "cohort", "All admissions")["median"]) == 4.85
    assert float(row(r["Q05"], "diagnosis_category", "Circulatory").pct_primary) == 24.4
    q06 = r["Q06"]
    assert int(q06[q06.step.str.contains("denominator")].iloc[0].admissions) == 255
    assert int(q06[q06.step.str.contains("numerator")].iloc[0].admissions) == 52
    assert float(row(r["Q07"], "age_group", "80+").rate_pct) == 11.9
    assert float(row(r["Q08"], "diagnosis_category", "Respiratory").rate_pct) == 38.5
    assert float(row(r["Q09"], "gap_bucket", "15-30 days").cumulative_pct) == 30.3
    assert float(row(r["Q10"], "frequency_band", "7+").pct_of_admissions) == 43.6
    assert float(r["Q11"].iloc[0].pct_icu_admissions_with_repeat_icu_stay) == 7.0
    assert float(r["Q12"].iloc[0].overall_median_icu_days) == 2.16
    assert float(row(r["Q13"], "utilization_rank", 1).pct_icu_days) == 22.7
    q14 = r["Q14"].iloc[0]
    assert (q14.from_unit_type, q14.to_unit_type, q14.transitions) == ("ICU", "Medical ward", 56)
    assert float(row(r["Q15"], "dimension", "Overall").icu_mortality_pct) == 8.6
    assert float(r["Q16"].iloc[-1].cumulative_pct) == 56.8
    assert float(row(r["Q17"], "lab_test_name", "Red Blood Cells").pct_flag_abnormal) == 86.8
    assert int(r["Q18"].iloc[0].admissions_with_both) == 31
    q19 = r["Q19"].iloc[0]
    assert (q19.drug_name, float(q19.pct_admissions_exposed)) == ("acetaminophen", 64.0)
    assert float(row(r["Q20"], "diagnosis_category", "Respiratory").mortality_pct) == 16.7
    assert float(row(r["Q21"], "admission_type", "URGENT").median_vs_overall) == 1.62
    assert float(row(r["Q22"], "admission_group", "All admissions").pct_3plus_changes) == 17.8
    assert float(r["Q23"].iloc[0].pct_of_lab_volume) == 32.7
    q24 = r["Q24"].query("admission_frequency_band == '4+'")
    assert float(row(q24, "sequence_position", "4th+ admission").pct_with_icu) == 16.2
    assert float(row(r["Q25"], "charlson_band", "5+").los_index) == 1.39
