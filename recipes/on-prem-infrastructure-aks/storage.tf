# StorageClass for Model Storage
#
# Provides ReadWriteMany (RWX) storage for vLLM model weights on Azure Files
# premium NFS shares, so the model replicas share one download. The aks profile
# requests this StorageClass by name.

resource "kubernetes_storage_class" "azurefile_retain" {
  metadata {
    name = "premium-azurefile-retain"
  }

  storage_provisioner    = "file.csi.azure.com"
  reclaim_policy         = "Retain"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true

  parameters = {
    skuName  = "Premium_LRS"
    protocol = "nfs"
  }

  mount_options = ["nconnect=4"]

  depends_on = [
    azurerm_role_assignment.cluster_network_contributor,
  ]
}
