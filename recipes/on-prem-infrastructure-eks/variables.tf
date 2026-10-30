# AWS Region Configuration
variable "region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "eks-polar-sky"
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

variable "gpu_node_capacity_type" {
  description = "Capacity type for GPU nodes (ON_DEMAND or SPOT)"
  type        = string
  default     = "SPOT"

  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.gpu_node_capacity_type)
    error_message = "GPU node capacity type must be ON_DEMAND or SPOT"
  }
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid CIDR block"
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
