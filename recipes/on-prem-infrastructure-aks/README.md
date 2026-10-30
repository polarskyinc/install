# AKS On-Prem Infrastructure

Terraform configuration for the Polar Sky on-prem AKS cluster. Provisions a resource group, a virtual network, an AKS cluster, and node pools for running AI model servers with GPU support. Pairs with the `aks` infrastructure profile of the `polar-sky-onprem` Helm chart.

## Architecture

### Node Pools

| Pool | VM Size | Capacity | Scaling | OS |
|------|---------|----------|---------|----|
| **System** | Standard_D4s_v5 (4 vCPU, 16 GiB) | On-demand | 3–6 nodes | Ubuntu (AKS default) |
| **GPU** | Standard_NC8as_T4_v3 (8 vCPU, 56 GiB, 1x NVIDIA T4 16 GiB) | On-demand | 0–6 nodes | Azure Linux |

The GPU pool carries the `accelerator=nvidia` label and the `sku=gpu:NoSchedule` taint that the `aks` profile expects.

#### No Spot GPU Nodes

Unlike the GKE and EKS recipes, this recipe has no spot option. Azure taints spot node pools with `kubernetes.azure.com/scalesetpriority=spot:NoSchedule`, and the `aks` profile does not tolerate that taint, so model pods would never schedule on spot nodes.

### GPU Support

GPU nodes need three things to schedule GPU workloads:

1. **NVIDIA drivers**: AKS installs them on the GPU pool (`gpu_driver = "Install"`)
2. **NVIDIA device plugin**: deployed with Helm into `kube-system`; it tolerates the `sku=gpu` taint and runs only on nodes labeled `accelerator=nvidia`. Without it, GPU nodes appear to have zero GPUs
3. **Taint and toleration**: GPU nodes are tainted `sku=gpu:NoSchedule` so only GPU workloads land on them

### Networking

One virtual network with a single node subnet for both pools. Pods use Azure CNI overlay (`pods_cidr`), so they take no addresses from the virtual network. The cluster runs the Cilium data plane with Cilium network policy, which enforces the Kubernetes NetworkPolicy resources the Helm chart installs by default. Nodes have no public IPs; outbound traffic for image pulls and model downloads leaves through the cluster's standard load balancer. The API server endpoint is public for kubectl access.

The cluster keeps AKS local accounts, and OpenTofu reaches the cluster with them to install the device plugin and the StorageClass. The cluster is not Entra-integrated, so `kubelogin` is not needed.

### Storage

The `premium-azurefile-retain` StorageClass provisions Azure Files premium NFS shares with ReadWriteMany access, so all model replicas share one copy of the model weights. The Azure Files CSI driver creates the storage account in the cluster's node resource group and adds a storage service endpoint to the node subnet; the cluster identity is granted Network Contributor on the virtual network for that.

### Kubernetes Version

`kubernetes_version` is a required minor version, such as `1.35`, and comes from the onboarding approval. The cluster uses the `patch` upgrade channel, so AKS applies patch releases within that minor while AKS supports it. When AKS retires the minor, it upgrades the cluster to the next supported minor by itself, outside any maintenance window, so agree a new approved minor with Polar Sky and upgrade before that date. Check which versions a region offers with `az aks get-versions --location <location> --output table`, and when each minor retires in the AKS Kubernetes release calendar.

## Prerequisites

- **Permissions**: the person applying the recipe needs Owner, or Contributor and User Access Administrator, on the subscription. The recipe creates the resource group and assigns Network Contributor to the cluster identity; Contributor alone fails at that role assignment.
- **GPU quota**: AKS adds one extra node to each pool while it upgrades the pool, and that node needs quota too. Four GPU nodes plus that extra node need 40 vCPUs of the NCasT4_v3 family quota in the chosen region (56 at the six-node maximum), and the system pool needs 16 to 28 vCPUs of the Dsv5 family. New subscriptions often have no GPU quota. Check with `az vm list-usage --location <location> --output table` and request more under the subscription's Usage + quotas page.

## Usage

```bash
# Initialize
tofu init

# Plan
tofu plan -var subscription_id=<your-subscription> -var kubernetes_version=<approved-minor>

# Apply
tofu apply -var subscription_id=<your-subscription> -var kubernetes_version=<approved-minor>

# Configure kubectl
$(tofu output -raw aks_get_credentials_command)
```

### Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `subscription_id` | Azure subscription ID | (required) |
| `kubernetes_version` | Approved Kubernetes minor version | (required) |
| `location` | Azure region (must offer NCasT4_v3) | `eastus` |
| `resource_group_name` | Resource group the recipe creates | `rg-polar-sky` |
| `cluster_name` | AKS cluster name and DNS prefix | `aks-polar-sky` |
| `gpu_node_min_count` | Min GPU nodes | `0` |
| `gpu_node_max_count` | Max GPU nodes (at least 4) | `6` |
| `vnet_cidr` | Virtual network address space | `10.0.0.0/16` |
| `nodes_cidr` | Node subnet CIDR | `10.0.0.0/20` |
| `pods_cidr` | Pod overlay CIDR | `10.244.0.0/16` |
| `services_cidr` | Service CIDR | `172.16.0.0/16` |
