# Virtual Network for the AKS Cluster
#
# One node subnet for both node pools. Pods run on the Azure CNI overlay
# (pods_cidr), so they take no addresses from the virtual network. Nodes have
# no public IPs; outbound traffic leaves through the cluster's standard load
# balancer.

resource "azurerm_virtual_network" "polar_sky" {
  name                = "vnet-${var.cluster_name}"
  location            = azurerm_resource_group.polar_sky.location
  resource_group_name = azurerm_resource_group.polar_sky.name
  address_space       = [var.vnet_cidr]
  tags                = var.tags
}

resource "azurerm_subnet" "nodes" {
  name                 = "snet-${var.cluster_name}-nodes"
  resource_group_name  = azurerm_resource_group.polar_sky.name
  virtual_network_name = azurerm_virtual_network.polar_sky.name
  address_prefixes     = [var.nodes_cidr]

  lifecycle {
    # The Azure Files CSI driver adds a storage service endpoint to this subnet when it provisions the first NFS share.
    ignore_changes = [service_endpoints]
  }
}

# The Azure Files CSI driver uses the cluster identity to add that service
# endpoint, which needs Network Contributor on the virtual network.
resource "azurerm_role_assignment" "cluster_network_contributor" {
  scope                = azurerm_virtual_network.polar_sky.id
  role_definition_name = "Network Contributor"
  principal_id         = azurerm_kubernetes_cluster.polar_sky.identity[0].principal_id
}
