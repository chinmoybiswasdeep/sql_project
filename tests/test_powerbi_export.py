"""Tests for the Power BI package (powerbi/).

Integration tests export the warehouse into a temporary directory and check
that the files are complete, that row counts match PostgreSQL, and that the
headline KPIs recomputed in pandas from the exported CSVs reproduce
reporting.rpt_executive_kpis. Static tests check the DAX, Tabular Editor
script, Power Query and theme files for internal consistency.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

POWERBI = Path(__file__).resolve().parents[1] / "powerbi"
DAX_PATH = POWERBI / "measures" / "measures.dax"

# Tables another process may append to while the test runs.
LIVE_APPEND_TABLES = {"query_benchmarks", "ingestion_runs"}


def _db_available() -> bool:
    try:
        from analytics.metrics.db import read_sql

        read_sql("select 1 from marts.fact_admissions limit 1")
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="PostgreSQL warehouse unreachable")


def _wilson(x: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Line-for-line transliteration of the DAX Wilson measures in measures.dax."""
    p = x / n
    d = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def _bool(series: pd.Series) -> pd.Series:
    mapped = series.map({"true": True, "false": False, True: True, False: False})
    assert mapped.notna().all(), f"non-boolean values in {series.name}"
    return mapped.astype(bool)


# --------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def export_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from powerbi.export_powerbi_datasets import run_export

    out = tmp_path_factory.mktemp("powerbi_datasets")
    run_export(out, write_parquet=True, quiet=True)
    return out


@pytest.fixture(scope="module")
def manifest(export_dir: Path) -> dict:
    return json.loads((export_dir / "manifest.json").read_text())


