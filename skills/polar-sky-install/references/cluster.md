# Phase 3: Cluster and preflight checks

Use the platform (`POLAR_SKY_INFRA_PROFILE`) and the cluster type the person confirmed in phase 2. Use Polar Sky's recipe exactly as supplied: do not change node counts, GPU types, storage classes or other settings.

## New cluster from the recipe (GKE, EKS or AKS)

Ask the person for the path to the recipe folder they got from Polar Sky: `on-prem-infrastructure-gke` for `gke`, `on-prem-infrastructure-eks` for `eks`, `on-prem-infrastructure-aks` for `aks`. Ask which region (and for GKE, which zone) to use; the recipe's defaults are `us-central1` / `us-central1-a` (GKE), `us-east-1` (EKS) and `eastus` (AKS). Write the answers into `values.env` as `CLUSTER_REGION` and, for GKE, `CLUSTER_ZONE`.

### Plan

For GKE, ask which Google Cloud project the cluster goes in. It may be the service-account project from phase 2 or another one. Write it into `values.env` as `CLUSTER_PROJECT_ID`.

For GKE, before the plan, check that the project has billing (read only; the first command turns on the Cloud Billing API, which costs nothing). It must print `True`:

```bash
gcloud services enable cloudbilling.googleapis.com --project="${CLUSTER_PROJECT_ID}" && gcloud billing projects describe "${CLUSTER_PROJECT_ID}" --format='value(billingEnabled)'
```

If it prints `False`, stop: without billing Google refuses to turn on Compute Engine and Kubernetes Engine, and the apply fails part way. Tell the person a billing account must be linked to the project (Cloud Console, Billing), usually by a billing administrator. You may go on with phase 4 and phase 5 while they do it.

For AKS, ask three more things before you plan:

1. **Subscription.** Which Azure subscription the cluster goes in. You may propose the subscription `az` is signed in to, saying where it came from. Write its ID into `values.env` as `CLUSTER_SUBSCRIPTION_ID`. The person needs Owner, or Contributor and User Access Administrator, on it: the recipe creates a resource group and assigns a role to the cluster. With Contributor alone, `apply` fails at that role assignment.
2. **Kubernetes version.** The Kubernetes minor version Polar Sky approved for this install, such as `1.35`. Ask the person for it; do not pick one. Check that the region offers it (read only), then write it into `values.env` as `CLUSTER_KUBERNETES_VERSION`:

   ```bash
   az aks get-versions --location "${CLUSTER_REGION}" --subscription "${CLUSTER_SUBSCRIPTION_ID}" --output table
   ```

