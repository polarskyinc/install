# Phase 2: Look before asking

**Tell the person:** Polar Sky first looks at what is already on this machine and in their cloud, so the person gets one plan to check instead of a form to fill in.

Find out what you can first, with read-only commands. Then show the whole install plan in one message, and ask only about the gaps.

## Run the detection script

It only reads. It installs nothing, signs in to nothing and prints no secret. A tool that is missing or not signed in shows as `not found` or `not signed in`.

```bash
<skill folder>/scripts/detect.sh
```

It reports:

- the platform (`uname -s`)
- the Google Cloud CLI: the active account and project, whether its sign-in still works, and whether the sign-in that OpenTofu and Terraform use (application default credentials) works
- the AWS CLI: the signed-in identity
- the Azure CLI: the subscription and user, and whether its sign-in still works
- Terraform and OpenTofu, and their versions
- kubectl, its current context, and whether that context answers
- Helm and its version (Helm 3 or Helm 4)
- OpenSSL and its version

Do not sign in or install anything to make a line pass. If a needed tool is missing, tell the person what to install and stop until they have it. A configured account is not proof that its sign-in works: when a needed sign-in has expired, give the person the command to run in their own terminal (in Claude Code they can type it here with `!` in front), such as `gcloud auth login` or `az login`. It opens a browser. Run the script again when they are done.

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

- **The Google Cloud organization of the Workspace domain.** The service accounts work from any project the person can use, but a project in the organization that owns the company's Google Workspace domain is usually the one to recommend. In a hybrid install that is often not the organization of the cluster. List the organizations; an organization's name is usually its domain: `gcloud organizations list --format="table(displayName,name)"`. An empty list can mean the account may not see the organization, not that there is none: then ask.
- **A second Google account,** when the gcloud account does not belong to the Workspace's organization, for example a partner's account. The person signs it in, in their own terminal, without making it the active account, so the cluster's commands keep using the current one: `gcloud auth login <account> --no-activate`, where `<account>` is their email in the Workspace domain. Check it with `gcloud auth list --format="table(account,status)"`, and run the lookups for the service account project with `--account=<account>` at the end. Once the plan is confirmed, write `export GOOGLE_CLOUD_ACCOUNT='<account>'` into `values.env`.
- **Google Cloud projects** the person can use, and where each sits: `gcloud projects list --format="table(projectId,name,parent.type,parent.id)" --limit=50`. Prefer a project whose parent is that organization, or a folder in it. Before you recommend a project, look inside it: service accounts from an earlier install show with `gcloud iam service-accounts list --project="<project>" --format="value(email)"`.
- **Google APIs already on** in each project you will use, so the plan turns on only what is off: `gcloud services list --enabled --project="<project>" --format="value(config.name)"`.
- **Whether the organization blocks service account keys,** before planning rather than when a key fails. A rule with `enforce: true` and no condition blocks keys; put it in the plan as a blocker, since the person's Google Cloud administrator must allow keys for the two Polar Sky service accounts. If the check cannot run, for example for lack of permission, say so and go on:

  ```bash
  gcloud org-policies describe iam.disableServiceAccountKeyCreation --effective --project="<project>" --format="yaml(spec.rules)"
  ```

  ```bash
  gcloud org-policies describe iam.managed.disableServiceAccountKeyCreation --effective --project="<project>" --format="yaml(spec.rules)"
  ```

- **Existing clusters,** for the platform the signals point to. kubectl: `kubectl config get-contexts -o name`. GKE: `gcloud container clusters list --project="<gcloud project>" --format="table(name,location,status,currentMasterVersion)"`. EKS: `aws eks list-clusters --region="<region>"`, for the AWS CLI's region and for the region in an `arn:aws:eks:...` kubectl context; it lists one region only, so do not take an empty list as "no cluster". AKS: `az aks list -o table`. If a lookup fails, for example because the Kubernetes Engine API is not enabled, you do not know which clusters exist. Say so in plain words, and do not tell the person there is none.
- **Workspace admin candidates:** the gcloud account, and the account the person signed in to Polar Sky with if you know it. No command shows whether an account is a Workspace administrator, so these are only candidates for the person to confirm.

