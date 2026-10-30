# VPC and Networking for GKE Cluster
#
# Creates a custom-mode VPC with a single node subnet plus secondary ranges
# for pods and services (VPC-native cluster). Cloud NAT provides outbound
# internet access for the private nodes (image pulls, model downloads).

resource "google_compute_network" "polar_sky" {
  name                    = "vpc-${var.cluster_name}"
  auto_create_subnetworks = false

  depends_on = [google_project_service.required]
}

resource "google_compute_subnetwork" "nodes" {
  name          = "snet-${var.cluster_name}-nodes"
  network       = google_compute_network.polar_sky.id
  region        = var.region
  ip_cidr_range = var.nodes_cidr

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }

  private_ip_google_access = true
}

# Cloud NAT (single, regional) for outbound access from private nodes
resource "google_compute_router" "polar_sky" {
  name    = "router-${var.cluster_name}"
  network = google_compute_network.polar_sky.id
  region  = var.region
}

resource "google_compute_router_nat" "polar_sky" {
  name                               = "nat-${var.cluster_name}"
  router                             = google_compute_router.polar_sky.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