3. **GPU quota.** Check the region's quota (read only):

   ```bash
   az vm list-usage --location "${CLUSTER_REGION}" --subscription "${CLUSTER_SUBSCRIPTION_ID}" --output table
   ```

   AKS adds one extra node to each pool while it upgrades the pool, so the recipe needs 40 free vCPUs in the NCasT4_v3 family for four GPU nodes and that extra node (56 for the pool's maximum of six), 16 to 28 in the Dsv5 family for the system pool, and the total in the regional vCPU limit. If the NCasT4_v3 limit is too low, stop: the person requests more on the subscription's Usage + quotas page in the Azure portal, and you plan once it is granted.

Then run `scripts/check-values.sh` again as in phase 1.

GKE:

```bash
cd <recipe folder> && $IAC init && $IAC plan -var="project_id=${CLUSTER_PROJECT_ID}" -var="region=${CLUSTER_REGION}" -var="zone=${CLUSTER_ZONE}" -var='gpu_node_spot=false' -out=polar-sky.plan
```

For EKS, check how the AWS CLI is signed in (read only). It prints a value when the person signed in with `aws login`:

```bash
aws configure get login_session --profile "${AWS_PROFILE:-default}"
```

If it prints a value, OpenTofu and Terraform cannot use that sign-in, and the 15-minute credentials it hands out run out during the apply. Write `aws-config` in the install folder with your file tool, with the person's profile name in place of `<profile>` and the home folder written out in full:

```ini
[profile polar-sky-install]
credential_process = env AWS_CONFIG_FILE=<home folder>/.aws/config aws configure export-credentials --profile <profile> --format process
region = <CLUSTER_REGION>
```

Then add `export AWS_CONFIG_FILE='<home folder>/polar-sky-install/aws-config'` and `export AWS_PROFILE='polar-sky-install'` to `values.env`. Every later `aws`, OpenTofu, Terraform and `kubectl` command gets fresh credentials from the person's `aws login` through it, so load `values.env` first in each of them. Check it works:

```bash
. ~/polar-sky-install/values.env && aws sts get-caller-identity --query Arn --output text
```

EKS:

```bash
cd <recipe folder> && $IAC init && $IAC plan -var="region=${CLUSTER_REGION}" -var='gpu_node_capacity_type=ON_DEMAND' -out=polar-sky.plan
```

AKS:

```bash
cd <recipe folder> && $IAC init && $IAC plan -var="subscription_id=${CLUSTER_SUBSCRIPTION_ID}" -var="location=${CLUSTER_REGION}" -var="kubernetes_version=${CLUSTER_KUBERNETES_VERSION}" -out=polar-sky.plan
```

`init` downloads providers and may set up state; it creates no cloud resource. Show the person the plan's summary line (`Plan: N to add, 0 to change, 0 to destroy`) and the main resources. If the plan changes or destroys anything that already exists, stop and ask the person why before going on. The GKE recipe follows GKE's `REGULAR` channel: show the planned Kubernetes version. Polar Sky needs Kubernetes 1.33 or newer. The AKS recipe stays on the minor version you planned and takes only its patch releases while AKS supports that minor. Tell the person that when AKS retires the minor, AKS upgrades the cluster to the next minor by itself, so they agree a new minor with Polar Sky before that date.

### Apply

Only after the person says yes to this plan:

```bash
cd <recipe folder> && $IAC apply polar-sky.plan
```

It takes 15 to 30 minutes. If your agent stops commands after a time limit, run it in the background, or ask the person to run it in their own terminal and tell you when it ends. If it fails, show the error and stop. Do not run `apply` again without a new plan and a new yes.

### Point kubectl at the new cluster

```bash
cd <recipe folder> && $IAC output -raw gke_get_credentials_command
```

For EKS use `eks_update_kubeconfig_command`, and for AKS `aks_get_credentials_command`. The output is a `gcloud`, `aws` or `az` command. Show it, say it adds the cluster to the kubeconfig and makes it the current context, and run it after a yes.

### GPU pool at zero

The recipes start the GPU pool at zero nodes. GPU nodes appear only when the model pods ask for them in phase 6. So preflight may find no GPU nodes. Then check the pool itself (read only):

GKE:

```bash
gcloud container node-pools describe gpu --cluster gke-polar-sky --location "${CLUSTER_ZONE}" --project "${CLUSTER_PROJECT_ID}" --format='yaml(config.machineType,config.accelerators,config.taints,autoscaling)'
```

EKS:

```bash
aws eks describe-nodegroup --cluster-name eks-polar-sky --nodegroup-name gpu --region "${CLUSTER_REGION}" --query 'nodegroup.{instanceTypes:instanceTypes,scaling:scalingConfig,labels:labels,taints:taints}' --output yaml
```

AKS:

```bash
az aks nodepool show --subscription "${CLUSTER_SUBSCRIPTION_ID}" --resource-group rg-polar-sky --cluster-name aks-polar-sky --name gpu --query '{vmSize:vmSize,minCount:minCount,maxCount:maxCount,labels:nodeLabels,taints:nodeTaints}' --output yaml
```

The pool must have the profile's GPU type, label and taint (table below), and a maximum of at least 4 nodes.

## Existing cluster (AKS, EKS or GKE)

Polar Sky approves an existing cluster before the install. Show and run (read only):

```bash
kubectl config current-context && kubectl get nodes && kubectl get storageclass
```

Ask the person to confirm the context is the approved cluster. For Entra-integrated AKS, `kubelogin` must be installed. Preflight warns when the cluster already runs Flux outside the Polar Sky namespace, or Argo CD. Then tell the person to agree the install path with Polar Sky before phase 6: Argo CD must not take over Flux resources, and an existing Flux needs a review.

## What the profile needs

| Profile | GPU nodes: label | GPU nodes: taint | StorageClass |
| --- | --- | --- | --- |
| `gke` | `cloud.google.com/gke-accelerator=nvidia-l4` | `nvidia.com/gpu`, `NoSchedule` | None needed |
| `eks` | `workload-type=gpu` and `gpu-type=t4` | `nvidia.com/gpu`, `NoSchedule` | `efs-polarsky-retain` (ReadWriteMany) |
| `aks` | `accelerator=nvidia` | `sku=gpu`, `NoSchedule` | `premium-azurefile-retain` (ReadWriteMany) |

The standard model fleet needs four schedulable NVIDIA GPUs. All Polar Sky nodes must be Linux `amd64`.

## Preflight checks

The script checks the cluster against guide section 2 and reports every problem at once, each with its fix. It checks:

- the context and the Kubernetes version (1.33 or newer)
- every node is Linux `amd64`
- GPU nodes: label, taint and allocatable GPUs (the NVIDIA device plugin), or a note that the pool is at zero
- the profile's StorageClass
- that the person can install Flux (custom resource definitions, cluster roles and their bindings) and manage resources in the namespace, with `kubectl auth can-i`
- whether another Flux, or Argo CD, already runs in the cluster (a warning, not a failure)
- that the cluster enforces NetworkPolicy: two test pods in a new temporary namespace `polar-sky-preflight-<time>`, first allowed to talk, then blocked by a policy
- outbound DNS and HTTPS from a short-lived pod in the Polar Sky namespace to each required host; for the Polar Sky host it trusts the Polar Sky CA in [scripts/polar-sky-ca.crt](../scripts/polar-sky-ca.crt), because that host's certificate is not from a public CA

It changes the cluster in two ways, so ask before running it:

1. It creates a new namespace `polar-sky-preflight-<time>` with three short-lived `busybox` pods and one NetworkPolicy, and deletes only that namespace at the end.
2. It runs one `curlimages/curl` pod in the Polar Sky namespace and deletes it at the end. The Polar Sky namespace must exist first.

Create the Polar Sky namespace if it is missing, after a dry run and a yes:

```bash
kubectl create namespace "${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
kubectl get namespace "${POLAR_SKY_NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${POLAR_SKY_NAMESPACE}"
```

Then run the checks:

```bash
. ~/polar-sky-install/values.env && <skill folder>/scripts/preflight.sh
```

It ends with `PREFLIGHT PASSED` or `PREFLIGHT FAILED` and a list of every failure and its fix. Show the whole list to the person in one message. Lines marked `WARN` need the person's attention but do not block.

If a check fails, the person fixes the cluster or the network, and you run the script again. Do not go to phase 4 until it passes. A blocked host is usually opened by the network team: give them the host list from the script output, and say pulls may follow HTTPS redirects to download hosts, so a proxy or allowlist must allow the whole chain.

On a new recipe cluster the GPU checks may only say the pool is at zero. Then run the GPU pool check above. Real GPU placement is checked in phase 6.
