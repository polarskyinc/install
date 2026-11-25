# EKS On-Prem Infrastructure

Terraform configuration for the Polar Sky on-prem EKS cluster. Provisions a VPC, EKS cluster, node groups, and all required add-ons for running AI model servers with GPU support.

## Architecture

### Node Pools

| Pool | Instance Types | Capacity | Scaling | Root Volume |
|------|---------------|----------|---------|-------------|
| **System** | m5.xlarge | ON_DEMAND | 3–6 nodes | 50 GiB gp3 |
| **GPU** | g4dn.4xlarge, g4dn.8xlarge, g4dn.12xlarge | SPOT (default) | 0–6 nodes | 100 GiB gp3 |

#### Spot vs On-Demand for GPU Nodes

The GPU node pool defaults to **SPOT** instances (`gpu_node_capacity_type = "SPOT"`), which is suitable for testing and development. Spot instances offer significant cost savings but can be reclaimed by AWS with 2 minutes notice, causing in-flight inference requests to fail.

**For production or stable deployments, switch to on-demand:**

```hcl
gpu_node_capacity_type = "ON_DEMAND"
```

Multiple g4dn instance types are configured to improve spot capacity availability. If spot fulfillment fails (`UnfulfillableCapacity`), the pool draws from whichever instance type has available capacity.

### Cluster Add-ons

#### EKS Managed Add-ons

- **vpc-cni** — Pod networking via AWS VPC CNI, with NetworkPolicy enforcement turned on
- **coredns** — Cluster DNS
- **kube-proxy** — Service networking
- **aws-efs-csi-driver** — EFS volume provisioning (IRSA-enabled)

#### Helm-deployed Add-ons

- **Cluster Autoscaler** — Scales node groups based on pending pod demand. Uses auto-discovery via `k8s.io/cluster-autoscaler` tags. IRSA-enabled with scoped IAM permissions.
- **NVIDIA Device Plugin** — DaemonSet that runs on GPU nodes (tolerates `nvidia.com/gpu:NoSchedule` taint). Registers `nvidia.com/gpu` as a schedulable Kubernetes resource. Without this, GPU nodes appear to have zero GPUs.

### NVIDIA GPU Support

GPU nodes require three things to schedule GPU workloads:

1. **GPU AMI** — `AL2023_x86_64_NVIDIA` includes NVIDIA drivers and the container toolkit
2. **NVIDIA Device Plugin** — Exposes `nvidia.com/gpu` to the Kubernetes scheduler
3. **Taint + Toleration** — GPU nodes are tainted with `nvidia.com/gpu=true:NoSchedule` so only GPU workloads land on them

### Storage

An EFS filesystem provides ReadWriteMany (RWX) storage for model weights, allowing multiple pods to mount the same volume concurrently. The `efs-polarsky-retain` StorageClass provisions EFS Access Points with IAM authentication.

**Clusters upgraded from a chart that served Phi-4-mini.** That chart made a 100 Gi claim named `<release>-phi-4-mini-storage-claim` (usually `polar-sky-phi-4-mini-storage-claim`) in the namespace the engine was installed in. The Helm upgrade deletes the claim, but the StorageClass has reclaim policy `Retain`, so the volume behind it stays in status `Released` and its EFS Access Point and the downloaded weights stay in the filesystem. To look for it:

```bash
kubectl get pv -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,NAMESPACE:.spec.claimRef.namespace,CLAIM:.spec.claimRef.name,SIZE:.spec.capacity.storage | grep phi-4-mini-storage-claim
```

Act only on a line whose NAMESPACE is the namespace the engine is installed in and whose STATUS is `Released`. A line with status `Bound` means the upgrade has not finished: wait. First write down the backing storage. `kubectl get pv <NAME> -o jsonpath='{.spec.csi.volumeHandle}'` prints `fs-...::fsap-...`, the filesystem and the Access Point, but not the directory. Record the directory too: `aws efs describe-access-points --access-point-id <fsap-...> --query 'AccessPoints[0].RootDirectory.Path' --output text`. Then delete the PersistentVolume with `kubectl delete pv <NAME>`, delete that Access Point in EFS, and last delete the recorded directory from the filesystem. Nothing else uses the volume.

## Usage

```bash
# Initialize
tofu init

# Plan with defaults (spot GPU, 0 min nodes)
tofu plan

# Apply
tofu apply

# Configure kubectl
$(tofu output -raw eks_update_kubeconfig_command)
```

### Variables

The supplied `variables.tf` is authoritative for recipe defaults. Review it and the saved OpenTofu plan rather than relying on a copied README table.

| Variable | Description | Default |
|----------|-------------|---------|
| `region` | AWS region | `us-east-1` |
| `cluster_name` | EKS cluster name | `eks-polar-sky` |
| `gpu_node_min_count` | Min GPU nodes | `0` |
| `gpu_node_max_count` | Max GPU nodes | `6` |
| `gpu_node_capacity_type` | `ON_DEMAND` or `SPOT` | `SPOT` |
| `vpc_cidr` | VPC CIDR block | `10.0.0.0/16` |
