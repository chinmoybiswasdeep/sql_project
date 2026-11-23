"""Cached, parameterised, aggregate-only queries against the warehouse.

Rules enforced here:
* User selections only ever reach SQL as bound parameters (``:name``). Column names used
  for grouping come from the fixed ``_GROUP_COLUMNS`` allow-list, never from user input.
* Every query returns aggregates; no subject_id / hadm_id level rows leave this module.
* The sidebar filters are applied to ``marts.fact_admissions`` in a ``fa`` CTE; other facts
  are joined to it on ``hadm_id`` so they inherit the same cohort.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yaml
from sqlalchemy import text

from analytics.metrics.db import analytical_query_files, get_engine, parse_header, read_sql
from config.settings import PROJECT_ROOT

TTL_SECONDS = 600

_GROUP_COLUMNS: dict[str, str] = {
    "age_group": "age_group",
    "sex": "sex",
    "admission_group": "admission_group",
    "primary_diagnosis_category": "coalesce(primary_diagnosis_category, 'Not recorded')",
    "los_band": "los_band",
    "had_icu_stay": "case when had_icu_stay then 'ICU care' else 'No ICU care' end",
}


# --------------------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Filters:
    """Sidebar selections. Empty tuples mean 'no restriction'."""

    sexes: tuple[str, ...] = ()
    age_groups: tuple[str, ...] = ()
    admission_groups: tuple[str, ...] = ()
    icu: str = "All"  # "All" | "ICU care" | "No ICU care"

    @property
    def is_active(self) -> bool:
        return bool(self.sexes or self.age_groups or self.admission_groups) or self.icu != "All"

    def where_clause(self) -> tuple[str, dict[str, Any]]:
        """Build a parameterised WHERE clause for marts.fact_admissions."""
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if self.sexes:
            clauses.append("sex = any(:f_sex)")
            params["f_sex"] = list(self.sexes)
        if self.age_groups:
            clauses.append("age_group = any(:f_age)")
            params["f_age"] = list(self.age_groups)
        if self.admission_groups:
            clauses.append("admission_group = any(:f_adm)")
            params["f_adm"] = list(self.admission_groups)
        if self.icu in {"ICU care", "No ICU care"}:
            clauses.append("had_icu_stay = :f_icu")
            params["f_icu"] = self.icu == "ICU care"
        where = ("where " + " and ".join(clauses)) if clauses else ""
        return where, params

    def describe(self) -> str:
        parts = []
        if self.sexes:
            parts.append("sex: " + ", ".join(self.sexes))
        if self.age_groups:
            parts.append("age: " + ", ".join(self.age_groups))
        if self.admission_groups:
            parts.append("admission: " + ", ".join(self.admission_groups))
        if self.icu != "All":
            parts.append(self.icu)
        return "; ".join(parts) if parts else "All admissions"


def _cohort(f: Filters) -> tuple[str, dict[str, Any]]:
    where, params = f.where_clause()
    return f"with fa as (select * from marts.fact_admissions {where})\n", params


# --------------------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------------------
def _freeze(params: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in params.items()))


@st.cache_data(ttl=TTL_SECONDS, show_spinner=False)
def _read(sql: str, frozen_params: tuple[tuple[str, Any], ...]) -> pd.DataFrame:
    params = {k: list(v) if isinstance(v, tuple) else v for k, v in frozen_params}
    return read_sql(sql, params)


def query(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    return _read(sql, _freeze(params or {}))


def check_connection() -> str | None:
    """Return None when the warehouse is reachable, otherwise a short error message."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("select 1 from marts.fact_admissions limit 1"))
        return None
    except Exception as exc:  # noqa: BLE001 - surfaced to the user verbatim
        return f"{type(exc).__name__}: {str(exc).splitlines()[0]}"


# --------------------------------------------------------------------------------------
# Filter options
# --------------------------------------------------------------------------------------
@st.cache_data(ttl=TTL_SECONDS, show_spinner=False)
def filter_options() -> dict[str, list[str]]:
    df = read_sql(
        "select 'sex' as dim, sex as val from marts.fact_admissions group by 2 "
        "union all select 'age_group', age_group from marts.fact_admissions group by 2 "
        "union all select 'admission_group', admission_group from marts.fact_admissions group by 2"
    )
    return {dim: sorted(g["val"].dropna().tolist()) for dim, g in df.groupby("dim")}


