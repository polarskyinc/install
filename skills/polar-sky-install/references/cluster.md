# Phase 3: Cluster and preflight checks

**Tell the person:** Polar Sky's engine runs in a Kubernetes cluster in the person's own cloud, with GPU nodes for the AI models that read their files. A new cluster takes 15 to 30 minutes.

Use the platform (`POLAR_SKY_INFRA_PROFILE`) and the cluster type the person confirmed in phase 2. Use Polar Sky's recipe exactly as supplied: do not change node counts, GPU types, storage classes or other settings.

## New cluster from the recipe (GKE, EKS or AKS)

The recipe is Polar Sky's OpenTofu/Terraform code for the cluster, published in `recipes/` of `github.com/polarskyinc/install`: `on-prem-infrastructure-gke` for GKE, `on-prem-infrastructure-eks` for EKS, `on-prem-infrastructure-aks` for AKS. The folder name ends in the platform's setting value. The recipe folder is `~/polar-sky-install/on-prem-infrastructure-${POLAR_SKY_INFRA_PROFILE}`. Show and run (it only downloads files; it creates no cloud resource):

```bash
. ~/polar-sky-install/values.env && cd ~/polar-sky-install && if [ -e "on-prem-infrastructure-${POLAR_SKY_INFRA_PROFILE}" ]; then echo "recipe folder already here"; else curl -fsSL https://github.com/polarskyinc/install/archive/refs/heads/main.tar.gz | tar -xz --strip-components=2 "install-main/recipes/on-prem-infrastructure-${POLAR_SKY_INFRA_PROFILE}"; fi && ls "on-prem-infrastructure-${POLAR_SKY_INFRA_PROFILE}"
```

If the folder was already there, it may hold the Terraform state of an earlier run: use it as it is and never download over it. If the person got a recipe folder from Polar Sky and wants to use that one, use their folder instead.

Use the region, and for GKE the zone, from the install plan; if the plan did not settle them, ask. The recipe's defaults are `us-central1` / `us-central1-a` (GKE), `us-east-1` (EKS) and `eastus` (AKS). Write the answers into `values.env` as `CLUSTER_REGION` and, for GKE, `CLUSTER_ZONE`. On GKE the zone holds the control plane and the system pool. The GPU pool spans every zone in the region that offers L4, so the zone does not decide where the models run.

### Plan

For GKE, use the cluster's Google Cloud project from the install plan. It may be the service-account project or another one. Write it into `values.env` as `CLUSTER_PROJECT_ID`.

