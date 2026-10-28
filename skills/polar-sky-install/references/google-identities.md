# Phase 4: Google identities and delegation

Polar Sky reads Google Workspace through two Google service accounts in the customer's own project (`GOOGLE_CLOUD_PROJECT_ID`):

| Service account | Used by | Key |
| --- | --- | --- |
| `polar-sky-on-prem-dpe` | The engine in the cluster | A JSON key, which goes only into the cluster |
| `polar-sky-cloud-integration` | Polar Sky Cloud | A JSON key, uploaded once to Polar Sky in phase 8, then deleted |

Show the active gcloud account (`gcloud config get-value account`) and ask the person to confirm it is the one to use. They need to create service accounts, keys and service-account IAM bindings in the project, and to enable APIs.

## Enable the APIs

```bash
gcloud services enable admin.googleapis.com drive.googleapis.com --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

This turns on the Admin SDK and Google Drive APIs in the project. Run it after a yes.

## On-premises service account and its key

Show both commands, say they create one service account and one key file, and run them after a yes:

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

## Cloud service account and its key

Show both commands, say they create one service account and one key file, and run them after a yes:

```bash
gcloud iam service-accounts create polar-sky-cloud-integration --display-name="Polar Sky Cloud" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

```bash
cd ~/polar-sky-install && umask 077 && gcloud iam service-accounts keys create cloud-key.json --iam-account="polar-sky-cloud-integration@${GOOGLE_CLOUD_PROJECT_ID}.iam.gserviceaccount.com" --project="${GOOGLE_CLOUD_PROJECT_ID}"
```

The key goes straight into `cloud-key.json`. Never open, print or send this file, and never pass it to a tool or the chat. In phase 8 it goes to Polar Sky once, uploaded with the one-time `curl` command from `start_key_upload`, and then you delete it. The same organization policy as above can block this key; handle it the same way.

Add to `values.env`:

```bash
export GOOGLE_CLOUD_SERVICE_ACCOUNT='polar-sky-cloud-integration@<project>.iam.gserviceaccount.com'
```

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
