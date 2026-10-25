# Dataproc Serverless runs inside a subnet with Private Google Access, so
# workloads reach Google APIs without external IPs or Cloud NAT.

resource "google_compute_network" "main" {
  project                 = var.project_id
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "dataproc" {
  project                  = var.project_id
  name                     = "${var.name_prefix}-dataproc"
  region                   = var.region
  network                  = google_compute_network.main.id
  ip_cidr_range            = var.subnet_cidr
  private_ip_google_access = true
}

# Dataproc Serverless requires nodes in the batch to talk to each other.
resource "google_compute_firewall" "internal" {
  project       = var.project_id
  name          = "${var.name_prefix}-allow-internal"
  network       = google_compute_network.main.name
  direction     = "INGRESS"
  source_ranges = [var.subnet_cidr]

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }
}
