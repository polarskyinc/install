# AKS Cluster and Node Pools
#
# Creates an AKS cluster with:
# - System node pool: Standard_D4s_v5 (4 vCPU, 16 GiB) - on-demand, autoscaling 3-6
# - GPU node pool: Standard_NC8as_T4_v3 (1x NVIDIA T4) - on-demand, autoscaling
#
# Networking is Azure CNI overlay with the Cilium data plane, which enforces the
# Kubernetes NetworkPolicy resources the Helm chart installs. AKS installs the
# NVIDIA drivers on GPU nodes; the device plugin is deployed in addons.tf.
#
# The GPU pool is on-demand only: Azure taints spot pools with
# kubernetes.azure.com/scalesetpriority=spot:NoSchedule, which the aks profile
# does not tolerate, so model pods would never schedule on spot nodes.

resource "azurerm_kubernetes_cluster" "polar_sky" {
  name                = var.cluster_name
  location            = azurerm_resource_group.polar_sky.location
  resource_group_name = azurerm_resource_group.polar_sky.name
  dns_prefix          = var.cluster_name
  kubernetes_version  = var.kubernetes_version

  automatic_upgrade_channel = "patch"

  default_node_pool {
    name                        = "system"
    vm_size                     = "Standard_D4s_v5"
    vnet_subnet_id              = azurerm_subnet.nodes.id
    auto_scaling_enabled        = true
    min_count                   = 3
    max_count                   = 6
    temporary_name_for_rotation = "systemtmp"

    upgrade_settings {
      max_surge = "10%"
    }
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_data_plane  = "cilium"
    network_policy      = "cilium"
    load_balancer_sku   = "standard"
    pod_cidr            = var.pods_cidr
    service_cidr        = var.services_cidr
    dns_service_ip      = cidrhost(var.services_cidr, 10)
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# GPU Node Pool - autoscaling, runs vLLM model servers
resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  name                  = "gpu"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.polar_sky.id
  vm_size               = "Standard_NC8as_T4_v3"
  vnet_subnet_id        = azurerm_subnet.nodes.id

  os_type    = "Linux"
  os_sku     = "AzureLinux"
  gpu_driver = "Install"

  auto_scaling_enabled = true
  min_count            = var.gpu_node_min_count
  max_count            = var.gpu_node_max_count

  node_labels = {
    "accelerator" = "nvidia"
  }

  node_taints = ["sku=gpu:NoSchedule"]

  upgrade_settings {
    max_surge = "10%"
  }

  tags = var.tags
}
