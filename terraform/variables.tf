variable "project_id" {
  description = "GCP project that hosts the platform."
  type        = string
}

variable "region" {
  description = "Region for buckets, networking and Dataproc Serverless."
  type        = string
  default     = "us-central1"
}

variable "bq_location" {
  description = "BigQuery dataset location (multi-region such as US, or a region)."
  type        = string
  default     = "US"
}

variable "name_prefix" {
  description = "Short prefix for resource names (3-10 chars, lowercase letters and digits)."
  type        = string
  default     = "cdp"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{2,9}$", var.name_prefix))
    error_message = "name_prefix must be 3-10 lowercase letters or digits, starting with a letter."
  }
}

variable "subnet_cidr" {
  description = "CIDR range of the Dataproc Serverless subnet."
  type        = string
  default     = "10.10.0.0/24"
}

variable "raw_retention_days" {
  description = "Days to keep raw files before lifecycle deletion (0 keeps them forever)."
  type        = number
  default     = 30
}

variable "force_destroy" {
  description = "Allow `terraform destroy` to delete non-empty buckets and datasets. Keep false outside a sandbox."
  type        = bool
  default     = true
}

variable "deletion_protection" {
  description = "Enable BigQuery table deletion protection."
  type        = bool
  default     = false
}

variable "analyst_members" {
  description = "IAM members (for example user:jane@example.com) granted read access to the marts dataset only."
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Extra labels applied to buckets and datasets."
  type        = map(string)
  default     = {}
}
