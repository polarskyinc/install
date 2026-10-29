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

## When the service accounts already exist

If `service-accounts create` answers that the account already exists (an earlier, stopped install), keep it: save its email and client ID as below, and do not create a second one. For its key:

- If the person still has the key file from that install, they move it into the install folder under the name below. Check it belongs to the account without showing the private key: this prints only two public fields of the file, and Google's list of the account's keys, which must include that key ID and show it not disabled.

  ```bash
  cd ~/polar-sky-install && grep -oE '"(client_email|private_key_id)": *"[^"]*"' <key file> && gcloud iam service-accounts keys list --iam-account="<account email>" --managed-by=user --project="${GOOGLE_CLOUD_PROJECT_ID}" --format='value(name.basename(),disabled)'
  ```

- If they don't have it, create a new key as below, and tell them the old key stays active until their administrator deletes it.

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

A Google Workspace super admin adds two entries in the Google Admin console. Make a link for each entry that opens the console's "Add a new client ID" dialog with the client ID and scopes already filled in (read only, prints two links):

```bash
. ~/polar-sky-install/values.env && enc() { printf '%s' "$1" | sed 's/:/%3A/g; s#/#%2F#g; s/,/%2C/g'; } && echo "https://admin.google.com/ac/owl/domainwidedelegation?clientIdToAdd=${GOOGLE_CLOUD_CLIENT_ID}&clientScopeToAdd=$(enc "${POLAR_SKY_CLOUD_SCOPES}")&overwriteClientId=true" && echo "https://admin.google.com/ac/owl/domainwidedelegation?clientIdToAdd=${GOOGLE_ON_PREM_CLIENT_ID}&clientScopeToAdd=$(enc "${POLAR_SKY_ON_PREM_SCOPES}")&overwriteClientId=true"
```

The super admin opens each link signed in to the Admin console, checks the client ID and scopes in the dialog, and clicks **Authorize**. Give the two links and, as the fallback if a link does not open the dialog, both entries with the exact values to add by hand under **Security** > **Access and data control** > **API controls** > **Domain-wide delegation** > **Manage all**:

| Entry | Client ID | Scopes (one line, comma-separated, no spaces) |
| --- | --- | --- |
| Polar Sky Cloud | `GOOGLE_CLOUD_CLIENT_ID` | `POLAR_SKY_CLOUD_SCOPES` |
| Polar Sky On-Premises | `GOOGLE_ON_PREM_CLIENT_ID` | `POLAR_SKY_ON_PREM_SCOPES` |

Show the real values, not the names. Always add this warning:

> **Important:** Each link replaces any existing entry for that client ID with exactly these scopes, and editing an entry by hand also replaces its entire scope list. If a client ID already has an entry with other scopes it still needs, add them by hand instead.

Also say: the Workspace admin Polar Sky acts as (`GOOGLE_WORKSPACE_ADMIN_EMAIL`) needs the **Reports** privilege, and Google can take up to 24 hours to apply delegation changes.

If the person is a super admin, they can open the links now. If not, write them a message to forward. Fill in every value, with the two links in full:

```text
Hello,

We are installing Polar Sky. Please add two domain-wide delegation entries in the Google Admin console.
Open each link while signed in as a super admin, check the client ID and scopes, and click Authorize:

1. <link for GOOGLE_CLOUD_CLIENT_ID>
2. <link for GOOGLE_ON_PREM_CLIENT_ID>

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

Ask the person to tell you when the entries are added. You can go on with phase 5 while you wait.
