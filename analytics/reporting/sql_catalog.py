"""Execute every analytical query and generate docs/sql_catalog.md.

For each query: parse its documentation header, execute it, time it, save the
full result to reports/sql_results/<id>.csv (git-ignored, regenerated
locally) and render the result plus the documented interpretation into the
catalog. Interpretations live in sql/interpretations.yml and were written
after reviewing the actual results of the run recorded in the catalog header.

In full-dataset mode, count columns describing patients/admissions below
HI_MIN_CELL_SIZE are masked in the Markdown catalog (small-cell suppression).

Usage:  python -m analytics.reporting.sql_catalog
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pandas as pd
import yaml

from analytics.metrics.db import analytical_query_files, parse_header, run_sql_file
from config.settings import PROJECT_ROOT, get_settings

RESULTS_DIR = PROJECT_ROOT / "reports" / "sql_results"
CATALOG = PROJECT_ROOT / "docs" / "sql_catalog.md"
INTERPRETATIONS = PROJECT_ROOT / "sql" / "interpretations.yml"
COUNT_COLUMN_HINTS = ("patients", "admissions", "stays", "deaths", "readmissions",
                      "discharges", "transitions")
FIELDS = [
    ("business_question", "Business question"),
    ("metric", "Metric"),
    ("output_grain", "Output grain"),
    ("joins", "Join logic"),
    ("denominator_and_exclusions", "Denominator and exclusions"),
    ("potential_biases", "Potential biases"),
    ("expected_output", "Expected output"),
    ("techniques", "SQL techniques"),
]


def suppress_small_cells(df: pd.DataFrame, min_cell: int) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if any(h in col.lower() for h in COUNT_COLUMN_HINTS) and pd.api.types.is_numeric_dtype(out[col]):
            mask = out[col].between(1, min_cell - 1)
            out[col] = out[col].astype(object).where(~mask, f"<{min_cell}")
    return out


def to_markdown(df: pd.DataFrame, max_rows: int = 25) -> str:
    shown = df.head(max_rows)
    md = shown.to_markdown(index=False, floatfmt=".2f")
    if len(df) > max_rows:
        md += f"\n\n_{len(df) - max_rows} more rows in reports/sql_results._"
    return md


def main() -> None:
    settings = get_settings()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    interpretations = yaml.safe_load(INTERPRETATIONS.read_text()) if INTERPRETATIONS.exists() else {}
    files = analytical_query_files()
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    sections, index_rows = [], []
    current_module = None
    for path in files:
        meta = parse_header(path)
        started = time.perf_counter()
        df = run_sql_file(path)
        elapsed_ms = (time.perf_counter() - started) * 1000
        df.to_csv(RESULTS_DIR / f"{meta['query_id'].lower()}.csv", index=False)
        shown = suppress_small_cells(df, settings.min_cell_size) \
            if settings.dataset_mode == "full" else df

        rel = path.relative_to(PROJECT_ROOT).as_posix()
        anchor = f"{meta['query_id'].lower()}"
        index_rows.append(f"| [{meta['query_id']}](#{anchor}) | {meta['title']} | "
                          f"{meta.get('module', '')} | {len(df)} | {elapsed_ms:.0f} |")
        if meta.get("module") != current_module:
            current_module = meta.get("module")
            sections.append(f"\n## {current_module}\n")
        body = [f'<a id="{anchor}"></a>', f"### {meta['query_id']}: {meta['title']}", "",
                f"**File:** [`{rel}`](../{rel})  ", f"**Execution:** {len(df)} rows in "
                f"{elapsed_ms:.0f} ms (includes client round-trip)", ""]
        for key, label in FIELDS:
            if key in meta:
                body.append(f"- **{label}:** {meta[key]}")
        body += ["", "**Result (actual output):**", "", to_markdown(shown), ""]
        note = interpretations.get(meta["query_id"])
        if note:
            body += [f"**Interpretation:** {note.strip()}", ""]
        sections.append("\n".join(body))

    header = [
        "# SQL Query Catalog", "",
        f"_Generated {generated} by `python -m analytics.reporting.sql_catalog` against "
        f"`{settings.dataset_label}` ({settings.dataset_mode} mode). Results are pasted from "
        "that execution and nothing is hand-edited._", "",
        "> **Read results with the cohort in mind.** The public demo has 100 patients, and "
        "every one had at least one ICU stay, so it is an ICU-patient cohort, not a "
        "hospital-wide population. Rates are descriptive of this sample; confidence intervals "
        "are wide. See [limitations](limitations.md).", "",
        "All queries target the dbt marts (`marts.*`) in PostgreSQL. Each file has a "
        "structured header documenting the question, metric, grain, joins, denominator, "
        "exclusions and biases; this catalog is rendered from those headers.", "",
        "| ID | Query | Module | Rows | ms |", "|---|---|---|---:|---:|", *index_rows, "",
    ]
    CATALOG.write_text("\n".join(header + sections) + "\n")
    print(f"executed {len(files)} queries; wrote {CATALOG.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
