variable "project_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "location" {
  description = "Bucket location (region or multi-region)."
  type        = string
}

variable "buckets" {
  description = "Buckets to create, keyed by suffix. retention_days = 0 disables lifecycle deletion."
  type = map(object({
    retention_days = optional(number, 0)
    versioning     = optional(bool, false)
  }))
}

variable "force_destroy" {
  type    = bool
  default = false
}

variable "labels" {
  type    = map(string)
  default = {}
}
