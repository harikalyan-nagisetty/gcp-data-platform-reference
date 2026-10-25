locals {
  labels = merge(
    {
      project    = "gcp-data-platform-reference"
      managed_by = "terraform"
    },
    var.labels
  )

  apis = [
    "bigquery.googleapis.com",
    "compute.googleapis.com",
    "dataproc.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
  ]

  # retention_days = 0 means objects are kept until deleted explicitly.
  buckets = {
    raw     = { retention_days = var.raw_retention_days, versioning = false }
    curated = { retention_days = 0, versioning = false }
    code    = { retention_days = 0, versioning = true }
    staging = { retention_days = 7, versioning = false }
  }
}

resource "google_project_service" "apis" {
  for_each = toset(local.apis)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "lake" {
  source = "./modules/gcs-lake"

  project_id    = var.project_id
  name_prefix   = var.name_prefix
  location      = var.region
  buckets       = local.buckets
  force_destroy = var.force_destroy
  labels        = local.labels

  depends_on = [google_project_service.apis]
}

module "warehouse" {
  source = "./modules/bq-warehouse"

  project_id          = var.project_id
  name_prefix         = var.name_prefix
  location            = var.bq_location
  force_destroy       = var.force_destroy
  deletion_protection = var.deletion_protection
  labels              = local.labels

  depends_on = [google_project_service.apis]
}
