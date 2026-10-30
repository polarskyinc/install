# GKE Cluster and Node Pools
#
# Creates a zonal VPC-native GKE cluster with:
# - System node pool: e2-standard-4 (4 vCPU, 16 GiB) - on-demand, autoscaling 3-6
# - GPU node pool: g2-standard-8 (1x NVIDIA L4) - spot (default), autoscaling
#
# GKE manages the cluster autoscaler, NVIDIA drivers, and device plugin
# natively, so no Helm-deployed add-ons are required.
# GPU nodes are automatically labeled cloud.google.com/gke-accelerator=nvidia-l4;
# the matching nvidia.com/gpu=present:NoSchedule taint is declared explicitly
# on the GPU pool rather than relying on GKE's auto-taint.

resource "google_container_cluster" "polar_sky" {
  name     = var.cluster_name
  location = var.zone

  network    = google_compute_network.polar_sky.id
  subnetwork = google_compute_subnetwork.nodes.id

  networking_mode = "VPC_NATIVE"

  datapath_provider = "ADVANCED_DATAPATH"

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_cidr
  }

  release_channel {
    channel = "REGULAR"
  }

  remove_default_node_pool = true
  initial_node_count       = 1

  deletion_protection = false

  resource_labels = var.labels

  depends_on = [google_project_service.required]

  lifecycle {
    precondition {
      condition     = startswith(var.zone, "${var.region}-")
      error_message = "zone must be inside region (e.g. region us-central1 with zone us-central1-a); a zonal cluster cannot attach to a subnet in a different region"
    }
  }
}

# System Node Pool - always-on, runs system pods
resource "google_container_node_pool" "system" {
  name     = "system"
  cluster  = google_container_cluster.polar_sky.name
  location = var.zone

  depends_on = [google_project_iam_member.gke_node]

  initial_node_count = 3

  autoscaling {
    min_node_count = 3
    max_node_count = 6
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = "e2-standard-4"
    disk_size_gb    = 50
    disk_type       = "pd-balanced"
    service_account = google_service_account.gke_node.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# GPU Node Pool - autoscaling, runs vLLM model servers
resource "google_container_node_pool" "gpu" {
  name     = "gpu"
  cluster  = google_container_cluster.polar_sky.name
  location = var.zone

  depends_on = [google_project_iam_member.gke_node]

  initial_node_count = var.gpu_node_min_count

  autoscaling {
    min_node_count = var.gpu_node_min_count
    max_node_count = var.gpu_node_max_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = "g2-standard-8"
    disk_size_gb    = 100
    disk_type       = "pd-balanced"
    spot            = var.gpu_node_spot
    service_account = google_service_account.gke_node.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

    # Same taint GKE auto-applies to GPU pools, declared explicitly because the
    # auto-taint only triggers when a non-GPU pool already exists and the system
    # pool is created concurrently with this one.
    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }

    guest_accelerator {
      type  = "nvidia-l4"
      count = 1

      gpu_driver_installation_config {
        gpu_driver_version = "DEFAULT"
      }
    }
  }
}
