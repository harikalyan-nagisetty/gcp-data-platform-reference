import csv
from datetime import date

import pytest
from include.synthetic_claims import COLUMNS, generate_claims, write_csv

DS = date(2026, 1, 15)


def test_output_is_deterministic():
    assert generate_claims(DS, 200, seed=1) == generate_claims(DS, 200, seed=1)


def test_seed_changes_output():
    assert generate_claims(DS, 200, seed=1) != generate_claims(DS, 200, seed=2)


def test_row_count_includes_dirty_rows():
    assert len(generate_claims(DS, rows=1000, dirty_rate=0.05)) == 1050


def test_zero_dirty_rate_gives_only_valid_rows():
    rows = generate_claims(DS, rows=100, dirty_rate=0)
    assert len(rows) == 100
    assert len({r["claim_id"] for r in rows}) == 100
    assert all(r["service_date"] == DS.isoformat() for r in rows)
    assert all(float(r["paid_amount"]) <= float(r["billed_amount"]) for r in rows)
    assert all(r["claim_status"] in {"PAID", "DENIED", "PENDING"} for r in rows)


def test_dirty_rows_are_present():
    rows = generate_claims(DS, rows=1000, dirty_rate=0.05)
    assert len({r["claim_id"] for r in rows}) < len(rows)


def test_identifiers_are_opaque_tokens():
    row = generate_claims(DS, rows=1, dirty_rate=0)[0]
    assert row["member_id"].startswith("M") and row["provider_id"].startswith("P")


def test_write_csv_round_trip(tmp_path):
    rows = generate_claims(DS, rows=50)
    path = write_csv(rows, tmp_path / "nested" / "claims.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == COLUMNS
        assert list(reader) == rows


@pytest.mark.parametrize("kwargs", [{"rows": -1}, {"dirty_rate": 2}, {"dirty_rate": -0.1}])
def test_invalid_arguments_raise(kwargs):
    with pytest.raises(ValueError):
        generate_claims(DS, **kwargs)
