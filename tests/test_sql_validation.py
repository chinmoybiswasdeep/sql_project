"""Run the independent SQL validation queries (sql/validation) and require exact agreement."""

from __future__ import annotations

from decimal import Decimal

import pytest

from config.settings import PROJECT_ROOT

pytestmark = pytest.mark.integration
VALIDATION = sorted((PROJECT_ROOT / "sql" / "validation").glob("v*.sql"))


@pytest.mark.parametrize("path", VALIDATION, ids=lambda p: p.stem)
def test_validation_components_agree(db, path):
    with db.cursor() as cur:
        cur.execute(path.read_text())
        rows = cur.fetchall()
    assert rows, f"{path.name} returned no rows"
    mismatches = [(c, w, i) for c, w, i in rows if Decimal(str(w)) != Decimal(str(i))]
    assert not mismatches, f"warehouse vs independent mismatch: {mismatches}"
