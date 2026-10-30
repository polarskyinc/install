# Terraform Outputs for GKE Polar Sky Infrastructure

# GKE Cluster Information
output "gke_cluster_name" {
  description = "Name of the GKE cluster (use with kubectl commands)"
  value       = google_container_cluster.polar_sky.name
}

# kubectl Access Command
output "gke_get_credentials_command" {
  description = "gcloud command to configure kubectl with GKE cluster credentials"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.polar_sky.name} --zone ${var.zone} --project ${var.project_id}"
}
