# GCP Project and Location Configuration
variable "project_id" {
  description = "GCP project ID for resources"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone for the zonal GKE cluster (must offer G2 machine types with NVIDIA L4)"
  type        = string
  default     = "us-central1-a"
}

variable "cluster_name" {
  description = "Name of the GKE cluster (at most 25 characters so the derived node service-account ID fits GCP's 30-character limit)"
  type        = string
  default     = "gke-polar-sky"

  validation {
    condition     = can(regex("^[a-z]([a-z0-9-]{0,23}[a-z0-9])?$", var.cluster_name))
    error_message = "cluster_name must start with a lowercase letter, end with a letter or digit, use only lowercase letters, digits, and hyphens, and be at most 25 characters (the node service-account ID appends -node and must stay within 30 characters)"
  }
}

# GPU Node Pool Configuration
variable "gpu_node_min_count" {
  description = "Minimum number of GPU nodes in the autoscaling pool (0 for cost savings)"
  type        = number
  default     = 0

  validation {
    condition     = var.gpu_node_min_count >= 0 && var.gpu_node_min_count <= 10
    error_message = "GPU node min count must be between 0 and 10"
  }
}

variable "gpu_node_max_count" {
  description = "Maximum number of GPU nodes in the autoscaling pool"
  type        = number
  default     = 6

  validation {
    condition     = var.gpu_node_max_count >= 1 && var.gpu_node_max_count <= 10
    error_message = "GPU node max count must be between 1 and 10"
  }
}

variable "gpu_node_spot" {
  description = "Use spot VMs for GPU nodes (cheaper, but can be preempted with 30 seconds notice)"
  type        = bool
  default     = true
}

# Network Configuration
variable "nodes_cidr" {
  description = "Primary CIDR range for the node subnet"
  type        = string
  default     = "10.0.0.0/20"

  validation {
    condition     = can(cidrhost(var.nodes_cidr, 0))
    error_message = "nodes_cidr must be a valid CIDR block"
  }
}

variable "pods_cidr" {
  description = "Secondary CIDR range for pods (VPC-native)"
  type        = string
  default     = "10.4.0.0/14"

  validation {
    condition     = can(cidrhost(var.pods_cidr, 0))
    error_message = "pods_cidr must be a valid CIDR block"
  }
}

variable "services_cidr" {
  description = "Secondary CIDR range for services (VPC-native)"
  type        = string
  default     = "10.8.0.0/20"

  validation {
    condition     = can(cidrhost(var.services_cidr, 0))
    error_message = "services_cidr must be a valid CIDR block"
  }
}

variable "master_cidr" {
  description = "CIDR range for the GKE control plane peering (must be a /28)"
  type        = string
  default     = "172.16.0.0/28"

  validation {
    condition     = can(cidrhost(var.master_cidr, 0)) && can(regex("/28$", var.master_cidr))
    error_message = "master_cidr must be a valid /28 CIDR block (GKE requires a /28 for master_ipv4_cidr_block)"
  }
}

# Resource Labeling
variable "labels" {
  description = "Labels to apply to all resources"
  type        = map(string)
  default = {
    environment = "test"
    project     = "polar-sky"
    managed_by  = "opentofu"
    purpose     = "polar-sky-on-prem"
  }
}
