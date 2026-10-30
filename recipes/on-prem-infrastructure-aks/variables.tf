# Azure Subscription and Location Configuration
variable "subscription_id" {
  description = "Azure subscription ID the cluster is created in"
  type        = string

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.subscription_id))
    error_message = "subscription_id must be an Azure subscription ID (a GUID)"
  }
}

variable "location" {
  description = "Azure region for resources (must offer NCasT4_v3 virtual machines)"
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Name of the resource group the recipe creates"
  type        = string
  default     = "rg-polar-sky"
}

variable "cluster_name" {
  description = "Name of the AKS cluster, also used as its DNS prefix"
  type        = string
  default     = "aks-polar-sky"

  validation {
    condition     = can(regex("^[a-z]([a-z0-9-]{0,52}[a-z0-9])?$", var.cluster_name))
    error_message = "cluster_name must start with a lowercase letter, end with a letter or digit, use only lowercase letters, digits, and hyphens, and be at most 54 characters (the AKS DNS prefix limit)"
  }
}

variable "kubernetes_version" {
  description = "Kubernetes minor version approved for this install, such as 1.35; AKS applies patch releases within it"
  type        = string

  validation {
    condition     = can(regex("^1\\.[0-9]+$", var.kubernetes_version))
    error_message = "kubernetes_version must be a minor version such as 1.35, without a patch number"
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
    condition     = var.gpu_node_max_count >= 4 && var.gpu_node_max_count <= 10
    error_message = "GPU node max count must be between 4 and 10; the model fleet needs four GPU nodes"
  }
}

# Network Configuration
variable "vnet_cidr" {
  description = "Address space of the virtual network"
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vnet_cidr, 0))
    error_message = "vnet_cidr must be a valid CIDR block"
  }
}

variable "nodes_cidr" {
  description = "CIDR range of the node subnet, inside vnet_cidr"
  type        = string
  default     = "10.0.0.0/20"

  validation {
    condition     = can(cidrhost(var.nodes_cidr, 0))
    error_message = "nodes_cidr must be a valid CIDR block"
  }
}

variable "pods_cidr" {
  description = "Overlay CIDR range for pods, outside vnet_cidr"
  type        = string
  default     = "10.244.0.0/16"

  validation {
    condition     = can(cidrhost(var.pods_cidr, 0))
    error_message = "pods_cidr must be a valid CIDR block"
  }
}

variable "services_cidr" {
  description = "CIDR range for services, outside vnet_cidr and pods_cidr"
  type        = string
  default     = "172.16.0.0/16"

  validation {
    condition     = can(cidrhost(var.services_cidr, 10))
    error_message = "services_cidr must be a valid CIDR block with room for the cluster DNS address"
  }
}

# Resource Tagging
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    environment = "test"
    project     = "polar-sky"
    managed_by  = "opentofu"
    purpose     = "polar-sky-on-prem"
  }
}
