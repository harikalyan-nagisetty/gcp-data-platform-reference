resource "google_storage_bucket" "this" {
  for_each = var.buckets

  # Bucket names are global, so include the project id.
  name          = "${var.name_prefix}-${var.project_id}-${each.key}"
  project       = var.project_id
  location      = var.location
  force_destroy = var.force_destroy
  labels        = var.labels

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = each.value.versioning
  }

  dynamic "lifecycle_rule" {
    for_each = each.value.retention_days > 0 ? [each.value.retention_days] : []

    content {
      condition {
        age = lifecycle_rule.value
      }
      action {
        type = "Delete"
      }
    }
  }
}
