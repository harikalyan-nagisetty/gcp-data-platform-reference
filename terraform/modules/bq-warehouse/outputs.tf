output "curated_dataset_id" {
  value = google_bigquery_dataset.curated.dataset_id
}

output "marts_dataset_id" {
  value = google_bigquery_dataset.marts.dataset_id
}
