# Terraform Outputs for AKS Polar Sky Infrastructure

# AKS Cluster Information
output "aks_cluster_name" {
  description = "Name of the AKS cluster (use with kubectl commands)"
  value       = azurerm_kubernetes_cluster.polar_sky.name
}

output "resource_group_name" {
  description = "Name of the resource group holding the cluster"
  value       = azurerm_resource_group.polar_sky.name
}

# kubectl Access Command
output "aks_get_credentials_command" {
  description = "Azure CLI command to configure kubectl with AKS cluster credentials"
  value       = "az aks get-credentials --subscription ${var.subscription_id} --resource-group ${azurerm_resource_group.polar_sky.name} --name ${azurerm_kubernetes_cluster.polar_sky.name}"
}
