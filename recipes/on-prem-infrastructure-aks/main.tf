provider "azurerm" {
  subscription_id = var.subscription_id

  features {}
}

provider "kubernetes" {
  host                   = azurerm_kubernetes_cluster.polar_sky.kube_config[0].host
  client_certificate     = base64decode(azurerm_kubernetes_cluster.polar_sky.kube_config[0].client_certificate)
  client_key             = base64decode(azurerm_kubernetes_cluster.polar_sky.kube_config[0].client_key)
  cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.polar_sky.kube_config[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = azurerm_kubernetes_cluster.polar_sky.kube_config[0].host
    client_certificate     = base64decode(azurerm_kubernetes_cluster.polar_sky.kube_config[0].client_certificate)
    client_key             = base64decode(azurerm_kubernetes_cluster.polar_sky.kube_config[0].client_key)
    cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.polar_sky.kube_config[0].cluster_ca_certificate)
  }
}

resource "azurerm_resource_group" "polar_sky" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}
