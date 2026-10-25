import os
import shutil
import sys

import pytest

pytest.importorskip("pyspark")
if shutil.which("java") is None:
    pytest.skip("Java is required for Spark tests", allow_module_level=True)

from clean_claims import RAW_COLUMNS, RAW_SCHEMA, split_claims  # noqa: E402

BASE = {
    "claim_id": "CLM-1",
    "member_id": "M000001",
    "provider_id": "P00001",
    "service_date": "2026-01-15",
    "diagnosis_code": "E11.9",
    "procedure_code": "99213",
    "billed_amount": "100.00",
    "paid_amount": "80.00",
    "claim_status": "PAID",
}


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    # Make Spark workers use the same interpreter as the test run, otherwise a
    # different `python3` on PATH causes a driver/worker version mismatch.
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    session = (
        SparkSession.builder.master("local[1]")
        .appName("clean-claims-tests")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


def make_df(spark, *overrides):
    rows = [tuple({**BASE, **o}[c] for c in RAW_COLUMNS) for o in overrides]
    return spark.createDataFrame(rows, schema=RAW_SCHEMA)


def test_valid_row_passes_unchanged(spark):
    valid, rejects = split_claims(make_df(spark, {}))
    assert rejects.count() == 0
    row = valid.collect()[0]
    assert row["claim_id"] == "CLM-1"
    assert str(row["billed_amount"]) == "100.00"
    assert str(row["service_date"]) == "2026-01-15"


def test_messy_text_is_standardised_not_rejected(spark):
    valid, rejects = split_claims(
        make_df(spark, {"diagnosis_code": "  e11.9 ", "claim_status": "Paid"})
    )
    assert rejects.count() == 0
    row = valid.collect()[0]
    assert row["diagnosis_code"] == "E11.9"
    assert row["claim_status"] == "PAID"


def test_exact_duplicates_collapse_to_one_row(spark):
    valid, rejects = split_claims(make_df(spark, {}, {}, {}))
    assert valid.count() == 1
    assert rejects.count() == 0


def test_conflicting_duplicate_claim_ids_are_both_rejected(spark):
    valid, rejects = split_claims(make_df(spark, {}, {"billed_amount": "200.00"}))
    assert valid.count() == 0
    assert {r["reject_reason"] for r in rejects.collect()} == {"conflicting_duplicate_claim_id"}
    assert rejects.count() == 2


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"claim_id": ""}, "missing_claim_id"),
        ({"claim_id": None}, "missing_claim_id"),
        ({"service_date": "2026-13-45"}, "invalid_service_date"),
        ({"service_date": None}, "invalid_service_date"),
        ({"billed_amount": "-5.00"}, "invalid_billed_amount"),
        ({"billed_amount": "abc"}, "invalid_billed_amount"),
        ({"paid_amount": "-1.00"}, "invalid_paid_amount"),
        ({"paid_amount": "150.00"}, "paid_exceeds_billed"),
        ({"claim_status": "UNKNOWN"}, "invalid_status"),
    ],
)
def test_each_rule_rejects_with_reason(spark, override, reason):
    valid, rejects = split_claims(make_df(spark, override))
    assert valid.count() == 0
    assert [r["reject_reason"] for r in rejects.collect()] == [reason]


def test_valid_and_rejected_rows_are_split(spark):
    df = make_df(
        spark,
        {"claim_id": "CLM-1"},
        {"claim_id": "CLM-2"},
        {"claim_id": "CLM-3", "claim_status": "UNKNOWN"},
    )
    valid, rejects = split_claims(df)
    assert valid.count() == 2
    assert rejects.count() == 1
