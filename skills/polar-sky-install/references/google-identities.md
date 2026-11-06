# Phase 4: Google identities and delegation

**Tell the person:** Polar Sky reads files, sharing and permissions through Google service accounts that a Workspace super admin approves. No one's password is used, and each account gets only the access in its delegation entry. A Cloud install needs one account; an On-Prem install needs two.

Polar Sky reads Google Workspace through Google service accounts in the customer's own project (`GOOGLE_CLOUD_PROJECT_ID`):

| Service account | Used by | Key | Models |
| --- | --- | --- | --- |
| `polar-sky-cloud-integration` | Polar Sky Cloud | A JSON key, uploaded once to Polar Sky in phase 9, then deleted | Both |
| `polar-sky-on-prem-dpe` | The engine in the cluster | A JSON key, which goes only into the cluster | On-Prem only |

Use the gcloud account and project the person confirmed in the final plan. The account needs to create service accounts, keys and service-account IAM bindings in the project, and to enable APIs. When `GOOGLE_CLOUD_ACCOUNT` is in `values.env`, a second Google account creates the service accounts: add `--account="${GOOGLE_CLOUD_ACCOUNT}"` at the end of every gcloud command in this stage, so the active account, which the cluster uses, stays as it is. The one exception is a new project that holds both the cluster and the service accounts, as [Create a new project](#create-a-new-project) says. Turn on only the APIs that phase 2 found off.

Even right after the final plan's yes, show this stage's commands and ask again. This stage needs only the project, not the cluster, so start it as soon as the plan is approved, before or during the cluster build in On-Prem. Its plan: turn on two APIs, create the service accounts and their key files, then prepare the super admin's request. In Cloud that is one service account and one key. Show it in one message and ask "Does this look right?" That one yes covers every command below except where it says otherwise.

## Create a new project

Only when the final plan has a new project. Creating it is a stage of its own, with its own yes, before anything else in this file: show the commands and ask. Do this for each new project in the plan: `GOOGLE_CLOUD_PROJECT_ID`, `CLUSTER_PROJECT_ID`, or both when the plan has two new projects; the commands below show the first. First check whether the project is already there, from an earlier, stopped install. If this prints `ACTIVE` with the folder or organization from the plan, and the person confirms it is the project from that earlier install, skip the create. If it sits elsewhere, or the person does not know it, it is someone else's project: ask for another ID. An error that the project is not found, or that you may not see it, is the normal answer for a new project, not a failure: go on and create it. The `--account` rule above is for a project that holds only the service accounts. Create and link any project that holds the cluster with the active account, which the cluster uses, even when it also holds the service accounts. When one new project holds both, the active account creates it and becomes its owner: leave out `--account` in every command of this file, including the service account commands below.

```bash
gcloud projects describe "${GOOGLE_CLOUD_PROJECT_ID}" --format='value(lifecycleState,parent.type,parent.id)'
```

```bash
gcloud projects create "${GOOGLE_CLOUD_PROJECT_ID}" --folder="<folder id>"
```

For a project directly under the organization, use `--organization="<organization id>"` in place of `--folder`. A project ID has 6 to 30 characters: lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen, and no other project in Google Cloud may use it. If Google answers that the ID is in use, ask the person for another, and write it into `values.env`. When the new project holds the cluster, link the billing account the person chose in the same stage:

```bash
gcloud billing projects link "${CLUSTER_PROJECT_ID}" --billing-account="<billing account id>"
```

If Google refuses to create the project or link billing for lack of permission, stop and call `report_issue`, outcome `blocked`. Tell the person the two ways out from the plan: use an existing project, or ask their Google Cloud administrator for the Project Creator role (or Billing Account User for billing) or to do this step for them.

## Enable the APIs

```bash
gcloud services enable admin.googleapis.com drive.googleapis.com --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

This turns on the Admin SDK and Google Drive APIs in the project.

## When the service accounts already exist

If `service-accounts create` answers that the account already exists (an earlier, stopped install), or the person tells you it exists, keep it: save its email and client ID as below, and do not create a second one. When the person told you first, do not run `create`: write the account's email into `values.env` as below (`<account name>@<project>.iam.gserviceaccount.com`), then read its client ID with the read-only `describe` command in [Delegation entries](#delegation-entries), which also shows the account exists. For its key:

- If the person still has the key file from that install, they move it into the install folder under the name below. Check it belongs to the account without showing the private key: this prints only two public fields of the file, and Google's list of the account's keys, which must include that key ID and show it not disabled.

  ```bash
  cd ~/polar-sky-install && grep -oE '"(client_email|private_key_id)": *"[^"]*"' <key file> && gcloud iam service-accounts keys list --iam-account="<account email>" --managed-by=user --project="${GOOGLE_CLOUD_PROJECT_ID}" --format='value(name.basename(),disabled)'
  ```

- If they don't have it, create a new key as below, and tell them the old key stays active until their administrator deletes it.

If a key file is already in the install folder, never create a key over it: check it as above, or ask the person.

A kept account still needs its delegation entry checked, even when the person says the super admin already approved it. The entry may come from an earlier install of the other model, and the two models put different scopes on each entry: in Cloud, Polar Sky Cloud's entry also holds `drive.readonly` and `drive`; in On-Prem, it must not. So the super admin's request stays in this stage's plan. In that plan, show each entry's client ID and its full scope line for the chosen model (`POLAR_SKY_CLOUD_SCOPES`, and in On-Prem `POLAR_SKY_ON_PREM_SCOPES`), and say the entry must have every scope in this line. When only Polar Sky uses the account, which is the usual case, recommend that the super admin opens the link from [Delegation entries](#delegation-entries) and clicks **Authorize** again: it sets exactly this line, and doing it again does no harm. If they would rather check by hand, they compare the entry in the Admin console with the line, and in On-Prem they also make sure Polar Sky Cloud's entry has no `drive.readonly` or `drive`. If the person says something else also uses the account, do not recommend the link: the super admin adds the missing scopes by hand and keeps the ones the other use still needs. In On-Prem, if that other use needs `drive.readonly` or `drive` on Polar Sky Cloud's account, use a new account instead, as below. This is part of the stage's one "Does this look right?", not a new yes.

If the person does not trust an existing account, or cannot use it, they may choose a new account with another name instead; never delete the old one without its own yes, since something may still use it. Google needs 6 to 30 characters: lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen. Check the name before you run anything. Then use it in place of `polar-sky-on-prem-dpe` or `polar-sky-cloud-integration` in every command and `values.env` line below, so the account email becomes `<new name>@<project>.iam.gserviceaccount.com`. Later steps read the emails from `values.env`, so nothing after this stage changes. Report it with `report_issue`, outcome `worked_around`.

## Cloud service account and its key

Show both commands, say they create one service account and one key file, and run them:

```bash
gcloud iam service-accounts create polar-sky-cloud-integration --display-name="Polar Sky Cloud" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

```bash
cd ~/polar-sky-install && umask 077 && gcloud iam service-accounts keys create cloud-key.json --iam-account="polar-sky-cloud-integration@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

Google can take a minute before a new service account can get a key. Before each `keys create`, wait until the account is readable (read only), and if `keys create` still answers `NOT_FOUND`, delete the empty key file it left (`[ ! -s <file> ] && rm <file>`) and try again after a minute:

```bash
for attempt in 1 2 3 4 5 6; do gcloud iam service-accounts describe "<account email>" --project="${GOOGLE_CLOUD_PROJECT_ID}" --format='value(email)' && break; sleep 10; done
```

The key goes straight into `cloud-key.json`. Never open, print or send this file, and never pass it to a tool or the chat. In phase 9 it goes to Polar Sky once, uploaded with the one-time `curl` command from `start_key_upload`, and then you delete it. If Google refuses to create the key because of an organization policy (`iam.disableServiceAccountKeyCreation`), stop. Tell the person their organization blocks service account keys, and that their Google Cloud administrator must allow a key for this service account, or they contact Polar Sky.

Add to `values.env`:

```bash
export GOOGLE_CLOUD_SERVICE_ACCOUNT='polar-sky-cloud-integration@<project>.iam.gserviceaccount.com'
```

## On-premises service account and its key

On-Prem only. Skip this section in a Cloud install.

Show both commands, say they create one service account and one key file, and run them:

```bash
gcloud iam service-accounts create polar-sky-on-prem-dpe --display-name="Polar Sky On-Premises" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

```bash
cd ~/polar-sky-install && umask 077 && gcloud iam service-accounts keys create on-prem-key.json --iam-account="polar-sky-on-prem-dpe@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

Google can take a minute before a new service account can get a key. Before each `keys create`, wait until the account is readable (read only), and if `keys create` still answers `NOT_FOUND`, delete the empty key file it left (`[ ! -s <file> ] && rm <file>`) and try again after a minute:

```bash
for attempt in 1 2 3 4 5 6; do gcloud iam service-accounts describe "<account email>" --project="${GOOGLE_CLOUD_PROJECT_ID}" --format='value(email)' && break; sleep 10; done
```

The key goes straight into `on-prem-key.json`. Never open, print or send this file. It goes only into the cluster, in phase 6.

If Google refuses to create the key because of an organization policy (`iam.disableServiceAccountKeyCreation`), stop. Tell the person their organization blocks service account keys, and that their Google Cloud administrator must allow a key for these two service accounts, or they contact Polar Sky.

Add to `values.env`:

```bash
export GOOGLE_ON_PREM_SERVICE_ACCOUNT='polar-sky-on-prem-dpe@<project>.iam.gserviceaccount.com'
export GOOGLE_ONPREM_KEY_FILE="$HOME/polar-sky-install/on-prem-key.json"
```

## Delegation entries

Get the Polar Sky Cloud account's numeric client ID (read only, public):

```bash
gcloud iam service-accounts describe "${GOOGLE_CLOUD_SERVICE_ACCOUNT}" --format='value(oauth2ClientId)' --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

On-Prem only, also get the engine account's client ID:

```bash
gcloud iam service-accounts describe "${GOOGLE_ON_PREM_SERVICE_ACCOUNT}" --format='value(oauth2ClientId)' --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

Write them into `values.env` as `GOOGLE_CLOUD_CLIENT_ID` and, in On-Prem, `GOOGLE_ON_PREM_CLIENT_ID`. Never read a client ID from a key file.

A Google Workspace super admin adds the entries in the Google Admin console. Make a link for each entry that opens the console's "Add a new client ID" dialog with the client ID and scopes already filled in (read only).

Cloud: one link, for Polar Sky Cloud's entry:

```bash
. ~/polar-sky-install/values.env && enc() { printf '%s' "$1" | sed 's/:/%3A/g; s#/#%2F#g; s/,/%2C/g'; } && echo "https://admin.google.com/ac/owl/domainwidedelegation?clientIdToAdd=${GOOGLE_CLOUD_CLIENT_ID}&clientScopeToAdd=$(enc "${POLAR_SKY_CLOUD_SCOPES}")&overwriteClientId=true"
```

On-Prem: two links, one for each entry:

```bash
. ~/polar-sky-install/values.env && enc() { printf '%s' "$1" | sed 's/:/%3A/g; s#/#%2F#g; s/,/%2C/g'; } && echo "https://admin.google.com/ac/owl/domainwidedelegation?clientIdToAdd=${GOOGLE_CLOUD_CLIENT_ID}&clientScopeToAdd=$(enc "${POLAR_SKY_CLOUD_SCOPES}")&overwriteClientId=true" && echo "https://admin.google.com/ac/owl/domainwidedelegation?clientIdToAdd=${GOOGLE_ON_PREM_CLIENT_ID}&clientScopeToAdd=$(enc "${POLAR_SKY_ON_PREM_SCOPES}")&overwriteClientId=true"
```

The super admin opens each link signed in to the Admin console, checks the client ID and scopes in the dialog, and clicks **Authorize**. Give the links and, as the fallback if a link does not open the dialog, the entries with the exact values to add by hand under **Security** > **Access and data control** > **API controls** > **Domain-wide delegation** > **Manage all**.

Cloud:

| Entry | Client ID | Scopes (one line, comma-separated, no spaces) |
| --- | --- | --- |
| Polar Sky Cloud | `GOOGLE_CLOUD_CLIENT_ID` | `POLAR_SKY_CLOUD_SCOPES` |

On-Prem:

| Entry | Client ID | Scopes (one line, comma-separated, no spaces) |
| --- | --- | --- |
| Polar Sky Cloud | `GOOGLE_CLOUD_CLIENT_ID` | `POLAR_SKY_CLOUD_SCOPES` |
| Polar Sky On-Premises | `GOOGLE_ON_PREM_CLIENT_ID` | `POLAR_SKY_ON_PREM_SCOPES` |

Show the real values, not the names. There are no optional scopes: every scope the install uses is on an entry, and each item in the `scopes` list of `get_install_values` says which one in `required_for`.

- **Cloud:** Polar Sky Cloud's entry is the only entry. It holds Polar Sky Cloud's scopes plus `drive.readonly` and `drive`, because Polar Sky Cloud reads file content and applies the access changes the team approves. Give the full line from `POLAR_SKY_CLOUD_SCOPES`, as one line.
- **On-Prem:** the engine's entry holds the Drive content scopes so that Polar Sky Cloud never needs them. Polar Sky Cloud's entry must not list `drive.readonly` or `drive`.

`admin.directory.group` is on Polar Sky Cloud's line, because the Polar Sky Cloud key is what writes groups. It stays on the line even when the organization does not need it today. The `scopes` item for it has `needed_now` and `needed_now_reason`. If `needed_now` is false, say what `needed_now_reason` says, in one plain sentence: "Polar Sky does not use it with your current settings. It is on the line so a later change to group settings needs no second admin visit." If `needed_now` is true, say Polar Sky uses it today. Do not call it optional, and do not drop it from the line.

Always add this warning:

> **Important:** Each link replaces any existing entry for that client ID with exactly these scopes, and editing an entry by hand also replaces its entire scope list. These client IDs belong to Polar Sky's own service accounts, so their entries should hold exactly these lines, and the link is the safe way to set them. Only if a client ID is also used by something else, and its entry has other scopes that still need to stay, add them by hand instead.

Also say: the Workspace admin Polar Sky acts as (`GOOGLE_WORKSPACE_ADMIN_EMAIL`) needs the **Reports** privilege.

## What each entry lets Polar Sky do

A super admin should know what they approve. In the message, under each entry, give one plain line per scope in that entry: its `purpose` from the `scopes` list of `get_install_values`. Never write your own explanation. For `admin.directory.group`, also give its `needed_now_reason`, as above. For `drive`, also say: before a change in a shared drive, Polar Sky may add the Workspace admin as a manager of that drive, because only managers can change sharing there; that membership stays.

In On-Prem, Polar Sky Cloud's entry has no scope that reaches file content. Only the engine, which runs in the company's own cloud, can read content and change sharing, and it changes sharing only when the team approves a control.

In Cloud, Polar Sky Cloud's entry holds the two content scopes, so Polar Sky Cloud reads file content itself and makes the approved access changes. Nothing runs in the customer's cloud.

## Send the request and keep going

Google can take up to 24 hours to apply delegation changes, though it is often minutes. Nothing waits on this until connecting Google Workspace, where Polar Sky tests each scope. Say so. In On-Prem, recommend going on: "I recommend getting the engine's certificate and installing the engine meanwhile." In Cloud, there is nothing else to run, so say that the connection waits for the entry.

If the person is a super admin, they can open the links now. If not, write a message for them to forward to the super admin they named. Fill in every value, with the links in full and the scope lines from [What each entry lets Polar Sky do](#what-each-entry-lets-polar-sky-do).

Cloud:

```text
Hello,

We are installing Polar Sky. Please add one domain-wide delegation entry in the Google Admin console.
Open the link while signed in as a super admin, check the client ID and scopes, and click Authorize:

1. <link for GOOGLE_CLOUD_CLIENT_ID>

What the entry lets Polar Sky do (Polar Sky Cloud reads file content and makes the access changes our team approves):
   - <one line per scope in POLAR_SKY_CLOUD_SCOPES>

If the link does not open the dialog, add the entry by hand
(Security > Access and data control > API controls > Domain-wide delegation > Manage all):

   Client ID: <GOOGLE_CLOUD_CLIENT_ID>
   Scopes: <POLAR_SKY_CLOUD_SCOPES>

Each link, and each edit by hand, replaces the entry's entire scope list, so if the client ID already has
an entry, keep every scope it needs.

Please also make sure <GOOGLE_WORKSPACE_ADMIN_EMAIL> has the Reports admin privilege.

Thank you.
```

On-Prem:

```text
Hello,

We are installing Polar Sky. Please add two domain-wide delegation entries in the Google Admin console.
Open each link while signed in as a super admin, check the client ID and scopes, and click Authorize:

1. <link for GOOGLE_CLOUD_CLIENT_ID>
2. <link for GOOGLE_ON_PREM_CLIENT_ID>

What each entry lets Polar Sky do:

1. Polar Sky Cloud (no access to file content):
   - <one line per scope in POLAR_SKY_CLOUD_SCOPES>
2. Polar Sky engine, which runs in our own cloud:
   - <one line per scope in POLAR_SKY_ON_PREM_SCOPES>

If a link does not open the dialog, add the entries by hand
(Security > Access and data control > API controls > Domain-wide delegation > Manage all):

1. Client ID: <GOOGLE_CLOUD_CLIENT_ID>
   Scopes: <POLAR_SKY_CLOUD_SCOPES>

2. Client ID: <GOOGLE_ON_PREM_CLIENT_ID>
   Scopes: <POLAR_SKY_ON_PREM_SCOPES>

Each link, and each edit by hand, replaces the entry's entire scope list, so if a client ID already has
an entry, keep every scope it needs.

Please also make sure <GOOGLE_WORKSPACE_ADMIN_EMAIL> has the Reports admin privilege.

Thank you.
```

Ask the person to tell you when the super admin has added the entries, and go on with the next step meanwhile.
