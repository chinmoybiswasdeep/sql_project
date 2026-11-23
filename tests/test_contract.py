"""Unit tests for the source contract and generated DDL."""

from __future__ import annotations

from config.settings import Settings, load_source_contract
from ingestion.loaders.ddl import contract_hash, create_table_sql, render_all
from ingestion.validators.schema import _parse_expr


def test_every_table_is_in_load_order_and_parents_load_first():
    contract = load_source_contract()
    order = contract["load_order"]
    assert set(order) == set(contract["tables"])
    for name, spec in contract["tables"].items():
        for target in spec.get("parents", {}).values():
            parent = target.split(".")[0]
            assert order.index(parent) < order.index(name), f"{parent} must load before {name}"


def test_keys_and_not_null_columns_exist_in_column_list():
    for name, spec in load_source_contract()["tables"].items():
        cols = set(spec["columns"])
        assert set(spec["primary_key"]) <= cols, name
        assert set(spec.get("not_null", [])) <= cols, name
        for fk in spec.get("parents", {}):
            assert fk in cols, name


def test_every_contract_type_is_supported_by_the_parser():
    for spec in load_source_contract()["tables"].values():
        for col, typ in spec["columns"].items():
            _parse_expr(col, typ)  # raises ValueError for unsupported types


def test_ddl_includes_lineage_columns_and_all_tables():
    ddl = render_all()
    contract = load_source_contract()
    for name in contract["tables"]:
        assert f"CREATE TABLE IF NOT EXISTS raw.{name}" in ddl
    assert "_source_line" in create_table_sql("patients", contract["tables"]["patients"])


def test_contract_hash_changes_when_contract_changes():
    spec = {"columns": {"a": "integer"}, "primary_key": ["a"]}
    changed = {"columns": {"a": "bigint"}, "primary_key": ["a"]}
    assert contract_hash(spec) != contract_hash(changed)
    assert contract_hash(spec) == contract_hash(dict(spec))


def test_settings_reject_invalid_mode(monkeypatch):
    monkeypatch.setenv("HI_DATASET_MODE", "everything")
    try:
        Settings()
    except ValueError as exc:
        assert "HI_DATASET_MODE" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid mode accepted")