def _csv(export_dir: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(export_dir / f"{name}.csv", dtype=str, keep_default_na=False,
                       na_values=[""])


# ---------------------------------------------------------------- integration tests
@pytest.mark.integration
@requires_db
def test_all_files_and_manifest_written(export_dir: Path, manifest: dict) -> None:
    from powerbi.export_powerbi_datasets import export_specs

    expected = {s.name for s in export_specs()}
    assert set(manifest["tables"]) == expected
    assert manifest["dataset_label"]
    assert manifest["exported_at_utc"]
    for name, entry in manifest["tables"].items():
        assert (export_dir / f"{name}.csv").stat().st_size > 0, name
        assert (export_dir / f"{name}.parquet").exists(), name
        assert entry["columns"], name
        header = (export_dir / f"{name}.csv").read_text(encoding="utf-8").splitlines()[0]
        assert header.split(",") == [c["name"] for c in entry["columns"]], name


@pytest.mark.integration
@requires_db
def test_row_counts_match_database(export_dir: Path, manifest: dict) -> None:
    from analytics.metrics.db import read_sql
    from powerbi.export_powerbi_datasets import export_specs

    for spec in export_specs():
        entry = manifest["tables"][spec.name]
        csv_rows = len(_csv(export_dir, spec.name))
        parquet_rows = pq.ParquetFile(export_dir / f"{spec.name}.parquet").metadata.num_rows
        assert entry["rows"] == csv_rows == parquet_rows, spec.name

        query_rows = int(read_sql(f"select count(*) as n from ({spec.query}) q").n[0])
        if spec.name in LIVE_APPEND_TABLES:
            assert entry["rows"] <= query_rows, spec.name
            continue
        assert entry["rows"] == query_rows, spec.name
        if spec.source != "derived" and spec.source_count_sql is None:
            source_rows = int(read_sql(f"select count(*) as n from {spec.source}").n[0])
            assert entry["rows"] == source_rows == entry["source_rows"], spec.name


@pytest.mark.integration
@requires_db
def test_dim_diagnosis_covers_every_fact_code(export_dir: Path) -> None:
    dim = _csv(export_dir, "dim_diagnosis")
    fact = _csv(export_dir, "fact_diagnoses")
    assert dim["diagnosis_key"].is_unique
    assert set(fact["diagnosis_key"]) <= set(dim["diagnosis_key"])


@pytest.mark.integration
@requires_db
def test_relationship_keys_are_unique_and_complete(export_dir: Path) -> None:
    """Every Power BI relationship in data_model.md is many-to-one with no orphans."""
    rels = [
        ("fact_admissions", "subject_id", "dim_patient", "subject_id"),
        ("fact_admissions", "admission_type", "dim_admission_type", "admission_type"),
        ("fact_admissions", "age_group", "dim_age_group", "age_group"),
        ("fact_admissions", "insurance", "dim_insurance", "insurance"),
        ("fact_admissions", "race_group", "dim_race_group", "race_group"),
        ("fact_admissions", "los_band", "dim_los_band", "los_band"),
        ("fact_readmissions", "subject_id", "dim_patient", "subject_id"),
        ("fact_readmissions", "index_admission_type", "dim_admission_type", "admission_type"),
        ("fact_readmissions", "age_group", "dim_age_group", "age_group"),
        ("fact_readmissions", "insurance", "dim_insurance", "insurance"),
        ("fact_readmissions", "race_group", "dim_race_group", "race_group"),
        ("fact_icu_stays", "hadm_id", "fact_admissions", "hadm_id"),
        ("fact_icu_stays", "first_careunit", "dim_care_unit", "care_unit"),
        ("fact_care_transfers", "hadm_id", "fact_admissions", "hadm_id"),
        ("fact_care_transfers", "care_unit", "dim_care_unit", "care_unit"),
        ("fact_diagnoses", "hadm_id", "fact_admissions", "hadm_id"),
        ("fact_diagnoses", "diagnosis_key", "dim_diagnosis", "diagnosis_key"),
        ("fact_lab_events", "hadm_id", "fact_admissions", "hadm_id"),
        ("fact_lab_events", "itemid", "dim_lab_test", "itemid"),
        ("fact_medication_orders", "hadm_id", "fact_admissions", "hadm_id"),
        ("fact_medication_orders", "medication_key", "dim_medication", "medication_key"),
    ]
    frames: dict[str, pd.DataFrame] = {}
    for many, fk, one, pk in rels:
        frames.setdefault(many, _csv(export_dir, many))
        frames.setdefault(one, _csv(export_dir, one))
        keys = frames[one][pk]
        assert keys.notna().all() and keys.is_unique, f"{one}[{pk}] is not a unique key"
        fks = frames[many][fk].dropna()
        orphans = set(fks) - set(keys)
        assert not orphans, f"{many}[{fk}] has {len(orphans)} values missing from {one}"


@pytest.mark.integration
@requires_db
def test_kpis_recomputed_from_csv_match_reporting(export_dir: Path) -> None:
    from analytics.metrics.db import read_sql

    ref = read_sql("select * from reporting.rpt_executive_kpis").iloc[0]
    exported_ref = _csv(export_dir, "rpt_executive_kpis").iloc[0]

    adm = _csv(export_dir, "fact_admissions")
    adm["los_days"] = adm["los_days"].astype(float)
    rd = _csv(export_dir, "fact_readmissions")
    eligible = rd[_bool(rd["is_eligible_index"])]

    total_patients = adm["subject_id"].nunique()
    total_admissions = len(adm)
    median_los = adm["los_days"].median()  # = percentile_cont(0.5) = PERCENTILE.INC
    icu_pct = 100 * _bool(adm["had_icu_stay"]).mean()
    mortality_pct = 100 * _bool(adm["died_in_hospital"]).mean()
    readm_num = int(_bool(eligible["is_readmitted_30d"]).sum())
    readm_den = len(eligible)
    unplanned_num = int(_bool(eligible["is_unplanned_readmitted_30d"]).sum())

    assert total_patients == ref.total_patients == int(exported_ref.total_patients)
    assert total_admissions == ref.total_admissions == int(exported_ref.total_admissions)
    assert round(total_admissions / total_patients, 2) == pytest.approx(
        float(ref.admissions_per_patient))
    assert median_los == pytest.approx(float(ref.median_los_days), abs=1e-9)
    assert median_los == pytest.approx(float(exported_ref.median_los_days), abs=1e-9)
    assert round(icu_pct, 1) == pytest.approx(float(ref.icu_admission_pct))
    assert round(mortality_pct, 1) == pytest.approx(float(ref.hospital_mortality_pct))
    assert readm_den == ref.readmission_denominator
    assert readm_num == ref.readmission_numerator
    assert round(100 * readm_num / readm_den, 1) == pytest.approx(float(ref.readmission_30d_pct))
    assert round(100 * unplanned_num / readm_den, 1) == pytest.approx(
        float(ref.unplanned_readmission_30d_pct))
    # the readmission denominator is eligible index admissions, not all admissions
    assert readm_den < total_admissions


@pytest.mark.integration
@requires_db
def test_clinical_measures_recomputed_from_csv_match_sql(export_dir: Path) -> None:
    """Therapeutic-medication and lab definitions in the DAX match the SQL filters."""
    from analytics.metrics.db import read_sql

    meds = _csv(export_dir, "fact_medication_orders")
    therapeutic = meds[(meds["drug_type"] != "BASE")
                       & ~meds["drug_name_normalized"].str.contains("flush", case=False)]
    sql_ther = read_sql(
        "select count(*) as n from marts.fact_medication_orders "
        "where drug_type <> 'BASE' and drug_name_normalized not like '%flush%'").n[0]
    assert len(therapeutic) == sql_ther

    labs = _csv(export_dir, "fact_lab_events")
    adm = _csv(export_dir, "fact_admissions")
    linked = int(_bool(labs["is_admission_linked"]).sum())
    assert linked == labs["hadm_id"].notna().sum()
    assert linked / len(adm) == pytest.approx(adm["n_lab_events"].astype(int).mean())


@pytest.mark.integration
@requires_db
def test_power_query_matches_manifest(manifest: dict) -> None:
    """power_query.m declares exactly the exported columns for every table."""
    text = (POWERBI / "documentation" / "power_query.m").read_text()
    for name, entry in manifest["tables"].items():
        block = text.split(f"// Query: {name}\n", 1)
        assert len(block) == 2, f"no query for {name}"
        body = block[1].split("// Query:", 1)[0]
        declared = re.findall(r'\{"([^"]+)", (?:Int64\.Type|type \w+)\}', body)
        assert declared == [c["name"] for c in entry["columns"]], name


@pytest.mark.integration
@requires_db
def test_dax_column_references_exist(manifest: dict) -> None:
    text = DAX_PATH.read_text()
    columns = {(t, c["name"]) for t, e in manifest["tables"].items() for c in e["columns"]}
    refs = set(re.findall(r"(?<!['\w])([a-z_]+)\[([^\]]+)\]", text))
    missing = sorted(r for r in refs if r not in columns)
    assert not missing, f"DAX references unknown columns: {missing}"
    tables = set(re.findall(r"(?:COUNTROWS|REMOVEFILTERS)\s*\(\s*([a-z_]+)\s*\)", text))
    assert tables <= set(manifest["tables"]), tables - set(manifest["tables"])


# ----------------------------------------------------------------------- static tests
def test_dax_measure_references_resolve() -> None:
    from powerbi.measures.generate_tabular_editor_script import parse_measures

    text = DAX_PATH.read_text()
    measures = parse_measures(text)
    names = {m.name for m in measures}
    assert len(measures) >= 80
    folders = {m.folder.split("\\")[0] for m in measures}
    assert folders == {"Volume", "LOS", "ICU", "Outcomes", "Readmission", "Clinical",
                       "Data Quality"}
    assert all(m.description for m in measures), "every measure needs a definition comment"
    code = "\n".join(ln.split("//")[0] for ln in text.splitlines())
    used = set(re.findall(r"(?<![\w'\]])\[([^\]]+)\]", code))
    assert not used - names, f"unknown measures referenced: {sorted(used - names)}"
    for required in ["Total Patients", "Total Admissions", "Median LOS (days)",
                     "ICU Admission %", "Readmission 30d %", "Hospital Mortality %",
                     "Readmission 30d % CI Lower", "Readmission 30d % CI Upper",
                     "Hospital Mortality % CI Lower", "Hospital Mortality % CI Upper",
                     "Admissions per Patient", "Labs per Admission", "ICU Mortality %",
                     "Unplanned Readmission 30d %", "Therapeutic Orders"]:
        assert required in names, required
    # safe division: no bare '/' operator in measure code
    assert not re.search(r"[\w\)\]]\s*/\s*[\w\(\[]", code.split("EVALUATE")[0])


def test_tabular_editor_script_in_sync() -> None:
    from powerbi.measures.generate_tabular_editor_script import (
        CSX_PATH,
        parse_measures,
        render_csx,
    )

    expected = render_csx(parse_measures(DAX_PATH.read_text()))
    assert CSX_PATH.read_text() == expected, "regenerate measures_tabular_editor.csx"


def test_wilson_formula_matches_scipy() -> None:
    from scipy.stats import binomtest

    for x, n in [(52, 255), (48, 255), (15, 275), (12, 140), (0, 20), (20, 20)]:
        ci = binomtest(x, n).proportion_ci(confidence_level=0.95, method="wilson")
        lo, hi = _wilson(x, n)
        assert lo == pytest.approx(ci.low, abs=1e-6)
        assert hi == pytest.approx(ci.high, abs=1e-6)


def test_theme_is_valid_power_bi_theme() -> None:
    theme = json.loads((POWERBI / "documentation" / "theme.json").read_text())
    for key in ["name", "dataColors", "background", "foreground", "tableAccent",
                "good", "neutral", "bad", "textClasses"]:
        assert key in theme, key
    hexes = theme["dataColors"] + [theme[k] for k in
                                   ("background", "foreground", "good", "neutral", "bad")]
    assert all(re.fullmatch(r"#[0-9A-Fa-f]{6}", h) for h in hexes)