## Show the install plan

Write one message with:

1. **What you found,** in a few lines, so the person can correct it. For example: "You're signed in to Polar Sky as **Acme Corp**, and to Google Cloud as `ana@acme.com`. The organization `acme.com` has the project `acme-security`. There is no Kubernetes cluster in that project yet."
2. **What you will do, stage by stage,** with how long each takes, using the step table from phase 1 and the answers below. Say which steps run at the same time (see the phase order in `SKILL.md`). For a new GKE cluster, name the free preparation steps: turning on the Cloud Billing and Compute Engine APIs in the cluster's project, and the Kubernetes Engine and IAM APIs if the name check in phase 3 needs them. For a new cluster, say it runs in the person's cloud account and costs money while it runs, most of it for the GPU nodes; give no price you have not looked up.
3. **The open questions,** all together. For each, say in one line why Polar Sky needs it, and put the answer you found or the recommended one first, marked "(recommended)", with a few words on why. Leave out any question you can already answer.

End with "Does this look right? Any changes, or shall I go ahead?" Record only answers the person has confirmed.

The answers the plan needs:

1. **Platform.** Which Kubernetes platform the engine runs on: GKE (Google Kubernetes Engine on Google Cloud), EKS (Amazon EKS on AWS) or AKS (Azure Kubernetes Service). Why: the cluster and its setup differ by cloud. Recommend the one that the signed-in cloud CLI and the kubectl context point to, and say how you found it. For example, a context named `gke_...` is GKE, and one whose cluster is an `arn:aws:eks:...` is EKS. If the signals disagree, or none points to a platform, ask without a recommendation. Write the confirmed answer into `values.env` as its setting value, `export POLAR_SKY_INFRA_PROFILE='gke'` (or `eks` or `aks`), then run `scripts/check-values.sh` again as in phase 1.
2. **Cluster.** A new cluster from Polar Sky's recipe, or an existing cluster? Always ask. A kubectl context or a listed cluster only shows that some cluster exists, not that it is the one to use. Why: the engine needs GPU nodes for its AI models. Recommend a new cluster from Polar Sky's recipe, because it comes with the GPU nodes and network settings the engine needs. Polar Sky has a recipe for each of GKE, EKS and AKS. Mention any existing cluster you found as the other choice.
3. **Where a new cluster goes:** the region, and for GKE the zone, the Google Cloud project (it may differ from the service-account project) and the GPU zones, every zone in the region that offers L4; the recipe's defaults are `us-central1` / `us-central1-a` (GKE), `us-east-1` (EKS) and `eastus` (AKS). For AKS also the subscription and the Kubernetes version Polar Sky approved (see phase 3). Write the answers into `values.env` as phase 3 says.
4. **Terraform or OpenTofu,** for a new cluster. If only one is installed, say you will use it and do not ask. If both are installed, ask which one. Write `export IAC='terraform'` or `export IAC='tofu'` into `values.env`.
5. **Google Cloud project** for the Polar Sky service accounts. Why: the two service accounts that read Google Workspace live in it. Recommend a project in the Workspace domain's organization if there is one, saying how you found it, and offer the other projects you found. Record it only after the person names or confirms it. Write `export GOOGLE_CLOUD_PROJECT_ID='...'` into `values.env`.
6. **Workspace admin email.** The Google Workspace administrator Polar Sky acts as. Why: Polar Sky reads who can open each file as this admin. It must be an active, monitored Workspace administrator account that can manage all shared drives and has the Reports privilege; a super admin has both. Being in the company's domain is not enough: the account you or Polar Sky are signed in as is often not an administrator. Offer the candidates you found, and ask the person to confirm the one they choose is an administrator in the Google Admin console. Write `export GOOGLE_WORKSPACE_ADMIN_EMAIL='...'` into `values.env`. If they are not sure, go on: phase 8 tests the account, and the fix for a wrong one is there.
7. **Who is the Google Workspace super admin?** Why: a super admin must approve the service accounts' access in the Google Admin console, which takes them a few minutes. If it is not the person, you prepare a message for them.

Once the person confirms the plan, start the first stage. Do not ask again for what the plan already settled.
