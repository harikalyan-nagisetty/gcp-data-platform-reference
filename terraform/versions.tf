terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Local state keeps this reference simple. For anything shared, use a remote
  # backend (GCS bucket with versioning and state locking).
}

provider "google" {
  project = var.project_id
  region  = var.region
}
