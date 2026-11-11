# Phase 4: Microsoft app registrations and admin consent

**Tell the person:** Polar Sky reads Microsoft 365 through app registrations in their own Microsoft Entra ID, which sign in with certificates made on this machine. No one's password is used, and each app gets only the permissions an administrator grants it. A Cloud install needs one app registration; an On-Prem install needs two.

This is the Microsoft 365 version of [Google identities](google-identities.md):

| App registration | Used by | Certificate | Models |
| --- | --- | --- | --- |
| `Polar Sky Cloud` | Polar Sky Cloud. In Cloud, to read people, groups, files and sharing, and to make the access changes the team approves. In On-Prem, to read people, groups and the audit log, and to manage the groups for approved controls; never file content | `microsoft-cloud-app.pem`, uploaded once to Polar Sky when connecting Microsoft 365, then deleted | Both |
| `Polar Sky On-Premises` | The engine in the cluster, to read files and sharing in SharePoint and OneDrive, and to make the approved access changes on files | `microsoft-on-prem-app.pem`, which goes only into the cluster's Kubernetes Secret and never to Polar Sky | On-Prem only |

Each app asks for its own list in `microsoft-permissions.json`: the entries with `required_for` `polar_sky_cloud` for `Polar Sky Cloud`, and `engine` for `Polar Sky On-Premises`. In On-Prem, `Polar Sky Cloud` must hold no file or site permission, so Polar Sky Cloud never reads file content: the app check below fails when it holds one.

Use the `az` sign-in and the tenant the person confirmed in the final plan (`MICROSOFT_TENANT_ID`). The person who runs this stage must be allowed to register applications. Microsoft Entra ID allows every user to by default; otherwise they need the Application Developer or Application Administrator role.

Report a problem in this stage with `report_issue`, step `microsoft_apps`.

