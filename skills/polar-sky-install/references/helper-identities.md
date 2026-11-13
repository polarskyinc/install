# Optional: helper identities in the customer's own Google Cloud project

**Tell the person:** Polar Sky's AI helpers act through their own Google accounts. By default those accounts live in a Google Cloud project Polar Sky owns, and this step puts them in a project you own instead, so you see and control them. Google Drive still treats them as outside your Workspace, so a Shared Drive that blocks outside sharing has to allow it before a helper can read there.

Run this step only when the person asks for it, or when the install plan has it. It is not needed for the install to work, and it comes after the install is done. It is for Google Workspace, in both models. It changes nothing for helpers that already exist: they keep the account they have, and only new helpers are created in the new project.

It needs three kinds of rights. Ask who has them before you start:

- **Create a project** (Project Creator, and Billing Account User to link billing). Not needed when the project already exists.
- **Change an organization policy** (Organization Policy Administrator, `roles/orgpolicy.policyAdmin`). The role is granted on the Google Cloud organization only, not on a folder or the project (Google refuses it there), and is almost always held by the organization administrators rather than the person you are talking to.
- **Create roles and grant them in the project** (Owner, or Role Administrator together with Project IAM Admin).

A Google Workspace super admin is needed for one more thing at the end: the ceiling checker's delegation entry.

## Look first

Use the gcloud account the person confirmed in the final plan, or ask which one to use. Call `get_helper_identity_values` (read only). It gives:

- `provisioner_service_account` and `worker_service_account`: the two Polar Sky service accounts that each get one role in the project. The provisioner creates helper accounts. The worker reads as them and withdraws them when a helper is revoked;
- `workspace_customer_id`: Polar Sky's Google Workspace customer ID, which the project's organization policy must allow;
- `apis_to_enable`, `role_grants` (two roles, each with its `role_id`, `title` and `permissions`) and `organization_policies`: the exact setup, which the sections below use;
- `registered_project_id`: the project already recorded for this organization, or null;
- `delegation_link`, `delegation_client_id` and `delegation_scopes`, only when Polar Sky has already set up this organization's ceiling checker.

If `registered_project_id` is set, tell the person which project it is and ask whether to keep it. If they want another, go on and register the new one at the end: it replaces the old one for new helpers.

Write what you need into `values.env`, copying each value exactly:

```bash
export HELPER_IDENTITY_PROJECT_ID='<the project ID>'
export POLAR_SKY_PROVISIONER_ACCOUNT='<provisioner_service_account>'
export POLAR_SKY_WORKER_ACCOUNT='<worker_service_account>'
export POLAR_SKY_WORKSPACE_CUSTOMER_ID='<workspace_customer_id>'
```

## Pick the project

Recommend a project of its own for the helper accounts, for example `<company>-polar-sky-helpers`. Say why in one sentence: this project switches off service account keys, and the project that holds Polar Sky's own integration key should not.

Ask whether they have a project in mind or want a new one. For an existing project, check it exists and that the active account can see it (read only):

```bash
gcloud projects describe "${HELPER_IDENTITY_PROJECT_ID}" --format='value(lifecycleState,parent.type,parent.id)'
```

