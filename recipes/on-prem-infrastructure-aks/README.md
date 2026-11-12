# AKS On-Prem Infrastructure

Terraform configuration for the Polar Sky on-prem AKS cluster. Provisions a resource group, a virtual network, an AKS cluster, and node pools for running AI model servers with GPU support. Pairs with the `aks` infrastructure profile of the `polar-sky-onprem` Helm chart.

## Architecture

### Node Pools

| Pool | VM Size | Capacity | Scaling | OS |
|------|---------|----------|---------|----|
| **System** | `system_node_vm_size`, Standard_D4s_v5 by default (4 vCPU, 16 GiB) | On-demand | 3–6 nodes | Ubuntu (AKS default) |
| **GPU** | Standard_NC8as_T4_v3 (8 vCPU, 56 GiB, 1x NVIDIA T4 16 GiB) | On-demand | 0–6 nodes | Azure Linux |

The GPU pool carries the `sku=gpu:NoSchedule` taint that the `aks` profile expects. AKS puts the `accelerator=nvidia` label on NVIDIA GPU nodes itself, and refuses it on a node pool, so the pool must not set it.

#### System Pool Size

The system pool uses `Standard_D4s_v5` unless `system_node_vm_size` names another size. The variable takes only these sizes, in Polar Sky's order of preference: `Standard_D4s_v5`, `Standard_D4ds_v5`, `Standard_D4as_v5`, `Standard_D4ads_v5`, `Standard_D4s_v4`, `Standard_D4ds_v4`, `Standard_D4as_v4`, `Standard_DC4ads_v5`. All are x86 sizes with 4 vCPUs and 16 GiB; `Standard_DC4ads_v5` is a confidential-computing size.

Azure can block a size for a subscription in a region even when the subscription has quota for its family, and the quota page does not show that block. List the sizes with their restrictions; `--all` is needed, because without it Azure leaves a blocked size out:

```bash
az vm list-skus --location <location> --subscription <your-subscription> --all --resource-type virtualMachines --query "[?contains(['Standard_D4s_v5','Standard_D4ds_v5','Standard_D4as_v5','Standard_D4ads_v5','Standard_D4s_v4','Standard_D4ds_v4','Standard_D4as_v4','Standard_DC4ads_v5','Standard_NC8as_T4_v3'], name)].{name:name,family:family,locationRestrictions:restrictions[?type=='Location'].reasonCode}" --output json
```

Use the first system size in the order above that the output lists with no `Location` restriction. A `Zone` restriction alone does not matter, because the pools use no zones. `Standard_NC8as_T4_v3` must be listed with no `Location` restriction too. If no listed system size is allowed, ask Azure support to allow one in the region for the subscription, or choose another region.

#### No Spot GPU Nodes

Unlike the GKE and EKS recipes, this recipe has no spot option. Azure taints spot node pools with `kubernetes.azure.com/scalesetpriority=spot:NoSchedule`, and the `aks` profile does not tolerate that taint, so model pods would never schedule on spot nodes.

### GPU Support

GPU nodes need three things to schedule GPU workloads:

1. **NVIDIA drivers**: AKS installs them on the GPU pool (`gpu_driver = "Install"`)
2. **NVIDIA device plugin**: deployed with Helm into `kube-system`; it tolerates the `sku=gpu` taint and runs only on nodes labeled `accelerator=nvidia`, the label AKS sets on NVIDIA GPU nodes. Without it, GPU nodes appear to have zero GPUs
3. **Taint and toleration**: GPU nodes are tainted `sku=gpu:NoSchedule` so only GPU workloads land on them

### Networking

One virtual network with a single node subnet for both pools. Pods use Azure CNI overlay (`pods_cidr`), so they take no addresses from the virtual network. The cluster runs the Cilium data plane with Cilium network policy, which enforces the Kubernetes NetworkPolicy resources the Helm chart installs by default. Nodes have no public IPs; outbound traffic for image pulls and model downloads leaves through the cluster's standard load balancer. The API server endpoint is public for kubectl access.

