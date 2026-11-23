"""Export the warehouse star schema and reporting tables for Power BI.

Writes one CSV (UTF-8, ISO-8601 timestamps, booleans as true/false) and one
Parquet file per table to ``powerbi/datasets/`` plus a ``manifest.json`` with
row counts, column names/types, export time and the dataset label.

Run from the project root:

    .venv/bin/python -m powerbi.export_powerbi_datasets
    .venv/bin/python -m powerbi.export_powerbi_datasets --output-dir /tmp/pbi --no-parquet

Access is read-only (the session is opened READ ONLY and only SELECTs run).
Rows are streamed through a server-side cursor in batches, so the script also
works on the full credentialed MIMIC-IV build.

PRIVACY: the outputs are patient-level. ``powerbi/datasets/*`` is git-ignored.
Never commit or publish them when the credentialed dataset is loaded
(PhysioNet MIMIC-IV data use agreement).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq

from config.settings import PROJECT_ROOT, get_settings

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "powerbi" / "datasets"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class ExportSpec:
    """One exported Power BI table."""

    name: str  # Power BI table name and file stem
    query: str  # SELECT producing the exported rows
    source: str  # warehouse object (or 'derived')
    role: str  # fact | dimension | slicer_dimension | reporting | audit
    grain: str
    source_count_sql: str | None = None  # row count of the source object, if it differs
    note: str | None = None


def _derived_slicer(name: str, column: str, order_case: str | None = None) -> str:
    """Conformed slicer dimension built from values in fact_admissions and fact_readmissions."""
    order = f", {order_case} as {column}_order" if order_case else ""
    return (
        f"select {column}{order} from ("
        f" select {column} from marts.fact_admissions where {column} is not null"
        f" union select {column} from marts.fact_readmissions where {column} is not null"
        f") v order by {'2' if order_case else '1'}, 1"
    )


AGE_ORDER = (
    "case age_group when '<18' then 1 when '18-44' then 2 when '45-64' then 3 "
    "when '65-79' then 4 when '80+' then 5 else 99 end"
)
LOS_BAND_ORDER = (
    "case los_band when '<1 day' then 1 when '1-2 days' then 2 when '3-6 days' then 3 "
    "when '7-13 days' then 4 when '14+ days' then 5 else 99 end"
)
DIAGNOSIS_KEY = "(d.icd_version::text || '-' || d.icd_code)"


def export_specs(full_diagnosis_dictionary: bool = False) -> list[ExportSpec]:
    dim_dx_filter = (
        ""
        if full_diagnosis_dictionary
        else " where exists (select 1 from marts.fact_diagnoses f"
        " where f.icd_code = d.icd_code and f.icd_version = d.icd_version)"
    )
    return [
        # ---------------------------------------------------------- facts
        ExportSpec("fact_admissions", "select * from marts.fact_admissions order by hadm_id",
                   "marts.fact_admissions", "fact", "one row per hospital admission (hadm_id)"),
        ExportSpec("fact_readmissions",
                   "select * from marts.fact_readmissions order by index_hadm_id",
                   "marts.fact_readmissions", "fact",
                   "one row per potential index admission (index_hadm_id); "
                   "rate denominator = is_eligible_index"),
        ExportSpec("fact_icu_stays", "select * from marts.fact_icu_stays order by stay_id",
                   "marts.fact_icu_stays", "fact", "one row per ICU stay (stay_id)"),
        ExportSpec("fact_care_transfers",
                   "select * from marts.fact_care_transfers order by transfer_id",
                   "marts.fact_care_transfers", "fact",
                   "one row per admission-linked care-unit movement (transfer_id)"),
        ExportSpec("fact_diagnoses",
                   f"select {DIAGNOSIS_KEY} as diagnosis_key, d.* from marts.fact_diagnoses d "
                   "order by d.hadm_id, d.seq_num",
                   "marts.fact_diagnoses", "fact",
                   "one row per billed diagnosis (hadm_id, seq_num)",
                   note="diagnosis_key = icd_version || '-' || icd_code (single-column key "
                        "for the Power BI relationship to dim_diagnosis)"),
        ExportSpec("fact_lab_events", "select * from marts.fact_lab_events order by labevent_id",
                   "marts.fact_lab_events", "fact", "one row per lab measurement (labevent_id)",
                   note="hadm_id is null for outpatient labs (is_admission_linked = false)"),
        ExportSpec("fact_medication_orders",
                   "select * from marts.fact_medication_orders order by prescription_key",
                   "marts.fact_medication_orders", "fact",
                   "one row per prescription order (prescription_key)"),
        # ----------------------------------------------------- dimensions
        ExportSpec("dim_patient", "select * from marts.dim_patient order by subject_id",
                   "marts.dim_patient", "dimension", "one row per patient (subject_id)"),
        ExportSpec("dim_admission_type",
                   "select * from marts.dim_admission_type order by admission_group, "
                   "admission_type",
                   "marts.dim_admission_type", "dimension", "one row per admission_type"),
        ExportSpec("dim_care_unit", "select * from marts.dim_care_unit order by care_unit",
                   "marts.dim_care_unit", "dimension", "one row per care unit"),
        ExportSpec("dim_diagnosis",
                   f"select {DIAGNOSIS_KEY} as diagnosis_key, d.* from marts.dim_diagnosis d"
                   f"{dim_dx_filter} order by d.icd_version, d.icd_code",
                   "marts.dim_diagnosis", "dimension",
                   "one row per (icd_version, icd_code) = diagnosis_key",
                   source_count_sql=(
                       None if full_diagnosis_dictionary
                       else "select count(*) from marts.dim_diagnosis"),
                   note=None if full_diagnosis_dictionary else
                   "filtered to codes used in fact_diagnoses (pass "
                   "--full-diagnosis-dictionary for all codes)"),
        ExportSpec("dim_lab_test", "select * from marts.dim_lab_test order by itemid",
                   "marts.dim_lab_test", "dimension", "one row per lab itemid"),
        ExportSpec("dim_medication", "select * from marts.dim_medication order by medication_key",
                   "marts.dim_medication", "dimension", "one row per normalised drug name"),
        # ------------------------------- conformed slicer dims (derived)
        ExportSpec("dim_age_group", _derived_slicer("dim_age_group", "age_group", AGE_ORDER),
                   "derived", "slicer_dimension", "one row per age_group (with sort order)",
                   note="distinct values of fact_admissions/fact_readmissions.age_group"),
        ExportSpec("dim_insurance", _derived_slicer("dim_insurance", "insurance"),
                   "derived", "slicer_dimension", "one row per insurance value",
                   note="distinct values of fact_admissions/fact_readmissions.insurance"),
        ExportSpec("dim_race_group", _derived_slicer("dim_race_group", "race_group"),
                   "derived", "slicer_dimension", "one row per race_group",
                   note="distinct values of fact_admissions/fact_readmissions.race_group"),
        ExportSpec("dim_los_band",
                   f"select distinct los_band, {LOS_BAND_ORDER} as los_band_order "
                   "from marts.fact_admissions where los_band is not null order by 2",
                   "derived", "slicer_dimension", "one row per LOS band (with sort order)",
                   note="distinct values of fact_admissions.los_band"),
        # ------------------------------------------------------ reporting
        ExportSpec("rpt_executive_kpis", "select * from reporting.rpt_executive_kpis",
                   "reporting.rpt_executive_kpis", "reporting", "one row (headline KPIs)"),
        ExportSpec("rpt_pipeline_status",
                   "select * from reporting.rpt_pipeline_status order by table_name",
                   "reporting.rpt_pipeline_status", "reporting", "one row per source table"),
        ExportSpec("rpt_data_quality_checks",
                   "select * from reporting.rpt_data_quality_checks order by table_name, "
                   "check_name",
                   "reporting.rpt_data_quality_checks", "reporting",
                   "one row per validation check (latest run)"),
        ExportSpec("rpt_missingness",
                   "select * from reporting.rpt_missingness order by table_name, column_name",
                   "reporting.rpt_missingness", "reporting",
                   "one row per (table_name, column_name), latest profile"),
        # ---------------------------------------------------------- audit
        ExportSpec("query_benchmarks",
                   "select * from meta.query_benchmarks order by benchmark_id",
                   "meta.query_benchmarks", "audit", "one row per benchmark measurement",
                   note="may be empty if benchmarks have not been run"),
        ExportSpec("ingestion_runs", "select * from meta.ingestion_runs order by run_id",
                   "meta.ingestion_runs", "audit", "one row per ingestion run"),
    ]


# PostgreSQL type OID -> (manifest type, arrow type, Power Query type)
_TYPES: dict[int, tuple[str, pa.DataType, str]] = {
    16: ("boolean", pa.bool_(), "type logical"),
    20: ("int64", pa.int64(), "Int64.Type"),
    21: ("int64", pa.int64(), "Int64.Type"),
    23: ("int64", pa.int64(), "Int64.Type"),
    700: ("float64", pa.float64(), "type number"),
    701: ("float64", pa.float64(), "type number"),
    1700: ("decimal", pa.float64(), "type number"),
    25: ("string", pa.string(), "type text"),
    1042: ("string", pa.string(), "type text"),
    1043: ("string", pa.string(), "type text"),
    1082: ("date", pa.date32(), "type date"),
    1114: ("timestamp", pa.timestamp("us"), "type datetime"),
    1184: ("timestamptz", pa.timestamp("us", tz="UTC"), "type datetimezone"),
}
_FALLBACK = ("string", pa.string(), "type text")  # json/arrays/other -> text


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, dict | list):
        return json.dumps(value)
    return value


def _arrow_value(value: Any, kind: str) -> Any:
    if value is None:
        return None
    if kind in ("decimal", "float64"):
        return float(value)
    if kind == "string" and not isinstance(value, str):
        return json.dumps(value) if isinstance(value, dict | list) else str(value)
    return value


def _count(conn: psycopg.Connection, sql: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql)
        return int(cur.fetchone()[0])


def export_table(conn: psycopg.Connection, spec: ExportSpec, output_dir: Path,
                 batch_rows: int, write_parquet: bool) -> dict[str, Any]:
    started = time.perf_counter()
    csv_path = output_dir / f"{spec.name}.csv"
    parquet_path = output_dir / f"{spec.name}.parquet"
    rows = 0
    with conn.cursor(name=f"pbi_{spec.name}") as cur:
        cur.itersize = batch_rows
        cur.execute(spec.query)
        columns = [d.name for d in cur.description]
        types = [_TYPES.get(d.type_code, _FALLBACK) for d in cur.description]
        schema = pa.schema([pa.field(c, t[1]) for c, t in zip(columns, types, strict=True)])
        writer = pq.ParquetWriter(parquet_path, schema) if write_parquet else None
        try:
            with csv_path.open("w", newline="", encoding="utf-8") as fh:
                out = csv.writer(fh, lineterminator="\n")
                out.writerow(columns)
                while batch := cur.fetchmany(batch_rows):
                    out.writerows([_csv_value(v) for v in row] for row in batch)
                    if writer is not None:
                        arrays = [
                            pa.array([_arrow_value(r[i], types[i][0]) for r in batch],
                                     type=types[i][1])
                            for i in range(len(columns))
                        ]
                        writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
                    rows += len(batch)
            if writer is not None and rows == 0:
                writer.write_table(schema.empty_table())
        finally:
            if writer is not None:
                writer.close()

    query_rows = _count(conn, f"select count(*) from ({spec.query}) q")
    source_rows = (_count(conn, spec.source_count_sql) if spec.source_count_sql
                   else _count(conn, f"select count(*) from {spec.source}")
                   if spec.source != "derived" else query_rows)
    if rows != query_rows:
        raise RuntimeError(f"{spec.name}: wrote {rows} rows but the query returns {query_rows}")
    entry: dict[str, Any] = {
        "source": spec.source,
        "role": spec.role,
        "grain": spec.grain,
        "rows": rows,
        "source_rows": source_rows,
        "files": {"csv": csv_path.name, **({"parquet": parquet_path.name} if write_parquet
                                           else {})},
        "columns": [{"name": c, "type": t[0], "power_query_type": t[2]}
                    for c, t in zip(columns, types, strict=True)],
        "seconds": round(time.perf_counter() - started, 3),
    }
    if spec.note:
        entry["note"] = spec.note
    if write_parquet:
        parquet_rows = pq.ParquetFile(parquet_path).metadata.num_rows
        if parquet_rows != rows:
            raise RuntimeError(f"{spec.name}: parquet has {parquet_rows} rows, expected {rows}")
    return entry


def run_export(output_dir: Path | None = None, write_parquet: bool = True,
               full_diagnosis_dictionary: bool = False, tables: list[str] | None = None,
               quiet: bool = False) -> dict[str, Any]:
    """Export all (or the selected) tables and return the manifest dict."""
    settings = get_settings()
    output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = export_specs(full_diagnosis_dictionary)
    if tables:
        unknown = set(tables) - {s.name for s in specs}
        if unknown:
            raise ValueError(f"Unknown table(s): {sorted(unknown)}")
        specs = [s for s in specs if s.name in tables]

    if settings.dataset_mode == "full" and not quiet:
        print("WARNING: credentialed MIMIC-IV mode. Exports are patient-level and must never "
              "be committed, shared or published (PhysioNet DUA).", file=sys.stderr)

    manifest: dict[str, Any] = {
        "dataset_label": settings.dataset_label,
        "dataset_mode": settings.dataset_mode,
        "exported_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_database": {"host": settings.pg.host, "port": settings.pg.port,
                            "database": settings.pg.dbname},
        "min_cell_size": settings.min_cell_size,
        "formats": {"csv": "UTF-8, comma-separated, header row, ISO-8601 timestamps "
                           "(timestamptz converted to UTC), booleans true/false, "
                           "empty field = null",
                    "parquet": "Apache Parquet (pyarrow)" if write_parquet else None},
        "cohort_caveat": (
            "MIMIC-IV demo: every patient had at least one ICU stay, so this is an "
            "ICU-patient cohort, not a hospital-wide population."
            if settings.dataset_mode == "demo" else None),
        "tables": {},
    }
    with psycopg.connect(settings.pg.conninfo) as conn:
        conn.read_only = True
        for spec in specs:
            entry = export_table(conn, spec, output_dir, settings.batch_rows, write_parquet)
            manifest["tables"][spec.name] = entry
            if not quiet:
                print(f"  {spec.name:<26} {entry['rows']:>10,} rows  "
                      f"(source {entry['source_rows']:,})  {entry['seconds']}s")
        conn.rollback()

    (output_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-parquet", action="store_true", help="CSV only")
    parser.add_argument("--full-diagnosis-dictionary", action="store_true",
                        help="export every ICD code, not only codes used in fact_diagnoses")
    parser.add_argument("--tables", nargs="+", help="export only these tables")
    args = parser.parse_args(argv)
    print(f"Exporting Power BI datasets to {args.output_dir}")
    manifest = run_export(args.output_dir, not args.no_parquet,
                          args.full_diagnosis_dictionary, args.tables)
    print(f"Wrote {len(manifest['tables'])} tables and {MANIFEST_NAME} "
          f"(dataset {manifest['dataset_label']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