# --------------------------------------------------------------------------------------
# Headline KPIs
# --------------------------------------------------------------------------------------
def kpis(f: Filters) -> pd.Series:
    cte, params = _cohort(f)
    sql = cte + """
    select
        count(distinct subject_id)                                                as patients,
        count(*)                                                                  as admissions,
        percentile_cont(0.5) within group (order by los_days)                     as median_los_days,
        count(*) filter (where had_icu_stay)                                      as icu_admissions,
        count(*) filter (where died_in_hospital)                                  as deaths,
        count(*) filter (where is_readmission_index_eligible)                     as readmit_den,
        count(*) filter (where is_readmission_index_eligible and is_readmitted_30d) as readmit_num,
        count(*) filter (where is_readmission_index_eligible
                           and is_unplanned_readmitted_30d)                       as unplanned_num
    from fa
    """
    return query(sql, params).iloc[0]


def reporting_kpis() -> pd.Series:
    return query("select * from reporting.rpt_executive_kpis").iloc[0]


# --------------------------------------------------------------------------------------
# Admissions / operations
# --------------------------------------------------------------------------------------
def admissions_by_age_sex(f: Filters) -> pd.DataFrame:
    cte, params = _cohort(f)
    return query(cte + """
    select age_group, sex, count(*) as admissions, count(distinct subject_id) as patients
    from fa group by age_group, sex order by age_group, sex
    """, params)


def los_histogram(f: Filters, cap_days: int = 30) -> pd.DataFrame:
    cte, params = _cohort(f)
    params = {**params, "cap": cap_days}
    return query(cte + """
    select least(floor(los_days)::int, :cap) as los_day, count(*) as admissions,
           count(distinct subject_id) as patients
    from fa where los_days is not null group by 1 order by 1
    """, params)


def los_summary(f: Filters) -> pd.Series:
    cte, params = _cohort(f)
    return query(cte + """
    select count(*) as admissions,
           percentile_cont(0.25) within group (order by los_days) as p25,
           percentile_cont(0.50) within group (order by los_days) as p50,
           percentile_cont(0.75) within group (order by los_days) as p75,
           percentile_cont(0.90) within group (order by los_days) as p90,
           avg(los_days) as mean
    from fa where los_days is not null
    """, params).iloc[0]


def admissions_by_category(f: Filters) -> pd.DataFrame:
    cte, params = _cohort(f)
    return query(cte + """
    select admission_group, count(*) as admissions, count(distinct subject_id) as patients,
           percentile_cont(0.25) within group (order by los_days) as los_p25,
           percentile_cont(0.50) within group (order by los_days) as los_p50,
           percentile_cont(0.75) within group (order by los_days) as los_p75
    from fa group by admission_group
    """, params)


def icu_by_unit(f: Filters) -> pd.DataFrame:
    cte, params = _cohort(f)
    return query(cte + """
    select s.first_careunit                                         as care_unit,
           count(*)                                                 as icu_stays,
           count(distinct s.subject_id)                             as patients,
           round(sum(s.icu_los_days)::numeric, 1)                   as icu_days,
           percentile_cont(0.5) within group (order by s.icu_los_days) as median_icu_los_days,
           count(*) filter (where s.died_in_icu)                    as icu_deaths
    from marts.fact_icu_stays s
    join fa on fa.hadm_id = s.hadm_id
    group by s.first_careunit
    order by icu_days desc
    """, params)


def transfer_flows(f: Filters) -> pd.DataFrame:
    cte, params = _cohort(f)
    return query(cte + """
    select coalesce(t.prev_unit_type, 'Unknown') as from_unit_type,
           coalesce(t.unit_type, 'Unknown')      as to_unit_type,
           count(*)                              as transitions,
           count(distinct t.hadm_id)             as admissions,
           count(distinct t.subject_id)          as patients
    from marts.fact_care_transfers t
    join fa on fa.hadm_id = t.hadm_id
    where t.is_unit_change
    group by 1, 2
    """, params)


def resource_by_category(f: Filters) -> pd.DataFrame:
    cte, params = _cohort(f)
    return query(cte + """
    select admission_group,
           count(*)                                                        as admissions,
           count(distinct subject_id)                                      as patients,
           percentile_cont(0.5) within group (order by n_lab_events)       as median_lab_events,
           percentile_cont(0.5) within group (order by n_prescriptions)    as median_prescriptions,
           percentile_cont(0.5) within group (order by n_procedures)       as median_procedures,
           percentile_cont(0.5) within group (order by n_diagnoses)        as median_diagnoses,
           round(avg(n_unit_changes), 2)                                   as mean_unit_changes,
           round(sum(coalesce(icu_days_total, 0))::numeric, 1)             as icu_days_total
    from fa group by admission_group
    """, params)


