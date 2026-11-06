# Phase 2: Questions and the final plan

**Tell the person:** Polar Sky now looks up what the chosen deployment needs, asks only what it cannot find, and then shows the whole plan for one approval.

The preview in [Start](start.md) already ran the detection script and read the install values. Use those results. Find out what else you can with read-only commands before you ask anything.

## Look up what the model needs

These only read. Run the ones that apply to the model the person chose, so you can propose answers instead of asking open questions.

Run the detection script again only when a sign-in has been fixed since the preview. Use `cloud` for a Cloud install and no argument for an On-Prem install:

```bash
<skill folder>/scripts/detect.sh cloud
```

```bash
<skill folder>/scripts/detect.sh
```

The script only reads. It installs nothing, signs in to nothing and prints no secret. A tool that is missing or not signed in shows as `not found` or `not signed in`. Do not sign in or install anything to make a line pass. If a needed tool is missing, tell the person what to install and stop until they have it. In Cloud, only gcloud matters: a missing tool other than gcloud is not part of the install, so say nothing about it.

A configured account is not proof that its sign-in works: when a needed sign-in has expired, give the person the command to run in their own terminal (in Claude Code they can type it here with `!` in front), such as `gcloud auth login` or `az login`. It opens a browser. Run the script again when they are done.

On-Prem only: write how Helm waits into `values.env`: `export HELM_WAIT='--wait'` for Helm 3, or `export HELM_WAIT='--wait=legacy'` for Helm 4. Helm 4's default wait never returns after the Flux chart's install hook finishes, so phase 6 uses the legacy wait with Helm 4.

### What each deployment needs

| Need | Cloud | On-Prem | For |
| --- | --- | --- | --- |
| `gcloud`, signed in | Yes | Yes | The Google service accounts live in a Google Cloud project |
| `kubectl`, Helm 3 or 4, OpenSSL | No | Yes | The engine in the cluster |
| Terraform or OpenTofu 1.6 or later | No | Yes, for a new cluster from Polar Sky's recipe | Building the cluster |
| `aws` signed in | No | Yes, for EKS | An EKS cluster, new or existing |
| `az` signed in, and `kubelogin` for an Entra-integrated AKS cluster | No | Yes, for AKS | An AKS cluster |
| `jq` | Yes, with Okta | Yes, with Okta | Connecting Okta |

### Look up more before you ask

- **The Google Cloud organization of the Workspace domain** (both). The service accounts work from any project the person can use, but a project in the organization that owns the company's Google Workspace domain is usually the one to recommend. In an On-Prem install that is often not the organization of the cluster. List the organizations; an organization's name is usually its domain: `gcloud organizations list --format="table(displayName,name)"`. An empty list can mean the account may not see the organization, not that there is none: then ask.
- **A second Google account** (both), when the gcloud account does not belong to the Workspace's organization, for example a partner's account. The person signs it in, in their own terminal, without making it the active account, so the cluster's commands keep using the current one: `gcloud auth login <account> --no-activate`, where `<account>` is their email in the Workspace domain. Check it with `gcloud auth list --format="table(account,status)"`, and run the lookups for the service account project with `--account=<account>` at the end. Once the person confirms the answer, write `export GOOGLE_CLOUD_ACCOUNT='<account>'` into `values.env`.
- **Google Cloud projects** the person can use, and where each sits (both): `gcloud projects list --format="table(projectId,name,parent.type,parent.id)" --limit=50`. Prefer a project whose parent is that organization, or a folder in it. Before you recommend a project, look inside it: service accounts from an earlier install show with `gcloud iam service-accounts list --project="<project>" --format="value(email)"`.
- **Google APIs already on** (both) in each project you will use, so the plan turns on only what is off: `gcloud services list --enabled --project="<project>" --format="value(config.name)"`.
- **Whether the organization blocks service account keys** (both), before planning rather than when a key fails. A rule with `enforce: true` and no condition blocks keys; put it in the plan as a blocker, since the person's Google Cloud administrator must allow keys for the Polar Sky service accounts (one in Cloud, two in On-Prem). If the check cannot run, for example for lack of permission, say so and go on:

  ```bash
  gcloud org-policies describe iam.disableServiceAccountKeyCreation --effective --project="<project>" --format="yaml(spec.rules)"
  ```

  ```bash
  gcloud org-policies describe iam.managed.disableServiceAccountKeyCreation --effective --project="<project>" --format="yaml(spec.rules)"
  ```

