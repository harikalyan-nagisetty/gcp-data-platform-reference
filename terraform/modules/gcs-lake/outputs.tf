output "bucket_names" {
  description = "Bucket names keyed by suffix (raw, curated, code, staging)."
  value       = { for key, bucket in google_storage_bucket.this : key => bucket.name }
}
