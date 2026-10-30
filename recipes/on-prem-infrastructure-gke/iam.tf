# IAM for GKE Nodes
#
# Dedicated least-privilege node service account. Nodes get the broad
# cloud-platform OAuth scope; effective permissions are bounded by these
# project-level role bindings. container.defaultNodeServiceAccount is GKE's
# documented minimum for custom node service accounts (it carries
# serviceusage.services.use and autoscaling.sites.writeMetrics, which the
# explicit telemetry roles do not).

resource "google_service_account" "gke_node" {
  account_id   = "${var.cluster_name}-node"
  display_name = "GKE node service account for ${var.cluster_name}"

  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "gke_node" {
  for_each = toset([
    "roles/container.defaultNodeServiceAccount",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/stackdriver.resourceMetadata.writer",
    "roles/artifactregistry.reader",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.gke_node.email}"
}
