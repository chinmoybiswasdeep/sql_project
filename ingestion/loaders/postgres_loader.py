"""Stream a MIMIC-IV CSV(.gz) file into raw.<table> with validation and audit.

Design choices
* Streaming: pyarrow's incremental CSV reader decompresses and parses in
  blocks, so memory stays bounded for multi-GB tables (e.g. full labevents).
* Transactional per table: TRUNCATE + all batches + post-load checks commit
  together. A failure rolls back and leaves the previous good load intact.
* Restartable: a table whose file checksum and contract hash match the last
  successful load (and whose row count still matches) is skipped.
* Bulk load via COPY FROM STDIN (CSV), the fastest PostgreSQL ingest path.
"""

from __future__ import annotations

import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl
import psycopg
import pyarrow as pa
import pyarrow.csv as pacsv
from psycopg import sql

from ingestion.download_demo import sha256_file
from ingestion.loaders.ddl import contract_hash, create_table_sql
from ingestion.logging_utils import get_logger
from ingestion.validators.schema import TIMESTAMP_FMT, parse_batch, validate_header

log = get_logger("ingestion.loader")

MAX_STORED_REJECTS = 1000  # per table per run; all rejects are still counted
BLOCK_SIZE = 32 << 20  # 32 MiB of decompressed CSV per arrow block


@dataclass
class TableLoadResult:
    table: str
    source_file: str
    status: str
    file_sha256: str | None = None
    contract_hash: str | None = None
    source_rows: int = 0
    loaded_rows: int = 0
    rejected_rows: int = 0
    duplicate_key_rows: int = 0
    orphan_rows: dict[str, int] = field(default_factory=dict)
    extra_columns: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    error_message: str | None = None


def read_header(path: Path) -> list[str]:
    reader = pacsv.open_csv(path, read_options=pacsv.ReadOptions(block_size=1 << 16))
    return reader.schema.names


def iter_string_batches(path: Path, columns: list[str], batch_rows: int):
    """Yield polars DataFrames of string columns, at most ``batch_rows`` rows each."""
    header = read_header(path)
    reader = pacsv.open_csv(
        path,
        read_options=pacsv.ReadOptions(block_size=BLOCK_SIZE),
        convert_options=pacsv.ConvertOptions(
            column_types={c: pa.string() for c in header},
            include_columns=[c for c in header if c in set(columns)],
            strings_can_be_null=True,
            quoted_strings_can_be_null=True,
        ),
    )
    for record_batch in reader:
        frame = pl.from_arrow(record_batch)
        assert isinstance(frame, pl.DataFrame)
        for offset in range(0, frame.height, batch_rows):
            yield frame.slice(offset, batch_rows)


def _copy_frame(cur: psycopg.Cursor, table: str, frame: pl.DataFrame, run_id: int) -> None:
    frame = frame.with_columns(pl.lit(run_id, dtype=pl.Int64).alias("_ingestion_run_id"))
    buf = io.BytesIO()
    frame.write_csv(buf, datetime_format=TIMESTAMP_FMT, date_format="%Y-%m-%d", null_value="")
    cols = sql.SQL(", ").join(sql.Identifier(c) for c in frame.columns)
    stmt = sql.SQL("COPY raw.{} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
        sql.Identifier(table), cols
    )
    with cur.copy(stmt) as copy:
        copy.write(buf.getvalue())


def _store_rejects(cur, run_id: int, table: str, rejects: list[dict[str, Any]]) -> None:
    cur.executemany(
        "INSERT INTO meta.rejected_rows (run_id, table_name, source_line, reason, raw_record)"
        " VALUES (%s, %s, %s, %s, %s)",
        [(run_id, table, r["line"], r["reason"], json.dumps(r["record"])) for r in rejects],
    )


def _previous_success(cur, table: str) -> tuple[str, str, int] | None:
    cur.execute(
        """SELECT file_sha256, contract_hash, loaded_rows FROM meta.ingestion_table_log
           WHERE table_name = %s AND status = 'loaded'
           ORDER BY logged_at DESC LIMIT 1""",
        (table,),
    )
    return cur.fetchone()


def _count(cur, table: str) -> int:
    cur.execute(sql.SQL("SELECT count(*) FROM raw.{}").format(sql.Identifier(table)))
    return int(cur.fetchone()[0])


def duplicate_key_rows(cur, table: str, key: list[str]) -> int:
    """Rows participating in a duplicated key (0 when the key is unique)."""
    keys = sql.SQL(", ").join(sql.Identifier(k) for k in key)
    cur.execute(
        sql.SQL(
            "SELECT coalesce(sum(n), 0) FROM (SELECT count(*) AS n FROM raw.{} "
            "GROUP BY {} HAVING count(*) > 1) d"
        ).format(sql.Identifier(table), keys)
    )
    return int(cur.fetchone()[0])


