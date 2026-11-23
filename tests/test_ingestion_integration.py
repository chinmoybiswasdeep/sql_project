"""Integration checks on the loaded raw layer and the ingestion audit trail."""

from __future__ import annotations

import pyarrow.csv as pacsv
import pytest

from config.settings import get_settings, load_source_contract

pytestmark = pytest.mark.integration
CONTRACT = load_source_contract()


def latest_loads(db) -> dict[str, tuple]:
    with db.cursor() as cur:
        cur.execute("""
            select distinct on (table_name) table_name, source_rows, loaded_rows, rejected_rows,
                   duplicate_key_rows, file_sha256
            from meta.ingestion_table_log where status = 'loaded'
            order by table_name, logged_at desc""")
        return {r[0]: r[1:] for r in cur.fetchall()}


def test_every_required_table_has_a_successful_load(db):
    loads = latest_loads(db)
    required = [t for t, s in CONTRACT["tables"].items() if not s.get("optional")]
    assert set(required) <= set(loads)


def test_reconciliation_source_equals_loaded_plus_rejected(db):
    for table, (source, loaded, rejected, *_rest) in latest_loads(db).items():
        assert source == loaded + rejected, table


@pytest.mark.parametrize("table", [t for t in CONTRACT["load_order"]
                                   if t not in ("d_icd_diagnoses", "d_icd_procedures")])
def test_raw_row_count_matches_source_file(table, scalar):
    path = get_settings().data_dir / CONTRACT["tables"][table]["file"]
    if not path.exists():
        pytest.skip(f"{path} not present")
    file_rows = pacsv.read_csv(path).num_rows  # independent count of the source file
    assert scalar(f"select count(*) from raw.{table}") == file_rows


def test_declared_primary_keys_are_unique(db):
    for table, (_s, _l, _r, dup, _h) in latest_loads(db).items():
        assert dup == 0, f"{table} has duplicate keys"


def test_no_error_severity_check_failed(db):
    with db.cursor() as cur:
        cur.execute("""select check_name from meta.validation_results
                       where run_id = (select max(run_id) from meta.validation_results)
                         and status = 'fail'""")
        assert cur.fetchall() == []
