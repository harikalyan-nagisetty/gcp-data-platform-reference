variable "project_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "location" {
  type = string
}

variable "force_destroy" {
  description = "Delete dataset contents on destroy."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Protect tables from accidental deletion."
  type        = bool
  default     = true
}

variable "labels" {
  type    = map(string)
  default = {}
}