For a new project, show this command and ask once, as in [Create a new project](google-identities.md#create-a-new-project), with `HELPER_IDENTITY_PROJECT_ID` in place of `GOOGLE_CLOUD_PROJECT_ID`:

```bash
gcloud projects create "${HELPER_IDENTITY_PROJECT_ID}" --folder="<folder id>"
```

For a project directly under the organization, use `--organization="<organization id>"` in place of `--folder`. If Google refuses for lack of permission, stop and call `report_issue` with step `other` and outcome `blocked`. Tell the person to ask their Google Cloud administrator for the Project Creator role, or to create the project for them.

## The plan to show

Show the whole setup in one message, with the commands of the next three sections filled in, and ask "Does this look right?" One yes covers all of them. Say plainly which commands need which rights:

- turning on APIs, creating the two roles and granting them need Owner on the project, or Role Administrator together with Project IAM Admin;
- the organization policy commands need Organization Policy Administrator. If the person does not have it, say so now and offer the message in [If you cannot change the organization policy](#if-you-cannot-change-the-organization-policy).

## Turn on the APIs

```bash
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com drive.googleapis.com orgpolicy.googleapis.com --project="${HELPER_IDENTITY_PROJECT_ID}"
```

This turns on the Google services Polar Sky uses to create the helper accounts, to act as them, and to read Drive as them. A helper reads Drive with its own token and no separate quota project, so without the Drive API in this project its first read is refused with a 403.
The Organization Policy API is what the `gcloud org-policies` commands in the next section go through; without it they stop with "API [orgpolicy.googleapis.com] not enabled on project" before any policy is read or set.

## Organization policies

Three policies, set on this project only. The first one exists so that Polar Sky's accounts may hold a role inside the customer's project, and a project that has no such restriction needs nothing. Read the effective policy (read only):

```bash
gcloud org-policies describe iam.allowedPolicyMemberDomains --project="${HELPER_IDENTITY_PROJECT_ID}" --effective
```

If the effective policy is not set, or lists no allowed values, the project accepts Polar Sky's accounts as they are: skip the rest of this policy and say so. If it lists allowed values, the project refuses accounts from other organizations, and Polar Sky's customer ID has to be added to its allowed values.

Setting a policy replaces the project's own policy for the constraint as a whole. Never replace one that already exists. First read the project's own policy, not the effective one (read only):

```bash
gcloud org-policies describe iam.allowedPolicyMemberDomains --project="${HELPER_IDENTITY_PROJECT_ID}"
```

**A fresh project with no policy of its own.** Google answers that the policy was not found. Replacement is safe here, because there is nothing to lose. Set it, keeping what the project inherits from its parent:

```bash
cat > ~/polar-sky-install/helper-allowed-domains.yaml <<EOF
name: projects/${HELPER_IDENTITY_PROJECT_ID}/policies/iam.allowedPolicyMemberDomains
spec:
  inheritFromParent: true
  rules:
  - values:
      allowedValues:
      - ${POLAR_SKY_WORKSPACE_CUSTOMER_ID}
EOF
gcloud org-policies set-policy ~/polar-sky-install/helper-allowed-domains.yaml
```

**A project that already has a policy of its own.** Merge, do not replace. Save the existing policy to a file, add Polar Sky's customer ID to its allowed values, and set the edited file:

```bash
gcloud org-policies describe iam.allowedPolicyMemberDomains --project="${HELPER_IDENTITY_PROJECT_ID}" > ~/polar-sky-install/helper-allowed-domains.yaml
```

Open that file and add one line, `- <POLAR_SKY_WORKSPACE_CUSTOMER_ID>`, under the `allowedValues:` list of the rule that already lists allowed values. If the policy has no rule with `allowedValues`, add the rule the fresh-project example shows and keep every other rule. Keep every existing value, every other rule, every condition, and `inheritFromParent` as it is. Show the person the edited file before you set it, and name the one value you added. Then set it:

```bash
gcloud org-policies set-policy ~/polar-sky-install/helper-allowed-domains.yaml
```

If the existing policy cannot be edited this way, for example because a rule has a condition you cannot read, do not set anything. Follow [If you cannot change the organization policy](#if-you-cannot-change-the-organization-policy) and let their administrator make the change.

Then switch off service account keys in the project, so nothing can take a copy of a helper's account:

```bash
for constraint in iam.managed.disableServiceAccountKeyCreation iam.managed.disableServiceAccountKeyUpload; do
cat > ~/polar-sky-install/helper-${constraint##*.}.yaml <<EOF
name: projects/${HELPER_IDENTITY_PROJECT_ID}/policies/${constraint}
spec:
  rules:
  - enforce: true
EOF
gcloud org-policies set-policy ~/polar-sky-install/helper-${constraint##*.}.yaml
done
```

If Google answers that the account lacks `orgpolicy.policy.set`, the person does not have the rights. Stop here and follow [If you cannot change the organization policy](#if-you-cannot-change-the-organization-policy). Google can take a few minutes to apply a policy change.

## Create and grant the two roles

Do this after the organization policy, because a project that restricts who may hold a role refuses Polar Sky's accounts until its policy allows them.

There are two grants: the provisioner and the worker each get one role on this project. They are the same two roles Polar Sky's own helper project gives them, narrowed to the few rights each needs. Neither is Service Account Admin, which would be wider. Take the permission lists from `role_grants` exactly as the tool returned them. The usual values are below.

The provisioner creates helper accounts and sets who may act as each one. It also deletes the throwaway account used when the project is registered:

```bash
gcloud iam roles create charterIdentityProvisioner --project="${HELPER_IDENTITY_PROJECT_ID}" --title="Charter identity provisioner" --stage=GA --permissions=iam.serviceAccounts.create,iam.serviceAccounts.get,iam.serviceAccounts.getIamPolicy,iam.serviceAccounts.setIamPolicy,iam.serviceAccounts.delete
```

```bash
gcloud projects add-iam-policy-binding "${HELPER_IDENTITY_PROJECT_ID}" --member="serviceAccount:${POLAR_SKY_PROVISIONER_ACCOUNT}" --role="projects/${HELPER_IDENTITY_PROJECT_ID}/roles/charterIdentityProvisioner" --condition=None
```

The worker withdraws a helper: it removes the right to act as its account, disables the account and deletes it.

```bash
gcloud iam roles create charterIdentityRevoker --project="${HELPER_IDENTITY_PROJECT_ID}" --title="Charter identity revoker" --stage=GA --permissions=iam.serviceAccounts.get,iam.serviceAccounts.getIamPolicy,iam.serviceAccounts.setIamPolicy,iam.serviceAccounts.disable,iam.serviceAccounts.delete
```

```bash
gcloud projects add-iam-policy-binding "${HELPER_IDENTITY_PROJECT_ID}" --member="serviceAccount:${POLAR_SKY_WORKER_ACCOUNT}" --role="projects/${HELPER_IDENTITY_PROJECT_ID}/roles/charterIdentityRevoker" --condition=None
```

If `roles create` answers that the role already exists, an earlier run made it: check its permissions against `role_grants` with `gcloud iam roles describe <role id> --project="${HELPER_IDENTITY_PROJECT_ID}"` and, if they differ, fix them with `gcloud iam roles update <role id> --project="${HELPER_IDENTITY_PROJECT_ID}" --permissions=<the list>`. A role that was deleted less than a week ago must be undeleted first.

Neither role gives Polar Sky anything else in the project or reaches the rest of the customer's Google Cloud. Polar Sky gives its worker the right to act as each helper account when it creates the account, so the customer grants nothing for that. Without the worker's role, a helper cannot be withdrawn: revoking it would fail and its account would stay.

## Register the project

Ask for the person's yes in a message of its own, saying what will happen: Polar Sky creates one throwaway account in the project, binds its worker to it, deletes it again and, if all three work, records the project as the home of new helpers. Then call `register_helper_identity_project` with `project_id` set to `HELPER_IDENTITY_PROJECT_ID`. It takes up to a minute.

When it answers `registered` true, tell the person the project is recorded, that new helpers are created there from now on, and that helpers they already have are unchanged.

When it is refused, it names the step and gives Google's reason. Nothing was recorded. Fix it and call it again:

| `failed_step` | What it means | Fix |
| --- | --- | --- |
| `create_service_account` | Polar Sky's provisioner may not create accounts in the project. | Check that the project ID is right, that `iam.googleapis.com` is on, and that the `charterIdentityProvisioner` role was created and granted to the provisioner account. Roles take a few minutes to apply: wait two minutes and try again before you change anything. |
| `grant_token_creator` | Polar Sky could not give its worker the right to act as the new account. | The project's organization policy refuses accounts from other organizations: check [Organization policies](#organization-policies), and that `iamcredentials.googleapis.com` is on. A policy change can take a few minutes to apply. |
| `delete_service_account` | Polar Sky could not delete its throwaway account. | The `charterIdentityProvisioner` role lacks `iam.serviceAccounts.delete`: compare it with `role_grants`. The person can delete a leftover account named `polar-sky-probe-` followed by eight characters. |

When the answer has the `reason` `helper_provisioning_unavailable` and no step, Polar Sky's helper provisioner did not answer. Helpers may not be switched on for this organization yet. Call `report_issue` with step `other` and outcome `blocked`, and tell the person Polar Sky needs to switch helpers on first.

Call `report_issue` with step `other` for any other refusal you cannot fix, as in [Report issues](../SKILL.md#report-issues).

## If you cannot change the organization policy

When the person lacks the organization policy rights, write a message for them to forward to their Google Cloud organization administrator. Fill in every value:

```text
Hello,

We are setting up Polar Sky's AI helpers so they act through Google accounts in a project we own,
which we own and control. Please set these organization policies on the
project <HELPER_IDENTITY_PROJECT_ID> (Organization Policy Administrator on our Google Cloud organization is needed; the role cannot be granted on a folder or the project itself):

1. If iam.allowedPolicyMemberDomains is enforced for the project, add this Google Workspace customer ID
   to its allowed values and keep inheriting from the parent: <POLAR_SKY_WORKSPACE_CUSTOMER_ID>
   (This is Polar Sky's customer ID. Without it, the project cannot give Polar Sky's accounts a role.)
2. Enforce iam.managed.disableServiceAccountKeyCreation on the project.
3. Enforce iam.managed.disableServiceAccountKeyUpload on the project.

Thank you.
```

Say the setup waits for them, and that the rest of the install is not affected. Go on with the other commands only when they tell you it is done.

## The ceiling checker's delegation entry

Only when `get_helper_identity_values` gave a `delegation_link`. The ceiling checker is the separate identity Polar Sky uses to check that the person a helper acts for can still open each approved folder. A Google Workspace super admin adds its entry, and the link opens the Admin console's dialog with its client ID and scopes already filled in.

Give the person the link exactly as it was returned. Tell them to open it while signed in as a super admin, check the client ID (`delegation_client_id`) and the scopes (`delegation_scopes`), and click **Authorize**. If the link does not open the dialog, give the entry to add by hand under **Security** > **Access and data control** > **API controls** > **Domain-wide delegation** > **Manage all**, with the scopes as one line, comma-separated, no spaces. Add this warning:

> **Important:** The link and an edit by hand both replace the entry's whole scope list. This client ID belongs to Polar Sky's ceiling checker, so its entry should hold exactly these scopes.

Google can take up to 24 hours to apply it, though it is often minutes.

When there is no `delegation_link`, say the ceiling checker is not set up for this organization yet, and that Polar Sky will send the entry when helpers are switched on.

## Finish

Tell the person, in plain words: the project (`HELPER_IDENTITY_PROJECT_ID`) holds the accounts of new helpers, Polar Sky's provisioner and worker service accounts have one role each in that project and nowhere else, service account keys are switched off there, and helpers that already exist did not change. Then go back to what the person was doing.