The cluster keeps AKS local accounts, and OpenTofu reaches the cluster with them to install the device plugin and the StorageClass. The cluster is not Entra-integrated, so `kubelogin` is not needed.

### Storage

The `premium-azurefile-retain` StorageClass provisions Azure Files premium NFS shares with ReadWriteMany access, so all model replicas share one copy of the model weights. The Azure Files CSI driver creates the storage account in the cluster's node resource group and adds a storage service endpoint to the node subnet; the cluster identity is granted Network Contributor on the virtual network for that.

### Kubernetes Version

`kubernetes_version` is the required Kubernetes minor version the cluster runs, such as `1.35`. Use the newest minor that AKS offers in the region and that is not a preview; Polar Sky needs 1.33 or newer. The cluster uses the `patch` upgrade channel, so AKS applies patch releases within that minor while AKS supports it. When AKS retires the minor, it upgrades the cluster to the next supported minor by itself, outside any maintenance window. The AKS Kubernetes release calendar shows when each minor retires.

List the minors a region offers, with their preview flag:

```bash
az aks get-versions --location <location> --subscription <your-subscription> --query 'values[].{minor:version,preview:isPreview || `false`}' --output table
```

## Prerequisites

- **Permissions**: the person applying the recipe needs Owner, or Contributor and User Access Administrator, on the subscription. The recipe creates the resource group and assigns Network Contributor to the cluster identity; Contributor alone fails at that role assignment.
- **GPU quota**: AKS adds one extra node to each pool while it upgrades the pool, and that node needs quota too. Four GPU nodes plus that extra node need 40 vCPUs of the NCasT4_v3 family quota in the chosen region (56 at the six-node maximum), and the system pool needs 16 to 28 vCPUs of its size's family. New subscriptions often have no GPU quota. The `family` that `az vm list-skus` prints for a size (see [System Pool Size](#system-pool-size)) is the `name.value` of its quota line. Check with `az vm list-usage --location <location> --query "[].{family:name.value,used:currentValue,limit:limit}" --output table` and request more under the subscription's Usage + quotas page.
- **Machine sizes**: quota does not mean the subscription may use a size in the region. Check the sizes as [System Pool Size](#system-pool-size) shows before you plan.

## Usage

```bash
# Initialize
tofu init

# Plan
tofu plan -var subscription_id=<your-subscription> -var kubernetes_version=<kubernetes-minor>

# Apply
tofu apply -var subscription_id=<your-subscription> -var kubernetes_version=<kubernetes-minor>

# Configure kubectl
$(tofu output -raw aks_get_credentials_command)
```

When the size check picks a system size other than `Standard_D4s_v5`, add `-var system_node_vm_size=<size>` to both `plan` and `apply`.

### Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `subscription_id` | Azure subscription ID | (required) |
| `kubernetes_version` | Kubernetes minor version the cluster runs | (required) |
| `location` | Azure region (must offer NCasT4_v3) | `eastus` |
| `resource_group_name` | Resource group the recipe creates | `rg-polar-sky` |
| `cluster_name` | AKS cluster name and DNS prefix | `aks-polar-sky` |
| `system_node_vm_size` | System pool size, one of the sizes in [System Pool Size](#system-pool-size) | `Standard_D4s_v5` |
| `gpu_node_min_count` | Min GPU nodes | `0` |
| `gpu_node_max_count` | Max GPU nodes (at least 4) | `6` |
| `vnet_cidr` | Virtual network address space | `10.0.0.0/16` |
| `nodes_cidr` | Node subnet CIDR | `10.0.0.0/20` |
| `pods_cidr` | Pod overlay CIDR | `10.244.0.0/16` |
| `services_cidr` | Service CIDR | `172.16.0.0/16` |