- **Existing clusters** (On-Prem only), for the platform the signals point to. kubectl: `kubectl config get-contexts -o name`. GKE: `gcloud container clusters list --project="<gcloud project>" --format="table(name,location,status,currentMasterVersion)"`. EKS: `aws eks list-clusters --region="<region>"`, for the AWS CLI's region and for the region in an `arn:aws:eks:...` kubectl context; it lists one region only, so do not take an empty list as "no cluster". AKS: `az aks list -o table`. If a lookup fails, for example because the Kubernetes Engine API is not enabled, you do not know which clusters exist. Say so in plain words, and do not tell the person there is none.
- **Workspace admin candidates** (both): the gcloud account, and the account the person signed in to Polar Sky with if you know it. No command shows whether an account is a Workspace administrator, so these are only candidates for the person to confirm.

## Ask the open questions

Put every open question in one message, after the lookups. Each question gets one line on why Polar Sky needs the answer. Put the answer you found, or the recommended one, first, marked "(recommended)", with a few words on why. Leave out any question the lookups or the person's earlier answers already settled.

If an answer raises a new question, ask that new question in its own message before you show the final plan. Never add a new question to the final plan.

The answers the plan needs:

1. **Platform** (On-Prem only). Which Kubernetes platform the engine runs on: GKE (Google Kubernetes Engine on Google Cloud), EKS (Amazon EKS on AWS) or AKS (Azure Kubernetes Service). Why: the cluster and its setup differ by cloud. Recommend the one that the signed-in cloud CLI and the kubectl context point to, and say how you found it. For example, a context named `gke_...` is GKE, and one whose cluster is an `arn:aws:eks:...` is EKS. If the signals disagree, or none points to a platform, ask without a recommendation. Once the person confirms the answer, write it into `values.env` as its setting value, `export POLAR_SKY_INFRA_PROFILE='gke'` (or `eks` or `aks`), then run `scripts/check-values.sh` again as in [Start](start.md).
2. **Cluster** (On-Prem only). A new cluster from Polar Sky's recipe, or an existing cluster? Always ask. A kubectl context or a listed cluster only shows that some cluster exists, not that it is the one to use. Why: the engine needs GPU nodes for its AI models. Recommend a new cluster from Polar Sky's recipe, because it comes with the GPU nodes and network settings the engine needs. Polar Sky has a recipe for each of GKE, EKS and AKS. Mention any existing cluster you found as the other choice.
3. **Where a new cluster goes** (On-Prem only): the region, and for GKE the zone, the Google Cloud project (it may differ from the service-account project); the recipe's defaults are `us-central1` / `us-central1-a` (GKE), `us-east-1` (EKS) and `eastus` (AKS). For AKS also the subscription and the Kubernetes version Polar Sky approved (see [Cluster](cluster.md)). Write the answers into `values.env` as [Cluster](cluster.md) says. Do not ask for the GPU zones: [Cluster](cluster.md) finds every zone in the region that offers L4.
4. **Terraform or OpenTofu** (On-Prem only), for a new cluster. If only one is installed, say you will use it and do not ask. If both are installed, ask which one. Write `export IAC='terraform'` or `export IAC='tofu'` into `values.env`.
5. **Google Cloud project** (both) for the Polar Sky service accounts. Why: the service accounts that read Google Workspace live in it. Recommend a project in the Workspace domain's organization if there is one, saying how you found it, and offer the other projects you found. Record it only after the person names or confirms it. Write `export GOOGLE_CLOUD_PROJECT_ID='...'` into `values.env`.
6. **Workspace admin email** (both). The Google Workspace administrator Polar Sky acts as. Why: Polar Sky reads who can open each file as this admin. It must be an active, monitored Workspace administrator account that can manage all shared drives and has the Reports privilege; a super admin has both. Being in the company's domain is not enough: the account you or Polar Sky are signed in as is often not an administrator. Offer the candidates you found, and ask the person to confirm the one they choose is an administrator in the Google Admin console. Write `export GOOGLE_WORKSPACE_ADMIN_EMAIL='...'` into `values.env`. If they are not sure, go on: the connection step tests the account, and the fix for a wrong one is there.
7. **Who is the Google Workspace super admin** (both)? Why: a super admin must approve the Polar Sky service accounts' access in the Google Admin console, which takes them a few minutes. If it is not the person, you prepare a message for them.
8. **Does the company manage its groups in Okta** (both)? Why: when it does, Polar Sky creates the groups for approved controls in Okta, so the plan adds the step that connects Okta (phase 8), in either model. Always ask, unless `get_install_values` answered `okta_connected` true: then say Okta is already connected, with `okta_org_url`, and ask only whether to keep it. If they do not use Okta, leave the stage out. Write the answer into `values.env` as soon as the person gives it: `export POLAR_SKY_OKTA_PLANNED='yes'` when the plan has the Okta stage, `'no'` when it leaves it out. This needs no yes, like every recorded answer.
9. **Only with Okta: the Okta org URL, and who is an Okta Super Administrator** (both)? Why: creating Polar Sky's app in Okta and giving it an admin role needs a super admin, for a few minutes. If it is not the person, they do the Okta part from a message you prepare. Say in the same item that Polar Sky names its groups starting with `ps-`, and that the person can tell you if they want their own naming convention instead. Do not ask how groups reach Google Workspace: phase 8 finds out.
10. **What Polar Sky monitors** (both), only when `get_drive_choice` is among the Install tools; without it, the person chooses in the console after the connection, and the plan says so. Why: Polar Sky reads only what the organization chooses. Recommend everything, marked "(recommended)": every shared drive, including ones added later, and everyone's personal drive (My Drive), including people who join later. Say plainly that this includes every person's own files. If the person wants less, take their words (for example "only the finance drives") and say you will find the matching drives once Google Workspace is connected. Do not list drives or ask about sizes here.