If the install plan has a new project for the cluster, create it first, as [Google identities](google-identities.md#create-a-new-project) says. For GKE, before the plan, check that the project has billing. The first command turns on the Cloud Billing API, which costs nothing; name it in the install plan, so the plan's yes covers it. If phase 2 found the API already on, leave that part out. It must print `True`:

```bash
gcloud services enable cloudbilling.googleapis.com --project="${CLUSTER_PROJECT_ID}" && gcloud billing projects describe "${CLUSTER_PROJECT_ID}" --format='value(billingEnabled)'
```

If it prints `False`, stop: without billing Google refuses to turn on Compute Engine and Kubernetes Engine, and the apply fails part way. Tell the person a billing account must be linked to the project (Cloud Console, Billing), usually by a billing administrator. Nothing else waits on billing, so recommend going on with the Google service accounts and the certificate while they do it.

For GKE, list the zones in the region that offer NVIDIA L4 GPUs. The recipe puts the GPU pool in all of them. The first command turns on the Compute Engine API, which costs nothing; name it in the install plan too, and leave it out if phase 2 found the API already on:

```bash
. ~/polar-sky-install/values.env && gcloud services enable compute.googleapis.com --project="${CLUSTER_PROJECT_ID}" && gcloud compute accelerator-types list --project="${CLUSTER_PROJECT_ID}" --format='value(name,zone.basename())' | awk -v region="${CLUSTER_REGION}-" '$1 == "nvidia-l4" && index($2, region) == 1 {print $2}'
```

Write the listed zones into `values.env` as one list, for example `export CLUSTER_GPU_ZONES='["us-central1-a","us-central1-b","us-central1-c"]'`. If the list is empty, propose another region. `CLUSTER_ZONE` does not have to offer L4, but recommend a zone from the list anyway.

Tell the person this shows which zones offer L4, not which have one free right now. The cluster places each GPU node in whichever listed zone has capacity, so one zone running out does not stop the models. If no listed zone has capacity in phase 6, see [When GPU nodes cannot start](#when-gpu-nodes-cannot-start).

For GKE, check that OpenTofu and Terraform can sign in to Google. They use application default credentials, not the gcloud account, and a plan on a new cluster can pass without them, so only the apply would fail. This only reads, and prints no token, because the token goes to `/dev/null`:

```bash
gcloud auth application-default print-access-token >/dev/null && echo ADC OK
```

If it does not print `ADC OK`, tell the person to run `gcloud auth application-default login` in their own terminal, and to choose the Google account that may create the cluster in `CLUSTER_PROJECT_ID`. It opens a browser. Run the check again when they are done.

For AKS, check five more things before you plan. Use the subscription from the install plan, and ask only if the plan did not settle it:

1. **Subscription.** Which Azure subscription the cluster goes in. Propose the subscription `az` is signed in to, saying where it came from. Write its ID into `values.env` as `CLUSTER_SUBSCRIPTION_ID`. The person needs Owner, or Contributor and User Access Administrator, on it: the recipe creates a resource group and assigns a role to the cluster. With Contributor alone, `apply` fails at that role assignment.
2. **Resource providers.** A subscription must register an Azure service's resource provider before it can use that service, and a new subscription may have none of the four the cluster needs. Without them, the version list, the machine size check and the quota check below fail. Check them (read only):

   ```bash
   . ~/polar-sky-install/values.env && for namespace in Microsoft.ContainerService Microsoft.Compute Microsoft.Network Microsoft.Storage; do echo "${namespace} $(az provider show --namespace "${namespace}" --subscription "${CLUSTER_SUBSCRIPTION_ID}" --query registrationState --output tsv)"; done
   ```

   If all four say `Registered`, go on. Otherwise show the person the command below for each provider that says `NotRegistered` or `Unregistered`; one that says `Registering` needs none. Say that registering is free and changes only this subscription, and ask for a yes. In the same message, say that OpenTofu's or Terraform's Azure provider also registers Azure's standard set of resource providers by itself on its first plan, which is free too. After the yes, run them:

   ```bash
   . ~/polar-sky-install/values.env && az provider register --namespace <namespace> --subscription "${CLUSTER_SUBSCRIPTION_ID}"
   ```

   Registering usually takes a few minutes. Tell the person so in one line. Then run the check again every minute or so, and go on only when all four say `Registered`. Do not wait a set time and assume it worked.

3. **Kubernetes version.** Do not ask the person for it: pick it yourself. List the minor versions AKS offers in the region, with their preview flag (read only):

   ```bash
   az aks get-versions --location "${CLUSTER_REGION}" --subscription "${CLUSTER_SUBSCRIPTION_ID}" --query 'values[].{minor:version,preview:isPreview || `false`}' --output table
   ```

   Pick the newest minor whose `Preview` is `False` and that is 1.33 or newer. Write it into `values.env` as `CLUSTER_KUBERNETES_VERSION`, the minor only, such as `1.37`, and show it in the plan. If the command fails or lists no such minor, show the person what it printed and do not guess a version: you pick it once the region's list can be read. If it fails because a resource provider is not registered, go back to step 2.

4. **Machine sizes.** Do not ask the person for them: check them yourself. A subscription can have quota for a machine size and still not be allowed to use it in a region. Azure's Usage + quotas page does not show that block, and the apply fails on it. The recipe's system pool takes one of these sizes, in this order: `Standard_D4s_v5`, `Standard_D4ds_v5`, `Standard_D4as_v5`, `Standard_D4ads_v5`, `Standard_D4s_v4`, `Standard_D4ds_v4`, `Standard_D4as_v4`, `Standard_DC4ads_v5`. The GPU pool always uses `Standard_NC8as_T4_v3`. List them all with their restrictions (read only). It takes a minute or two: tell the person so in one line.

   ```bash
   . ~/polar-sky-install/values.env && az vm list-skus --location "${CLUSTER_REGION}" --subscription "${CLUSTER_SUBSCRIPTION_ID}" --all --resource-type virtualMachines --query "[?contains(['Standard_D4s_v5','Standard_D4ds_v5','Standard_D4as_v5','Standard_D4ads_v5','Standard_D4s_v4','Standard_D4ds_v4','Standard_D4as_v4','Standard_DC4ads_v5','Standard_NC8as_T4_v3'], name)].{name:name,family:family,locationRestrictions:restrictions[?type=='Location'].reasonCode}" --output json
   ```

   Keep `--all`: without it, Azure leaves a blocked size out instead of showing its restriction. Pick the first system size in the order above whose `locationRestrictions` is empty. A `Zone` restriction alone does not block, because the recipe's pools use no zones, so the command leaves it out. A size missing from the output is not offered in the region: skip it like a blocked one. Write the size you picked into `values.env`, for example `export CLUSTER_SYSTEM_VM_SIZE='Standard_D4s_v5'`. Keep the `family` of that size and of `Standard_NC8as_T4_v3` for the quota check.

   If no system size in the list is allowed, or `Standard_NC8as_T4_v3` has a `Location` restriction, stop. Tell the person the two ways out: they ask Azure support to allow the size in this region for the subscription, which can go in the same support case as a GPU quota request, or they choose another region where both are allowed. If `Standard_NC8as_T4_v3` is missing from the output, the region does not offer it: propose another region. Do not pick a size outside the list yourself: that is Polar Sky's decision, so report it with `report_issue`. If the command fails because a resource provider is not registered, go back to step 2.

5. **Quota.** Quota and the size check in step 4 are separate: a size can be blocked while its family has quota, and an allowed size can have no quota. Check the quota of the two families from step 4 and the region's total (read only). Put the `family` of the system size you picked and the `family` of `Standard_NC8as_T4_v3` in place of the placeholders:

   ```bash
   . ~/polar-sky-install/values.env && az vm list-usage --location "${CLUSTER_REGION}" --subscription "${CLUSTER_SUBSCRIPTION_ID}" --query "[?contains(['<system family>','<GPU family>','cores'], name.value)].{family:name.value,used:currentValue,limit:limit}" --output table
   ```

   Each `family` from step 4 is the `name.value` of its quota line, and `cores` is the regional vCPU limit. The engine needs one GPU node for each copy of the inference model and one for the embedding model, 8 vCPUs each, and AKS adds one extra node to each pool while it upgrades the pool. So with its 3 copies the recipe needs 40 free vCPUs in the GPU family for four GPU nodes and that extra node (56 for the pool's maximum of six). Only when `values.env` already has `POLAR_SKY_INFERENCE_MODEL_REPLICAS`, because the person asked for fewer copies ([Fewer copies of the inference model](#fewer-copies-of-the-inference-model)), it needs 32 with 2 copies and 24 with 1 copy. It also needs 16 to 28 in the system size's family for the system pool, and the total in the regional vCPU limit. If one of these limits is too low, stop: the person requests more on the subscription's Usage + quotas page in the Azure portal, and you plan once it is granted.

Check that nothing the recipe creates already exists (read only). A plan on a new cluster cannot see a clash, so the apply would fail part way. On GKE the recipe creates the cluster `gke-polar-sky`, the network `vpc-gke-polar-sky` and the service account `gke-polar-sky-node`. Run the three lists one by one. If one fails because its API is not enabled, it cannot tell you what exists: turn that API on, then list again. It costs nothing, the recipe turns it on during the apply anyway, and the install plan names it with the other free APIs:

```bash
. ~/polar-sky-install/values.env && gcloud container clusters list --project="${CLUSTER_PROJECT_ID}" --format="value(name)"
```

```bash
. ~/polar-sky-install/values.env && gcloud compute networks list --project="${CLUSTER_PROJECT_ID}" --format="value(name)"
```

```bash
. ~/polar-sky-install/values.env && gcloud iam service-accounts list --project="${CLUSTER_PROJECT_ID}" --format="value(email)"
```

On EKS the recipe creates the cluster `eks-polar-sky` (`ResourceNotFoundException` means the name is free):

```bash
. ~/polar-sky-install/values.env && aws eks describe-cluster --name eks-polar-sky --region "${CLUSTER_REGION}" --query cluster.status --output text
```

It also creates IAM roles and a policy whose names start with `eks-polar-sky-`. IAM names hold across the whole AWS account, so an install in another region clashes too. Both lists must be empty:

```bash
. ~/polar-sky-install/values.env && aws iam list-roles --query "Roles[?starts_with(RoleName, 'eks-polar-sky-')].RoleName" --output text
```

```bash
. ~/polar-sky-install/values.env && aws iam list-policies --scope Local --query "Policies[?starts_with(PolicyName, 'eks-polar-sky-')].PolicyName" --output text
```

On AKS it creates the resource group `rg-polar-sky` (`false` means the name is free):

```bash
. ~/polar-sky-install/values.env && az group exists --name rg-polar-sky --subscription "${CLUSTER_SUBSCRIPTION_ID}"
```

If one of these names exists, first check whether this recipe folder's state already holds it (read only: `cd <recipe folder> && $IAC state list`), as after a failed apply. Then it is this install's own resource, and the new plan takes it into account. Otherwise tell the person and ask what it is. It may be an earlier Polar Sky install, whose state would be in its own recipe folder. Do not plan over a resource this folder's state does not hold.

For AKS, OpenTofu and Terraform use the Azure CLI's sign-in. Check that it still works for the subscription. This only reads, and prints no token:

```bash
. ~/polar-sky-install/values.env && az account get-access-token --subscription "${CLUSTER_SUBSCRIPTION_ID}" >/dev/null 2>&1 && echo "Azure sign-in OK"
```

If it does not print `Azure sign-in OK`, the person runs `az login` in their own terminal, and you check again.

Then run `scripts/check-values.sh` again as in phase 1. On GKE, `CLUSTER_GPU_ZONES` must be in `values.env`. A recipe folder from an earlier download, or one Polar Sky sent, may predate the GPU zone list. Check it (read only; it prints nothing for an older recipe):

```bash
grep -l 'variable "gpu_zones"' <recipe folder>/variables.tf
```

If it prints nothing, leave `-var="gpu_zones=${CLUSTER_GPU_ZONES}"` out of the GKE plan. That recipe keeps the GPU pool in `CLUSTER_ZONE` only, so that zone must offer L4, and one zone running out of GPUs stops the models.

On AKS, `CLUSTER_SYSTEM_VM_SIZE` must be in `values.env`. Check the same way that the recipe folder takes it (read only; it prints nothing for an older recipe):

```bash
grep -l 'variable "system_node_vm_size"' <recipe folder>/variables.tf
```

If it prints nothing, do not plan with that folder and do not edit it: it has no size choice, and its GPU pool sets a label AKS refuses, so the apply fails. If `$IAC state list` in it says there is no state file, or lists no resource, nothing was built with it: tell the person, and after their yes, rename it to `on-prem-infrastructure-aks-old` and download the recipe again as above. Otherwise stop and report it with `report_issue`.

GKE:

```bash
cd <recipe folder> && $IAC init && $IAC plan -var="project_id=${CLUSTER_PROJECT_ID}" -var="region=${CLUSTER_REGION}" -var="zone=${CLUSTER_ZONE}" -var="gpu_zones=${CLUSTER_GPU_ZONES}" -var='gpu_node_spot=false' -out=polar-sky.plan
```

For EKS, OpenTofu and Terraform use the AWS CLI's sign-in, which the detection script checked, except a sign-in made with `aws login`. Check how the AWS CLI is signed in (read only). It prints a value when the person signed in with `aws login`:

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
cd <recipe folder> && $IAC init && $IAC plan -var="subscription_id=${CLUSTER_SUBSCRIPTION_ID}" -var="location=${CLUSTER_REGION}" -var="kubernetes_version=${CLUSTER_KUBERNETES_VERSION}" -var="system_node_vm_size=${CLUSTER_SYSTEM_VM_SIZE}" -out=polar-sky.plan
```

`init` downloads providers and may set up state; it creates no cloud resource. Show the person the plan's summary line (`Plan: N to add, 0 to change, 0 to destroy`) and the main resources. If the plan changes or destroys anything that already exists, stop and ask the person why before going on. The GKE recipe follows GKE's `REGULAR` channel: show the planned Kubernetes version. Polar Sky needs Kubernetes 1.33 or newer. The AKS recipe uses the minor version you picked: show it. It stays on that minor and takes only its patch releases while AKS supports it. Tell the person that when AKS retires the minor, AKS moves the cluster to the next minor by itself. Also show the system pool's machine size you picked. If it is not `Standard_D4s_v5`, the recipe's default, say why: the default is not available to the subscription in this region. If it is `Standard_DC4ads_v5`, also say that it is a confidential-computing size.

### Apply

The plan is this stage's yes. When you show it, say that after the apply you will point kubectl at the new cluster, create the Polar Sky namespace and run the preflight checks below (their short-lived test pods), with no new yes. Ask: "Does this plan look right? Any changes, or shall I go ahead?" Then:

```bash
cd <recipe folder> && $IAC apply polar-sky.plan
```

It takes 15 to 30 minutes. Before you start it, tell the person this, and that they can do other work meanwhile. Run it in the background if your agent can; if your agent stops commands after a time limit and cannot, ask the person to run it in their own terminal and tell you when it ends. While it runs, check its output every few minutes and tell the person in one line what is being created. Recommend using the time for the Google service accounts and the certificate (phases 4 and 5), which do not need the cluster. If it fails, check what it created before you say anything (read only: `cd <recipe folder> && $IAC state list`), then show the error, say what was created, and stop. Do not run `apply` again without a new plan and a new yes; show what the new plan changes compared with the one the person approved.

### Point kubectl at the new cluster

```bash
cd <recipe folder> && $IAC output -raw gke_get_credentials_command
```

For EKS use `eks_update_kubeconfig_command`, and for AKS `aks_get_credentials_command`. The output is a `gcloud`, `aws` or `az` command. Show it, say it adds the cluster to the kubeconfig and makes it the current context, and run it. It is part of this stage. This is the cluster this install built: do not ask the person to confirm it.

### GPU pool at zero

The recipes start the GPU pool at zero nodes. GPU nodes appear only when the model pods ask for them in phase 6. So preflight may find no GPU nodes. Then check the pool itself (read only):

GKE:

```bash
gcloud container node-pools describe gpu --cluster gke-polar-sky --location "${CLUSTER_ZONE}" --project "${CLUSTER_PROJECT_ID}" --format='yaml(config.machineType,config.accelerators,config.taints,autoscaling,locations)'
```

EKS:

```bash
aws eks describe-nodegroup --cluster-name eks-polar-sky --nodegroup-name gpu --region "${CLUSTER_REGION}" --query 'nodegroup.{instanceTypes:instanceTypes,scaling:scalingConfig,labels:labels,taints:taints}' --output yaml
```

AKS:

```bash
az aks nodepool show --subscription "${CLUSTER_SUBSCRIPTION_ID}" --resource-group rg-polar-sky --cluster-name aks-polar-sky --name gpu --query '{vmSize:vmSize,minCount:minCount,maxCount:maxCount,labels:nodeLabels,taints:nodeTaints}' --output yaml
```

The pool must have the platform's GPU type and taint (table below), and a maximum of at least the GPU nodes the model fleet needs: the copies of the inference model plus one, so 4 by default and fewer when `POLAR_SKY_INFERENCE_MODEL_REPLICAS` is set. On EKS it must also have the label. On AKS the pool's `labels` is empty by design: AKS puts `accelerator=nvidia` on the GPU nodes when they start. The AKS pool must still have the GPU size, the `sku=gpu` `NoSchedule` taint and that maximum. On GKE the maximum is for the whole pool across its zones (`totalMaxNodeCount`), the pool takes whichever zone has capacity (`locationPolicy: ANY`), and `locations` lists the GPU zones.

On GKE, also check that the GPU pool's instance groups exist (read only). When a zone has no L4 GPUs while the pool is created, GKE can still show the pool as running but leave it without instance groups, and then no GPU node ever starts:

```bash
. ~/polar-sky-install/values.env && urls=$(gcloud container node-pools describe gpu --cluster gke-polar-sky --location "${CLUSTER_ZONE}" --project "${CLUSTER_PROJECT_ID}" --format='value(instanceGroupUrls)') && if [ -z "$urls" ]; then echo "MISSING no instance groups"; else echo "$urls" | tr ';' '\n' | while read -r url; do zone=$(echo "$url" | awk -F/ '{print $(NF-2)}'); name=${url##*/}; if out=$(gcloud compute instance-groups managed describe "$name" --zone "$zone" --project "${CLUSTER_PROJECT_ID}" --format='value(name)' 2>&1); then echo "found   $zone $name"; elif echo "$out" | grep -q 'was not found'; then echo "MISSING $zone $name"; else echo "ERROR   $zone $name: $out"; fi; done; fi
```

It must print at least one line, and every line should say `found`. If a line says `ERROR`, or the command fails, show the error and stop: it is usually a missing permission, not a GPU problem. If some lines say `found` and others `MISSING`, the pool can still start GPU nodes in the zones whose groups were found: tell the person, report it with `report_issue`, and go on; the fix below can wait for a quiet time. If every line says `MISSING`, stop and tell the person: "The GPU pool was created while a zone had no free GPUs, so it cannot start GPU nodes there." Report it with `report_issue`. The fix is a new plan that replaces only the GPU pool (`-replace=google_container_node_pool.gpu`) when the region has GPUs again (recommended, it keeps the cluster), or a new cluster in another region. With an older recipe whose GPU pool has one zone, a new cluster in another zone that offers L4 works too. Either way, show the plan and wait for a yes: it deletes or replaces resources.

### When GPU nodes cannot start

A zone can run out of a GPU type even though it offers it. The recipes already spread the GPU pool over several zones: on GKE every zone in the region that offers L4. Phase 6 shows when none has capacity: model pods stay `Pending`, and their events say they need a GPU node that is not there, for example `FailedScheduling` with `Insufficient nvidia.com/gpu`, or that the cluster could not add one, for example `FailedScaleUp` with "out of resources" or `ZONE_RESOURCE_POOL_EXHAUSTED`. First rule out the cloud quota, then tell the person plainly that their cloud has no GPU machines free in the region right now, and that GPU machines that do not start cost nothing.

The install goes on while the models wait (phase 6), and the models start on their own when a GPU node appears. A new cluster in another zone of the same region is not the fix, except with an older GKE recipe that keeps the GPU pool in one zone. Recommend waiting and checking again later. If capacity stays short for a long time, the person may choose a new cluster in another region: it deletes this cluster and everything in it, so it needs its own yes, and you report it with `report_issue`, outcome `worked_around`.

### Fewer copies of the inference model

The engine runs 3 copies of the inference model, each on its own GPU, and 1 copy of the embedding model, so it needs four GPU nodes. Always install it with 3 copies. Never ask the person how many copies they want, and never offer fewer: most people cannot judge this, and a GPU shortage has its own fixes, more quota or waiting for capacity. Fewer copies is an escape hatch for small clusters, used only when the person asks for it in their own words, for example because their GPU quota allows only 2 or 3 GPU machines, or because Polar Sky told them to.

When they ask without naming a number, do not ask for one: use the most copies the cluster can run, which is the GPU nodes it can have minus one for the embedding model, and at most 3. On AKS, step 5 of the AKS checks in [Plan](#plan) gives the quota for each count. Before you change anything, tell them the count and what it costs:

- 3 copies (the default) need 4 GPUs, 2 copies need 3, and 1 copy needs 2.
- Each copy removed takes away about a third of the capacity for judging how sensitive files are.
- With 1 copy there is no spare: if its pod or its node restarts, judging pauses for about 20 minutes while the model loads again.
- An update of the models starts each new copy before it stops an old one, so it needs one free GPU while it runs, as it does with 3 copies. A GPU pool that can grow adds that node by itself. On a cluster whose GPU pool cannot grow, model updates wait until a GPU is free, so leave one GPU free if the cluster has one.
- They can go back to 3 copies later, once the GPUs are there.

With their yes, write `export POLAR_SKY_INFERENCE_MODEL_REPLICAS='<copies>'` into `values.env`. Before the engine is installed, phase 6 sets it up with the install ([Fewer inference model copies](engine.md#fewer-inference-model-copies)). On an engine that is already installed, change it as [Change the number of inference model copies](engine.md#change-the-number-of-inference-model-copies) says.

## Existing cluster (AKS, EKS or GKE)

Polar Sky approves an existing cluster before the install. Show and run (read only):

```bash
kubectl config current-context && kubectl get nodes && kubectl get storageclass
```

Check that the context is the cluster the person named in the install plan; ask only if it is not. For Entra-integrated AKS, `kubelogin` must be installed. Preflight warns when the cluster already runs Flux outside the Polar Sky namespace, or Argo CD. Then tell the person to agree the install path with Polar Sky before phase 6: Argo CD must not take over Flux resources, and an existing Flux needs a review.

## What each platform needs

| Platform (setting value) | GPU nodes: label | GPU nodes: taint | StorageClass |
| --- | --- | --- | --- |
| GKE (`gke`) | `cloud.google.com/gke-accelerator=nvidia-l4` | `nvidia.com/gpu`, `NoSchedule` | None needed |
| EKS (`eks`) | `workload-type=gpu` and `gpu-type=t4` | `nvidia.com/gpu`, `NoSchedule` | `efs-polarsky-retain` (ReadWriteMany) |
| AKS (`aks`) | `accelerator=nvidia`, which AKS sets on NVIDIA GPU nodes | `sku=gpu`, `NoSchedule` | `premium-azurefile-retain` (ReadWriteMany) |

The model fleet needs one schedulable NVIDIA GPU for each copy of the inference model and one for the embedding model: four with the default 3 copies, and fewer when `POLAR_SKY_INFERENCE_MODEL_REPLICAS` is set. All Polar Sky nodes must be Linux `amd64`.

## Preflight checks

The script checks the cluster against guide section 2 and reports every problem at once, each with its fix. It checks:

- the context and the Kubernetes version (1.33 or newer)
- every node is Linux `amd64`
- GPU nodes: label, taint and allocatable GPUs (the NVIDIA device plugin), or a note that the pool is at zero
- the platform's StorageClass
- that the person can install Flux (custom resource definitions, cluster roles and their bindings) and manage resources in the namespace, with `kubectl auth can-i`
- whether another Flux, or Argo CD, already runs in the cluster (a warning, not a failure)
- that the cluster enforces NetworkPolicy: two test pods in a new temporary namespace `polar-sky-preflight-<time>`, first allowed to talk, then blocked by a policy
- outbound DNS and HTTPS from a short-lived pod in the Polar Sky namespace to each required host: for Google Workspace the Google sign-in and API hosts, and for Microsoft 365 `login.microsoftonline.com`, `graph.microsoft.com` and the tenant's SharePoint and OneDrive hosts from `MICROSOFT_SHAREPOINT_HOST`; for the Polar Sky host it trusts the Polar Sky CA in [scripts/polar-sky-ca.crt](../scripts/polar-sky-ca.crt), because that host's certificate is not from a public CA

It changes the cluster in two ways. On a new cluster, the plan's yes covers them. On an existing cluster, this is the stage's yes: tell the person both, and ask "Any concerns, or shall I go ahead?"

1. It creates a new namespace `polar-sky-preflight-<time>` with three short-lived `busybox` pods and one NetworkPolicy, and deletes only that namespace at the end.
2. It runs one `curlimages/curl` pod in the Polar Sky namespace and deletes it at the end. The Polar Sky namespace must exist first.

Create the Polar Sky namespace if it is missing, after a dry run:

```bash
kubectl create namespace "${POLAR_SKY_NAMESPACE}" --dry-run=server
```

```bash
kubectl get namespace "${POLAR_SKY_NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${POLAR_SKY_NAMESPACE}"
```

Check whether an earlier install set a count of inference model copies on this cluster (read only). It prints only the count line, never the rest of the ConfigMap, which may hold the API key:

```bash
kubectl get configmap polar-sky-customer-config --namespace="${POLAR_SKY_NAMESPACE}" --ignore-not-found -o jsonpath='{.data.values\.yaml}' | grep -E '^[[:space:]]+inferenceModelReplicas:' || echo "no count set"
```

A count in the ConfigMap is the one the cluster runs. If it prints a count of 1, 2 or 3, and the person did not ask for another count in this conversation, keep it without asking, even when `values.env` holds another one: write it into `values.env` as `export POLAR_SKY_INFERENCE_MODEL_REPLICAS='<count>'`, and tell the person in one line how many copies of the inference model run and that their ConfigMap sets it. The GPU checks then expect that many GPUs plus one. If it prints another number, stop and report it with `report_issue`.

Then run the checks:

```bash
. ~/polar-sky-install/values.env && <skill folder>/scripts/preflight.sh
```

It ends with `PREFLIGHT PASSED` or `PREFLIGHT FAILED` and a list of every failure and its fix. Show the whole list to the person in one message. Lines marked `WARN` need the person's attention but do not block.

If a check fails, the person fixes the cluster or the network, and you run the script again. A blocked host is usually opened by the network team: give them the host list from the script output, and say pulls may follow HTTPS redirects to download hosts, so a proxy or allowlist must allow the whole chain. Do not install the engine (phase 6) until preflight passes, or every failure left is one the person chose to skip.

### When a check fails on an existing cluster

Explain each failure: what it means and what can go wrong if the install goes on. Some failures the person may choose to accept, with a reason they state. Record each one with `report_issue`, outcome `worked_around`, and say it again in the summary at the end.

| Failure | May the person go on? |
| --- | --- |
| The cluster does not enforce NetworkPolicy | Yes. Risk: Polar Sky's network policies do not limit traffic to and from the engine, so the namespace is less isolated. Recommend asking the platform team first |
| The NetworkPolicy test did not finish | Run the script again first. If it fails again, the same as above |
| A GPU node has no allocatable GPU, or lacks the platform's taint | Yes. Risk: the AI models may not run, or other pods may use the GPU nodes. Phase 6 then says the models are not ready |
| No HTTPS to `huggingface.co` (EKS and AKS only) | Yes. Risk: the AI models cannot download, as above |
| Kubernetes older than 1.33, a missing StorageClass, missing permissions | No: the install cannot work. The cluster must be fixed first |
| A node that is not Linux `amd64` | No, unless Polar Sky agrees with the person how to keep Polar Sky pods off that node |
| No DNS, no HTTPS or TLS inspection for any other host (on GKE including `storage.googleapis.com`, which image downloads may also use), or the egress test could not run or be read | No: the engine cannot pull its images, reach Google Workspace or Microsoft 365, or reach Polar Sky Cloud. The network must be fixed first |

Warnings never block; explain them the same way.

On a new recipe cluster the GPU checks may only say the pool is at zero. Then run the GPU pool check above. Real GPU placement is checked in phase 6.
