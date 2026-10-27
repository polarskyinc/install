# Phase 4: Google identities and delegation

Polar Sky reads Google Workspace through two Google service accounts in the customer's own project (`GOOGLE_CLOUD_PROJECT_ID`):

| Service account | Used by | Key |
| --- | --- | --- |
| `polar-sky-on-prem-dpe` | The engine in the cluster | A JSON key, which goes only into the cluster |
| `polar-sky-cloud-integration` | Polar Sky Cloud | No key when keyless is allowed; otherwise a JSON key the person uploads in the console |

Show the active gcloud account (`gcloud config get-value account`) and ask the person to confirm it is the one to use. They need to create service accounts, keys and service-account IAM bindings in the project, and to enable APIs.

## Enable the APIs

```bash
gcloud services enable admin.googleapis.com drive.googleapis.com iamcredentials.googleapis.com --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

This turns on the Admin SDK, Google Drive and IAM Credentials APIs in the project. Run it after a yes.

## On-premises service account and its key

Show both commands, say they create one service account and one key file, and run them after a yes:

```bash
gcloud iam service-accounts create polar-sky-on-prem-dpe --display-name="Polar Sky On-Premises" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

```bash
cd ~/polar-sky-install && umask 077 && gcloud iam service-accounts keys create on-prem-key.json --iam-account="polar-sky-on-prem-dpe@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

The key goes straight into `on-prem-key.json`. Never open, print or send this file. It goes only into the cluster, in phase 6.

If Google refuses to create the key because of an organization policy (`iam.disableServiceAccountKeyCreation`), stop. Tell the person their organization blocks service account keys, and that their Google Cloud administrator must allow a key for this one service account, or they contact Polar Sky.

Add to `values.env`:

```bash
export GOOGLE_ON_PREM_SERVICE_ACCOUNT='polar-sky-on-prem-dpe@<project>.iam.gserviceaccount.com'
export GOOGLE_ONPREM_KEY_FILE="$HOME/polar-sky-install/on-prem-key.json"
```

## Cloud service account: keyless or key

### Check the organization policy first

If `values.env` has no `POLAR_SKY_SIGNER_PRINCIPAL`, Polar Sky does not offer keyless yet. Skip this check and use the [key fallback](#key-fallback).

Polar Sky signs as the cloud service account through Google's IAM Credentials API, so no key is needed. For that, the project must allow Polar Sky's signer group as an IAM member. Read the policy (read only):

```bash
gcloud resource-manager org-policies describe constraints/iam.allowedPolicyMemberDomains --effective --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

| What it shows | Meaning | Path |
| --- | --- | --- |
| No `listPolicy`, an empty `listPolicy: {}`, or `allValues: ALLOW` | No restriction | Keyless |
| `allowedValues:` with a list | Only members of the listed Google customer IDs are allowed. You cannot tell from the list alone whether Polar Sky's group is one of them | Try keyless once; the grant below shows the answer |
| `allValues: DENY`, or an error that you may not read the policy | Restricted, or unknown | Ask the person; if they cannot find out, use the key fallback |

Tell the person which path you will take and why.

### Keyless

Show these, say they create the service account and let only Polar Sky's signer group sign as this one account (not the project), and run them after a yes:

```bash
gcloud iam service-accounts create polar-sky-cloud-integration --display-name="Polar Sky Cloud" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

```bash
gcloud iam service-accounts add-iam-policy-binding "polar-sky-cloud-integration@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com" --member="${POLAR_SKY_SIGNER_PRINCIPAL}" --role='roles/iam.serviceAccountTokenCreator' --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

If the grant fails with a message that a member does not belong to a permitted customer, the organization policy blocks keyless. Tell the person and use the key fallback. Any other error: stop and explain.

Add to `values.env`:

```bash
export GOOGLE_CLOUD_SERVICE_ACCOUNT='polar-sky-cloud-integration@<project>.iam.gserviceaccount.com'
export GOOGLE_CLOUD_ACCESS='keyless'
```

### Key fallback

Create the service account as above if it is not there yet (`gcloud iam service-accounts create polar-sky-cloud-integration ...`). Do not add the signer group grant. Then, after a yes:

```bash
cd ~/polar-sky-install && umask 077 && gcloud iam service-accounts keys create cloud-key.json --iam-account="polar-sky-cloud-integration@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

The person uploads `cloud-key.json` in the Polar Sky console in phase 8. Never open it, print it, or pass it to a tool or the chat.

Add to `values.env` the same `GOOGLE_CLOUD_SERVICE_ACCOUNT` line, and `export GOOGLE_CLOUD_ACCESS='key'`.

## Delegation entries

Get each account's numeric client ID (read only, public):

```bash
gcloud iam service-accounts describe "${GOOGLE_CLOUD_SERVICE_ACCOUNT}" --format='value(oauth2ClientId)' --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

```bash
gcloud iam service-accounts describe "${GOOGLE_ON_PREM_SERVICE_ACCOUNT}" --format='value(oauth2ClientId)' --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

Write them into `values.env` as `GOOGLE_CLOUD_CLIENT_ID` and `GOOGLE_ON_PREM_CLIENT_ID`. Never read a client ID from a key file.

A Google Workspace super admin adds two entries in the [Google Admin console](https://admin.google.com/): **Security** > **Access and data control** > **API controls** > **Domain-wide delegation** > **Manage all**. Give them both entries with the exact values, one per client ID:

| Entry | Client ID | Scopes (one line, comma-separated, no spaces) |
| --- | --- | --- |
| Polar Sky Cloud | `GOOGLE_CLOUD_CLIENT_ID` | `POLAR_SKY_CLOUD_SCOPES` |
| Polar Sky On-Premises | `GOOGLE_ON_PREM_CLIENT_ID` | `POLAR_SKY_ON_PREM_SCOPES` |

Show the real values, not the names. Always add this warning:

> **Important:** Editing an existing delegation entry replaces its entire scope list. If a client ID already has an entry, enter every scope it needs again. Never paste only the new scope.

Also say: the Workspace admin Polar Sky acts as (`GOOGLE_WORKSPACE_ADMIN_EMAIL`) needs the **Reports** privilege, and Google can take up to 24 hours to apply delegation changes.

If the person is not a super admin, write them a message to forward. Fill in every value:

```text
Hello,

We are installing Polar Sky. Please add two domain-wide delegation entries in the Google Admin console
(Security > Access and data control > API controls > Domain-wide delegation > Manage all):

1. Client ID: <GOOGLE_CLOUD_CLIENT_ID>
   Scopes: <POLAR_SKY_CLOUD_SCOPES>

2. Client ID: <GOOGLE_ON_PREM_CLIENT_ID>
   Scopes: <POLAR_SKY_ON_PREM_SCOPES>

Paste each scope line exactly as written, as one line. Editing an existing entry replaces its entire scope list,
so if a client ID already has an entry, keep every scope it needs.

Please also make sure <GOOGLE_WORKSPACE_ADMIN_EMAIL> has the Reports admin privilege.

Thank you.
```

Ask the person to tell you when the entries are added. You can go on with phase 5 while you wait.
