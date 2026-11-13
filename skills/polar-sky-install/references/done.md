# Phase 10: Done

**Tell the person:** Polar Sky now works on what it monitors, the locations the person chose or, for Microsoft 365, everything: it finds overexposed files and proposes controls, and their team reviews and approves them in the Polar Sky console. They can also review controls from their AI assistant: the last step of the install connects it.

## On-Prem

First run the pod checks from phase 6 again (read only). Say the install is done only if every check there passes.

For Microsoft 365, also only when all of these hold:

- the engine app's check ended with `APP OK`, and both workers passed their check in [Engine connected](connection.md#microsoft-365-the-engine-app-in-the-workers);
- the upload answered `connected` true, or Microsoft 365 was already connected and its checks in [Connect Microsoft 365](microsoft365.md#when-microsoft-365-was-already-connected) passed;
- the cloud app's key file is deleted, or the person moved it to their secrets store;
- a later `get_install_values` with `provider` `microsoft365` and `reading_since` set to `POLAR_SKY_ENGINE_CONNECTED_AT` still answers `microsoft365_connected` true, with `enabled` true and `files_read` above zero.

Otherwise, say at the top: "Everything is set up, but Polar Sky has not read the first files through the engine yet. They are on their way, and Polar Sky will follow up." Do not call the install done, and give the summary below.

If model pods still wait for GPU capacity, do not call the install complete. Say instead, naming Microsoft 365 in place of Google Workspace in a Microsoft 365 install: "Everything is set up except the AI models, which are waiting for a free GPU machine in your cloud. They start on their own when one is free. Meanwhile the engine and Google Workspace are connected, and Polar Sky finds your files and who can open them, but it cannot judge how sensitive they are until the models run." Give the summary below with that line at the top, and offer to check the models again later.

If a model pod is not ready for another reason, say: "Everything is set up except the AI models, which are not running yet. Polar Sky cannot process documents until they do." Name the cause from phase 6, report it with `report_issue`, and give the summary below with that line at the top.

Give the person a short summary, with real values:

- **Runs in your cluster** (context, namespace `POLAR_SKY_NAMESPACE`): Flux, the Polar Sky chart version `POLAR_SKY_CHART_VERSION` on the `latest` channel, the two workers, the AI Gateway and the model servers on GPU nodes. When `POLAR_SKY_INFERENCE_MODEL_REPLICAS` is below 3, also say how many copies of the inference model run, what that costs as [Fewer copies of the inference model](cluster.md#fewer-copies-of-the-inference-model) says, and that the person can go back to 3 once the cluster can have four GPU nodes ([Change the number of inference model copies](engine.md#change-the-number-of-inference-model-copies)).
- **Google:** the service accounts `GOOGLE_ON_PREM_SERVICE_ACCOUNT` and `GOOGLE_CLOUD_SERVICE_ACCOUNT` in `GOOGLE_CLOUD_PROJECT_ID`, and their two delegation entries. Polar Sky keeps the cloud account's key, encrypted.
- **Microsoft 365** (in place of the Google line): the app registrations `Polar Sky Cloud` (`MICROSOFT_CLOUD_APP_CLIENT_ID`, or `microsoft365_client_id` for a connection made before this install), which reads people, groups and the audit log for Polar Sky Cloud, and `Polar Sky On-Premises` (`MICROSOFT_ON_PREM_APP_CLIENT_ID`), which the engine uses to read files, in the tenant `MICROSOFT_TENANT_ID`, by the tenant's name, with admin consent for their permissions. Polar Sky keeps the cloud app's certificate bundle, encrypted. The engine app's key is only in your cluster, in the `microsoft365-credentials` secret.
- **Certificate:** the end date from `scripts/check-certificate.sh`. It must be renewed before that date: run phase 5 again with a new key, and replace the `polar-sky-mtls` secret.
- **Microsoft 365 certificates** (Microsoft 365 only): the end date of each app's certificate, from the `certificate end date` the app script printed, or `certificate_expires_at` for a connection made before this install. Before the cloud app's date, make a new certificate, add it to the app, and give it to Polar Sky with **Update credentials** on the Microsoft 365 card on the Platform page of the Polar Sky console. Before the engine app's date, renew it as [Replace the Microsoft 365 secret](engine.md#replace-the-microsoft-365-secret) says: the workers read the new key only after a restart.
- **Okta** (only with Okta): the Okta org `OKTA_ORG_URL`, the app `Polar Sky Group Provisioning` with the Organization Administrator role, the start of Polar Sky's group names `OKTA_GROUP_PREFIX`, and how groups reach Google Workspace, in the words of phase 8. Polar Sky keeps the app's private key, encrypted; it never was on this machine.
- **Monitoring:** what the person chose in the conversation, in their own drive names. They can change it again here or in the console. When the tools were not listed, the locations they chose in the console. For Microsoft 365: everything, every SharePoint site and everyone's OneDrive, including ones added later; choosing sites is not available for Microsoft 365 yet.
- **Audit logging** (Microsoft 365 only): it must be on in Microsoft Purview, which the administrator checks; Polar Sky cannot check it from here.
- **Slack:** when the plan had Slack and `get_install_values` answers `slack_connected` true, the workspace in `slack_workspace_name`, where Polar Sky can now send direct messages from the Polar Sky app. Requests Polar Sky raises on its own stay email-only until an administrator turns Slack on in the console under **Controls** > **Settings**. Otherwise: "Slack: not connected; you can connect it later from the Platform page in the Polar Sky console." Leave this line out when the company does not use Slack.
- **Webhooks:** only when the person added a webhook endpoint in this conversation: its name, the host it sends to, and whether the test notification arrived. They edit, turn off or remove it on the Platform page.
- **Checks skipped:** any preflight failure the person chose to accept, with their reason, if there was one.

## Cloud

For Microsoft 365, give the [Microsoft 365 Cloud](#microsoft-365-cloud) summary instead.

There is no cluster, no engine and no AI model to check, so skip the pod checks. Say the install is done once the person has chosen what Polar Sky monitors, in the conversation or in the console.

Give the person a short summary, with real values:

- **Runs in Polar Sky Cloud:** the reading of Google Workspace, with the content scopes on the Polar Sky Cloud entry. Nothing runs in your cloud.
- **Google:** the service account `GOOGLE_CLOUD_SERVICE_ACCOUNT` in `GOOGLE_CLOUD_PROJECT_ID`, and its delegation entry with the scopes in `POLAR_SKY_CLOUD_SCOPES`. Polar Sky keeps the account's key, encrypted.
- **Okta** (only with Okta): the Okta org `OKTA_ORG_URL`, the app `Polar Sky Group Provisioning` with the Organization Administrator role, the start of Polar Sky's group names `OKTA_GROUP_PREFIX`, and how groups reach Google Workspace, in the words of phase 8. Polar Sky keeps the app's private key, encrypted; it never was on this machine.
- **Monitoring:** what the person chose in the conversation, in their own drive names. They can change it again here or in the console. When the tools were not listed, the locations they chose in the console.
- **Slack:** when the plan had Slack and `get_install_values` answers `slack_connected` true, the workspace in `slack_workspace_name`, where Polar Sky can now send direct messages from the Polar Sky app. Requests Polar Sky raises on its own stay email-only until an administrator turns Slack on in the console under **Controls** > **Settings**. Otherwise: "Slack: not connected; you can connect it later from the Platform page in the Polar Sky console." Leave this line out when the company does not use Slack.
- **Webhooks:** only when the person added a webhook endpoint in this conversation: its name, the host it sends to, and whether the test notification arrived. They edit, turn off or remove it on the Platform page.

## Microsoft 365 Cloud

There is no cluster, no engine and no AI model to check. Say the install is done only when all of these hold:

- the upload answered `connected` true, or Microsoft 365 was already connected and its checks in [Connect Microsoft 365](microsoft365.md#when-microsoft-365-was-already-connected) passed;
- the key file is deleted, or the person moved it to their secrets store;
- a later `get_install_values` with `provider` `microsoft365` still answers `microsoft365_connected` true, with `enabled` true and `files_read` above zero (for a connection made before this install, `files` above zero).

Otherwise, say at the top: "Everything is set up, but Polar Sky has not read the first files yet. Polar Sky will follow up." Do not call the install done, and give the summary below.

Give the person a short summary, with real values:

- **Runs in Polar Sky Cloud:** the reading of Microsoft 365: every SharePoint site and everyone's OneDrive, including ones added later. Nothing runs in your cloud. Choosing sites is not available for Microsoft 365 yet.
- **Microsoft 365:** the app registration (its name and `MICROSOFT_CLOUD_APP_CLIENT_ID`, or `microsoft365_client_id` for a connection made before this install) in the tenant `MICROSOFT_TENANT_ID`, by the tenant's name, with admin consent for its permissions. Polar Sky keeps its certificate bundle, encrypted.
- **Certificate:** the end date, from the `certificate end date` the app script printed, or `certificate_expires_at` for a connection made before this install. Before that date, make a new certificate, add it to the app, and give it to Polar Sky with **Update credentials** on the Microsoft 365 card on the Platform page of the Polar Sky console.
- **Audit logging:** it must be on in Microsoft Purview, which the administrator checks; Polar Sky cannot check it from here.
- **Slack:** as in the Cloud summary above.

## What Polar Sky checks afterwards

Polar Sky's team checks the install on its own side, later and without the person.

- **On-Prem:** the workers read Google Workspace in the chosen locations, or all of Microsoft 365, and process documents, local inference and embedding work, and the results show in Polar Sky Cloud.
- **Cloud:** Polar Sky Cloud reads Google Workspace in the chosen locations, or all of Microsoft 365, and the results show in Polar Sky Cloud. No models run in the customer's cloud, so there is no local inference to check.

Tell the person in one line that Polar Sky checks the install on its side and contacts them only if something needs their help. The person has nothing to arrange.

## Connect your AI assistant to Polar Sky controls

In Claude Code and in Codex. With this connection, the person reviews Polar Sky's controls from their AI assistant: they ask why a control was proposed and who would lose access, change who keeps access, and approve or reject it. Every organization can use it. The final plan's yes covers this step, so do not ask again. Show the command for the agent you are, then run it.

In Claude Code, check first, read only, whether a claude.ai connector already points at Polar Sky controls. Claude Team and Enterprise accounts can bring one from their organization, and a second server would show the same tools twice:

```bash
claude mcp list 2>/dev/null | grep -E '^claude\.ai [^:]+: https://mcp\.polarsky\.ai/controls( |$)'
```

If it prints a line, do not add `polar-sky-controls`. Tell the person in one line that Claude Code already has Polar Sky controls through their organization's connector, by the name it shows (for example `claude.ai Polar Sky Controls`). If that line says it needs authentication, they sign in as below, choosing that connector in `/mcp`. If it says it failed to connect, tell them to choose that connector in `/mcp` and reconnect it, and to ask their Claude administrator if it still fails; do not add a second server for it. Then go on to the skills. In Codex, which cannot show such connectors, add the server as below.

In Claude Code (`--scope user`, so it works in any folder, like the install server):

```bash
claude mcp add --scope user --transport http polar-sky-controls https://mcp.polarsky.ai/controls
```

In Codex:

```bash
codex mcp add polar-sky-controls --url https://mcp.polarsky.ai/controls
```

If the command says `polar-sky-controls` already exists, keep it: do not remove it or add it again. Check its address (read only): `claude mcp get polar-sky-controls` in Claude Code, `codex mcp get polar-sky-controls` in Codex. If it is `https://mcp.polarsky.ai/controls`, the person is already connected, or signs in as below. If it is another address, do not change it: tell the person that their `polar-sky-controls` server points somewhere else, so Polar Sky controls do not work through it, and give them the command above to run after they remove it themselves.

Then tell the person how they sign in. They sign in with their Polar Sky console account, in the browser:

- In Claude Code: Claude Code opens the browser the first time they use Polar Sky controls, or they type `/mcp`, choose `polar-sky-controls`, or the claude.ai connector by the name `claude mcp list` showed when you did not add the server, and **Authenticate**. `/mcp` hides a claude.ai connector that is not signed in: tell them to choose **Show unused connectors** at the bottom of the list to find it.
- In Codex: they run `codex mcp login polar-sky-controls` in their own terminal, and Codex opens the browser.

On the Polar Sky page they sign in and choose **Approve**. The page says that Polar Sky cannot verify which program on their computer is asking: they choose **Approve** only if they started the sign-in themselves. Only administrators, named reviewers and delegates see controls; a delegate sees only the controls delegated to them.

If the command fails, call `report_issue`, tell the person the install is done without the connection, and give them the command above to run later. Do not try another way.

## Add Polar Sky's skills to Claude Code

Only in Claude Code; skip this in Codex, which has no plugins. Run it after the connection above: the skills read Polar Sky controls through it. These skills let the person's team ask Claude for Polar Sky work, such as an access review report for their auditor. The final plan's yes covers this step, so do not ask again. Show the two commands, then run them:

```bash
claude plugin marketplace add polarskyinc/install
claude plugin install polar-sky-access-reviews@polar-sky --scope user
```

If the first command says the marketplace is already added, run `claude plugin marketplace update polar-sky` instead, then the second command. If a command fails, call `report_issue`, tell the person the install is done without the skills, and give them the two commands to run later. Do not try another way.

Tell the person in one line: Polar Sky controls and the skills work in a new Claude Code session. In Codex, tell them Polar Sky controls work in a new Codex session, after they signed in.

## Clean up the install folder

Ask the person before deleting anything. Suggest:

- On-Prem: move `on-prem-key.json` and `client.key` to their approved secrets store, or delete them: the cluster already holds them in the `gws-creds` and `polar-sky-mtls` secrets. With Microsoft 365, `on-prem-key.json` is not there; if `microsoft-on-prem-app.pem` (or its dated name) is still there, the same goes for it: the cluster holds it in the `microsoft365-credentials` secret. Keep both `.crt` files of the apps: they are public, and they show which certificate is on each app.
- Keep `values.env` for their records. In On-Prem, also keep `client.crt` and the rendered files.
- With Okta: if `okta-admin-header` is still there, the Okta API token was not cleaned up. Ask the person to revoke the token in Okta (**Security** > **API** > **Tokens**) and delete the file, as in phase 8.
- Cloud: the key file is already deleted after the upload, so `values.env` is the only file to keep. With Microsoft 365, also keep `microsoft-cloud-app.crt`, the public certificate on the app. `microsoft-permissions.json` and `microsoft-cloud-app-access.json` are public and can go.

On-Prem only: remind them that Kubernetes secrets are only base64-encoded. Their cluster should encrypt secrets at rest, and only a few people should be able to read the Polar Sky namespace.

## What is left

After the summary, call `get_install_checklist` with `check_live` true, as [Say what is left to set up](../SKILL.md#say-what-is-left-to-set-up) says, and add one line for each optional item it reports as missing, with its next step. Leave out the `group_provisioning` item when `values.env` has `POLAR_SKY_OKTA_PLANNED='no'` and Okta is not connected: the company does not use Okta, so the group setting is the normal default, as question 8 in [Look up what the model needs](discover.md#ask-the-open-questions) says, and the person changes nothing. Do not let it change whether the install is done: that stays with the checks above.
