output "project_id" {
  value = var.project_id
}

output "raw_bucket" {
  value = module.lake.bucket_names["raw"]
}

output "curated_bucket" {
  value = module.lake.bucket_names["curated"]
}

output "code_bucket" {
  value = module.lake.bucket_names["code"]
}

output "staging_bucket" {
  value = module.lake.bucket_names["staging"]
}

output "curated_dataset" {
  value = module.warehouse.curated_dataset_id
}

output "marts_dataset" {
  value = module.warehouse.marts_dataset_id
}

output "bq_location" {
  value = var.bq_location
}

output "region" {
  value = var.region
}

output "spark_service_account" {
  value = google_service_account.spark.email
}

output "airflow_service_account" {
  value = google_service_account.airflow.email
}

output "subnetwork_uri" {
  value = google_compute_subnetwork.dataproc.self_link
}
