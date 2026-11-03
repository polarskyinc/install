# Phase 2: Look before asking

**Tell the person:** Polar Sky first looks at what is already on this machine, so the person only confirms answers instead of filling in a form.

Find out what you can on this machine first. Then the person only confirms answers or fills gaps.

## Run the detection script

It only reads. It installs nothing, signs in to nothing and prints no secret. A tool that is missing or not signed in shows as `not found` or `not signed in`.

```bash
<skill folder>/scripts/detect.sh
```

It reports:

- the platform (`uname -s`)
- the Google Cloud CLI: the active account and project
- the AWS CLI: the signed-in identity
- the Azure CLI: the subscription and user
- Terraform and OpenTofu, and their versions
- kubectl, its current context, and whether that context answers
- Helm and its version (Helm 3 or Helm 4)
- OpenSSL and its version

Do not sign in or install anything to make a line pass. If a needed tool is missing, tell the person what to install and stop until they have it.

Write how Helm waits into `values.env`: `export HELM_WAIT='--wait'` for Helm 3, or `export HELM_WAIT='--wait=legacy'` for Helm 4. Helm 4's default wait never returns after the Flux chart's install hook finishes, so phase 6 uses the legacy wait with Helm 4.

## What each install needs

| Need | For |
| --- | --- |
| `kubectl`, Helm 3 or 4, OpenSSL | Every install |
| `gcloud`, signed in | Every install: the Google service accounts live in a Google Cloud project |
| Terraform or OpenTofu 1.6 or later | A new cluster from Polar Sky's recipe |
| `aws` signed in | A new EKS cluster, or an existing EKS cluster |
| `az` signed in, and `kubelogin` for an Entra-integrated AKS cluster | AKS |

## Look up more before you ask

These only read. Run the ones that apply, so you can propose answers instead of asking open questions:

- **Existing clusters,** for the platform the signals point to. GKE: `gcloud container clusters list --project="<gcloud project>" --format="table(name,location,status,currentMasterVersion)"`. EKS: `aws eks list-clusters --region="<region>"`, for the AWS CLI's region and for the region in an `arn:aws:eks:...` kubectl context; it lists one region only, so do not take an empty list as "no cluster". AKS: `az aks list -o table`. If a lookup fails, for example because the Kubernetes Engine API is not enabled, you do not know which clusters exist. Say so in plain words, and do not tell the person there is none.
- **Google Cloud projects** the person can use: `gcloud projects list --format="table(projectId,name)" --limit=20`.

## Confirm with the person, one question at a time

First say in one or two sentences what you found, so they can correct it. For example: "You're signed in to Google Cloud as `ana@example.com` in project `acme-platform`, and there is no Kubernetes cluster in that project yet."

Then ask each question below. For each, say in one line why Polar Sky needs it, and put the answer you found or the recommended one first, marked "(recommended)", with a few words on why.

1. **Platform.** Which Kubernetes platform the engine runs on: `gke` (Google Kubernetes Engine on Google Cloud), `eks` (Amazon EKS on AWS) or `aks` (Azure Kubernetes Service). Why: the cluster and its setup differ by cloud. Recommend the one that the signed-in cloud CLI and the kubectl context point to, and say how you found it. For example, a context named `gke_...` is GKE, and one whose cluster is an `arn:aws:eks:...` is EKS. If the signals disagree, or none points to a platform, ask without a recommendation. Write the confirmed answer into `values.env` as `export POLAR_SKY_INFRA_PROFILE='gke'` (or `eks` or `aks`), then run `scripts/check-values.sh` again as in phase 1.
2. **Cluster.** A new cluster from Polar Sky's recipe, or an existing cluster? Always ask. A kubectl context or a listed cluster only shows that some cluster exists, not that it is the one to use. Why: the engine needs GPU nodes for its AI models. Recommend a new cluster from Polar Sky's recipe, because it comes with the GPU nodes and network settings the engine needs. Polar Sky has a recipe for each of `gke`, `eks` and `aks`. Mention any existing cluster you found as the other choice.
3. **Terraform or OpenTofu,** for a new cluster. If only one is installed, say you will use it and do not ask. If both are installed, ask which one. Write `export IAC='terraform'` or `export IAC='tofu'` into `values.env`.
4. **Google Cloud project** for the Polar Sky service accounts. Why: the two service accounts that read Google Workspace live in it. Recommend the gcloud project, saying where it came from, and offer the other projects you found. Record it only after the person names or confirms it. Write `export GOOGLE_CLOUD_PROJECT_ID='...'` into `values.env`.
5. **Workspace admin email.** The Google Workspace administrator Polar Sky acts as. Why: Polar Sky reads who can open each file as this admin. It must be an active, monitored Workspace administrator account that can manage all shared drives and has the Reports privilege; a super admin has both. Being in the company's domain is not enough: the account you or Polar Sky are signed in as is often not an administrator. Ask the person which account is a Workspace administrator, and if they name the account they signed in with, ask them to confirm it is an administrator in the Google Admin console. Write `export GOOGLE_WORKSPACE_ADMIN_EMAIL='...'` into `values.env`. If they are not sure, go on: phase 8 tests the account, and the fix for a wrong one is there.
6. **Is the person a Google Workspace super admin?** Why: a super admin must approve the service accounts' access in the Google Admin console, which takes them a few minutes. If not, ask who is, so you can prepare a message for them.

Record only answers the person has confirmed.
