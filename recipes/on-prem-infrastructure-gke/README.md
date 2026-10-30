# GKE On-Prem Infrastructure

Terraform configuration for the Polar Sky on-prem GKE cluster. Provisions a VPC, a zonal VPC-native GKE cluster, and node pools for running AI model servers with GPU support. Pairs with the `gke` infrastructure profile of the `polar-sky-onprem` Helm chart.

## Architecture

### Node Pools

| Pool | Machine Type | Capacity | Scaling | Boot Disk |
|------|-------------|----------|---------|-----------|
| **System** | e2-standard-4 | On-demand | 3–6 nodes | 50 GiB pd-balanced |
| **GPU** | g2-standard-8 (1x NVIDIA L4, 24 GiB VRAM) | Spot (default) | 0–6 nodes | 100 GiB pd-balanced |

#### Spot vs On-Demand for GPU Nodes

The GPU node pool defaults to **spot VMs** (`gpu_node_spot = true`), which is suitable for testing and development. Spot VMs offer significant cost savings but can be preempted by GCP with 30 seconds notice, causing in-flight inference requests to fail.

**For production or stable deployments, switch to on-demand:**

```hcl
gpu_node_spot = false
```

### GKE-Managed Components

No Helm-deployed add-ons are needed; GKE manages these natively:

- **Cluster autoscaler** — built into GKE node pool autoscaling (`min_node_count`/`max_node_count`)
- **NVIDIA drivers and device plugin** — installed automatically via `gpu_driver_installation_config` (`gpu-driver-version=default`); no GPU Operator required
- **GPU labels** — GKE labels GPU nodes with `cloud.google.com/gke-accelerator=nvidia-l4` automatically; the matching `nvidia.com/gpu=present:NoSchedule` taint is declared explicitly on the GPU pool because GKE's auto-taint only applies when a non-GPU pool already exists

### Networking

Custom-mode VPC with a single node subnet plus secondary ranges for pods and services (VPC-native cluster). Nodes are private (no public IPs); Cloud NAT provides outbound access for container image pulls and model downloads. The control plane endpoint stays public for kubectl access. The cluster runs GKE Dataplane V2 (`datapath_provider = "ADVANCED_DATAPATH"`), which enforces the Kubernetes NetworkPolicy resources the Helm chart installs by default; without it, Standard GKE accepts but silently ignores them.

### Model Storage

The `gke` Helm profile streams model weights directly from the Polar Sky public GCS mirror (`gs://polar-sky-public-models`) using vLLM's Run:ai model streamer, so no PersistentVolumeClaim is needed. This follows from two GKE realities: the managed RWX option (Filestore) has a 1 TiB per-volume minimum (~$160/month each), and the spot GPU nodes restart often enough that per-restart Hugging Face downloads would be slow and would meter Cloud NAT. Same-region GCS reads travel Private Google Access (enabled on the node subnet), incur no egress or NAT charges, and hydrate a model far faster than a public-internet download. A small node-local `emptyDir` serves as `HF_HOME` scratch for tokenizer and config staging.

The bucket is publicly readable, so consumers need no bucket permissions, billing project, or other access setup, and they do not need to run in any particular GCP project. Mirroring a model into the bucket is a Polar Sky release step, not a customer step; see `docs/runbooks/mirror-hf-model-to-gcs.md` when adding or changing a model.

## Cost Estimate

Approximate us-central1 list prices (August 2026); verify with the [GCP pricing calculator](https://cloud.google.com/products/calculator) before relying on them.

| Component | Hourly | Daily | Monthly |
|-----------|--------|-------|---------|
| System pool (3x e2-standard-4) | $0.40 | $9.70 | ~$295 |
| GPU pool (4x g2-standard-8 spot) | ~$1.20 | ~$29 | ~$875 |
| Boot disks (~550 GiB pd-balanced) | $0.08 | $1.80 | ~$55 |
| Cloud NAT gateway | $0.04 | $1.06 | ~$32 |
| GKE cluster management fee | $0.10 | $2.40 | ~$73 |
| **Total (spot GPUs, 24/7)** | **~$1.80** | **~$44** | **~$1,330** |

- **GPU pool sized for the chart's default fleet**: 3 phi-4-mini replicas + 1 bge-embedding replica = 4 nodes at 1 GPU each.
- **On-demand GPUs** (~$0.85/hr per g2-standard-8) roughly triple the GPU line: total ~$4.00/hr, ~$2,950/month.
- **GPU pool scaled to zero** (idle cluster): ~$0.57/hr, ~$14/day, ~$420/month.
- The GKE management fee is often $0 in practice: GCP's free tier credit covers one zonal cluster per billing account.
- Cloud NAT data processing ($0.045/GiB) adds a small variable amount for container image pulls; model weights travel Private Google Access and never touch the NAT.

## Usage

```bash
# Initialize
tofu init

# Plan with defaults (spot GPU, 0 min GPU nodes)
tofu plan -var project_id=<your-project>

# Apply
tofu apply -var project_id=<your-project>

# Configure kubectl
$(tofu output -raw gke_get_credentials_command)
```

### Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `project_id` | GCP project ID | (required) |
| `region` | GCP region | `us-central1` |
| `zone` | GCP zone (must offer G2 machine types) | `us-central1-a` |
| `cluster_name` | GKE cluster name (max 25 characters) | `gke-polar-sky` |
| `gpu_node_min_count` | Min GPU nodes | `0` |
| `gpu_node_max_count` | Max GPU nodes | `6` |
| `gpu_node_spot` | Use spot VMs for GPU nodes | `true` |
| `nodes_cidr` | Node subnet CIDR | `10.0.0.0/20` |
| `pods_cidr` | Pod secondary range CIDR | `10.4.0.0/14` |
| `services_cidr` | Service secondary range CIDR | `10.8.0.0/20` |
| `master_cidr` | Control plane peering CIDR (/28) | `172.16.0.0/28` |
