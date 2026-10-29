# Phase 2: Look before asking

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

## Confirm with the person, one question at a time

First say what you found and how, so they can correct it. For example: "gcloud is signed in as `ana@example.com` with project `acme-platform`, OpenTofu 1.8 is installed, and kubectl points at `gke_acme_us-central1-a_prod`."

Then ask, proposing what you detected:

1. **Platform.** Which Kubernetes platform the engine runs on: `gke` (Google Kubernetes Engine on Google Cloud), `eks` (Amazon EKS on AWS) or `aks` (Azure Kubernetes Service). Propose the one that the signed-in cloud CLI and the kubectl context point to, and say how you found it. For example, a context named `gke_...` is GKE, and one whose cluster is an `arn:aws:eks:...` is EKS. If the signals disagree, or none points to a platform, ask. Write the confirmed answer into `values.env` as `export POLAR_SKY_INFRA_PROFILE='gke'` (or `eks` or `aks`), then run `scripts/check-values.sh` again as in phase 1.
2. **Cluster.** A new cluster from Polar Sky's recipe, or an existing cluster? Always ask. A kubectl context only shows that some cluster exists, not that it is the one to use. Polar Sky has a recipe only for `gke` and `eks`; for `aks`, the cluster is always an existing one.
3. **Terraform or OpenTofu,** for a new cluster. If both are installed, ask which one. Write `export IAC='terraform'` or `export IAC='tofu'` into `values.env`.
4. **Google Cloud project** for the Polar Sky service accounts. You may propose the gcloud project, saying where it came from, but record it only after the person names or confirms it. Write `export GOOGLE_CLOUD_PROJECT_ID='...'` into `values.env`.
5. **Workspace admin email.** The Google Workspace administrator Polar Sky acts as. It must be an active, monitored administrator account with the Reports privilege. Write `export GOOGLE_WORKSPACE_ADMIN_EMAIL='...'` into `values.env`.
6. **Is the person a Google Workspace super admin?** If not, ask who is. Phase 4 needs them.

Record only answers the person has confirmed.