Even right after the final plan's yes, show this stage's commands and ask again. This stage needs only the tenant, not the cluster: in On-Prem, start it as soon as the plan is approved, so the administrator can grant consent while the cluster builds. Its plan: create each app and its service principal, make each app's certificate on this machine and add the public half to the app, and set each app's permissions. Show it in one message, with the permissions each app will ask for, from the list in `microsoft-permissions.json` (see [Prepare the permissions](#prepare-the-permissions)); for a kept app, also what the questions found it asks for today, and each `REMOVE` entry by name: the permissions that come off its list. Ask "Does this look right?" That one yes covers every command below for every app in the plan, including taking the `REMOVE` entries the plan named off a kept app's list. Admin consent, deleting anything, and a `REMOVE` entry the plan did not name get their own yes.

The commands below come first for `Polar Sky Cloud`, then for `Polar Sky On-Premises`, which only an On-Prem install runs.

## Check the sign-in

Read only:

```bash
az account show --query '{tenant:tenantId, user:user.name}' -o tsv
```

The tenant must be `MICROSOFT_TENANT_ID`. If it is another tenant, or `az` is not signed in, the person signs in, in their own terminal (in Claude Code they can type it here with `!` in front). It opens a browser. Many Microsoft 365 tenants have no Azure subscription; `--allow-no-subscriptions` lets the sign-in work without one:

```bash
az login --tenant "<MICROSOFT_TENANT_ID>" --allow-no-subscriptions
```

On AKS, the cluster's Azure subscription may sit in another tenant than Microsoft 365, and `az` works in one tenant at a time. Then say which tenant each step uses, and do not switch `az` to the other tenant while a command that uses it runs, such as the cluster build: finish this stage's commands before the build starts, or after it ends.

## The app's name

The cloud app is named `Polar Sky Cloud`, and the engine app `Polar Sky On-Premises`. When the questions found an app of that name and the person chose a new app instead of keeping it, because another Polar Sky organization uses it, for example the company's other Polar Sky installation, or because something else uses it, add the organization name: `Polar Sky Cloud (<POLAR_SKY_ORGANIZATION_NAME>)` or `Polar Sky On-Premises (<POLAR_SKY_ORGANIZATION_NAME>)`. If an app of that name is there too, ask the person for another name that starts with the same words. Use the name in place of `Polar Sky Cloud` or `Polar Sky On-Premises` in the create command below. The certificate's name stays `Polar Sky Cloud` or `Polar Sky On-Premises`.

The new app's name must be one no app in the tenant has yet. When an app of exactly that name exists, `az ad app create` changes that app instead of making a new one. Run the lookups from the questions again (read only) right before you create, the second one only in On-Prem:

```bash
az ad app list --display-name 'Polar Sky Cloud' --query '[].{name:displayName, appId:appId, created:createdDateTime}' -o tsv
```

```bash
az ad app list --display-name 'Polar Sky On-Premises' --query '[].{name:displayName, appId:appId, created:createdDateTime}' -o tsv
```

If a lookup lists an app with exactly the name you are about to use, do not create: keep that app only if it is the one the person chose to keep, and otherwise choose another name with the person. If `az ad app create` still answers that it found an existing application, stop: it changed that app. Tell the person, and call `report_issue`.

## When the app already exists

When the person chose in the questions to keep an app from an earlier, stopped install, do not create a second one. Write its client ID into `values.env` as below, skip [Create the app](#create-the-app) for it, and go on with its service principal. Its permissions are set again below, and it gets a new certificate when the install folder has none that matches it, as [Make the certificate](#make-the-certificate) says.

Something else may use an existing app, so never delete one without its own yes.

## Create the app

It is for this tenant only, with no redirect URI and no secret. The command prints only its client ID:

```bash
az ad app create --display-name 'Polar Sky Cloud' --sign-in-audience AzureADMyOrg --query appId -o tsv
```

Write it into `values.env`:

```bash
export MICROSOFT_CLOUD_APP_CLIENT_ID='<appId>'
```

In On-Prem, create the engine app the same way:

```bash
az ad app create --display-name 'Polar Sky On-Premises' --sign-in-audience AzureADMyOrg --query appId -o tsv
```

```bash
export MICROSOFT_ON_PREM_APP_CLIENT_ID='<appId>'
```

If Microsoft Entra ID refuses for lack of rights (`Insufficient privileges`), the person may not register applications. Stop and call `report_issue`, outcome `blocked`. The way out: an administrator gives them the Application Developer role, or runs this stage with them.

Microsoft Entra ID can take a minute before a new app is found. Wait until it is readable (read only), for each app you created:

```bash
. ~/polar-sky-install/values.env && for attempt in 1 2 3 4 5 6; do az ad app show --id "${MICROSOFT_CLOUD_APP_CLIENT_ID}" --query appId -o tsv && break; sleep 10; done
```

```bash
. ~/polar-sky-install/values.env && for attempt in 1 2 3 4 5 6; do az ad app show --id "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" --query appId -o tsv && break; sleep 10; done
```

## Create its service principal

Admin consent is recorded on each app's service principal, its entry in this tenant. Check whether it exists (read only):

```bash
. ~/polar-sky-install/values.env && az ad sp show --id "${MICROSOFT_CLOUD_APP_CLIENT_ID}" --query id -o tsv
```

If it is not found, create it:

```bash
. ~/polar-sky-install/values.env && az ad sp create --id "${MICROSOFT_CLOUD_APP_CLIENT_ID}" --query id -o tsv
```

In On-Prem, the same for the engine app:

```bash
. ~/polar-sky-install/values.env && az ad sp show --id "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" --query id -o tsv
```

```bash
. ~/polar-sky-install/values.env && az ad sp create --id "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" --query id -o tsv
```

## Make the certificate

Each app signs in with a certificate made on this machine. First write the certificate this install uses into `values.env`:

```bash
export MICROSOFT_CLOUD_APP_CERTIFICATE="$HOME/polar-sky-install/microsoft-cloud-app.crt"
```

Then make it. It only creates new files in the install folder, so it runs without a yes, and it never overwrites a file:

```bash
cd ~/polar-sky-install && umask 077 && if [ -e microsoft-cloud-app.pem ] || [ -e microsoft-cloud-app.crt ]; then echo "microsoft-cloud-app.pem or microsoft-cloud-app.crt already exists: nothing made"; else openssl req -x509 -nodes -newkey rsa:2048 -days 730 -subj '/CN=Polar Sky Cloud' -keyout microsoft-cloud-app.pem -out microsoft-cloud-app.crt && openssl x509 -in microsoft-cloud-app.crt >> microsoft-cloud-app.pem; fi
```

`microsoft-cloud-app.pem` holds the private key and the certificate. It is a secret (hard rules 4 and 5): it leaves this machine only in the one-time upload when connecting Microsoft 365. `microsoft-cloud-app.crt` is the public certificate, which goes on the app. The certificate lasts two years.

In On-Prem, the engine app's certificate is made the same way. Write both of its lines into `values.env` together: the public certificate, and the key file that goes into the cluster:

```bash
export MICROSOFT_ON_PREM_APP_CERTIFICATE="$HOME/polar-sky-install/microsoft-on-prem-app.crt"
export MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE="$HOME/polar-sky-install/microsoft-on-prem-app.pem"
```

```bash
cd ~/polar-sky-install && umask 077 && if [ -e microsoft-on-prem-app.pem ] || [ -e microsoft-on-prem-app.crt ]; then echo "microsoft-on-prem-app.pem or microsoft-on-prem-app.crt already exists: nothing made"; else openssl req -x509 -nodes -newkey rsa:2048 -days 730 -subj '/CN=Polar Sky On-Premises' -keyout microsoft-on-prem-app.pem -out microsoft-on-prem-app.crt && openssl x509 -in microsoft-on-prem-app.crt >> microsoft-on-prem-app.pem; fi
```

`microsoft-on-prem-app.pem` is a secret too, and never leaves this machine except into the cluster: the engine install puts it into the Kubernetes Secret through a pipe. It is never uploaded to Polar Sky.

When the files are already there, check them first. When both are there, compare their public keys (read only). The two lines must show the same hash:

```bash
cd ~/polar-sky-install && openssl x509 -in microsoft-cloud-app.crt -noout -pubkey | openssl sha256 && openssl pkey -in microsoft-cloud-app.pem -pubout | openssl sha256
```

```bash
cd ~/polar-sky-install && openssl x509 -in microsoft-on-prem-app.crt -noout -pubkey | openssl sha256 && openssl pkey -in microsoft-on-prem-app.pem -pubout | openssl sha256
```

- **The same hash:** keep the files and use them. The app check below compares the certificate with the app.
- **Otherwise,** for example when only the `.crt` is left from an earlier install: make a new certificate with today's date in both names, such as `microsoft-cloud-app-20261109.pem` and `microsoft-cloud-app-20261109.crt`, or `microsoft-on-prem-app-20261109.pem` and `.crt`. Put the dated names in place of both names everywhere in the command above, and write them into `values.env`: the dated `.crt` as `MICROSOFT_CLOUD_APP_CERTIFICATE`, or for the engine app the dated `.crt` as `MICROSOFT_ON_PREM_APP_CERTIFICATE` and the dated `.pem` as `MICROSOFT_ON_PREM_APP_CERTIFICATE_FILE`, always together. Every later step reads them from there. Leave the old files where they are: moving or deleting them needs its own yes.

## Prepare the permissions

Polar Sky gives the permission list. Never type a permission name or ID yourself (hard rule 6). The list is in `microsoft-permissions.json`, first written from `microsoft365_permissions` when you got the install values ([Start](start.md#get-the-install-values)). Polar Sky's list can change between sessions, so each time before you run the script below, call `get_install_values` again with the `deployment_model` in `values.env` and `provider` `microsoft365` (it only reads), and write `microsoft365_permissions` to that file again, exactly as given, as one JSON array, with your file tool. In On-Prem, the list has entries for both apps.

Run the script for each app. It only reads, apart from writing one public file: `microsoft-cloud-app-access.json` for the cloud app, `microsoft-on-prem-app-access.json` for the engine app:

```bash
. ~/polar-sky-install/values.env && cd ~/polar-sky-install && <skill folder>/scripts/microsoft-app-access.sh cloud "${MICROSOFT_CLOUD_APP_CLIENT_ID}" "${MICROSOFT_CLOUD_APP_CERTIFICATE}"
```

```bash
. ~/polar-sky-install/values.env && cd ~/polar-sky-install && <skill folder>/scripts/microsoft-app-access.sh engine "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" "${MICROSOFT_ON_PREM_APP_CERTIFICATE}"
```

It looks up each permission in the tenant by name, and prints:

- `request`: each permission the app will ask for.
- `REMOVE`: an application permission the app asks for today that Polar Sky does not. Only an app kept from an earlier install can have one. It comes off the app's list when you set the permissions below. When the stage plan did not name it, show it and ask for its own yes before you set the permissions. Coming off the list does not take back a grant consent already gave: the app check shows such a grant as `EXTRA`, or for the cloud app in On-Prem as `SURPLUS`, and [Check the app](#check-the-app) says how to remove it.
- `KEEP`: an entry the app keeps, a permission on another API or a delegated permission. Admin consent grants these too. An app this install created has none. See [Kept entries](#kept-entries).
- `certificate end date`: when the certificate expires, for the next command.

It ends with `ACCESS FILE WRITTEN`, or with a `PROBLEM` line and `ACCESS FILE NOT WRITTEN`. A permission the tenant does not know is a failure: stop, and follow hard rule 8.

### Kept entries

`KEEP` lines mean something else may use this app. Do not grant consent on it: recommend a new app with another name, because an app that something else uses should not carry Polar Sky's tenant-wide permissions. If the person still keeps the app, the consent step and the administrator's message list every `KEEP` entry by name, and the yes covers exactly that list. Report it with `report_issue`, outcome `worked_around`.

## Add the certificate and set the permissions

Add the public certificate to the app. `--append` keeps the app's other credentials. Put the `certificate end date` the script printed for that app in place of `<end date>`, so the credential lasts as long as the certificate; without it, Microsoft Entra ID gives it one year:

```bash
. ~/polar-sky-install/values.env && az ad app credential reset --id "${MICROSOFT_CLOUD_APP_CLIENT_ID}" --cert @"${MICROSOFT_CLOUD_APP_CERTIFICATE}" --append --end-date "<end date>" --query appId -o tsv
```

Never leave out `--append`: without it, the command removes the app's other credentials.

Set the permissions in one command, to exactly the list in the file:

```bash
. ~/polar-sky-install/values.env && az ad app update --id "${MICROSOFT_CLOUD_APP_CLIENT_ID}" --required-resource-accesses @"$HOME/polar-sky-install/microsoft-cloud-app-access.json"
```

In On-Prem, the same for the engine app, with its own end date and its own file:

```bash
. ~/polar-sky-install/values.env && az ad app credential reset --id "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" --cert @"${MICROSOFT_ON_PREM_APP_CERTIFICATE}" --append --end-date "<end date>" --query appId -o tsv
```

```bash
. ~/polar-sky-install/values.env && az ad app update --id "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" --required-resource-accesses @"$HOME/polar-sky-install/microsoft-on-prem-app-access.json"
```

This only asks for the permissions. Nothing is granted until an administrator gives admin consent.

## Admin consent

Admin consent grants an app every permission it asks for, across the whole tenant. Only a Global Administrator or a Privileged Role Administrator can grant it. In On-Prem, both apps need it.

An administrator should know what they grant. List each app's permissions under its name, one line each, with its `purpose`, as written: the entries with `required_for` `polar_sky_cloud` in `microsoft-permissions.json` for `Polar Sky Cloud`, and `engine` for `Polar Sky On-Premises`. Never write your own explanation. Do not call a permission optional: the install asks for every one. `required` false only means Polar Sky works without it, while the feature in its purpose waits for it. With a kept app, add every `KEEP` entry.

In Cloud there is nothing else to run, so the connection waits for consent. Say so. In On-Prem, the cluster and the engine certificate do not wait for it, but the engine install and the connection do.

### When the person can grant it

When the person holds Global Administrator or Privileged Role Administrator, grant it here with `az`, after its own yes: it grants tenant-wide access, so it gets its own yes, like the certificate upload. In On-Prem, ask once for both apps: show both commands, each with its app's permissions, and that one yes covers exactly these two commands. A service principal made a minute ago is not ready for consent yet, and Microsoft Entra ID then answers with the same `Insufficient privileges` error as a real lack of rights. So the command tries again for about a minute before you believe it:

```bash
. ~/polar-sky-install/values.env && for attempt in 1 2 3 4 5 6; do az ad app permission admin-consent --id "${MICROSOFT_CLOUD_APP_CLIENT_ID}" && echo granted && break; sleep 10; done
```

```bash
. ~/polar-sky-install/values.env && for attempt in 1 2 3 4 5 6; do az ad app permission admin-consent --id "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" && echo granted && break; sleep 10; done
```

If it never prints `granted`, a role held through Privileged Identity Management may not be active yet. The person activates it, and you run the command once more. If that fails too, the person cannot grant it: write the message below for an administrator who can.

### When an administrator grants it

Write a message for the person to forward to the administrator they named, with every value filled in. Each app's link opens its **API permissions** page in the Microsoft Entra admin center; put the app's client ID in it:

```text
https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/CallAnAPI/appId/<client ID>/isMSAApp~/false
```

The message, with one block for each app: in Cloud only `Polar Sky Cloud`, in On-Prem both. What each app is for:

- `Polar Sky Cloud` in Cloud: Polar Sky Cloud reads file content and makes the access changes our team approves.
- `Polar Sky Cloud` in On-Prem: Polar Sky Cloud reads people, groups and the audit log, and manages the groups for the controls our team approves. It never reads file content.
- `Polar Sky On-Premises`: the Polar Sky engine in our own cluster reads file content and makes the file access changes our team approves. Its key stays in our cluster.

```text
Hello,

We are connecting Polar Sky to our Microsoft 365. Please grant admin consent to <the app registration or the two
app registrations> below in Microsoft Entra ID. It needs a Global Administrator or a Privileged Role
Administrator, for a few minutes.

For each app registration below:
1. Open its page while signed in as that administrator. If the link does not open it: Microsoft Entra admin
   center > Identity > Applications > App registrations > All applications > the app's name > API permissions.
2. Check the permissions there against the list below, then select "Grant admin consent for <tenant name>"
   and confirm.

App registration: <app name>, client ID <client ID>
Page: <link>
What it is for: <what this app is for>
What each permission lets Polar Sky do:
   - <API>, <permission>: <purpose>

Please also make sure audit logging is on in Microsoft Purview: in the Microsoft Purview portal, open Audit,
and if it offers to start recording user and admin activity, select it.

Thank you.
```

Ask the person to tell you when the administrator has granted it.

## Check the app

Consent can take a few minutes to show. Check what Microsoft Entra ID recorded, and that the certificate this install made is on the app (read only). In On-Prem, check both apps:

```bash
. ~/polar-sky-install/values.env && cd ~/polar-sky-install && <skill folder>/scripts/check-microsoft-app.sh cloud "${MICROSOFT_CLOUD_APP_CLIENT_ID}" "${MICROSOFT_CLOUD_APP_CERTIFICATE}"
```

```bash
. ~/polar-sky-install/values.env && cd ~/polar-sky-install && <skill folder>/scripts/check-microsoft-app.sh engine "${MICROSOFT_ON_PREM_APP_CLIENT_ID}" "${MICROSOFT_ON_PREM_APP_CERTIFICATE}"
```

It prints `granted` or `MISSING` for each permission, `EXTRA` for a granted permission Polar Sky does not ask for, `SURPLUS` for one the cloud app must not hold in On-Prem, and whether the certificate is on the app. It ends with `APP OK`, `APP INCOMPLETE` (Polar Sky could work, but a permission a feature needs is `MISSING`) or `APP NOT OK`.

- **`APP OK`:** in Cloud, go on to [Connect Microsoft 365](microsoft365.md); the upload is tried only after `APP OK`. In On-Prem, the engine app's `APP OK` lets the engine install go on, and connecting Microsoft 365 waits for `APP OK` on both apps and for the engine to reach Polar Sky Cloud.
- **`MISSING` soon after consent,** with `APP INCOMPLETE` or `APP NOT OK`: consent can take a few minutes to show. Wait a minute and run the check once more. Still `MISSING`: show which permissions, call `report_issue`, and ask the administrator to grant consent again, as above.
- **The certificate is not on the app:** add it again, as in [Add the certificate and set the permissions](#add-the-certificate-and-set-the-permissions), then check again.
- **`SURPLUS`:** only for the cloud app in On-Prem. It holds a grant outside its On-Prem list, most often a file or site permission from an earlier Cloud setup, which would let Polar Sky Cloud reach file content. Taking a permission off the app's list does not take back a grant that consent already gave. It blocks the install until no `SURPLUS` grant is left. Recommend a new app, named as [The app's name](#the-apps-name) says, created after its own yes. If the person keeps this app, remove each `SURPLUS` grant, each after its own yes, with the command under `EXTRA` below, then run the check again.
- **`EXTRA`:** the app holds a grant for a permission Polar Sky does not use, usually from an earlier setup. Taking a permission off the app's list does not take back a grant that consent already gave, so the app keeps that access until the grant itself is removed. It does not block the install. Tell the person, and recommend removing each one. Removing a grant needs a Global Administrator or Privileged Role Administrator, and each one gets its own yes. Put the service principal and the grant the check printed in the command:

  ```bash
  az rest --method DELETE --url "https://graph.microsoft.com/v1.0/servicePrincipals/<service principal>/appRoleAssignments/<grant>"
  ```

  Then run the check again. If the person cannot remove them, say the app still holds them, and report it with `report_issue`.

## Old certificates on a kept app

Only for an app kept from an earlier install, or an engine app whose certificate was renewed, and only after Microsoft 365 is connected and, for the engine app, the workers passed their check with the new key and Polar Sky has read the first files through the engine. List the app's certificates (read only), with `MICROSOFT_ON_PREM_APP_CLIENT_ID` in place of `MICROSOFT_CLOUD_APP_CLIENT_ID` for the engine app:

```bash
. ~/polar-sky-install/values.env && az ad app credential list --id "${MICROSOFT_CLOUD_APP_CLIENT_ID}" --cert --query '[].{key:keyId, thumbprint:customKeyIdentifier, ends:endDateTime}' -o tsv
```

The one whose thumbprint the app check printed is this install's and stays. Another certificate may still be how something else signs in with this app, and a different thumbprint does not show that nothing does. So ask the person first whether anything other than Polar Sky signs in with this app. Only when they are sure nothing does, offer to remove each other certificate, each with its own yes. Otherwise leave them in place:

```bash
. ~/polar-sky-install/values.env && az ad app credential delete --id "${MICROSOFT_CLOUD_APP_CLIENT_ID}" --key-id "<key>" --cert
```
