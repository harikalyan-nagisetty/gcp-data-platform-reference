# Least privilege: two service accounts, grants scoped to a single bucket or
# dataset wherever possible. Only the job-level roles are project-wide because
# GCP does not allow narrowing them.

resource "google_service_account" "spark" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-spark"
  display_name = "Dataproc Serverless Spark runner"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "airflow" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-airflow"
  display_name = "Airflow pipeline runner"

  depends_on = [google_project_service.apis]
}

locals {
  spark_member   = "serviceAccount:${google_service_account.spark.email}"
  airflow_member = "serviceAccount:${google_service_account.airflow.email}"

  bucket_grants = {
    spark_read_raw       = { bucket = "raw", role = "roles/storage.objectViewer", member = local.spark_member }
    spark_read_code      = { bucket = "code", role = "roles/storage.objectViewer", member = local.spark_member }
    spark_write_curated  = { bucket = "curated", role = "roles/storage.objectAdmin", member = local.spark_member }
    spark_use_staging    = { bucket = "staging", role = "roles/storage.objectAdmin", member = local.spark_member }
    airflow_write_raw    = { bucket = "raw", role = "roles/storage.objectAdmin", member = local.airflow_member }
    airflow_read_curated = { bucket = "curated", role = "roles/storage.objectViewer", member = local.airflow_member }
    airflow_read_code    = { bucket = "code", role = "roles/storage.objectViewer", member = local.airflow_member }
  }
}

resource "google_storage_bucket_iam_member" "grants" {
  for_each = local.bucket_grants

  bucket = module.lake.bucket_names[each.value.bucket]
  role   = each.value.role
  member = each.value.member
}

# Dataproc Serverless: the batch service account needs the worker role.
resource "google_project_iam_member" "spark_worker" {
  project = var.project_id
  role    = "roles/dataproc.worker"
  member  = local.spark_member
}

# Airflow submits batches and runs BigQuery jobs.
resource "google_project_iam_member" "airflow_dataproc" {
  project = var.project_id
  role    = "roles/dataproc.editor"
  member  = local.airflow_member
}

resource "google_project_iam_member" "airflow_bq_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = local.airflow_member
}

# Allow Airflow to run batches as the Spark service account (and nothing else).
resource "google_service_account_iam_member" "airflow_acts_as_spark" {
  service_account_id = google_service_account.spark.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.airflow_member
}

# Dataset-level BigQuery access.
resource "google_bigquery_dataset_iam_member" "airflow_curated" {
  project    = var.project_id
  dataset_id = module.warehouse.curated_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = local.airflow_member
}

resource "google_bigquery_dataset_iam_member" "airflow_marts" {
  project    = var.project_id
  dataset_id = module.warehouse.marts_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = local.airflow_member
}

# Analysts read the marts only, never the curated layer.
resource "google_bigquery_dataset_iam_member" "analysts_marts" {
  for_each = toset(var.analyst_members)

  project    = var.project_id
  dataset_id = module.warehouse.marts_dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = each.value
}