def labs_by_los_band(f: Filters) -> pd.DataFrame:
    cte, params = _cohort(f)
    return query(cte + """
    select los_band, count(*) as admissions, count(distinct subject_id) as patients,
           percentile_cont(0.5) within group (order by n_lab_events) as median_lab_events,
           percentile_cont(0.5) within group (order by n_prescriptions) as median_prescriptions
    from fa where los_band is not null group by los_band
    """, params)


# --------------------------------------------------------------------------------------
# Outcomes
# --------------------------------------------------------------------------------------
def readmission_by(f: Filters, dim: str) -> pd.DataFrame:
    col = _GROUP_COLUMNS[dim]  # KeyError for anything outside the allow-list
    cte, params = _cohort(f)
    return query(cte + f"""
    select {col} as grp,
           count(*)                                    as denominator,
           count(*) filter (where is_readmitted_30d)   as numerator,
           count(distinct subject_id)                  as patients
    from fa
    where is_readmission_index_eligible
    group by 1
    """, params)


def mortality_by(f: Filters, dim: str) -> pd.DataFrame:
    col = _GROUP_COLUMNS[dim]
    cte, params = _cohort(f)
    return query(cte + f"""
    select {col} as grp,
           count(*)                                    as denominator,
           count(*) filter (where died_in_hospital)    as numerator,
           count(distinct subject_id)                  as patients
    from fa
    group by 1
    """, params)


def los_by_age_icu(f: Filters) -> pd.DataFrame:
    cte, params = _cohort(f)
    return query(cte + """
    select age_group,
           case when had_icu_stay then 'ICU care' else 'No ICU care' end as icu_group,
           count(*) as admissions, count(distinct subject_id) as patients,
           percentile_cont(0.25) within group (order by los_days) as p25,
           percentile_cont(0.50) within group (order by los_days) as p50,
           percentile_cont(0.75) within group (order by los_days) as p75
    from fa where los_days is not null
    group by 1, 2
    """, params)


def los_by_outcome(f: Filters) -> pd.DataFrame:
    cte, params = _cohort(f)
    return query(cte + """
    select case when died_in_hospital then 'Died in hospital' else 'Survived to discharge' end
               as outcome,
           count(*) as admissions, count(distinct subject_id) as patients,
           percentile_cont(0.25) within group (order by los_days) as p25,
           percentile_cont(0.50) within group (order by los_days) as p50,
           percentile_cont(0.75) within group (order by los_days) as p75
    from fa where los_days is not null
    group by 1
    """, params)


# --------------------------------------------------------------------------------------
# Clinical
# --------------------------------------------------------------------------------------
def diagnosis_categories(f: Filters) -> pd.DataFrame:
    cte, params = _cohort(f)
    return query(cte + """
    , any_pos as (
        select d.diagnosis_category, count(distinct d.hadm_id) as admissions_any_position
        from marts.fact_diagnoses d join fa on fa.hadm_id = d.hadm_id
        group by 1
    )
    select coalesce(fa.primary_diagnosis_category, 'Not recorded') as category,
           count(*)                    as admissions,
           count(distinct fa.subject_id) as patients,
           max(a.admissions_any_position) as admissions_any_position
    from fa
    left join any_pos a on a.diagnosis_category = fa.primary_diagnosis_category
    group by 1
    order by admissions desc
    """, params)


def top_lab_tests(f: Filters, limit: int = 15) -> pd.DataFrame:
    cte, params = _cohort(f)
    params = {**params, "lim": limit}
    return query(cte + """
    select d.lab_test_name || ' (' || lower(d.fluid) || ')'  as lab_test,
           d.lab_category,
           count(*)                                        as results,
           count(distinct l.hadm_id)                       as admissions,
           count(distinct l.subject_id)                    as patients,
           count(*) filter (where l.flag_abnormal)         as abnormal_results,
           count(*) filter (where l.range_direction = 'high') as high_results,
           count(*) filter (where l.range_direction = 'low')  as low_results
    from marts.fact_lab_events l
    join fa on fa.hadm_id = l.hadm_id
    join marts.dim_lab_test d on d.itemid = l.itemid
    group by 1, 2
    order by results desc
    limit :lim
    """, params)


def top_medications(f: Filters, limit: int = 15) -> pd.DataFrame:
    cte, params = _cohort(f)
    params = {**params, "lim": limit}
    return query(cte + """
    select m.drug_name_normalized                   as drug,
           count(*)                                 as orders,
           count(distinct m.hadm_id)                as admissions,
           count(distinct m.subject_id)             as patients,
           (select count(*) from fa)                as cohort_admissions
    from marts.fact_medication_orders m
    join fa on fa.hadm_id = m.hadm_id
    where m.drug_type <> 'BASE'
      and m.drug_name_normalized not ilike '%flush%'
    group by 1
    order by admissions desc, orders desc
    limit :lim
    """, params)


