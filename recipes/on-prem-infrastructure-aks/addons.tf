# =============================================================================
# NVIDIA Device Plugin (Helm)
# =============================================================================
#
# Registers nvidia.com/gpu as a schedulable resource on the GPU nodes. Its
# default affinity needs Node Feature Discovery labels this cluster does not
# have, so it is pinned to the GPU pool's label and tolerates the pool's taint.

resource "helm_release" "nvidia_device_plugin" {
  name       = "nvidia-device-plugin"
  namespace  = "kube-system"
  repository = "https://nvidia.github.io/k8s-device-plugin"
  chart      = "nvidia-device-plugin"
  version    = "0.17.1"

  set {
    name  = "tolerations[0].key"
    value = "sku"
  }

  set {
    name  = "tolerations[0].operator"
    value = "Equal"
  }

  set {
    name  = "tolerations[0].value"
    value = "gpu"
  }

  set {
    name  = "tolerations[0].effect"
    value = "NoSchedule"
  }

  set {
    name  = "affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms[0].matchExpressions[0].key"
    value = "accelerator"
  }

  set {
    name  = "affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms[0].matchExpressions[0].operator"
    value = "In"
  }

  set {
    name  = "affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution.nodeSelectorTerms[0].matchExpressions[0].values[0]"
    value = "nvidia"
  }

  depends_on = [
    azurerm_kubernetes_cluster_node_pool.gpu,
  ]
}
