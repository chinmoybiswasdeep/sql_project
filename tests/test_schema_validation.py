"""Unit tests for header validation and type-safe batch parsing (no database needed)."""

from __future__ import annotations

import datetime as dt

import polars as pl

from ingestion.validators.schema import parse_batch, validate_header

COLUMNS = {
    "subject_id": "integer",
    "admittime": "timestamp",
    "dod": "date",
    "flag": "smallint",
    "code": "varchar(3)",
    "value": "double precision",
    "note": "text",
}


def frame(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema={c: pl.Utf8 for c in COLUMNS})


def good_row(**overrides) -> dict:
    row = {"subject_id": "10", "admittime": "2150-01-01 08:00:00", "dod": "2151-03-04",
           "flag": "1", "code": "ABC", "value": "1.5", "note": "free text"}
    row.update(overrides)
    return row


def test_header_detects_missing_and_extra_columns():
    check = validate_header(["a", "b", "z"], ["a", "b", "c"])
    assert check.missing == ["c"]
    assert check.extra == ["z"]
    assert not check.ok


def test_header_ok_when_all_expected_present():
    assert validate_header(["c", "a", "b"], ["a", "b", "c"]).ok


def test_valid_row_is_parsed_to_typed_values():
    parsed = parse_batch(frame([good_row()]), COLUMNS, ["subject_id"], first_line=1)
    assert parsed.n_rejected == 0
    row = parsed.good.row(0, named=True)
    assert row["subject_id"] == 10
    assert row["admittime"] == dt.datetime(2150, 1, 1, 8, 0)
    assert row["dod"] == dt.date(2151, 3, 4)
    assert row["value"] == 1.5
    assert row["_source_line"] == 1


def test_nulls_are_preserved_not_rejected_for_nullable_columns():
    parsed = parse_batch(frame([good_row(dod=None, value=None, note=None)]), COLUMNS,
                         ["subject_id"], first_line=1)
    assert parsed.n_rejected == 0
    row = parsed.good.row(0, named=True)
    assert row["dod"] is None and row["value"] is None


def test_unparseable_values_are_rejected_with_reason_and_line():
    rows = [good_row(), good_row(admittime="not-a-date"), good_row(subject_id="x1")]
    parsed = parse_batch(frame(rows), COLUMNS, ["subject_id"], first_line=100)
    assert parsed.good.height == 1
    reasons = {r["line"]: r["reason"] for r in parsed.rejects}
    assert reasons[101] == "unparseable:admittime"
    assert "unparseable:subject_id" in reasons[102]
    # the original raw record is preserved for investigation
    assert parsed.rejects[0]["record"]["admittime"] == "not-a-date"


def test_not_null_violation_is_rejected():
    parsed = parse_batch(frame([good_row(subject_id=None)]), COLUMNS, ["subject_id"], 1)
    assert parsed.n_rejected == 1
    assert parsed.rejects[0]["reason"] == "null:subject_id"


def test_varchar_overflow_and_smallint_overflow_are_rejected():
    rows = [good_row(code="ABCD"), good_row(flag="40000")]
    parsed = parse_batch(frame(rows), COLUMNS, [], first_line=1)
    reasons = sorted(r["reason"] for r in parsed.rejects)
    assert reasons == ["out_of_range:code", "out_of_range:flag"]


def test_extreme_but_valid_numeric_values_are_kept():
    # clinically extreme values are flagged downstream, never dropped at ingestion
    parsed = parse_batch(frame([good_row(value="-780"), good_row(value="169000")]), COLUMNS,
                         [], first_line=1)
    assert parsed.n_rejected == 0
    assert parsed.good["value"].to_list() == [-780.0, 169000.0]


def test_source_line_ordinals_are_contiguous_across_batches():
    parsed = parse_batch(frame([good_row(), good_row()]), COLUMNS, [], first_line=501)
    assert parsed.good["_source_line"].to_list() == [501, 502]
