resource "google_bigquery_dataset" "curated" {
  project       = var.project_id
  dataset_id    = "${var.name_prefix}_curated"
  friendly_name = "Curated claims"
  description   = "Cleaned, typed claims. Loaded by the pipeline only; not for ad hoc access."
  location      = var.location
  labels        = var.labels

  delete_contents_on_destroy = var.force_destroy
}

resource "google_bigquery_dataset" "marts" {
  project       = var.project_id
  dataset_id    = "${var.name_prefix}_marts"
  friendly_name = "Claims marts"
  description   = "Aggregated, analyst-facing tables."
  location      = var.location
  labels        = var.labels

  delete_contents_on_destroy = var.force_destroy
}

resource "google_bigquery_table" "claims" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.curated.dataset_id
  table_id            = "claims"
  description         = "One row per valid claim, partitioned by service_date."
  deletion_protection = var.deletion_protection
  labels              = var.labels

  # Cost guardrail: every query must filter on the partition column.
  require_partition_filter = true

  time_partitioning {
    type  = "DAY"
    field = "service_date"
  }

  clustering = ["diagnosis_code", "provider_id"]

  schema = file("${path.module}/schemas/claims.json")
}

resource "google_bigquery_table" "claims_daily_summary" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.marts.dataset_id
  table_id            = "claims_daily_summary"
  description         = "Daily claim counts and amounts by diagnosis and status."
  deletion_protection = var.deletion_protection
  labels              = var.labels

  time_partitioning {
    type  = "DAY"
    field = "service_date"
  }

  clustering = ["diagnosis_code"]

  schema = file("${path.module}/schemas/claims_daily_summary.json")
}
