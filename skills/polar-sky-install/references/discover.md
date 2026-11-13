# Phase 2: Questions and the final plan

**Tell the person:** Polar Sky now looks up what the chosen deployment needs, asks only what it cannot find, and then shows the whole plan for one approval.

The preview in [Start](start.md) already ran the detection script and read the install values. Use those results. Find out what else you can with read-only commands before you ask anything.

For Microsoft 365, the lookups and the questions are in [Microsoft 365](#microsoft-365) below, in place of the Google ones. The rules for asking, and the form of the final plan, are the same for both.

## Look up what the model needs

These only read. Run the ones that apply to the model the person chose, so you can propose answers instead of asking open questions. Add `--quiet` to each gcloud lookup, so a question from gcloud fails the lookup instead of waiting for an answer.

Run the detection script again only when a sign-in has been fixed since the preview. Use `cloud` for a Google Workspace Cloud install, `cloud microsoft365` for a Microsoft 365 Cloud install, and no argument for an On-Prem install:

```bash
<skill folder>/scripts/detect.sh cloud
```

```bash
<skill folder>/scripts/detect.sh cloud microsoft365
```

```bash
<skill folder>/scripts/detect.sh
```

The script only reads. It installs nothing, signs in to nothing and prints no secret. A tool that is missing or not signed in shows as `not found` or `not signed in`. Do not sign in or install anything to make a line pass. If a needed tool is missing, tell the person what to install and stop until they have it. In a Google Workspace Cloud install, only gcloud matters; in a Microsoft 365 Cloud install, only `az`, `jq` and OpenSSL; in a Microsoft 365 On-Prem install, gcloud matters only for GKE. A missing tool that the install does not use is not part of it, so say nothing about it.

A configured account is not proof that its sign-in works: when a needed sign-in has expired, give the person the command to run in their own terminal (in Claude Code they can type it here with `!` in front), such as `gcloud auth login`, or `az login --tenant <the company's domain> --allow-no-subscriptions` for Microsoft 365. It opens a browser. Run the script again when they are done. A sign-in is needed only when the plan uses it: an expired second account in `gcloud auth list` that the plan does not use needs nothing, so do not mention it.

On-Prem only: write how Helm waits into `values.env`: `export HELM_WAIT='--wait'` for Helm 3, or `export HELM_WAIT='--wait=legacy'` for Helm 4. Helm 4's default wait never returns after the Flux chart's install hook finishes, so phase 6 uses the legacy wait with Helm 4.

### What each deployment needs

| Need | Cloud | On-Prem | For |
| --- | --- | --- | --- |
| `gcloud`, signed in | Google Workspace only | Google Workspace, or GKE | The Google service accounts live in a Google Cloud project, and a GKE cluster in one too |
| `az` signed in to the Microsoft 365 tenant, `jq` and OpenSSL | Microsoft 365 only | With Microsoft 365 | The Polar Sky app registration lives in the tenant's Microsoft Entra ID, its certificate is made with OpenSSL, and the app scripts read with `jq` |
| `kubectl`, Helm 3 or 4, OpenSSL | No | Yes | The engine in the cluster |
| Terraform or OpenTofu 1.6 or later | No | Yes, for a new cluster from Polar Sky's recipe | Building the cluster |
| `aws` signed in | No | Yes, for EKS | An EKS cluster, new or existing |
| `az` signed in, and `kubelogin` for an Entra-integrated AKS cluster | No | Yes, for AKS | An AKS cluster |
| `jq` | Yes, with Okta | Yes, with Okta | Connecting Okta |

### Look up more before you ask

- **The Google Cloud organization of the Workspace domain** (both). The service accounts work from any project the active gcloud account can set them up in, in any organization: Google Workspace trusts them through the super admin's approval, not through the project. Among the projects the active account can use, one in the organization that owns the company's Google Workspace domain is the one to recommend first. In an On-Prem install that is often not the organization of the cluster. List the organizations; an organization's name is usually its domain: `gcloud organizations list --format="table(displayName,name)"`. An empty list can mean the account may not see the organization, not that there is none: then ask.
- **A second Google account** (both), only when no project the active account can use passes the check below, for example a partner's account that may not create service accounts anywhere. A project in another organization is no reason for it: ask for a second account only when there is no usable project. The person signs it in, in their own terminal, without making it the active account, so the cluster's commands keep using the current one: `gcloud auth login <account> --no-activate`, where `<account>` is their email in the Workspace domain. Check it with `gcloud auth list --format="table(account,status)"`, and run the lookups for the service account project with `--account=<account>` at the end. Once the person confirms the answer, write `export GOOGLE_CLOUD_ACCOUNT='<account>'` into `values.env`.
- **Google Cloud projects** the active account can use, and where each sits (both): `gcloud projects list --format="table(projectId,name,parent.type,parent.id)" --limit=50`. Prefer a project whose parent is the Workspace's organization, or a folder in it, but a project elsewhere works as well. Before you recommend a project, look inside it: service accounts from an earlier install show with `gcloud iam service-accounts list --project="<project>" --format="value(email)"`.
- **Whether the active account may set up the service accounts in a project** (both), for the project you recommend and for any project the person names, read only. The token goes from gcloud to curl only through the pipe, as in the next check:

  ```bash
  gcloud auth print-access-token | sed 's/^/Authorization: Bearer /' | curl -sS --fail-with-body -H @- -H 'Content-Type: application/json' -d '{"permissions":["iam.serviceAccounts.create","serviceusage.services.enable"]}' 'https://cloudresourcemanager.googleapis.com/v1/projects/<project>:testIamPermissions'
  ```

  The project is usable when the answer lists `iam.serviceAccounts.create`, unless a Polar Sky service account to reuse is already there, and `serviceusage.services.enable`, unless the APIs are already on. When neither is needed, it is usable without the check. Then use it with the active account: no other sign-in. The right to create keys belongs to each service account, so this check does not test it: the service account step shows it if it is missing. Once the person uses a second Google account, run this check for its projects with `--account=<account>` after `print-access-token`. If the check itself fails, say so, take the project the person named or the one you recommend, and go on. A failed check is never a reason to ask for a sign-in.
- **Whether the account may create a new project** (both), only when the person asks for a new project or no project they can use fits. Recommend an existing project: the service accounts work from any project the account can use, and creating one needs a permission many accounts lack. Never run `gcloud projects create` to find out. Find the folder or organization the new project would go in, from the projects list above or by asking, then check, read only, whether the account may create projects there. Use `folders/<folder id>` for a folder or `organizations/<organization id>` for the organization, and add `--account=<account>` after `print-access-token` when the service accounts use the second Google account and the project holds only them. For a project that will hold the cluster, check the active account, which creates it. The access token goes from gcloud to curl only through the pipe, never into the chat, a command argument or a log; never add `-v`:

  ```bash
  gcloud auth print-access-token | sed 's/^/Authorization: Bearer /' | curl -sS --fail-with-body -H @- -H 'Content-Type: application/json' -d '{"permissions":["resourcemanager.projects.create"]}' 'https://cloudresourcemanager.googleapis.com/v3/folders/<folder id>:testIamPermissions'
  ```

  An answer that lists `resourcemanager.projects.create` means the account may create projects there. An empty answer (`{}`) means it may not, or cannot see that folder. Put that in the plan as a blocker with the two ways out: use an existing project (recommended), or ask the Google Cloud administrator to give the person the Project Creator role on that folder or organization, or to create the project for them. If the check itself fails, say so and recommend an existing project. A project that does not exist yet has nothing to look inside: skip its service account and API lookups, take its APIs as off, and run the key policy check below with `--folder="<folder id>"` or `--organization="<organization id>"` in place of `--project`.

  When the new project will also hold a new GKE cluster (On-Prem), it needs billing. List the billing accounts the person can see, then check each the same way, with `{"permissions":["billing.resourceAssociations.create"]}` and the address `https://cloudbilling.googleapis.com/v1/billingAccounts/<billing account id>:testIamPermissions`. No open account, or none that lists the permission, is a blocker too: a billing administrator links one, or the person uses an existing project with billing. Also say in the plan that a new project starts with Google's default quotas, which often allow no L4 GPUs, so a quota request may be needed, and it can take a day or more. Nothing checks that quota before the cluster is built: without it the GPU nodes do not start, which shows only after the build. Recommend that the person checks the L4 GPU quota for the region on the Quotas page of the Cloud Console once the project exists, and asks for more before the cluster is built. A project that holds only the service accounts needs no billing.

  ```bash
  gcloud billing accounts list --filter=open=true --format="table(name.basename(),displayName)"
  ```

- **Google APIs already on** (both) in each project you will use, so the plan turns on only what is off: `gcloud services list --enabled --project="<project>" --format="value(config.name)"`.
- **Whether the organization blocks service account keys** (both), before planning rather than when a key fails. A rule with `enforce: true` and no condition blocks keys; put it in the plan as a blocker, since the person's Google Cloud administrator must allow keys for the Polar Sky service accounts (one in Cloud, two in On-Prem). If the check cannot run, for example for lack of permission or because the Organization Policy API is off in the project, say so and go on. Keep `--quiet`: without it, gcloud asks whether to turn that API on and waits for an answer that never comes. Run these two checks on their own, not in one command with other lookups or with writing `values.env`:

  ```bash
  gcloud org-policies describe iam.disableServiceAccountKeyCreation --effective --project="<project>" --format="yaml(spec.rules)" --quiet
  ```

  ```bash
  gcloud org-policies describe iam.managed.disableServiceAccountKeyCreation --effective --project="<project>" --format="yaml(spec.rules)" --quiet
  ```

- **Existing clusters** (On-Prem only), for the platform the signals point to. kubectl: `kubectl config get-contexts -o name`. GKE: `gcloud container clusters list --project="<gcloud project>" --format="table(name,location,status,currentMasterVersion)"`. EKS: `aws eks list-clusters --region="<region>"`, for the AWS CLI's region and for the region in an `arn:aws:eks:...` kubectl context; it lists one region only, so do not take an empty list as "no cluster". AKS: `az aks list -o table`. If a lookup fails, for example because the Kubernetes Engine API is not enabled, you do not know which clusters exist. Say so in plain words, and do not tell the person there is none.
- **Workspace admin candidates** (both): the gcloud account, and the account the person signed in to Polar Sky with if you know it. No command shows whether an account is a Workspace administrator, so these are only candidates for the person to confirm.

## Ask the open questions

Put every open question in one message, after the lookups. Each question gets one line on why Polar Sky needs the answer. Put the answer you found, or the recommended one, first, marked "(recommended)", with a few words on why. Leave out any question the lookups or the person's earlier answers already settled.

If an answer raises a new question, ask that new question in its own message before you show the final plan. Never add a new question to the final plan.

The answers the plan needs:

1. **Platform** (On-Prem only). Which Kubernetes platform the engine runs on: GKE (Google Kubernetes Engine on Google Cloud), EKS (Amazon EKS on AWS) or AKS (Azure Kubernetes Service). Why: the cluster and its setup differ by cloud. Recommend the one that the signed-in cloud CLI and the kubectl context point to, and say how you found it. For example, a context named `gke_...` is GKE, and one whose cluster is an `arn:aws:eks:...` is EKS. If the signals disagree, or none points to a platform, ask without a recommendation. Once the person confirms the answer, write it into `values.env` as its setting value, `export POLAR_SKY_INFRA_PROFILE='gke'` (or `eks` or `aks`), then run `scripts/check-values.sh` again as in [Start](start.md).
2. **Cluster** (On-Prem only). A new cluster from Polar Sky's recipe, or an existing cluster? Always ask. A kubectl context or a listed cluster only shows that some cluster exists, not that it is the one to use. Why: the engine needs GPU nodes for its AI models. Recommend a new cluster from Polar Sky's recipe, because it comes with the GPU nodes and network settings the engine needs. Polar Sky has a recipe for each of GKE, EKS and AKS. Mention any existing cluster you found as the other choice.
3. **Where a new cluster goes** (On-Prem only): the region, and for GKE the zone, the Google Cloud project (it may differ from the service-account project); the recipe's defaults are `us-central1` / `us-central1-a` (GKE), `us-east-1` (EKS) and `eastus` (AKS). For AKS also the subscription (see [Cluster](cluster.md)). Write the answers into `values.env` as [Cluster](cluster.md) says. When the cluster's project is a new one, write `export CLUSTER_PROJECT_ID='...'` into `values.env` now, so the stage that creates it has the ID. Do not ask for the GPU zones, the AKS Kubernetes version or the AKS machine size: [Cluster](cluster.md) finds every zone in the region that offers L4, picks the newest Kubernetes version AKS offers there, and picks the first system pool size the subscription may use there. Do not ask how many copies of the inference model the engine runs either: it always installs with 3, and fewer copies is only for a person who asks for it ([Cluster](cluster.md#fewer-copies-of-the-inference-model)).
4. **Terraform or OpenTofu** (On-Prem only), for a new cluster. If only one is installed, say you will use it and do not ask. If both are installed, ask which one. Write `export IAC='terraform'` or `export IAC='tofu'` into `values.env`.
5. **Google Cloud project** (both) for the Polar Sky service accounts. Why: the service accounts that read Google Workspace live in it. Recommend a project the active account can use, by the check above: one in the Workspace domain's organization if there is one, saying how you found it, and offer the other usable projects you found. When the person names a project and it passes the check, or the check cannot run, take it with the active account and ask for no other sign-in. Offer a new project only when the person asks for one or none of their projects fits, and give the result of the check above with it. Record it only after the person names or confirms it. Write `export GOOGLE_CLOUD_PROJECT_ID='...'` into `values.env`.
6. **Workspace admin email** (both). The Google Workspace administrator Polar Sky acts as. Why: Polar Sky reads who can open each file as this admin. It must be an active, monitored Workspace administrator account that can manage all shared drives and has the Reports privilege; a super admin has both. Being in the company's domain is not enough: the account you or Polar Sky are signed in as is often not an administrator. Offer the candidates you found, and ask the person to confirm the one they choose is an administrator in the Google Admin console. Write `export GOOGLE_WORKSPACE_ADMIN_EMAIL='...'` into `values.env`. If they are not sure, go on: the connection step tests the account, and the fix for a wrong one is there.
7. **Who is the Google Workspace super admin** (both)? Why: a super admin must approve the Polar Sky service accounts' access in the Google Admin console, which takes them a few minutes. If it is not the person, you prepare a message for them.
8. **Does the company manage its groups in Okta** (both)? Why: when it does, Polar Sky creates the groups for approved controls in Okta, so the plan adds the step that connects Okta (phase 8), in either model. Always ask, unless `get_install_values` answered `okta_connected` true: then say Okta is already connected, with `okta_org_url`, and ask only whether to keep it. If they do not use Okta, leave the stage out. `get_install_values` also answers `provisioning_mode`, which is `okta` for a new organization even when the company does not use Okta. That is the normal default: while Okta is not connected, Polar Sky only watches the groups in Google Workspace. So when the person does not use Okta and `okta_connected` is false, do not mention this setting, do not warn about it, and do not send the person to Polar Sky to change it. Write the answer into `values.env` as soon as the person gives it: `export POLAR_SKY_OKTA_PLANNED='yes'` when the plan has the Okta stage, `'no'` when it leaves it out. This needs no yes, like every recorded answer.
9. **Only with Okta: the Okta org URL, and who is an Okta Super Administrator** (both)? Why: creating Polar Sky's app in Okta and giving it an admin role needs a super admin, for a few minutes. If it is not the person, they do the Okta part from a message you prepare. Say in the same item that Polar Sky names its groups starting with `ps-`, and that the person can tell you if they want their own naming convention instead. Do not ask how groups reach Google Workspace: phase 8 finds out.
10. **What Polar Sky monitors** (both), only when `get_drive_choice` is among the Install tools; without it, the person chooses in the console after the connection, and the plan says so. Why: Polar Sky reads only what the organization chooses. Recommend everything, marked "(recommended)": every shared drive, including ones added later, and everyone's personal drive (My Drive), including people who join later. Say plainly that this includes every person's own files. If the person wants less, take their words (for example "only the finance drives") and say you will find the matching drives once Google Workspace is connected. Do not list drives or ask about sizes here.
11. **Does the company use Slack, and should Polar Sky's messages go there** (both)? Why: Polar Sky sends messages such as "controls are ready for review" and requests to file owners as Slack direct messages from the Polar Sky app; without Slack they go by email. When the answer is yes, the plan ends with the optional [Slack step](slack.md). Ask in the same item who may add apps to their Slack: if the person cannot, Slack sends a request to their Slack admin, who approves it. If `get_install_values` answered `slack_connected` true, say Slack is already connected to the workspace in `slack_workspace_name`, and ask only whether to keep it. If they do not use Slack, or not now, leave the step out: they can connect it later from the Platform page.

Record only answers the person has confirmed. Write each one into `values.env` as soon as the person confirms it, before you show the plan. This needs no yes, even when the person wants nothing changed today, because it only records their answers on this machine. Never put writing `values.env` into the plan as a stage that needs a yes.

## Microsoft 365

For a Microsoft 365 install, these lookups and questions take the place of the Google ones above. The Slack question is the same. In On-Prem, also run the cluster lookups above (existing clusters) and ask the platform, cluster, region and Terraform or OpenTofu questions (1 to 4 above), unchanged.

First read the install values you got with `provider` `microsoft365`. When they have `microsoft365_reading` while `microsoft365_connected` is false, the organization has a Microsoft 365 connection that Polar Sky turned off. This install can neither turn it on nor connect another one, so do not create an app or ask for consent. Tell the person that their Polar Sky contact turns the connection on again, call `report_issue` with step `microsoft365`, outcome `blocked`, and stop.

### Look up what Microsoft 365 needs

These only read. Run them as soon as the provider and the model are known:

- **The `az` account and tenant:**

  ```bash
  az account show --query '{tenant:tenantId, user:user.name}' -o tsv
  ```

- **The tenant's name and domains:**

  ```bash
  az rest --method GET --url 'https://graph.microsoft.com/v1.0/organization?$select=displayName,verifiedDomains' --query 'value[0].{name:displayName, domains:verifiedDomains[].name}'
  ```

- **The signed-in person's directory roles.** A role that Privileged Identity Management makes eligible but that is not active does not show, so the answer is only a candidate:

  ```bash
  az rest --method GET --url 'https://graph.microsoft.com/v1.0/me/transitiveMemberOf/microsoft.graph.directoryRole?$select=displayName' --query 'value[].displayName' -o tsv
  ```

- **App registrations an earlier install left.** This lists the apps whose name starts with `Polar Sky Cloud`, so it also finds one named for an organization, such as `Polar Sky Cloud (Contoso)`:

  ```bash
  az ad app list --display-name 'Polar Sky Cloud' --query '[].{name:displayName, appId:appId, created:createdDateTime}' -o tsv
  ```

  An app whose `appId` is `microsoft365_client_id` is the connected one. For any other app named `Polar Sky Cloud`, or `Polar Sky Cloud (<POLAR_SKY_ORGANIZATION_NAME>)`, see what it asks for. This only reads, apart from writing the public file `microsoft-cloud-app-access.json`. Its `KEEP` lines mean something else uses the app:

  ```bash
  cd ~/polar-sky-install && <skill folder>/scripts/microsoft-app-access.sh cloud "<appId>"
  ```

  In On-Prem, look for the engine app the same way. For an app named `Polar Sky On-Premises`, or `Polar Sky On-Premises (<POLAR_SKY_ORGANIZATION_NAME>)`, run the script with `engine` in place of `cloud`; it writes `microsoft-on-prem-app-access.json`:

  ```bash
  az ad app list --display-name 'Polar Sky On-Premises' --query '[].{name:displayName, appId:appId, created:createdDateTime}' -o tsv
  ```

- **The SharePoint address** (On-Prem only), for the check that the engine can reach SharePoint and OneDrive. It is read from the tenant's root site, so it is right also for a tenant with a custom email domain or a renamed SharePoint domain:

  ```bash
  az rest --method GET --url 'https://graph.microsoft.com/v1.0/sites/root?$select=webUrl' --query webUrl -o tsv
  ```

  It prints an address such as `https://contoso.sharepoint.com`. Its host, in lowercase and with no `https://`, is the SharePoint host. Never work it out from the tenant's domains: they often differ from it.

- **A connection made for Cloud** (On-Prem only, when `microsoft365_connected` is true). A connection made in the Polar Sky console is made for Cloud, where the cloud app reads files. Check the connected app with the On-Prem list (read only; `microsoft-permissions.json` holds the On-Prem list, and `POLAR_SKY_DEPLOYMENT_MODEL` in `values.env` is `on_prem`):

  ```bash
  . ~/polar-sky-install/values.env && cd ~/polar-sky-install && <skill folder>/scripts/check-microsoft-app.sh cloud "<microsoft365_client_id>"
  ```

  A `SURPLUS` line for a file or site permission, one whose name starts with `Files.` or `Sites.`, means the connection was made for Cloud. Moving it to On-Prem is not part of this install: the engine certificate would change how Polar Sky reads with that connection while its first reading may still run. Do not plan any stage. Tell the person: "Your Microsoft 365 connection was made for Cloud. Moving it to On-Prem is a step Polar Sky does with you, so I will tell them." Call `report_issue` with step `microsoft365`, outcome `blocked`, and stop. Any other `SURPLUS` line is a grant Polar Sky does not ask for: put its removal into the plan, as [Check the app](microsoft-apps.md#check-the-app) says for `SURPLUS`.

If `az` is not signed in, or a lookup is refused, say what you could not find in plain words, and ask instead. Do not call `get_drive_choice` or the other drive choice tools for Microsoft 365: they are for Google Workspace.

### Ask the Microsoft 365 questions

Ask them as [Ask the open questions](#ask-the-open-questions) says: in one message, each with one line on why, and the answer found or recommended first. The answers the plan needs:

1. **The Microsoft 365 tenant.** Why: the Polar Sky app registrations live there, and Polar Sky reads it. Recommend the tenant `az` is signed in to, by its name and primary domain, when its domains include the company's, and say how you found it. If `microsoft365_connected` is true, it is the tenant in `microsoft365_tenant_id`: say so, and do not ask. Write `export MICROSOFT_TENANT_ID='<tenant ID>'` into `values.env`. On AKS, when the cluster's subscription sits in another tenant, ask which `az` sign-in the person uses for the cluster and which for Microsoft 365, and say that the app registrations are made before or after the cluster build, never while it runs.
2. **Who grants admin consent.** Why: an administrator grants each app its access across the tenant, which takes them a few minutes, and only a Global Administrator or a Privileged Role Administrator can. If the roles lookup shows one of these roles for the person, recommend that they grant it here, with your command, after its own yes. Otherwise they name the administrator, and you prepare a message for them. In the same item, say that audit logging must be on in Microsoft Purview, and that the administrator checks it: it cannot be checked from here. When Microsoft 365 is already connected in a Cloud install, leave this question out: ask it only if the checks of that connection later show a missing permission. In On-Prem, ask it even then, for the engine app.
3. **An existing app registration,** only when the lookup found one that is not the connected app. Why: Polar Sky's access should sit on apps that only Polar Sky uses. The same goes for the engine app, `Polar Sky On-Premises`, in On-Prem.
   - From an earlier, stopped install of this organization, with no `KEEP` lines: keep it (recommended), so it is set up again and no second app appears.
   - With `KEEP` lines: something else uses it. Recommend a new app named `Polar Sky Cloud (<POLAR_SKY_ORGANIZATION_NAME>)`, or `Polar Sky On-Premises (<POLAR_SKY_ORGANIZATION_NAME>)`, because an app that something else uses should not carry Polar Sky's tenant-wide permissions.
   - Another Polar Sky organization uses it, for example the company's other Polar Sky installation in the same tenant: recommend a new app named with the organization name in the same way, and leave the other one as it is.

   A new app always gets a name no app in the tenant has yet: `az ad app create` changes an existing app of exactly the same name instead of making a new one. Never delete an app registration without its own yes.
4. **The SharePoint address** (On-Prem only), only when the lookup could not read it. Why: the check before the engine install tests that the cluster can reach SharePoint and OneDrive. Ask the person to open SharePoint in their browser and give the address, of the form `https://<name>.sharepoint.com`. Write its host into `values.env`, in lowercase: `export MICROSOFT_SHAREPOINT_HOST='<name>.sharepoint.com'`. When the lookup read it, say it in the found facts, and write it the same way.
5. **Okta** is not asked for Microsoft 365. Write `export POLAR_SKY_OKTA_PLANNED='no'` into `values.env`. If the person says their groups live in Okta, say in one line that Polar Sky creates the groups for approved controls in Microsoft Entra ID, and that connecting Okta for Microsoft 365 is not part of this install. Then call `report_issue` with outcome `unanswered_question`.
6. **What Polar Sky monitors** is not a question for Microsoft 365. The plan states it: everything, every SharePoint site and everyone's OneDrive, including ones added later. Say plainly that this includes every person's own OneDrive files. If the person wants less, say that choosing sites is not available for Microsoft 365 yet, and call `report_issue` with outcome `unanswered_question`.
7. **Slack,** as in item 11 of the Google list above.

When Microsoft 365 is already connected, there is no cloud app to create and nothing to upload: the plan checks the connection instead, as [Connect Microsoft 365](microsoft365.md#when-microsoft-365-was-already-connected) says. In On-Prem, the plan still has the engine app, the cluster and the engine.

## Show the final plan

Once the answers are in, write one message with the final plan:

1. **What was found and settled,** in a few lines, so the person can correct it. For example, for Cloud: "You're signed in to Polar Sky as **Acme Corp**, and to Google Cloud as `ana@acme.com`. The project `acme-security` sits in the organization `acme.com`. Your Workspace admin is `admin@acme.com`." For Microsoft 365: "You're signed in to Polar Sky as **Contoso**, and to Azure as `ana@contoso.com`, in the Microsoft 365 tenant **Contoso** (`contoso.com`). You are a Global Administrator, so you can grant admin consent here."
2. **Each stage,** in order, with:
   - what it does, in one line;
   - how long it usually takes;
   - which stages run at the same time;
   - what the person, their super admin or their administrator has to do, and when;
   - for a new cluster, the cost: it runs in the person's cloud account and costs money while it runs, most of it for the GPU nodes. Give no price you have not looked up;
   - what they will have at the end.

   In the Google Workspace stage, say what Polar Sky will monitor, in the words of the answer to question 10: by default "everything: every shared drive, including ones added later, and everyone's personal drive". Say that you save it right after the connection, without asking again, unless they asked for less. Without `get_drive_choice`, say instead that the person chooses in the Polar Sky console after the connection, by ticking the drives.

   For Google Workspace in Cloud, the stages are: turn on the two Google APIs and create the Polar Sky Cloud service account and its key (no cluster, so no cluster cost); the super admin adds the Polar Sky Cloud delegation entry (a few minutes for them); connect Google Workspace with the one-time upload; save what Polar Sky monitors. At the end they have Polar Sky Cloud connected to Google Workspace, monitoring what they chose.

   For Microsoft 365 in Cloud, the stages are: create the Polar Sky Cloud app registration and its service principal, make its certificate on this machine and add the public half to the app, and set its permissions (about 10 minutes, one yes for the stage); admin consent, which you grant here after its own yes, or the administrator grants from your message (a few minutes for them), then a read-only check of the app; connect Microsoft 365 with the one-time upload of the certificate bundle, after its own yes; delete the key file from this machine, after its own yes; and confirm that Polar Sky started reading, which you check yourself, for up to about 15 minutes. There is no cluster, no Okta step and no cost in their cloud. Say what Polar Sky will monitor: everything, every SharePoint site and everyone's OneDrive, including ones added later. Name the administrator's to-do: audit logging on in Microsoft Purview. At the end they have Polar Sky Cloud connected to Microsoft 365 and reading it. When Microsoft 365 is already connected, the plan has only the read-only checks of the app and the saved connection.

   With Okta, in either model of a Google Workspace install, add the Okta stage before the Google Workspace connection: an Okta super admin's short-lived API token, the Okta app, and the read-only Group Push check (10 to 15 minutes). In Cloud it runs while the super admin approves the entry; in On-Prem, while the cluster builds.

   With Slack, in either model, add the optional Slack step last, after what Polar Sky monitors is saved, or for Microsoft 365 after the check that Polar Sky started reading: the person clicks Connect on the Platform page and allows the Polar Sky app in Slack (5 minutes, plus the Slack admin's approval if their Slack needs one). Say the install is done without it.

   For Microsoft 365 in On-Prem, the stages are:
   - create the two app registrations, Polar Sky Cloud and Polar Sky On-Premises, each with its service principal, its certificate made on this machine and its permissions (about 15 minutes, one yes for the stage). It starts right after the plan, so the administrator can grant consent while the cluster builds;
   - admin consent for both apps, which you grant here after its own yes, or the administrator grants from your message (a few minutes for them), then a read-only check of both apps;
   - the cluster and the engine certificate, as for Google Workspace;
   - the engine install with the Microsoft 365 secret, which holds the engine app's key; it waits for the engine app's check;
   - the connection check, with a read-only check that both workers use the engine app;
   - connect Microsoft 365 with the one-time upload of the cloud app's certificate bundle, after its own yes, then delete that key file, after its own yes;
   - confirm that Polar Sky started reading through the engine, which you check yourself, for up to about 15 minutes, then delete the engine app's key file from this machine, after its own yes.

   Say that Polar Sky Cloud reads only people, groups and the audit log, and the engine reads the files, with a key that stays in the cluster. Say what Polar Sky will monitor: everything, every SharePoint site and everyone's OneDrive, including ones added later. Name the administrator's to-do: audit logging on in Microsoft Purview. There is no Okta step. At the end they have the engine in their cluster reading Microsoft 365, connected to Polar Sky Cloud. When Microsoft 365 is already connected, the plan leaves out the cloud app and the upload, and checks the saved connection instead.

   For Google Workspace in On-Prem, the stages are the cluster, the Google service accounts, the engine certificate, the engine, the connection check, and the Google Workspace connection with what Polar Sky monitors. In both On-Prem installs, for a new GKE cluster, name the free preparation steps: turning on the Cloud Billing and Compute Engine APIs in the cluster's project, and the Kubernetes Engine and IAM APIs if the name check in phase 3 needs them. Say which steps run at the same time, as the phase order in [SKILL.md](../SKILL.md#phases) says.

   In either model, add the connection to Polar Sky controls as the last step: the person's AI assistant can then review controls (1 minute, then they sign in with their Polar Sky console account in the browser). In Claude Code, add Polar Sky's skills right after it: Claude Code gets Polar Sky's skills, such as the access review report for auditors (1 minute, nothing for the person to do).

   When the plan has a new project, creating it is the first stage, with its own yes, as [Google identities](google-identities.md#create-a-new-project) says. Name in the plan what the person may still lack for it, as a blocker with its two ways out.
3. **One approval question,** last: "Does this look right? Any changes, or shall I go ahead?"

This is the one plan approval. Each stage still gets its own yes, as in the hard rules in `SKILL.md`, except saving what Polar Sky monitors, connecting to Polar Sky controls and, in Claude Code, adding Polar Sky's skills: the plan's yes covers these, as [Google Workspace](workspace.md#choose-in-the-conversation) and [Done](done.md#connect-your-ai-assistant-to-polar-sky-controls) say. Once the person approves the final plan, start the first stage. Do not ask again for what the plan already settled.