Record only answers the person has confirmed. Write each one into `values.env` as soon as the person confirms it, before you show the plan. This needs no yes, even when the person wants nothing changed today, because it only records their answers on this machine. Never put writing `values.env` into the plan as a stage that needs a yes.

## Show the final plan

Once the answers are in, write one message with the final plan:

1. **What was found and settled,** in a few lines, so the person can correct it. For example, for Cloud: "You're signed in to Polar Sky as **Acme Corp**, and to Google Cloud as `ana@acme.com`. The project `acme-security` sits in the organization `acme.com`. Your Workspace admin is `admin@acme.com`."
2. **Each stage,** in order, with:
   - what it does, in one line;
   - how long it usually takes;
   - which stages run at the same time;
   - what the person or their super admin has to do, and when;
   - for a new cluster, the cost: it runs in the person's cloud account and costs money while it runs, most of it for the GPU nodes. Give no price you have not looked up;
   - what they will have at the end.

   In the Google Workspace stage, say what Polar Sky will monitor, in the words of the answer to question 10: by default "everything: every shared drive, including ones added later, and everyone's personal drive". Say that you save it right after the connection, without asking again, unless they asked for less. Without `get_drive_choice`, say instead that the person chooses in the Polar Sky console after the connection, by ticking the drives.

   For Cloud, the stages are: turn on the two Google APIs and create the Polar Sky Cloud service account and its key (no cluster, so no cluster cost); the super admin adds the Polar Sky Cloud delegation entry (a few minutes for them); connect Google Workspace with the one-time upload; save what Polar Sky monitors. At the end they have Polar Sky Cloud connected to Google Workspace, monitoring what they chose.

   With Okta, in either model, add the Okta stage before the Google Workspace connection: an Okta super admin's short-lived API token, the Okta app, and the read-only Group Push check (10 to 15 minutes). In Cloud it runs while the super admin approves the entry; in On-Prem, while the cluster builds.

   For On-Prem, the stages are the cluster, the Google service accounts, the engine certificate, the engine, the connection check, and the Google Workspace connection with what Polar Sky monitors. For a new GKE cluster, name the free preparation steps: turning on the Cloud Billing and Compute Engine APIs in the cluster's project, and the Kubernetes Engine and IAM APIs if the name check in phase 3 needs them. Say which steps run at the same time, as the phase order in [SKILL.md](../SKILL.md#phases) says.
3. **One approval question,** last: "Does this look right? Any changes, or shall I go ahead?"

This is the one plan approval. Each stage still gets its own yes, as in the hard rules in `SKILL.md`, except saving what Polar Sky monitors: the plan's yes covers that save, as [Google Workspace](workspace.md#choose-in-the-conversation) says. Once the person approves the final plan, start the first stage. Do not ask again for what the plan already settled.
