"""Header validation and type-safe batch parsing.

Every source value arrives as a string. Each column is parsed to its contract
type; a row is *rejected* (and kept for audit) when a non-empty source value
cannot be parsed, a varchar exceeds its declared length, an integer overflows
its PostgreSQL type, or a NOT NULL column is empty. Nothing is silently coerced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import polars as pl

TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
DATE_FMT = "%Y-%m-%d"
INT_RANGES = {
    "smallint": (-32768, 32767),
    "integer": (-2147483648, 2147483647),
    "bigint": (-(2**63), 2**63 - 1),
}
_VARCHAR = re.compile(r"varchar\((\d+)\)")


@dataclass
class HeaderCheck:
    missing: list[str]
    extra: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing


@dataclass
class ParsedBatch:
    good: pl.DataFrame
    rejects: list[dict[str, Any]] = field(default_factory=list)  # {line, reason, record}

    @property
    def n_rejected(self) -> int:
        return len(self.rejects)


def validate_header(actual: list[str], expected: list[str]) -> HeaderCheck:
    actual_set = set(actual)
    return HeaderCheck(
        missing=[c for c in expected if c not in actual_set],
        extra=[c for c in actual if c not in set(expected)],
    )


def _parse_expr(col: str, pg_type: str) -> tuple[pl.Expr, pl.Expr | None]:
    """Return (parsed value expr, extra-violation expr or None) for one column."""
    src = pl.col(col)
    if pg_type in INT_RANGES:
        lo, hi = INT_RANGES[pg_type]
        parsed = src.str.strip_chars().cast(pl.Int64, strict=False)
        return parsed, (parsed < lo) | (parsed > hi)
    if pg_type in {"double precision", "real", "numeric"}:
        return src.str.strip_chars().cast(pl.Float64, strict=False), None
    if pg_type == "timestamp":
        return src.str.strptime(pl.Datetime("us"), TIMESTAMP_FMT, strict=False), None
    if pg_type == "date":
        return src.str.strptime(pl.Date, DATE_FMT, strict=False), None
    match = _VARCHAR.fullmatch(pg_type)
    if match:
        return src, src.str.len_chars() > int(match.group(1))
    if pg_type == "text":
        return src, None
    raise ValueError(f"unsupported contract type {pg_type!r} for column {col}")


def parse_batch(
    raw: pl.DataFrame,
    columns: dict[str, str],
    not_null: list[str],
    first_line: int,
) -> ParsedBatch:
    """Parse a string-typed batch.

    ``first_line`` is the 1-based ordinal of the first data record in ``raw``;
    it becomes ``_source_line`` for lineage and for locating rejected rows.
    """
    raw = raw.select(list(columns)).with_columns(pl.col(c).cast(pl.Utf8) for c in columns)
    raw = raw.with_row_index("_ordinal", offset=first_line)

    parsed_exprs, reason_exprs = [], []
    for col, pg_type in columns.items():
        parsed, violation = _parse_expr(col, pg_type)
        parsed_exprs.append(parsed.alias(col))
        failed = pl.col(col).is_not_null() & parsed.is_null()
        reason_exprs.append(pl.when(failed).then(pl.lit(f"unparseable:{col}")))
        if violation is not None:
            reason_exprs.append(
                pl.when(violation.fill_null(False)).then(pl.lit(f"out_of_range:{col}"))
            )
        if col in not_null:
            reason_exprs.append(pl.when(parsed.is_null()).then(pl.lit(f"null:{col}")))

    reasons = raw.select(
        pl.col("_ordinal"),
        pl.concat_str(reason_exprs, separator=";", ignore_nulls=True).alias("_reason"),
    )
    bad_mask = reasons["_reason"].is_not_null() & (reasons["_reason"] != "")

    good = (
        raw.filter(~bad_mask)
        .select(pl.col("_ordinal").alias("_source_line"), *parsed_exprs)
    )
    rejects: list[dict[str, Any]] = []
    if bad_mask.any():
        bad_raw = raw.filter(bad_mask)
        bad_reasons = reasons.filter(bad_mask)["_reason"].to_list()
        for row, reason in zip(bad_raw.iter_rows(named=True), bad_reasons, strict=True):
            line = row.pop("_ordinal")
            rejects.append({"line": line, "reason": reason, "record": row})
    return ParsedBatch(good=good, rejects=rejects)
