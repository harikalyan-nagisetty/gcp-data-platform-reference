"""Daily synthetic claims pipeline.

    extract -> spark_clean -> load_curated -> build_mart -> quality_checks

Design choices (see docs/adr):
  * Every task is idempotent for a given logical date. Raw and curated writes
    are overwritten, the BigQuery load and mart build use WRITE_TRUNCATE on a
    single day partition, so a retry or backfill never double counts.
  * Configuration comes from environment variables, not Airflow Variables, so
    parsing the DAG never touches the metadata DB.
  * Spark runs on Dataproc Serverless, so there is no cluster to manage.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.operators.dataproc import DataprocCreateBatchOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from include.synthetic_claims import generate_claims, write_csv

# --- Configuration (set by `make env` from Terraform outputs) ----------------
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-gcp-project")
REGION = os.environ.get("GCP_REGION", "us-central1")
RAW_BUCKET = os.environ.get("RAW_BUCKET", "raw-bucket")
CURATED_BUCKET = os.environ.get("CURATED_BUCKET", "curated-bucket")
CODE_BUCKET = os.environ.get("CODE_BUCKET", "code-bucket")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET", "staging-bucket")
CURATED_DATASET = os.environ.get("CURATED_DATASET", "cdp_curated")
MARTS_DATASET = os.environ.get("MARTS_DATASET", "cdp_marts")
SPARK_SERVICE_ACCOUNT = os.environ.get("SPARK_SERVICE_ACCOUNT", "")
SUBNETWORK_URI = os.environ.get("SUBNETWORK_URI", "")
# Check which Dataproc Serverless runtimes are currently supported before changing this.
DATAPROC_RUNTIME_VERSION = os.environ.get("DATAPROC_RUNTIME_VERSION", "2.3")
ROWS_PER_DAY = int(os.environ.get("ROWS_PER_DAY", "5000"))


def _parse_ds(ds: str) -> date:
    try:
        return datetime.strptime(ds, "%Y-%m-%d").date()
    except ValueError as exc:  # defensive: ds is Airflow-provided
        raise AirflowFailException(f"unexpected ds value: {ds!r}") from exc


def extract_synthetic_claims(ds: str, **_: object) -> None:
    """Stand-in for a source system: write one day of synthetic claims to GCS raw."""
    rows = generate_claims(_parse_ds(ds), rows=ROWS_PER_DAY)
    with tempfile.TemporaryDirectory() as tmp:
        local = write_csv(rows, Path(tmp) / "claims.csv")
        GCSHook().upload(
            bucket_name=RAW_BUCKET,
            object_name=f"claims/ds={ds}/claims.csv",
            filename=str(local),
        )


def run_quality_checks(ds: str, **_: object) -> None:
    """Fail the run if the loaded partition or the mart looks wrong."""
    day = _parse_ds(ds).isoformat()
    curated = f"`{PROJECT_ID}.{CURATED_DATASET}.claims`"
    mart = f"`{PROJECT_ID}.{MARTS_DATASET}.claims_daily_summary`"
    checks = {
        "curated has rows": (
            f"SELECT COUNT(*) FROM {curated} WHERE service_date = DATE '{day}'",
            lambda v: v > 0,
        ),
        "no null claim_id": (
            f"SELECT COUNTIF(claim_id IS NULL) FROM {curated} WHERE service_date = DATE '{day}'",
            lambda v: v == 0,
        ),
        "claim_id is unique": (
            f"SELECT COUNT(*) - COUNT(DISTINCT claim_id) FROM {curated} "
            f"WHERE service_date = DATE '{day}'",
            lambda v: v == 0,
        ),
        "paid never exceeds billed": (
            f"SELECT COUNTIF(paid_amount > billed_amount) FROM {curated} "
            f"WHERE service_date = DATE '{day}'",
            lambda v: v == 0,
        ),
        "mart claim_count matches curated": (
            f"SELECT (SELECT SUM(claim_count) FROM {mart} WHERE service_date = DATE '{day}') "
            f"- (SELECT COUNT(*) FROM {curated} WHERE service_date = DATE '{day}')",
            lambda v: v == 0,
        ),
    }
    hook = BigQueryHook(use_legacy_sql=False)
    failures = []
    for name, (sql, passes) in checks.items():
        value = hook.get_first(sql)[0]
        if value is None or not passes(value):
            failures.append(f"{name} (got {value!r})")
    if failures:
        raise AirflowFailException("data quality checks failed: " + "; ".join(failures))


default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
}

with DAG(
    dag_id="synthetic_claims_pipeline",
    description="Synthetic claims: GCS raw -> Spark -> BigQuery curated -> mart -> checks",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,  # backfill explicitly: airflow dags backfill ...
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=2),
    params={
        "project_id": PROJECT_ID,
        "curated_dataset": CURATED_DATASET,
        "marts_dataset": MARTS_DATASET,
    },
    tags=["reference", "synthetic-data", "gcp"],
) as dag:
    extract = PythonOperator(
        task_id="extract_synthetic_claims",
        python_callable=extract_synthetic_claims,
        execution_timeout=timedelta(minutes=15),
    )

    spark_clean = DataprocCreateBatchOperator(
        task_id="spark_clean_claims",
        project_id=PROJECT_ID,
        region=REGION,
        # Batch IDs must be unique per project/region, so include the try number.
        batch_id="claims-clean-{{ ds_nodash }}-{{ ti.try_number }}",
        batch={
            "pyspark_batch": {
                "main_python_file_uri": f"gs://{CODE_BUCKET}/spark/clean_claims.py",
                "args": [
                    f"--input=gs://{RAW_BUCKET}/claims/ds={{{{ ds }}}}/claims.csv",
                    f"--output=gs://{CURATED_BUCKET}/claims/ds={{{{ ds }}}}",
                    f"--rejects=gs://{CURATED_BUCKET}/rejects/ds={{{{ ds }}}}",
                ],
            },
            "runtime_config": {"version": DATAPROC_RUNTIME_VERSION},
            "environment_config": {
                "execution_config": {
                    "service_account": SPARK_SERVICE_ACCOUNT,
                    "subnetwork_uri": SUBNETWORK_URI,
                    "staging_bucket": STAGING_BUCKET,
                }
            },
        },
        execution_timeout=timedelta(minutes=45),
    )

    load_curated = GCSToBigQueryOperator(
        task_id="load_curated_claims",
        bucket=CURATED_BUCKET,
        source_objects=["claims/ds={{ ds }}/*.parquet"],
        # The $YYYYMMDD decorator + WRITE_TRUNCATE replaces exactly one partition.
        destination_project_dataset_table=(
            f"{PROJECT_ID}.{CURATED_DATASET}.claims$" + "{{ ds_nodash }}"
        ),
        source_format="PARQUET",
        write_disposition="WRITE_TRUNCATE",
        create_disposition="CREATE_NEVER",
        autodetect=False,
        execution_timeout=timedelta(minutes=20),
    )

    build_mart = BigQueryInsertJobOperator(
        task_id="build_claims_daily_summary",
        configuration={
            "query": {
                "query": "{% include 'sql/claims_daily_summary.sql' %}",
                "useLegacySql": False,
                "destinationTable": {
                    "projectId": PROJECT_ID,
                    "datasetId": MARTS_DATASET,
                    "tableId": "claims_daily_summary${{ ds_nodash }}",
                },
                "writeDisposition": "WRITE_TRUNCATE",
                "createDisposition": "CREATE_NEVER",
            }
        },
        location=os.environ.get("BQ_LOCATION", "US"),
        execution_timeout=timedelta(minutes=20),
    )

    quality_checks = PythonOperator(
        task_id="quality_checks",
        python_callable=run_quality_checks,
        execution_timeout=timedelta(minutes=10),
    )

    extract >> spark_clean >> load_curated >> build_mart >> quality_checks