def orphan_rows(cur, table: str, parents: dict[str, str]) -> dict[str, int]:
    """Child rows whose non-null foreign key has no parent row."""
    result: dict[str, int] = {}
    for col, target in parents.items():
        parent_table, parent_col = target.split(".")
        if _count(cur, parent_table) == 0:
            continue  # parent not loaded (e.g. optional table skipped)
        cur.execute(
            sql.SQL(
                "SELECT count(*) FROM raw.{c} c WHERE c.{fk} IS NOT NULL AND NOT EXISTS "
                "(SELECT 1 FROM raw.{p} p WHERE p.{pk} = c.{fk})"
            ).format(
                c=sql.Identifier(table), fk=sql.Identifier(col),
                p=sql.Identifier(parent_table), pk=sql.Identifier(parent_col),
            )
        )
        result[f"{col}->{target}"] = int(cur.fetchone()[0])
    return result


def profile_columns(cur, run_id: int, table: str, columns: list[str], sample: bool) -> None:
    """Null counts per column. Large full-dataset tables use a 1% block sample."""
    tablesample = sql.SQL(" TABLESAMPLE SYSTEM (1)") if sample else sql.SQL("")
    counts = sql.SQL(", ").join(
        sql.SQL("count({})").format(sql.Identifier(c)) for c in columns
    )
    cur.execute(
        sql.SQL("SELECT count(*), {} FROM raw.{}{}").format(
            counts, sql.Identifier(table), tablesample
        )
    )
    row = cur.fetchone()
    total = int(row[0])
    cur.executemany(
        """INSERT INTO meta.column_profile
           (run_id, table_name, column_name, row_count, null_count, null_pct, sampled)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        [
            (run_id, table, col, total, total - int(nonnull),
             round(100.0 * (total - int(nonnull)) / total, 3) if total else 0.0, sample)
            for col, nonnull in zip(columns, row[1:], strict=True)
        ],
    )


def load_table(
    conn: psycopg.Connection,
    run_id: int,
    table: str,
    spec: dict[str, Any],
    data_dir: Path,
    batch_rows: int,
    full_mode: bool,
    force: bool = False,
) -> TableLoadResult:
    path = data_dir / spec["file"]
    result = TableLoadResult(table=table, source_file=spec["file"], status="failed")
    started = time.perf_counter()
    columns: dict[str, str] = spec["columns"]

    if not path.exists():
        result.status = "skipped_missing"
        result.error_message = f"file not found: {path}"
        return result

    result.file_sha256 = sha256_file(path)
    result.contract_hash = contract_hash(spec)
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(create_table_sql(table, spec))
            previous = _previous_success(cur, table)
            if (
                not force
                and previous is not None
                and previous[0] == result.file_sha256
                and previous[1] == result.contract_hash
                and _count(cur, table) == previous[2]
            ):
                result.status = "skipped_unchanged"
                result.loaded_rows = previous[2]
                result.duration_seconds = time.perf_counter() - started
                return result

            header = validate_header(read_header(path), list(columns))
            if not header.ok:
                raise ValueError(f"source file missing contract columns: {header.missing}")
            result.extra_columns = header.extra
            if header.extra:
                log.warning("extra source columns ignored",
                            extra={"table": table, "columns": header.extra})

            cur.execute(sql.SQL("TRUNCATE raw.{}").format(sql.Identifier(table)))
            stored_rejects = 0
            first_line = 1
            for batch in iter_string_batches(path, list(columns), batch_rows):
                parsed = parse_batch(batch, columns, spec.get("not_null", []), first_line)
                first_line += batch.height
                result.source_rows += batch.height
                result.rejected_rows += parsed.n_rejected
                if parsed.good.height:
                    _copy_frame(cur, table, parsed.good, run_id)
                    result.loaded_rows += parsed.good.height
                if parsed.rejects and stored_rejects < MAX_STORED_REJECTS:
                    keep = parsed.rejects[: MAX_STORED_REJECTS - stored_rejects]
                    _store_rejects(cur, run_id, table, keep)
                    stored_rejects += len(keep)
                if full_mode:
                    log.info("batch loaded", extra={"table": table, "rows": result.source_rows})

            loaded_in_db = _count(cur, table)
            if loaded_in_db != result.loaded_rows:
                raise RuntimeError(
                    f"reconciliation failed: parsed {result.loaded_rows} rows, "
                    f"database has {loaded_in_db}"
                )
            if result.source_rows != result.loaded_rows + result.rejected_rows:
                raise RuntimeError("reconciliation failed: source != loaded + rejected")

            result.duplicate_key_rows = duplicate_key_rows(cur, table, spec["primary_key"])
            result.orphan_rows = orphan_rows(cur, table, spec.get("parents", {}))
            profile_columns(cur, run_id, table, list(columns),
                            sample=full_mode and spec.get("large", False))
            result.status = "loaded"
    except Exception as exc:  # recorded in the audit log, then re-raised by the pipeline
        result.status = "failed"
        result.error_message = f"{type(exc).__name__}: {exc}"
    result.duration_seconds = time.perf_counter() - started
    return result