# --------------------------------------------------------------------------------------
# Data quality & pipeline (warehouse metadata; not affected by cohort filters)
# --------------------------------------------------------------------------------------
def ingestion_runs() -> pd.DataFrame:
    return query("""
    select run_id, dataset_label, dataset_mode, started_at, finished_at, status
    from meta.ingestion_runs order by started_at desc
    """)


_SAFE_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def reconciliation() -> pd.DataFrame:
    """Per raw table: rows in the source file at the last full load vs rows loaded vs rows
    currently in the raw schema. Table names come from information_schema (not user input)
    and are validated as plain identifiers before being quoted into the count query."""
    tables = query("""
        select table_name from information_schema.tables
        where table_schema = 'raw' and table_type = 'BASE TABLE' order by table_name
    """)["table_name"].tolist()
    tables = [t for t in tables if _SAFE_IDENT.match(t)]
    if not tables:
        return pd.DataFrame()
    counts_sql = " union all ".join(
        f"select '{t}' as table_name, count(*) as current_raw_rows from raw.\"{t}\"" for t in tables
    )
    current = query(counts_sql)
    last_load = query("""
        select distinct on (table_name)
               table_name, run_id as load_run_id, source_rows, loaded_rows, rejected_rows,
               duplicate_key_rows, logged_at as loaded_at
        from meta.ingestion_table_log
        where status = 'loaded'
        order by table_name, logged_at desc
    """)
    status = query("""
        select table_name, latest_status, latest_run_id, last_successful_load_at
        from reporting.rpt_pipeline_status
    """)
    out = current.merge(last_load, on="table_name", how="left").merge(
        status, on="table_name", how="left")
    expected = out["source_rows"] - out["rejected_rows"] - out["duplicate_key_rows"]
    out["reconciled"] = (out["loaded_rows"] == expected) & (out["current_raw_rows"] == out["loaded_rows"])
    return out


def quality_checks() -> pd.DataFrame:
    return query("""
    select check_name, table_name, severity, status, flagged_rows, description, checked_at, run_id
    from reporting.rpt_data_quality_checks
    order by case status when 'fail' then 0 when 'flag' then 1 else 2 end,
             case severity when 'error' then 0 when 'warn' then 1 else 2 end, check_name
    """)


def missingness() -> pd.DataFrame:
    return query("""
    select table_name, column_name, row_count, null_count, null_pct, sampled, run_id
    from reporting.rpt_missingness order by null_pct desc, table_name, column_name
    """)


def benchmarks() -> pd.DataFrame:
    return query("""
    select distinct on (case_name, variant)
           case_name, variant, dataset_label, runs, median_ms, min_ms, max_ms, result_rows,
           benchmarked_at
    from meta.query_benchmarks
    order by case_name, variant, benchmarked_at desc
    """)


def benchmark_case_label(case_name: str) -> str:
    """'c4' -> 'C4 · vitals counts', derived from the sql/optimization file names."""
    folder = PROJECT_ROOT / "sql" / "optimization"
    stems = sorted(p.stem for p in folder.glob(f"{case_name}_*.sql") if "_setup" not in p.stem)
    if not stems:
        return case_name.upper()
    words = stems[0].split("_")[1:]
    words = [w for w in words if w not in {"baseline", "optimized"}]
    return f"{case_name.upper()} · " + " ".join(words).replace("first24h", "first 24h")


# --------------------------------------------------------------------------------------
# SQL explorer
# --------------------------------------------------------------------------------------
@st.cache_data(ttl=TTL_SECONDS, show_spinner=False)
def query_catalog() -> list[dict[str, str]]:
    interpretations = _interpretations()
    catalog = []
    for path in analytical_query_files():
        meta = parse_header(path)
        meta["path"] = str(path.relative_to(PROJECT_ROOT))
        meta["interpretation"] = interpretations.get(meta["query_id"], "")
        catalog.append(meta)
    return catalog


def _interpretations() -> dict[str, str]:
    path = PROJECT_ROOT / "sql" / "interpretations.yml"
    if not path.exists():
        return {}
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}
    return {str(k).upper(): str(v).strip() for k, v in raw.items()}


def sql_text(rel_path: str) -> str:
    path = (PROJECT_ROOT / rel_path).resolve()
    allowed = {p.resolve() for p in analytical_query_files()}
    if path not in allowed:
        raise ValueError(f"{rel_path} is not one of the catalogued queries")
    return Path(path).read_text()


def run_catalog_query(rel_path: str) -> pd.DataFrame:
    return query(sql_text(rel_path))
