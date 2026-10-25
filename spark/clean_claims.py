"""Clean raw claims with Spark.

Reads the raw CSV, standardises types and text, removes exact duplicates, and
splits rows into:
  * curated: valid rows, written as Parquet (what BigQuery loads)
  * rejects: invalid rows with a `reject_reason`, written as Parquet for review

The split logic lives in `split_claims` (a pure DataFrame -> DataFrame
function) so it can be unit tested with a local SparkSession.

Rules are applied in order and the first failing rule wins.
"""

from __future__ import annotations

import argparse
import logging

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

LOG = logging.getLogger("clean_claims")

RAW_COLUMNS = [
    "claim_id",
    "member_id",
    "provider_id",
    "service_date",
    "diagnosis_code",
    "procedure_code",
    "billed_amount",
    "paid_amount",
    "claim_status",
]
RAW_SCHEMA = StructType([StructField(name, StringType(), True) for name in RAW_COLUMNS])
VALID_STATUSES = ["PAID", "DENIED", "PENDING"]
MONEY = "decimal(12,2)"


def standardise(df: DataFrame) -> DataFrame:
    """Trim and upper-case text, cast types. Bad casts become NULL, caught later."""
    text_cols = [
        "claim_id", "member_id", "provider_id",
        "diagnosis_code", "procedure_code", "claim_status",
    ]
    out = df
    for name in text_cols:
        out = out.withColumn(name, F.upper(F.trim(F.col(name))))
    # try_* variants return NULL on bad input under both ANSI and non-ANSI Spark,
    # so invalid values are rejected with a reason instead of failing the job.
    return (
        out.withColumn(
            "service_date",
            F.expr("to_date(try_to_timestamp(trim(service_date), 'yyyy-MM-dd'))"),
        )
        .withColumn("billed_amount", F.expr(f"try_cast(trim(billed_amount) AS {MONEY})"))
        .withColumn("paid_amount", F.expr(f"try_cast(trim(paid_amount) AS {MONEY})"))
    )


def split_claims(raw: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Return (valid, rejects). `rejects` has an extra `reject_reason` column."""
    df = standardise(raw.select(*RAW_COLUMNS)).dropDuplicates()

    # Same claim_id with different content after exact de-duplication is a conflict.
    id_count = F.count(F.lit(1)).over(Window.partitionBy("claim_id"))

    reason = (
        F.when(F.col("claim_id").isNull() | (F.col("claim_id") == ""), "missing_claim_id")
        .when(id_count > 1, "conflicting_duplicate_claim_id")
        .when(F.col("service_date").isNull(), "invalid_service_date")
        .when(
            F.col("billed_amount").isNull() | (F.col("billed_amount") < 0),
            "invalid_billed_amount",
        )
        .when(
            F.col("paid_amount").isNull() | (F.col("paid_amount") < 0),
            "invalid_paid_amount",
        )
        .when(F.col("paid_amount") > F.col("billed_amount"), "paid_exceeds_billed")
        .when(~F.col("claim_status").isin(VALID_STATUSES), "invalid_status")
    )
    flagged = df.withColumn("reject_reason", reason)
    valid = flagged.filter(F.col("reject_reason").isNull()).drop("reject_reason")
    rejects = flagged.filter(F.col("reject_reason").isNotNull())
    return valid, rejects


def run(
    spark: SparkSession, input_path: str, output_path: str, rejects_path: str
) -> dict[str, int]:
    raw = spark.read.option("header", True).schema(RAW_SCHEMA).csv(input_path)
    valid, rejects = split_claims(raw)

    # Small daily volumes: one file per run. Raise this for larger partitions.
    valid.coalesce(1).write.mode("overwrite").parquet(output_path)
    rejects.coalesce(1).write.mode("overwrite").parquet(rejects_path)

    stats = {
        "raw": raw.count(),
        "valid": spark.read.parquet(output_path).count(),
        "rejected": spark.read.parquet(rejects_path).count(),
    }
    LOG.info("clean_claims stats: %s", stats)
    print(f"clean_claims stats: {stats}")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Raw CSV path (local or gs://)")
    parser.add_argument("--output", required=True, help="Curated Parquet output path")
    parser.add_argument("--rejects", required=True, help="Rejected rows Parquet output path")
    args = parser.parse_args()

    spark = SparkSession.builder.appName("clean_claims").getOrCreate()
    try:
        run(spark, args.input, args.output, args.rejects)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
